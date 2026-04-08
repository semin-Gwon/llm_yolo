import importlib
import json
import math

import numpy as np
import rclpy
from rclpy.exceptions import ParameterUninitializedException
from rclpy.node import Node
from rclpy.time import Time
from sensor_msgs.msg import CameraInfo, Image
from std_msgs.msg import String
from tf2_ros import Buffer, TransformException, TransformListener


class PerceptionNode(Node):
    def __init__(self):
        super().__init__('perception_node')
        self.declare_parameter('mode', 'ground_truth')
        self.declare_parameter('sim_visible_objects_topic', '/sim/visible_objects')
        self.declare_parameter('normalized_objects_topic', '/perception/visible_objects')
        self.declare_parameter('camera_image_topic', '/camera/color/image_raw')
        self.declare_parameter('camera_depth_topic', '/camera/depth/image_rect_raw')
        self.declare_parameter('camera_info_topic', '/camera/camera_info')
        self.declare_parameter('default_visible_objects', ['chair', 'person'])
        self.declare_parameter('object_pose_topic', '/perception/object_poses')
        self.declare_parameter('object_pose_frame', 'map')
        self.declare_parameter('yolo_model', 'yolo11n.pt')
        self.declare_parameter('yolo_conf_threshold', 0.25)
        self.declare_parameter('yolo_target_classes', [''])

        self.mode = str(self.get_parameter('mode').value)
        self.objects = list(self.get_parameter('default_visible_objects').value)
        self.pub = self.create_publisher(String, self.get_parameter('normalized_objects_topic').value, 10)
        self.object_pose_pub = self.create_publisher(String, self.get_parameter('object_pose_topic').value, 10)
        self.debug_pub = self.create_publisher(String, '/perception_debug', 10)
        self.timer = self.create_timer(1.0, self.publish_state)
        self.sub = None
        self.image_sub = None
        self.depth_sub = None
        self.camera_info_sub = None
        self.model = None
        self.last_depth_msg = None
        self.last_camera_info = None
        self.last_object_poses = []
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
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
            self.depth_sub = self.create_subscription(
                Image,
                self.get_parameter('camera_depth_topic').value,
                self.on_depth,
                10,
            )
            self.camera_info_sub = self.create_subscription(
                CameraInfo,
                self.get_parameter('camera_info_topic').value,
                self.on_camera_info,
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
        self.last_object_poses = []

    def on_depth(self, msg: Image):
        self.last_depth_msg = msg

    def on_camera_info(self, msg: CameraInfo):
        self.last_camera_info = msg

    def _depth_to_numpy(self, msg: Image):
        if msg.encoding == '32FC1':
            return np.frombuffer(msg.data, dtype=np.float32).reshape((msg.height, msg.width))
        if msg.encoding == '16UC1':
            depth_mm = np.frombuffer(msg.data, dtype=np.uint16).reshape((msg.height, msg.width))
            return depth_mm.astype(np.float32) / 1000.0
        raise ValueError(f'unsupported_depth_encoding:{msg.encoding}')

    def _lookup_depth(self, u: int, v: int) -> float | None:
        if self.last_depth_msg is None:
            return None
        depth = self._depth_to_numpy(self.last_depth_msg)
        h, w = depth.shape
        if not (0 <= u < w and 0 <= v < h):
            return None
        half = 2
        x0, x1 = max(0, u - half), min(w, u + half + 1)
        y0, y1 = max(0, v - half), min(h, v + half + 1)
        window = depth[y0:y1, x0:x1]
        valid = window[np.isfinite(window) & (window > 0.05)]
        if valid.size == 0:
            center = depth[v, u]
            if not np.isfinite(center) or center <= 0.05:
                return None
            return float(center)
        return float(np.median(valid))

    def _camera_point_from_pixel(self, u: float, v: float, depth_m: float):
        if self.last_camera_info is None:
            return None
        k = self.last_camera_info.k
        fx = float(k[0])
        fy = float(k[4])
        cx = float(k[2])
        cy = float(k[5])
        if fx == 0.0 or fy == 0.0:
            return None
        x = (u - cx) / fx * depth_m
        y = (v - cy) / fy * depth_m
        z = depth_m
        return np.array([x, y, z], dtype=np.float64)

    def _rotate_vector(self, qx: float, qy: float, qz: float, qw: float, vec: np.ndarray) -> np.ndarray:
        x, y, z = vec
        ix = qw * x + qy * z - qz * y
        iy = qw * y + qz * x - qx * z
        iz = qw * z + qx * y - qy * x
        iw = -qx * x - qy * y - qz * z
        return np.array([
            ix * qw + iw * -qx + iy * -qz - iz * -qy,
            iy * qw + iw * -qy + iz * -qx - ix * -qz,
            iz * qw + iw * -qz + ix * -qy - iy * -qx,
        ], dtype=np.float64)

    def _transform_point_to_global(self, point_camera: np.ndarray, source_frame: str):
        target_frame = str(self.get_parameter('object_pose_frame').value)
        try:
            transform = self.tf_buffer.lookup_transform(target_frame, source_frame, Time())
        except TransformException as exc:
            self.last_yolo_error = f'tf_lookup_failed:{exc}'
            return None
        t = transform.transform.translation
        q = transform.transform.rotation
        rotated = self._rotate_vector(q.x, q.y, q.z, q.w, point_camera)
        return np.array([rotated[0] + t.x, rotated[1] + t.y, rotated[2] + t.z], dtype=np.float64)

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
        object_poses = []
        if results:
            result = results[0]
            boxes = getattr(result, 'boxes', None)
            if boxes is not None and boxes.cls is not None:
                cls_list = boxes.cls.tolist()
                conf_list = boxes.conf.tolist() if getattr(boxes, 'conf', None) is not None else [conf] * len(cls_list)
                xyxy_list = boxes.xyxy.tolist() if getattr(boxes, 'xyxy', None) is not None else []
                source_frame = msg.header.frame_id or 'camera_optical_frame'
                for i, cls_idx in enumerate(cls_list):
                    label = result.names.get(int(cls_idx), str(int(cls_idx)))
                    if self.class_filter and label not in self.class_filter:
                        continue
                    names.append(str(label))
                    if i >= len(xyxy_list):
                        continue
                    x0, y0, x1, y1 = xyxy_list[i]
                    u = int(round((float(x0) + float(x1)) * 0.5))
                    v = int(round((float(y0) + float(y1)) * 0.5))
                    depth_m = self._lookup_depth(u, v)
                    if depth_m is None:
                        continue
                    point_camera = self._camera_point_from_pixel(float(u), float(v), depth_m)
                    if point_camera is None:
                        continue
                    point_global = self._transform_point_to_global(point_camera, source_frame)
                    if point_global is None:
                        continue
                    object_poses.append({
                        'class_name': str(label),
                        'confidence': float(conf_list[i]) if i < len(conf_list) else float(conf),
                        'x_m': float(point_global[0]),
                        'y_m': float(point_global[1]),
                        'z_m': float(point_global[2]),
                        'bbox_area_norm': float(max(0.0, (float(x1) - float(x0)) * (float(y1) - float(y0))) / float(msg.width * msg.height)),
                        'bbox_center_x_norm': float(u) / float(msg.width) if msg.width > 0 else 0.5,
                    })
        self.objects = sorted(set(names))
        self.last_object_poses = object_poses
        self.last_yolo_error = None

    def publish_state(self):
        normalized = String()
        normalized.data = ','.join(self.objects)
        self.pub.publish(normalized)

        object_pose_msg = String()
        object_pose_msg.data = json.dumps({
            'frame_id': str(self.get_parameter('object_pose_frame').value),
            'objects': self.last_object_poses,
        }, ensure_ascii=False)
        self.object_pose_pub.publish(object_pose_msg)

        debug = String()
        if self.mode == 'yolo' and self.last_yolo_error:
            debug.data = f'mode=yolo error={self.last_yolo_error} objects={normalized.data}'
        else:
            debug.data = f'mode={self.mode} objects={normalized.data} poses={len(self.last_object_poses)}'
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
