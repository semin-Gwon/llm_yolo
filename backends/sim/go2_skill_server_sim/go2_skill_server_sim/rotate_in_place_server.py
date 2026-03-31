import math
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.action import ActionServer
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import Bool

from llm_yolo_interfaces.action import RotateInPlace


class RotateInPlaceServer(Node):
    def __init__(self):
        super().__init__('rotate_in_place_server')
        self.declare_parameter('cmd_vel_topic', '/cmd_vel')
        self.declare_parameter('angular_speed_rps', 0.8)
        self.declare_parameter('control_rate_hz', 10.0)
        self.callback_group = ReentrantCallbackGroup()
        self.emergency_stop_active = False
        self.cmd_vel_pub = self.create_publisher(Twist, self.get_parameter('cmd_vel_topic').value, 10)
        self.emergency_stop_sub = self.create_subscription(Bool, '/emergency_stop', self.on_emergency_stop, 10, callback_group=self.callback_group)
        self.emergency_clear_sub = self.create_subscription(Bool, '/emergency_clear', self.on_emergency_clear, 10, callback_group=self.callback_group)
        self.server = ActionServer(
            self,
            RotateInPlace,
            '/rotate_in_place',
            self.execute,
            callback_group=self.callback_group,
        )

    def on_emergency_stop(self, msg: Bool):
        if bool(msg.data):
            self.emergency_stop_active = True
            self.stop_robot()

    def on_emergency_clear(self, msg: Bool):
        if bool(msg.data):
            self.emergency_stop_active = False

    def stop_robot(self):
        self.cmd_vel_pub.publish(Twist())

    def execute(self, goal_handle):
        result = RotateInPlace.Result()
        angular_speed = float(self.get_parameter('angular_speed_rps').value)
        control_period = 1.0 / float(self.get_parameter('control_rate_hz').value)
        yaw = goal_handle.request.yaw_rad
        duration = abs(yaw) / max(angular_speed, 1e-3)
        direction = 1.0 if yaw >= 0.0 else -1.0
        deadline = time.time() + duration
        cmd = Twist()
        cmd.angular.z = direction * angular_speed

        while rclpy.ok() and time.time() < deadline:
            if self.emergency_stop_active:
                self.stop_robot()
                goal_handle.abort()
                result.success = False
                result.outcome = f'emergency_stop:{yaw:.2f}'
                return result
            if goal_handle.is_cancel_requested:
                self.stop_robot()
                goal_handle.canceled()
                result.success = False
                result.outcome = f'canceled:{yaw:.2f}'
                return result
            self.cmd_vel_pub.publish(cmd)
            time.sleep(control_period)

        self.stop_robot()
        goal_handle.succeed()
        result.success = True
        result.outcome = f'rotated:{math.degrees(yaw):.1f}deg'
        return result


def main(args=None):
    rclpy.init(args=args)
    node = RotateInPlaceServer()
    try:
        executor = MultiThreadedExecutor()
        executor.add_node(node)
        executor.spin()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
