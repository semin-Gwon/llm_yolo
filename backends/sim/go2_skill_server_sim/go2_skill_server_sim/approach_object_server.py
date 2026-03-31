import json
import math
import time

import rclpy
from nav_msgs.msg import Odometry
from rclpy.time import Time
from rclpy.action import ActionClient, ActionServer
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String
from tf2_ros import Buffer, TransformException, TransformListener

from llm_yolo_interfaces.action import ApproachObject, NavigateToPose


class ApproachObjectServer(Node):
    def __init__(self):
        super().__init__('approach_object_server')
        self.declare_parameter('object_pose_topic', '/perception/object_poses')
        self.declare_parameter('navigate_action_name', '/llm_navigate_to_pose')
        self.declare_parameter('odom_topic', '/odom')
        self.declare_parameter('default_approach_distance_m', 0.8)
        self.declare_parameter('global_frame', 'map')
        self.declare_parameter('base_frame', 'base_link')
        self.callback_group = ReentrantCallbackGroup()
        self.object_poses = {}
        self.current_pose = None
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.create_subscription(
            String,
            self.get_parameter('object_pose_topic').value,
            self.on_object_poses,
            10,
            callback_group=self.callback_group,
        )
        self.create_subscription(
            Odometry,
            self.get_parameter('odom_topic').value,
            self.on_odom,
            10,
            callback_group=self.callback_group,
        )
        self.navigate_client = ActionClient(
            self,
            NavigateToPose,
            self.get_parameter('navigate_action_name').value,
            callback_group=self.callback_group,
        )
        self.server = ActionServer(
            self,
            ApproachObject,
            '/approach_object',
            self.execute,
            callback_group=self.callback_group,
        )

    def on_object_poses(self, msg: String):
        try:
            payload = json.loads(msg.data) if msg.data else {}
        except Exception as exc:
            self.get_logger().warning(f'object pose parse failed: {exc}')
            return
        objects = payload.get('objects', [])
        grouped = {}
        if isinstance(objects, list):
            for item in objects:
                try:
                    class_name = str(item.get('class_name', '')).strip()
                    if not class_name:
                        continue
                    grouped.setdefault(class_name, []).append({
                        'x_m': float(item['x_m']),
                        'y_m': float(item['y_m']),
                        'z_m': float(item.get('z_m', 0.0)),
                        'confidence': float(item.get('confidence', 0.0)),
                    })
                except Exception:
                    continue
        self.object_poses = grouped

    def on_odom(self, msg: Odometry):
        position = msg.pose.pose.position
        orientation = msg.pose.pose.orientation
        yaw = math.atan2(
            2.0 * (orientation.w * orientation.z + orientation.x * orientation.y),
            1.0 - 2.0 * (orientation.y * orientation.y + orientation.z * orientation.z),
        )
        self.current_pose = (float(position.x), float(position.y), float(yaw))

    def current_pose_in_global(self):
        global_frame = str(self.get_parameter('global_frame').value)
        base_frame = str(self.get_parameter('base_frame').value)
        try:
            transform = self.tf_buffer.lookup_transform(global_frame, base_frame, Time())
            t = transform.transform.translation
            q = transform.transform.rotation
            yaw = math.atan2(
                2.0 * (q.w * q.z + q.x * q.y),
                1.0 - 2.0 * (q.y * q.y + q.z * q.z),
            )
            return (float(t.x), float(t.y), float(yaw))
        except TransformException:
            return self.current_pose

    def select_object(self, target_class: str):
        candidates = self.object_poses.get(target_class, [])
        if not candidates:
            return None
        return max(candidates, key=lambda item: float(item.get('confidence', 0.0)))

    def compute_goal_pose(self, obj: dict, approach_distance_m: float):
        pose = self.current_pose_in_global()
        if pose is None:
            return None
        robot_x, robot_y, _ = pose
        object_x = float(obj['x_m'])
        object_y = float(obj['y_m'])
        dx = object_x - robot_x
        dy = object_y - robot_y
        distance = math.hypot(dx, dy)
        yaw = math.atan2(dy, dx)
        if distance < 1e-3:
            return {
                'goal_x_m': robot_x,
                'goal_y_m': robot_y,
                'goal_yaw_rad': yaw,
            }
        unit_x = dx / distance
        unit_y = dy / distance
        stop_distance = min(max(approach_distance_m, 0.2), max(distance - 0.1, 0.2))
        goal_x = object_x - unit_x * stop_distance
        goal_y = object_y - unit_y * stop_distance
        return {
            'goal_x_m': float(goal_x),
            'goal_y_m': float(goal_y),
            'goal_yaw_rad': float(yaw),
        }

    def execute(self, goal_handle):
        result = ApproachObject.Result()
        target_class = str(goal_handle.request.target_class).strip()
        timeout_sec = int(goal_handle.request.timeout_sec or 30)
        approach_distance_m = float(
            goal_handle.request.approach_distance_m
            if goal_handle.request.approach_distance_m > 0.0
            else self.get_parameter('default_approach_distance_m').value
        )
        deadline = time.time() + float(timeout_sec)

        selected = None
        while rclpy.ok() and time.time() < deadline:
            if goal_handle.is_cancel_requested:
                goal_handle.canceled()
                result.success = False
                result.outcome = f'canceled:{target_class}'
                return result
            selected = self.select_object(target_class)
            if selected is not None and self.current_pose_in_global() is not None:
                break
            time.sleep(0.05)

        if selected is None or self.current_pose_in_global() is None:
            goal_handle.abort()
            result.success = False
            result.outcome = f'object_pose_unavailable:{target_class}'
            return result

        goal = self.compute_goal_pose(selected, approach_distance_m)
        if goal is None:
            goal_handle.abort()
            result.success = False
            result.outcome = f'goal_generation_failed:{target_class}'
            return result

        if not self.navigate_client.wait_for_server(timeout_sec=2.0):
            goal_handle.abort()
            result.success = False
            result.outcome = f'navigate_server_unavailable:{target_class}'
            return result

        nav_goal = NavigateToPose.Goal()
        nav_goal.target_name = f'approach:{target_class}'
        nav_goal.use_pose = True
        nav_goal.x_m = float(goal['goal_x_m'])
        nav_goal.y_m = float(goal['goal_y_m'])
        nav_goal.desired_yaw_rad = float(goal['goal_yaw_rad'])
        nav_goal.timeout_sec = timeout_sec
        nav_goal.speed_hint = str(goal_handle.request.speed_hint or 'normal')

        send_future = self.navigate_client.send_goal_async(nav_goal)
        while rclpy.ok() and not send_future.done():
            if goal_handle.is_cancel_requested:
                goal_handle.canceled()
                result.success = False
                result.outcome = f'canceled:{target_class}'
                return result
            time.sleep(0.05)

        nav_goal_handle = send_future.result()
        if nav_goal_handle is None or not nav_goal_handle.accepted:
            goal_handle.abort()
            result.success = False
            result.outcome = f'navigate_goal_rejected:{target_class}'
            return result

        result_future = nav_goal_handle.get_result_async()
        while rclpy.ok() and not result_future.done():
            if goal_handle.is_cancel_requested:
                nav_goal_handle.cancel_goal_async()
                goal_handle.canceled()
                result.success = False
                result.outcome = f'canceled:{target_class}'
                return result
            time.sleep(0.05)

        wrapped = result_future.result()
        nav_result = wrapped.result if wrapped is not None else None
        if nav_result is None:
            goal_handle.abort()
            result.success = False
            result.outcome = f'navigate_result_missing:{target_class}'
            return result

        result.success = bool(nav_result.success)
        result.outcome = str(nav_result.outcome)
        result.object_x_m = float(selected['x_m'])
        result.object_y_m = float(selected['y_m'])
        result.goal_x_m = float(goal['goal_x_m'])
        result.goal_y_m = float(goal['goal_y_m'])
        if result.success:
            goal_handle.succeed()
        else:
            goal_handle.abort()
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
