import importlib
import json
import math
import time
from typing import Any

import rclpy
from rclpy.action import ActionServer
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String

from llm_yolo_interfaces.action import ApproachObject


ROBOT_SPORT_API_ID_BALANCESTAND = 1002
ROBOT_SPORT_API_ID_STOPMOVE = 1003
ROBOT_SPORT_API_ID_MOVE = 1008


class ApproachObjectServer(Node):
    def __init__(self):
        super().__init__('approach_object_server')
        self.declare_parameter('object_pose_topic', '/perception/object_poses')
        self.declare_parameter('control_request_topic', '/api/sport/request')
        self.declare_parameter('object_pose_frame', 'camera_link')
        self.declare_parameter('default_approach_distance_m', 0.5)
        self.declare_parameter('heading_align_threshold_rad', 0.25)
        self.declare_parameter('heading_stop_threshold_rad', 0.6)
        self.declare_parameter('max_linear_speed_mps', 0.2)
        self.declare_parameter('max_angular_speed_radps', 0.4)
        self.declare_parameter('linear_gain', 0.6)
        self.declare_parameter('angular_gain', 1.2)
        self.declare_parameter('control_period_sec', 0.1)
        self.declare_parameter('stale_pose_timeout_sec', 1.0)
        self.declare_parameter('send_balance_stand_on_start', True)

        self.callback_group = ReentrantCallbackGroup()
        self.object_poses: dict[str, list[dict[str, Any]]] = {}
        self.object_pose_frame = str(self.get_parameter('object_pose_frame').value)
        self.last_pose_update_time = 0.0

        self.request_msg_cls = self._load_request_cls()
        self.request_pub = (
            self.create_publisher(
                self.request_msg_cls,
                str(self.get_parameter('control_request_topic').value),
                10,
            )
            if self.request_msg_cls is not None
            else None
        )

        self.create_subscription(
            String,
            str(self.get_parameter('object_pose_topic').value),
            self.on_object_poses,
            10,
            callback_group=self.callback_group,
        )
        self.server = ActionServer(
            self,
            ApproachObject,
            '/approach_object',
            self.execute,
            callback_group=self.callback_group,
        )

    def _load_request_cls(self):
        try:
            module = importlib.import_module('unitree_api.msg')
            return getattr(module, 'Request')
        except Exception as exc:
            self.get_logger().warning(f'unitree_api.msg.Request unavailable: {exc}')
            return None

    def on_object_poses(self, msg: String):
        try:
            payload = json.loads(msg.data) if msg.data else {}
        except Exception as exc:
            self.get_logger().warning(f'object pose parse failed: {exc}')
            return

        grouped: dict[str, list[dict[str, Any]]] = {}
        if str(payload.get('frame_id', '')).strip():
            self.object_pose_frame = str(payload.get('frame_id', '')).strip()
        objects = payload.get('objects', [])
        if isinstance(objects, list):
            for item in objects:
                try:
                    class_name = str(item.get('class_name', '')).strip()
                    if not class_name:
                        continue
                    grouped.setdefault(class_name, []).append({
                        'class_name': class_name,
                        'confidence': float(item.get('confidence', 0.0)),
                        'x_m': float(item['x_m']),
                        'y_m': float(item['y_m']),
                        'z_m': float(item.get('z_m', 0.0)),
                    })
                except Exception:
                    continue
        self.object_poses = grouped
        self.last_pose_update_time = time.time()

    def _select_object(self, target_class: str, object_selector: str = ''):
        candidates = self.object_poses.get(target_class, [])
        if not candidates:
            return None
        selector = str(object_selector or '').strip().lower()
        key_fn = lambda item: math.hypot(float(item.get('x_m', 0.0)), float(item.get('y_m', 0.0)))
        if selector == 'far':
            return max(candidates, key=key_fn)
        return min(candidates, key=key_fn)

    def _build_request(self, api_id: int, parameter: dict[str, Any] | None = None):
        if self.request_msg_cls is None:
            return None
        req = self.request_msg_cls()
        req.header.identity.api_id = int(api_id)
        req.parameter = json.dumps(parameter or {})
        req.binary = []
        return req

    def _publish_balance_stand(self):
        if self.request_pub is None:
            return
        req = self._build_request(ROBOT_SPORT_API_ID_BALANCESTAND)
        if req is not None:
            self.request_pub.publish(req)

    def _publish_stop(self):
        if self.request_pub is None:
            return
        req = self._build_request(ROBOT_SPORT_API_ID_STOPMOVE)
        if req is not None:
            self.request_pub.publish(req)

    def _publish_move(self, vx: float, vyaw: float):
        if self.request_pub is None:
            return
        req = self._build_request(
            ROBOT_SPORT_API_ID_MOVE,
            {'x': float(vx), 'y': 0.0, 'z': float(vyaw)},
        )
        if req is not None:
            self.request_pub.publish(req)

    def execute(self, goal_handle):
        result = ApproachObject.Result()
        target_class = str(goal_handle.request.target_class).strip()
        object_selector = str(goal_handle.request.object_selector).strip().lower()
        approach_distance_m = float(
            goal_handle.request.approach_distance_m
            if goal_handle.request.approach_distance_m > 0.0
            else self.get_parameter('default_approach_distance_m').value
        )
        timeout_sec = int(goal_handle.request.timeout_sec or 30)
        deadline = time.time() + float(timeout_sec)

        if self.request_pub is None:
            goal_handle.abort()
            result.success = False
            result.outcome = 'unitree_request_message_unavailable'
            return result

        if bool(self.get_parameter('send_balance_stand_on_start').value):
            self._publish_balance_stand()
            time.sleep(0.1)

        control_period = float(self.get_parameter('control_period_sec').value)
        stale_timeout_sec = float(self.get_parameter('stale_pose_timeout_sec').value)
        align_threshold = float(self.get_parameter('heading_align_threshold_rad').value)
        stop_threshold = float(self.get_parameter('heading_stop_threshold_rad').value)
        max_linear = float(self.get_parameter('max_linear_speed_mps').value)
        max_angular = float(self.get_parameter('max_angular_speed_radps').value)
        linear_gain = float(self.get_parameter('linear_gain').value)
        angular_gain = float(self.get_parameter('angular_gain').value)

        selected = None
        while rclpy.ok():
            now = time.time()
            if now >= deadline:
                self._publish_stop()
                goal_handle.abort()
                result.success = False
                result.outcome = f'timeout:{target_class}'
                return result

            if goal_handle.is_cancel_requested:
                self._publish_stop()
                goal_handle.canceled()
                result.success = False
                result.outcome = f'canceled:{target_class}'
                return result

            if now - self.last_pose_update_time > stale_timeout_sec:
                self._publish_stop()
                goal_handle.abort()
                result.success = False
                result.outcome = f'stale_object_pose:{target_class}'
                return result

            selected = self._select_object(target_class, object_selector)
            if selected is None:
                time.sleep(control_period)
                continue

            object_x = float(selected['x_m'])
            object_y = float(selected['y_m'])
            distance = math.hypot(object_x, object_y)
            heading = math.atan2(object_y, object_x)
            distance_error = distance - approach_distance_m

            if distance_error <= 0.0:
                self._publish_stop()
                result.success = True
                result.outcome = f'arrived:approach:{target_class}'
                result.object_x_m = object_x
                result.object_y_m = object_y
                result.goal_x_m = approach_distance_m
                result.goal_y_m = 0.0
                goal_handle.succeed()
                return result

            commanded_yaw = max(-max_angular, min(max_angular, angular_gain * heading))
            if abs(heading) > stop_threshold:
                commanded_linear = 0.0
            elif abs(heading) > align_threshold:
                commanded_linear = 0.0
            else:
                commanded_linear = max(
                    0.0,
                    min(max_linear, linear_gain * distance_error),
                )

            self._publish_move(commanded_linear, commanded_yaw)
            time.sleep(control_period)

        self._publish_stop()
        goal_handle.abort()
        result.success = False
        result.outcome = f'interrupted:{target_class}'
        return result


def main(args=None):
    rclpy.init(args=args)
    node = ApproachObjectServer()
    try:
        executor = MultiThreadedExecutor()
        executor.add_node(node)
        executor.spin()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
