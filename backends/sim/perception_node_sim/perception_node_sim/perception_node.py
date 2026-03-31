import importlib

import numpy as np
import rclpy
from rclpy.exceptions import ParameterUninitializedException
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String


class PerceptionNode(Node):
    def __init__(self):
        super().__init__('perception_node')
        self.declare_parameter('mode', 'ground_truth')
        self.declare_parameter('sim_visible_objects_topic', '/sim/visible_objects')
        self.declare_parameter('normalized_objects_topic', '/perception/visible_objects')
        self.declare_parameter('camera_image_topic', '/camera/color/image_raw')
        self.declare_parameter('default_visible_objects', ['chair', 'person'])
        self.declare_parameter('yolo_model', 'yolo11n.pt')
        self.declare_parameter('yolo_conf_threshold', 0.25)
        self.declare_parameter('yolo_target_classes', [''])

        self.mode = str(self.get_parameter('mode').value)
        self.objects = list(self.get_parameter('default_visible_objects').value)
        self.pub = self.create_publisher(String, self.get_parameter('normalized_objects_topic').value, 10)
        self.debug_pub = self.create_publisher(String, '/perception_debug', 10)
        self.timer = self.create_timer(1.0, self.publish_state)
        self.sub = None
        self.image_sub = None
        self.model = None
        try:
            raw_targets = self.get_parameter('yolo_target_classes').value
        except ParameterUninitializedException:
            raw_targets = []
        self.class_filter = set(str(x) for x in raw_targets if str(x).strip())
        self.last_yolo_error = None

        if self.mode == 'ground_truth':
            self.sub = self.create_subscription(
                String,
                self.get_parameter('sim_visible_objects_topic').value,
                self.on_visible_objects,
                10,
            )
            self.get_logger().info('perception_node_sim running in ground_truth mode')
        elif self.mode == 'yolo':
            self.model = self.load_yolo_model(
                str(self.get_parameter('yolo_model').value),
            )
            self.image_sub = self.create_subscription(
                Image,
                self.get_parameter('camera_image_topic').value,
                self.on_image,
                10,
            )
            self.get_logger().info('perception_node_sim running in yolo mode')
        else:
            raise ValueError(f'unsupported perception mode: {self.mode}')

    def load_yolo_model(self, model_name: str):
        ultralytics = importlib.import_module('ultralytics')
        model_cls = getattr(ultralytics, 'YOLO')
        return model_cls(model_name)

    def on_visible_objects(self, msg: String):
        self.objects = [item.strip() for item in msg.data.split(',') if item.strip()]

    def on_image(self, msg: Image):
        if self.model is None:
            return
        if msg.encoding.lower() not in ('rgb8', 'bgr8'):
            self.last_yolo_error = f'unsupported_encoding:{msg.encoding}'
            return
        channels = 3
        expected = msg.height * msg.width * channels
        if len(msg.data) < expected:
            self.last_yolo_error = f'invalid_image_size:{len(msg.data)}<{expected}'
            return
        image = np.frombuffer(msg.data, dtype=np.uint8).reshape((msg.height, msg.width, channels))
        if msg.encoding.lower() == 'bgr8':
            image = image[:, :, ::-1]
        conf = float(self.get_parameter('yolo_conf_threshold').value)
        try:
            results = self.model.predict(source=image, conf=conf, verbose=False)
        except Exception as exc:
            self.last_yolo_error = f'yolo_predict_failed:{exc}'
            return

        names = []
        if results:
            result = results[0]
            boxes = getattr(result, 'boxes', None)
            if boxes is not None and boxes.cls is not None:
                for cls_idx in boxes.cls.tolist():
                    label = result.names.get(int(cls_idx), str(int(cls_idx)))
                    if self.class_filter and label not in self.class_filter:
                        continue
                    names.append(str(label))
        self.objects = sorted(set(names))
        self.last_yolo_error = None

    def publish_state(self):
        normalized = String()
        normalized.data = ','.join(self.objects)
        self.pub.publish(normalized)

        debug = String()
        if self.mode == 'yolo' and self.last_yolo_error:
            debug.data = f'mode=yolo error={self.last_yolo_error} objects={normalized.data}'
        else:
            debug.data = f'mode={self.mode} objects={normalized.data}'
        self.debug_pub.publish(debug)


def main(args=None):
    rclpy.init(args=args)
    node = PerceptionNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
