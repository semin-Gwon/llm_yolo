import importlib
import json
import math

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.time import Time
from sensor_msgs.msg import CameraInfo, Image
from std_msgs.msg import String
from tf2_ros import Buffer, TransformException, TransformListener
from visualization_msgs.msg import Marker, MarkerArray


class PerceptionNode(Node):
    def __init__(self):
        super().__init__('perception_node_real')
        self.declare_parameter('normalized_objects_topic', '/perception/visible_objects')
        self.declare_parameter('object_pose_topic', '/perception/object_poses')
        self.declare_parameter('camera_image_topic', '/camera/color/image_raw')
        self.declare_parameter('camera_depth_topic', '/camera/depth/image_rect_raw')
        self.declare_parameter('camera_info_topic', '/camera/color/camera_info')
        self.declare_parameter('object_pose_frame', 'base_link')
        self.declare_parameter('fallback_camera_frame', '')
        self.declare_parameter('yolo_model', 'yolo11n.pt')
        self.declare_parameter('yolo_conf_threshold', 0.25)
        self.declare_parameter('yolo_target_classes', ['chair'])
        self.declare_parameter('enable_debug_image', False)
        self.declare_parameter('debug_image_topic', '/perception/debug_image')
        self.declare_parameter('enable_object_markers', False)
        self.declare_parameter('object_marker_topic', '/perception/object_markers')
        self.declare_parameter('marker_lifetime_sec', 0.6)
        self.declare_parameter('marker_scale_m', 0.14)
        self.declare_parameter('depth_mode', 'bbox_cluster')
        self.declare_parameter('depth_center_patch_radius_px', 2)
        self.declare_parameter('depth_min_valid_m', 0.05)
        self.declare_parameter('depth_max_valid_m', 8.0)
        self.declare_parameter('depth_cluster_gap_m', 0.15)
        self.declare_parameter('depth_cluster_min_pixels', 20)
        self.declare_parameter('depth_center_weight', 1.0)
        self.declare_parameter('depth_size_weight', 0.02)
        self.declare_parameter('depth_near_penalty_weight', 0.15)
        self.declare_parameter('max_objects_per_class', 1)
        self.declare_parameter('same_object_distance_threshold_m', 0.45)

        self.pub = self.create_publisher(
            String,
            str(self.get_parameter('normalized_objects_topic').value),
            10,
        )
        self.object_pose_pub = self.create_publisher(
            String,
            str(self.get_parameter('object_pose_topic').value),
            10,
        )
        self.debug_pub = self.create_publisher(String, '/perception_debug', 10)
        self.timer = self.create_timer(1.0, self.publish_state)
        self.bridge = None
        self.debug_image_pub = None
        self.marker_pub = None
        if bool(self.get_parameter('enable_debug_image').value):
            try:
                from cv_bridge import CvBridge
                self.bridge = CvBridge()
                self.debug_image_pub = self.create_publisher(
                    Image,
                    str(self.get_parameter('debug_image_topic').value),
                    10,
                )
            except Exception as exc:
                self.get_logger().warning(
                    f'debug image disabled: cv_bridge unavailable or incompatible: {exc}'
                )
        if bool(self.get_parameter('enable_object_markers').value):
            self.marker_pub = self.create_publisher(
                MarkerArray,
                str(self.get_parameter('object_marker_topic').value),
                10,
            )

        self.model = self.load_yolo_model(str(self.get_parameter('yolo_model').value))
        raw_targets = self.get_parameter('yolo_target_classes').value
        self.class_filter = set(str(x) for x in raw_targets if str(x).strip())

        self.last_depth_msg = None
        self.last_camera_info = None
        self.last_object_poses = []
        self.last_depth_debug = []
        self.last_objects = []
        self.last_yolo_error = None
        self.last_pose_stamp = None
        self.last_image_frame = ''
        self.last_debug_image_msg = None

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        self.create_subscription(
            Image,
            str(self.get_parameter('camera_image_topic').value),
            self.on_image,
            10,
        )
        self.create_subscription(
            Image,
            str(self.get_parameter('camera_depth_topic').value),
            self.on_depth,
            10,
        )
        self.create_subscription(
            CameraInfo,
            str(self.get_parameter('camera_info_topic').value),
            self.on_camera_info,
            10,
        )

    def load_yolo_model(self, model_name: str):
        ultralytics = importlib.import_module('ultralytics')
        model_cls = getattr(ultralytics, 'YOLO')
        return model_cls(model_name)

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

    def _valid_depth_mask(self, values: np.ndarray) -> np.ndarray:
        min_depth = float(self.get_parameter('depth_min_valid_m').value)
        max_depth = float(self.get_parameter('depth_max_valid_m').value)
        return np.isfinite(values) & (values >= min_depth) & (values <= max_depth)

    def _lookup_depth_center_patch(self, depth: np.ndarray, u: int, v: int) -> float | None:
        h, w = depth.shape
        if not (0 <= u < w and 0 <= v < h):
            return None
        half = int(self.get_parameter('depth_center_patch_radius_px').value)
        x0, x1 = max(0, u - half), min(w, u + half + 1)
        y0, y1 = max(0, v - half), min(h, v + half + 1)
        window = depth[y0:y1, x0:x1]
        valid = window[self._valid_depth_mask(window)]
        if valid.size == 0:
            center = depth[v, u]
            if not self._valid_depth_mask(np.array([center], dtype=np.float32))[0]:
                return None
            return float(center)
        return float(np.median(valid))

    def _lookup_depth_bbox_cluster(self, depth: np.ndarray, x0: float, y0: float, x1: float, y1: float):
        h, w = depth.shape
        ix0 = max(0, min(w - 1, int(math.floor(x0))))
        ix1 = max(0, min(w, int(math.ceil(x1))))
        iy0 = max(0, min(h - 1, int(math.floor(y0))))
        iy1 = max(0, min(h, int(math.ceil(y1))))
        if ix1 <= ix0 or iy1 <= iy0:
            return None, None

        roi = depth[iy0:iy1, ix0:ix1]
        valid_mask = self._valid_depth_mask(roi)
        if not np.any(valid_mask):
            return None, None

        ys, xs = np.nonzero(valid_mask)
        values = roi[valid_mask].astype(np.float32)
        order = np.argsort(values)
        xs = xs[order]
        ys = ys[order]
        values = values[order]

        gap = float(self.get_parameter('depth_cluster_gap_m').value)
        min_pixels = int(self.get_parameter('depth_cluster_min_pixels').value)
        center_weight = float(self.get_parameter('depth_center_weight').value)
        size_weight = float(self.get_parameter('depth_size_weight').value)
        near_penalty = float(self.get_parameter('depth_near_penalty_weight').value)

        roi_center_x = 0.5 * float(ix1 - ix0 - 1)
        roi_center_y = 0.5 * float(iy1 - iy0 - 1)
        roi_diag = max(math.hypot(float(ix1 - ix0), float(iy1 - iy0)), 1.0)

        best = None
        start = 0
        total = values.size
        while start < total:
            end = start + 1
            while end < total and float(values[end] - values[end - 1]) <= gap:
                end += 1
            cluster_values = values[start:end]
            cluster_xs = xs[start:end].astype(np.float32)
            cluster_ys = ys[start:end].astype(np.float32)
            pixel_count = int(cluster_values.size)
            if pixel_count >= min_pixels:
                median_depth = float(np.median(cluster_values))
                center_dx = float(np.mean(cluster_xs) - roi_center_x)
                center_dy = float(np.mean(cluster_ys) - roi_center_y)
                center_distance_norm = math.hypot(center_dx, center_dy) / roi_diag
                score = (
                    center_weight * (1.0 - center_distance_norm)
                    + size_weight * float(pixel_count)
                    - near_penalty * max(0.0, 1.0 - median_depth)
                )
                candidate = {
                    'depth_m': median_depth,
                    'score': score,
                    'pixel_count': pixel_count,
                }
                if best is None or candidate['score'] > best['score']:
                    best = candidate
            start = end
        if best is None:
            return None, None
        return float(best['depth_m']), best

    def _resize_mask_nearest(self, mask: np.ndarray, width: int, height: int) -> np.ndarray:
        if mask.shape == (height, width):
            return mask.astype(bool)
        from PIL import Image as PILImage

        image = PILImage.fromarray((mask.astype(np.uint8) * 255))
        image = image.resize((width, height), resample=PILImage.Resampling.NEAREST)
        return np.asarray(image) > 0

    def _lookup_depth_mask_cluster(self, depth: np.ndarray, mask: np.ndarray):
        h, w = depth.shape
        if mask.shape != depth.shape:
            mask = self._resize_mask_nearest(mask, w, h)
        valid_mask = mask & self._valid_depth_mask(depth)
        if not np.any(valid_mask):
            return None, None

        ys, xs = np.nonzero(valid_mask)
        values = depth[valid_mask].astype(np.float32)
        order = np.argsort(values)
        xs = xs[order]
        ys = ys[order]
        values = values[order]

        gap = float(self.get_parameter('depth_cluster_gap_m').value)
        min_pixels = int(self.get_parameter('depth_cluster_min_pixels').value)
        center_weight = float(self.get_parameter('depth_center_weight').value)
        size_weight = float(self.get_parameter('depth_size_weight').value)
        near_penalty = float(self.get_parameter('depth_near_penalty_weight').value)

        mask_ys, mask_xs = np.nonzero(mask)
        if mask_xs.size == 0:
            return None, None
        mask_center_x = float(np.mean(mask_xs))
        mask_center_y = float(np.mean(mask_ys))
        mask_diag = max(math.hypot(float(w), float(h)), 1.0)

        best = None
        start = 0
        total = values.size
        while start < total:
            end = start + 1
            while end < total and float(values[end] - values[end - 1]) <= gap:
                end += 1
            cluster_values = values[start:end]
            cluster_xs = xs[start:end].astype(np.float32)
            cluster_ys = ys[start:end].astype(np.float32)
            pixel_count = int(cluster_values.size)
            if pixel_count >= min_pixels:
                median_depth = float(np.median(cluster_values))
                u_depth = float(np.mean(cluster_xs))
                v_depth = float(np.mean(cluster_ys))
                center_distance_norm = math.hypot(u_depth - mask_center_x, v_depth - mask_center_y) / mask_diag
                score = (
                    center_weight * (1.0 - center_distance_norm)
                    + size_weight * float(pixel_count)
                    - near_penalty * max(0.0, 1.0 - median_depth)
                )
                candidate = {
                    'depth_m': median_depth,
                    'score': score,
                    'pixel_count': pixel_count,
                    'u_depth': u_depth,
                    'v_depth': v_depth,
                }
                if best is None or candidate['score'] > best['score']:
                    best = candidate
            start = end
        if best is None:
            return None, None
        return float(best['depth_m']), best

    def _mask_for_detection(self, result, index: int, width: int, height: int):
        masks = getattr(result, 'masks', None)
        if masks is None or getattr(masks, 'data', None) is None:
            return None
        if index >= len(masks.data):
            return None
        try:
            mask = masks.data[index].detach().cpu().numpy() > 0.5
        except Exception:
            return None
        return self._resize_mask_nearest(mask, width, height)

    def _lookup_depth(self, u: int, v: int, x0: float | None = None, y0: float | None = None, x1: float | None = None, y1: float | None = None):
        if self.last_depth_msg is None:
            return None, None
        depth = self._depth_to_numpy(self.last_depth_msg)
        mode = str(self.get_parameter('depth_mode').value).strip().lower()
        if mode == 'bbox_cluster' and None not in (x0, y0, x1, y1):
            cluster_depth, cluster_debug = self._lookup_depth_bbox_cluster(depth, float(x0), float(y0), float(x1), float(y1))
            if cluster_depth is not None:
                return cluster_depth, {'mode': 'bbox_cluster', **cluster_debug}
        patch_depth = self._lookup_depth_center_patch(depth, u, v)
        if patch_depth is None:
            return None, None
        return patch_depth, {'mode': 'center_patch'}

    def _lookup_depth_for_detection(self, u: int, v: int, result, index: int, image_width: int, image_height: int, x0: float, y0: float, x1: float, y1: float):
        if self.last_depth_msg is None:
            return None, None, float(u), float(v)
        depth = self._depth_to_numpy(self.last_depth_msg)
        mode = str(self.get_parameter('depth_mode').value).strip().lower()
        use_mask = mode in ('mask_cluster', 'segmentation', 'segmentation_mask', 'auto')
        if use_mask:
            mask = self._mask_for_detection(result, index, depth.shape[1], depth.shape[0])
            if mask is not None:
                mask_depth, mask_debug = self._lookup_depth_mask_cluster(depth, mask)
                if mask_depth is not None:
                    u_depth = float(mask_debug.get('u_depth', u))
                    v_depth = float(mask_debug.get('v_depth', v))
                    u_image = u_depth * float(image_width) / float(depth.shape[1])
                    v_image = v_depth * float(image_height) / float(depth.shape[0])
                    return mask_depth, {'mode': 'mask_cluster', **mask_debug}, u_image, v_image

        depth_m, depth_info = self._lookup_depth(u, v, x0, y0, x1, y1)
        return depth_m, depth_info, float(u), float(v)

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

    def _transform_point(self, point_camera: np.ndarray, source_frame: str):
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

    def _suppress_duplicate_objects(self, objects: list[dict], image_width: int, image_height: int):
        threshold_m = float(self.get_parameter('same_object_distance_threshold_m').value)
        max_per_class = int(self.get_parameter('max_objects_per_class').value)
        unlimited_per_class = max_per_class <= 0
        grouped: dict[str, list[dict]] = {}
        for item in objects:
            grouped.setdefault(str(item.get('class_name', '')), []).append(item)

        selected: list[dict] = []
        for class_name, candidates in grouped.items():
            ranked = sorted(
                candidates,
                key=lambda item: (
                    float(item.get('confidence', 0.0)),
                    float(item.get('bbox_area_norm', 0.0)),
                    -abs(float(item.get('bbox_center_x_norm', 0.5)) - 0.5),
                    -math.hypot(float(item.get('x_m', 0.0)), float(item.get('y_m', 0.0))),
                ),
                reverse=True,
            )
            kept: list[dict] = []
            for candidate in ranked:
                duplicate = False
                for existing in kept:
                    dx = float(candidate.get('x_m', 0.0)) - float(existing.get('x_m', 0.0))
                    dy = float(candidate.get('y_m', 0.0)) - float(existing.get('y_m', 0.0))
                    dz = float(candidate.get('z_m', 0.0)) - float(existing.get('z_m', 0.0))
                    if math.sqrt(dx * dx + dy * dy + dz * dz) <= threshold_m:
                        duplicate = True
                        break
                if duplicate:
                    continue
                kept.append(candidate)
                if not unlimited_per_class and len(kept) >= max_per_class:
                    break
            selected.extend(kept)
        return selected

    def _draw_box(self, image: np.ndarray, x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int]):
        image[max(0, y0):min(image.shape[0], y0 + 2), max(0, x0):min(image.shape[1], x1)] = color
        image[max(0, y1 - 2):min(image.shape[0], y1), max(0, x0):min(image.shape[1], x1)] = color
        image[max(0, y0):min(image.shape[0], y1), max(0, x0):min(image.shape[1], x0 + 2)] = color
        image[max(0, y0):min(image.shape[0], y1), max(0, x1 - 2):min(image.shape[1], x1)] = color

    def _draw_label(self, image: np.ndarray, x0: int, y0: int, label: str, color: tuple[int, int, int]):
        if not label:
            return
        block_h = 16
        block_w = min(image.shape[1] - max(0, x0), max(40, 8 * len(label)))
        top = max(0, y0 - block_h)
        left = max(0, x0)
        image[top:min(image.shape[0], y0), left:min(image.shape[1], left + block_w)] = color

    def _publish_debug_image(self, image: np.ndarray, header, overlays: list[dict]):
        if self.debug_image_pub is None or self.bridge is None:
            return
        try:
            canvas = image.copy()
            for overlay in overlays:
                x0 = int(overlay.get('x0', 0))
                y0 = int(overlay.get('y0', 0))
                x1 = int(overlay.get('x1', 0))
                y1 = int(overlay.get('y1', 0))
                color = tuple(int(v) for v in overlay.get('color', (0, 255, 0)))
                label = str(overlay.get('label', ''))
                self._draw_box(canvas, x0, y0, x1, y1, color)
                self._draw_label(canvas, x0, y0, label, color)
            msg = self.bridge.cv2_to_imgmsg(canvas[:, :, ::-1], encoding='bgr8')
            msg.header = header
            self.last_debug_image_msg = msg
            self.debug_image_pub.publish(msg)
        except Exception as exc:
            self.last_yolo_error = f'debug_image_failed:{exc}'

    def _publish_object_markers(self):
        if self.marker_pub is None:
            return
        frame_id = str(self.get_parameter('object_pose_frame').value)
        marker_array = MarkerArray()
        lifetime = float(self.get_parameter('marker_lifetime_sec').value)
        scale = float(self.get_parameter('marker_scale_m').value)
        stamp = self.get_clock().now().to_msg()
        for idx, obj in enumerate(self.last_object_poses):
            ns = f'perception_{str(obj.get("class_name", "object"))}'
            sphere = Marker()
            sphere.header.frame_id = frame_id
            sphere.header.stamp = stamp
            sphere.ns = ns
            sphere.id = idx * 2
            sphere.type = Marker.SPHERE
            sphere.action = Marker.ADD
            sphere.pose.position.x = float(obj.get('x_m', 0.0))
            sphere.pose.position.y = float(obj.get('y_m', 0.0))
            sphere.pose.position.z = float(obj.get('z_m', 0.0))
            sphere.pose.orientation.w = 1.0
            sphere.scale.x = scale
            sphere.scale.y = scale
            sphere.scale.z = scale
            sphere.color.r = 0.1
            sphere.color.g = 0.9
            sphere.color.b = 0.2
            sphere.color.a = 0.85
            sphere.lifetime.sec = int(lifetime)
            sphere.lifetime.nanosec = int((lifetime - int(lifetime)) * 1e9)
            marker_array.markers.append(sphere)

            text = Marker()
            text.header.frame_id = frame_id
            text.header.stamp = stamp
            text.ns = ns
            text.id = idx * 2 + 1
            text.type = Marker.TEXT_VIEW_FACING
            text.action = Marker.ADD
            text.pose.position.x = float(obj.get('x_m', 0.0))
            text.pose.position.y = float(obj.get('y_m', 0.0))
            text.pose.position.z = float(obj.get('z_m', 0.0)) + scale * 0.9
            text.pose.orientation.w = 1.0
            text.scale.z = max(0.08, scale * 0.75)
            text.color.r = 1.0
            text.color.g = 1.0
            text.color.b = 1.0
            text.color.a = 0.95
            text.text = (
                f'{str(obj.get("class_name", "object"))} '
                f'{float(obj.get("confidence", 0.0)):.2f} '
                f'{math.hypot(float(obj.get("x_m", 0.0)), float(obj.get("y_m", 0.0))):.2f}m'
            )
            text.lifetime.sec = int(lifetime)
            text.lifetime.nanosec = int((lifetime - int(lifetime)) * 1e9)
            marker_array.markers.append(text)
        self.marker_pub.publish(marker_array)

    def on_image(self, msg: Image):
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
        depth_debug = []
        overlays = []
        source_frame = msg.header.frame_id or str(self.get_parameter('fallback_camera_frame').value).strip() or 'camera_optical_frame'
        for result in results[:1]:
            boxes = getattr(result, 'boxes', None)
            if boxes is None or boxes.cls is None:
                continue
            cls_list = boxes.cls.tolist()
            conf_list = boxes.conf.tolist() if getattr(boxes, 'conf', None) is not None else [conf] * len(cls_list)
            xyxy_list = boxes.xyxy.tolist() if getattr(boxes, 'xyxy', None) is not None else []
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
                overlay = {
                    'x0': max(0, min(msg.width - 1, int(round(float(x0))))),
                    'y0': max(0, min(msg.height - 1, int(round(float(y0))))),
                    'x1': max(0, min(msg.width, int(round(float(x1))))),
                    'y1': max(0, min(msg.height, int(round(float(y1))))),
                    'color': (0, 200, 90),
                    'label': f'{str(label)} {float(conf_list[i]) if i < len(conf_list) else float(conf):.2f}',
                }
                depth_m, depth_info, point_u, point_v = self._lookup_depth_for_detection(
                    u, v, result, i, msg.width, msg.height, x0, y0, x1, y1
                )
                if depth_m is None:
                    overlay['color'] = (220, 140, 0)
                    overlay['label'] += ' depth?'
                    overlays.append(overlay)
                    continue
                point_camera = self._camera_point_from_pixel(float(point_u), float(point_v), depth_m)
                if point_camera is None:
                    overlay['color'] = (220, 140, 0)
                    overlay['label'] += ' proj?'
                    overlays.append(overlay)
                    continue
                point_target = self._transform_point(point_camera, source_frame)
                if point_target is None:
                    overlay['color'] = (200, 40, 40)
                    overlay['label'] += ' tf?'
                    overlays.append(overlay)
                    continue
                object_poses.append({
                    'class_name': str(label),
                    'confidence': float(conf_list[i]) if i < len(conf_list) else float(conf),
                    'x_m': float(point_target[0]),
                    'y_m': float(point_target[1]),
                    'z_m': float(point_target[2]),
                    'bbox_area_norm': float(max(0.0, (float(x1) - float(x0)) * (float(y1) - float(y0))) / float(msg.width * msg.height)),
                    'bbox_center_x_norm': float(point_u) / float(msg.width) if msg.width > 0 else 0.5,
                })
                overlay['label'] += f' {float(depth_m):.2f}m'
                overlays.append(overlay)
                if depth_info is not None:
                    depth_debug.append({
                        'class_name': str(label),
                        'depth_mode': str(depth_info.get('mode', 'unknown')),
                        'depth_m': float(depth_m),
                        'pixel_count': int(depth_info.get('pixel_count', 0)),
                        'score': float(depth_info.get('score', 0.0)),
                    })

        filtered_object_poses = self._suppress_duplicate_objects(object_poses, msg.width, msg.height)
        filtered_names = sorted({str(item.get('class_name', '')) for item in filtered_object_poses if str(item.get('class_name', '')).strip()})

        self.last_objects = filtered_names if filtered_names else sorted(set(names))
        self.last_object_poses = filtered_object_poses
        self.last_depth_debug = depth_debug
        self.last_pose_stamp = {'sec': int(msg.header.stamp.sec), 'nanosec': int(msg.header.stamp.nanosec)}
        self.last_image_frame = source_frame
        self.last_yolo_error = None
        self._publish_debug_image(image, msg.header, overlays)
        self._publish_object_markers()

    def publish_state(self):
        normalized = String()
        normalized.data = ','.join(self.last_objects)
        self.pub.publish(normalized)

        object_pose_msg = String()
        object_pose_msg.data = json.dumps({
            'frame_id': str(self.get_parameter('object_pose_frame').value),
            'source_frame': self.last_image_frame,
            'stamp': self.last_pose_stamp,
            'objects': self.last_object_poses,
        }, ensure_ascii=False)
        self.object_pose_pub.publish(object_pose_msg)

        debug = String()
        if self.last_yolo_error:
            debug.data = f'mode=yolo error={self.last_yolo_error} objects={normalized.data}'
        else:
            cluster_count = sum(1 for item in self.last_depth_debug if item.get('depth_mode') == 'bbox_cluster')
            target_frame = str(self.get_parameter('object_pose_frame').value)
            debug.data = (
                f'mode=yolo objects={normalized.data} poses={len(self.last_object_poses)} '
                f'cluster_poses={cluster_count} frame={target_frame}'
            )
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
