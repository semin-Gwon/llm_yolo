import time

import rclpy
from rclpy.action import ActionClient, ActionServer
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String

from llm_yolo_interfaces.action import RotateInPlace, ScanScene


class ScanSceneServer(Node):
    def __init__(self):
        super().__init__('scan_scene_server')
        self.declare_parameter('detected_objects_topic', '/perception/visible_objects')
        self.declare_parameter('default_detected_objects', ['chair', 'person'])
        self.declare_parameter('enable_rotate_scan', True)
        self.declare_parameter('rotate_scan_num_views', 4)
        self.declare_parameter('rotate_scan_step_yaw_rad', 1.57079632679)
        self.declare_parameter('rotate_scan_settle_sec', 0.3)
        self.declare_parameter('rotate_timeout_sec', 5)
        self.detected_objects = set(self.get_parameter('default_detected_objects').value)
        self.callback_group = ReentrantCallbackGroup()
        self.sub = self.create_subscription(
            String,
            self.get_parameter('detected_objects_topic').value,
            self.on_objects,
            10,
            callback_group=self.callback_group,
        )
        self.rotate_client = ActionClient(
            self,
            RotateInPlace,
            '/rotate_in_place',
            callback_group=self.callback_group,
        )
        self.server = ActionServer(
            self,
            ScanScene,
            '/scan_scene',
            self.execute,
            callback_group=self.callback_group,
        )

    def on_objects(self, msg: String):
        values = [item.strip() for item in msg.data.split(',') if item.strip()]
        self.detected_objects = set(values)

    def current_found(self, target: str) -> bool:
        return target in self.detected_objects

    def rotate_once(self, yaw_rad: float, timeout_sec: int) -> tuple[bool, str]:
        if not self.rotate_client.wait_for_server(timeout_sec=2.0):
            return False, 'rotate_server_unavailable'
        goal = RotateInPlace.Goal()
        goal.yaw_rad = float(yaw_rad)
        goal.timeout_sec = int(timeout_sec)
        send_future = self.rotate_client.send_goal_async(goal)
        while rclpy.ok() and not send_future.done():
            time.sleep(0.05)
        goal_handle = send_future.result()
        if goal_handle is None or not goal_handle.accepted:
            return False, 'rotate_goal_rejected'
        result_future = goal_handle.get_result_async()
        while rclpy.ok() and not result_future.done():
            time.sleep(0.05)
        wrapped = result_future.result()
        if wrapped is None:
            return False, 'rotate_result_missing'
        result = wrapped.result
        return bool(result.success), str(result.outcome)

    def execute(self, goal_handle):
        target = goal_handle.request.target_class
        result = ScanScene.Result()
        if self.current_found(target):
            result.found = True
            result.detection_state = 'FOUND'
            result.message = f'{target}:FOUND'
            goal_handle.succeed()
            return result

        rotate_enabled = bool(self.get_parameter('enable_rotate_scan').value)
        if rotate_enabled:
            num_views = max(1, int(self.get_parameter('rotate_scan_num_views').value))
            step_yaw = float(self.get_parameter('rotate_scan_step_yaw_rad').value)
            settle_sec = float(self.get_parameter('rotate_scan_settle_sec').value)
            rotate_timeout = int(self.get_parameter('rotate_timeout_sec').value)
            for _ in range(max(0, num_views - 1)):
                if goal_handle.is_cancel_requested:
                    goal_handle.canceled()
                    result.found = False
                    result.detection_state = 'CANCELED'
                    result.message = f'{target}:CANCELED'
                    return result
                rotate_ok, rotate_outcome = self.rotate_once(step_yaw, rotate_timeout)
                if not rotate_ok:
                    result.found = False
                    result.detection_state = 'ROTATE_FAILED'
                    result.message = f'{target}:ROTATE_FAILED:{rotate_outcome}'
                    goal_handle.abort()
                    return result
                time.sleep(settle_sec)
                if self.current_found(target):
                    result.found = True
                    result.detection_state = 'FOUND'
                    result.message = f'{target}:FOUND'
                    goal_handle.succeed()
                    return result

        result.found = False
        result.detection_state = 'NOT_FOUND'
        result.message = f'{target}:NOT_FOUND'
        goal_handle.succeed()
        return result


def main(args=None):
    rclpy.init(args=args)
    node = ScanSceneServer()
    try:
        executor = MultiThreadedExecutor()
        executor.add_node(node)
        executor.spin()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
