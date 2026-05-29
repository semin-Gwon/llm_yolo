import importlib
import json
import math
import time
from typing import Any

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import Bool


ROBOT_SPORT_API_ID_STOPMOVE = 1003
ROBOT_SPORT_API_ID_MOVE = 1008


class CmdVelToSportRequestNode(Node):
    def __init__(self):
        super().__init__('cmd_vel_to_sport_request_node')
        self.declare_parameter('cmd_vel_topic', '/cmd_vel')
        self.declare_parameter('control_request_topic', '/api/sport/request')
        self.declare_parameter('emergency_stop_topic', '/emergency_stop')
        self.declare_parameter('emergency_clear_topic', '/emergency_clear')
        self.declare_parameter('max_linear_x_mps', 0.3)
        self.declare_parameter('max_lateral_y_mps', 0.0)
        self.declare_parameter('max_yaw_radps', 0.4)
        self.declare_parameter('cmd_vel_timeout_sec', 0.35)
        self.declare_parameter('watchdog_period_sec', 0.1)
        self.declare_parameter('stop_repeat_count', 3)
        self.declare_parameter('publish_stop_on_zero_cmd', True)

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

        self.last_cmd_time = 0.0
        self.has_seen_cmd = False
        self.timeout_stop_sent = True
        self.emergency_stop_active = False

        self.create_subscription(
            Twist,
            str(self.get_parameter('cmd_vel_topic').value),
            self.on_cmd_vel,
            20,
        )
        self.create_subscription(
            Bool,
            str(self.get_parameter('emergency_stop_topic').value),
            self.on_emergency_stop,
            10,
        )
        self.create_subscription(
            Bool,
            str(self.get_parameter('emergency_clear_topic').value),
            self.on_emergency_clear,
            10,
        )
        self.create_timer(
            float(self.get_parameter('watchdog_period_sec').value),
            self.on_watchdog,
        )

        self.get_logger().info(
            'cmd_vel bridge ready: %s -> %s'
            % (
                str(self.get_parameter('cmd_vel_topic').value),
                str(self.get_parameter('control_request_topic').value),
            )
        )

    def _load_request_cls(self):
        try:
            module = importlib.import_module('unitree_api.msg')
            return getattr(module, 'Request')
        except Exception as exc:
            self.get_logger().error(f'unitree_api.msg.Request unavailable: {exc}')
            return None

    def _build_request(self, api_id: int, parameter: dict[str, Any] | None = None):
        if self.request_msg_cls is None:
            return None
        req = self.request_msg_cls()
        req.header.identity.api_id = int(api_id)
        req.parameter = json.dumps(parameter or {})
        req.binary = []
        return req

    def _clamp(self, value: float, limit: float) -> float:
        limit = abs(float(limit))
        return max(-limit, min(limit, float(value)))

    def _publish_stop(self):
        if self.request_pub is None:
            return
        req = self._build_request(ROBOT_SPORT_API_ID_STOPMOVE)
        if req is not None:
            self.request_pub.publish(req)

    def _publish_stop_burst(self):
        repeat_count = max(1, int(self.get_parameter('stop_repeat_count').value))
        for _ in range(repeat_count):
            self._publish_stop()
            time.sleep(0.02)

    def _publish_move(self, vx: float, vy: float, vyaw: float):
        if self.request_pub is None:
            return
        req = self._build_request(
            ROBOT_SPORT_API_ID_MOVE,
            {'x': float(vx), 'y': float(vy), 'z': float(vyaw)},
        )
        if req is not None:
            self.request_pub.publish(req)

    def on_emergency_stop(self, msg: Bool):
        if not bool(msg.data):
            return
        self.emergency_stop_active = True
        self.timeout_stop_sent = True
        self._publish_stop_burst()
        self.get_logger().warning('emergency_stop active: cmd_vel ignored, StopMove requested')

    def on_emergency_clear(self, msg: Bool):
        if not bool(msg.data):
            return
        self.emergency_stop_active = False
        self.timeout_stop_sent = True
        self.get_logger().info('emergency_stop cleared')

    def on_cmd_vel(self, msg: Twist):
        self.last_cmd_time = time.time()
        self.has_seen_cmd = True
        self.timeout_stop_sent = False

        if self.emergency_stop_active:
            self._publish_stop_burst()
            return

        vx = self._clamp(msg.linear.x, float(self.get_parameter('max_linear_x_mps').value))
        vy = self._clamp(msg.linear.y, float(self.get_parameter('max_lateral_y_mps').value))
        vyaw = self._clamp(msg.angular.z, float(self.get_parameter('max_yaw_radps').value))

        is_zero_cmd = math.isclose(vx, 0.0, abs_tol=1e-6) and math.isclose(vy, 0.0, abs_tol=1e-6) and math.isclose(vyaw, 0.0, abs_tol=1e-6)
        if is_zero_cmd and bool(self.get_parameter('publish_stop_on_zero_cmd').value):
            self._publish_stop()
            self.timeout_stop_sent = True
            return

        self._publish_move(vx, vy, vyaw)

    def on_watchdog(self):
        if not self.has_seen_cmd or self.timeout_stop_sent:
            return
        timeout_sec = float(self.get_parameter('cmd_vel_timeout_sec').value)
        if time.time() - self.last_cmd_time <= timeout_sec:
            return
        self._publish_stop_burst()
        self.timeout_stop_sent = True
        self.get_logger().warning('cmd_vel timeout: StopMove requested')


def main(args=None):
    rclpy.init(args=args)
    node = CmdVelToSportRequestNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
