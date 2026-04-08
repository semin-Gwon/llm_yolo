import json
import math
import threading
import time
from pathlib import Path

import rclpy
import yaml
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped, Twist
from nav2_msgs.action import NavigateToPose as Nav2NavigateToPose
from nav_msgs.msg import Odometry
from rclpy.action import ActionClient, ActionServer
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.time import Time
from std_msgs.msg import Bool, String
from tf2_ros import Buffer, TransformException, TransformListener

from llm_yolo_interfaces.action import NavigateToPose


class NavigateToPoseServer(Node):
    def __init__(self):
        super().__init__('navigate_to_pose_server')
        self.declare_parameter('navigation_mode', 'direct')
        self.declare_parameter('cmd_vel_topic', '/cmd_vel')
        self.declare_parameter('odom_topic', '/odom')
        self.declare_parameter('named_place_pose_topic', '/sim/named_place_poses')
        self.declare_parameter('control_rate_hz', 10.0)
        self.declare_parameter('linear_speed_mps', 0.35)
        self.declare_parameter('angular_speed_rps', 0.8)
        self.declare_parameter('yaw_gain', 1.5)
        self.declare_parameter('heading_tolerance_rad', 0.2)
        self.declare_parameter('named_places_file', '/home/jnu/llm_yolo/configs/sim/sim_named_places.yaml')
        self.declare_parameter('default_goal_radius_m', 0.5)
        self.declare_parameter('default_goal_yaw_rad', 0.0)
        self.declare_parameter('action_name', '/llm_navigate_to_pose')
        self.declare_parameter('nav2_action_name', '/navigate_to_pose')
        self.declare_parameter('global_frame', 'map')
        self.declare_parameter('nav2_server_wait_sec', 5.0)
        self.declare_parameter('speed_scale_slow', 0.6)
        self.declare_parameter('speed_scale_normal', 1.0)
        self.declare_parameter('speed_scale_fast', 1.25)
        self.declare_parameter('person_pause_enabled', True)
        self.declare_parameter('person_visible_objects_topic', '/perception/visible_objects')
        self.declare_parameter('person_object_pose_topic', '/perception/object_poses')
        self.declare_parameter('person_target_class', 'person')
        self.declare_parameter('person_pause_distance_m', 1.5)
        self.declare_parameter('person_pause_trigger_count', 1)
        self.declare_parameter('person_pause_clear_count', 2)

        self.callback_group = ReentrantCallbackGroup()
        self.cmd_vel_pub = self.create_publisher(
            Twist,
            self.get_parameter('cmd_vel_topic').value,
            10,
        )
        self.odom_sub = self.create_subscription(
            Odometry,
            self.get_parameter('odom_topic').value,
            self.on_odom,
            10,
            callback_group=self.callback_group,
        )
        self.named_place_pose_sub = self.create_subscription(
            String,
            self.get_parameter('named_place_pose_topic').value,
            self.on_named_place_poses,
            10,
            callback_group=self.callback_group,
        )
        self.emergency_stop_sub = self.create_subscription(
            Bool,
            '/emergency_stop',
            self.on_emergency_stop,
            10,
            callback_group=self.callback_group,
        )
        self.emergency_clear_sub = self.create_subscription(
            Bool,
            '/emergency_clear',
            self.on_emergency_clear,
            10,
            callback_group=self.callback_group,
        )
        self.visible_objects_sub = self.create_subscription(
            String,
            self.get_parameter('person_visible_objects_topic').value,
            self.on_visible_objects,
            10,
            callback_group=self.callback_group,
        )
        self.person_object_pose_sub = self.create_subscription(
            String,
            self.get_parameter('person_object_pose_topic').value,
            self.on_object_poses,
            10,
            callback_group=self.callback_group,
        )
        self.server = ActionServer(
            self,
            NavigateToPose,
            self.get_parameter('action_name').value,
            self.execute,
            callback_group=self.callback_group,
        )
        self.nav2_client = ActionClient(
            self,
            Nav2NavigateToPose,
            self.get_parameter('nav2_action_name').value,
            callback_group=self.callback_group,
        )
        self.named_places = self.load_named_places(self.get_parameter('named_places_file').value)
        self.named_place_overrides = {}
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.current_pose = None
        self.emergency_stop_active = False
        self.person_visible = False
        self.person_candidates = []
        self.person_pause_active = False
        self.person_detect_streak = 0
        self.person_clear_streak = 0

    def load_named_places(self, path_text: str):
        data = yaml.safe_load(Path(path_text).read_text()) or {}
        return data.get('named_places', {})

    def on_named_place_poses(self, msg: String):
        try:
            data = json.loads(msg.data) if msg.data else {}
        except Exception as exc:
            self.get_logger().warning(f'named place pose parse failed: {exc}')
            return
        if isinstance(data, dict):
            self.named_place_overrides = data

    def on_odom(self, msg: Odometry):
        position = msg.pose.pose.position
        orientation = msg.pose.pose.orientation
        yaw = math.atan2(
            2.0 * (orientation.w * orientation.z + orientation.x * orientation.y),
            1.0 - 2.0 * (orientation.y * orientation.y + orientation.z * orientation.z),
        )
        self.current_pose = (position.x, position.y, yaw)

    def on_emergency_stop(self, msg: Bool):
        if not bool(msg.data):
            return
        self.emergency_stop_active = True
        self.stop_robot()

    def on_emergency_clear(self, msg: Bool):
        if not bool(msg.data):
            return
        self.emergency_stop_active = False

    def on_visible_objects(self, msg: String):
        target_class = str(self.get_parameter('person_target_class').value).strip()
        names = {item.strip() for item in msg.data.split(',') if item.strip()}
        visible_now = bool(target_class) and target_class in names
        visible_for_pause = self.person_visible_for_pause(visible_now)
        self.person_visible = visible_for_pause
        if visible_for_pause:
            self.person_detect_streak += 1
            self.person_clear_streak = 0
        else:
            self.person_clear_streak += 1
            self.person_detect_streak = 0

        trigger_count = max(1, int(self.get_parameter('person_pause_trigger_count').value))
        clear_count = max(1, int(self.get_parameter('person_pause_clear_count').value))
        if self.person_detect_streak >= trigger_count:
            self.person_pause_active = True
        elif self.person_clear_streak >= clear_count:
            self.person_pause_active = False

    def on_object_poses(self, msg: String):
        target_class = str(self.get_parameter('person_target_class').value).strip()
        try:
            payload = json.loads(msg.data) if msg.data else {}
        except Exception:
            self.person_candidates = []
            return
        candidates = []
        objects = payload.get('objects', [])
        if isinstance(objects, list):
            for item in objects:
                try:
                    if str(item.get('class_name', '')).strip() != target_class:
                        continue
                    candidates.append({
                        'x_m': float(item['x_m']),
                        'y_m': float(item['y_m']),
                        'z_m': float(item.get('z_m', 0.0)),
                    })
                except Exception:
                    continue
        self.person_candidates = candidates

    def current_pose_in_global(self):
        target_frame = str(self.get_parameter('global_frame').value)
        try:
            transform = self.tf_buffer.lookup_transform(target_frame, 'base_link', Time())
            t = transform.transform.translation
            q = transform.transform.rotation
            yaw = math.atan2(
                2.0 * (q.w * q.z + q.x * q.y),
                1.0 - 2.0 * (q.y * q.y + q.z * q.z),
            )
            return (float(t.x), float(t.y), float(yaw))
        except TransformException:
            return self.current_pose

    def person_visible_for_pause(self, visible_now: bool) -> bool:
        if not visible_now:
            return False
        if not self.person_candidates:
            return True
        pose = self.current_pose_in_global()
        if pose is None:
            return True
        robot_x, robot_y, _ = pose
        min_distance = min(
            math.hypot(float(item.get('x_m', 0.0)) - robot_x, float(item.get('y_m', 0.0)) - robot_y)
            for item in self.person_candidates
        )
        return min_distance <= float(self.get_parameter('person_pause_distance_m').value)

    def resolve_speed_scale(self, speed_hint: str) -> float:
        hint = str(speed_hint or 'normal').strip().lower()
        if hint == 'slow':
            return float(self.get_parameter('speed_scale_slow').value)
        if hint == 'fast':
            return float(self.get_parameter('speed_scale_fast').value)
        return float(self.get_parameter('speed_scale_normal').value)

    def stop_robot(self):
        self.cmd_vel_pub.publish(Twist())

    def person_pause_enabled_for_target(self, target_name: str) -> bool:
        if not bool(self.get_parameter('person_pause_enabled').value):
            return False
        normalized = str(target_name or '').strip().lower()
        if normalized.startswith('approach:'):
            normalized = normalized.split(':', 1)[1].strip()
        person_target = str(self.get_parameter('person_target_class').value).strip().lower()
        return bool(person_target) and normalized != person_target

    def wait_while_person_blocked(self, goal_handle, target_name: str, deadline: float, result):
        if not self.person_pause_enabled_for_target(target_name):
            return None
        pause_logged = False
        while rclpy.ok() and self.person_pause_active:
            if not pause_logged:
                self.get_logger().info(f'person pause engaged: {target_name}')
                pause_logged = True
            self.stop_robot()
            if self.emergency_stop_active:
                goal_handle.abort()
                result.success = False
                result.outcome = f'emergency_stop:{target_name}'
                return result
            if goal_handle.is_cancel_requested:
                goal_handle.canceled()
                result.success = False
                result.outcome = f'canceled:{target_name}'
                return result
            if time.time() > deadline:
                goal_handle.abort()
                result.success = False
                result.outcome = f'timeout:{target_name}'
                return result
            time.sleep(0.05)
        if pause_logged:
            self.get_logger().info(f'person pause cleared: {target_name}')
        return None

    def wrap_angle(self, angle: float) -> float:
        return math.atan2(math.sin(angle), math.cos(angle))

    def resolve_target(self, target_name: str):
        target = dict(self.named_places.get(target_name, {}))
        override = self.named_place_overrides.get(target_name)
        if override is not None:
            target.update(override)
        return target or None

    def resolve_request_target(self, request):
        if bool(request.use_pose):
            return {
                'x_m': float(request.x_m),
                'y_m': float(request.y_m),
                'yaw_rad': float(request.desired_yaw_rad),
                'radius_m': float(self.get_parameter('default_goal_radius_m').value),
            }
        return self.resolve_target(request.target_name)

    def yaw_to_quaternion(self, yaw: float):
        half = 0.5 * yaw
        return (0.0, 0.0, math.sin(half), math.cos(half))

    def cancel_nav2_goal(self, nav2_goal_handle):
        if nav2_goal_handle is None:
            return
        try:
            nav2_goal_handle.cancel_goal_async()
        except Exception as exc:
            self.get_logger().warning(f'nav2 cancel failed: {exc}')

    def execute_direct(self, goal_handle, target_name: str, target: dict):
        result = NavigateToPose.Result()
        timeout_sec = float(goal_handle.request.timeout_sec or 30)
        deadline = time.time() + timeout_sec
        control_period = 1.0 / float(self.get_parameter('control_rate_hz').value)
        speed_scale = self.resolve_speed_scale(goal_handle.request.speed_hint)
        linear_speed = float(self.get_parameter('linear_speed_mps').value) * speed_scale
        angular_speed = float(self.get_parameter('angular_speed_rps').value) * speed_scale
        yaw_gain = float(self.get_parameter('yaw_gain').value)
        heading_tolerance = float(self.get_parameter('heading_tolerance_rad').value)
        goal_x = float(target.get('x_m', 0.0))
        goal_y = float(target.get('y_m', 0.0))
        goal_radius = float(target.get('radius_m', self.get_parameter('default_goal_radius_m').value))
        requested_yaw = float(goal_handle.request.desired_yaw_rad)
        desired_yaw = float(
            requested_yaw if abs(requested_yaw) > 1e-6 else target.get('yaw_rad', self.get_parameter('default_goal_yaw_rad').value)
        )

        while rclpy.ok():
            if self.emergency_stop_active:
                self.stop_robot()
                goal_handle.abort()
                result.success = False
                result.outcome = f'emergency_stop:{target_name}'
                return result

            blocked = self.wait_while_person_blocked(goal_handle, target_name, deadline, result)
            if blocked is not None:
                return blocked

            if goal_handle.is_cancel_requested:
                self.stop_robot()
                goal_handle.canceled()
                result.success = False
                result.outcome = f'canceled:{target_name}'
                return result

            if self.current_pose is None:
                if time.time() > deadline:
                    break
                self.stop_robot()
                time.sleep(control_period)
                continue

            current_x, current_y, current_yaw = self.current_pose
            dx = goal_x - current_x
            dy = goal_y - current_y
            distance = math.hypot(dx, dy)
            heading = math.atan2(dy, dx)
            heading_error = self.wrap_angle(heading - current_yaw)
            yaw_error = self.wrap_angle(desired_yaw - current_yaw)

            if distance <= goal_radius and abs(yaw_error) <= heading_tolerance:
                self.stop_robot()
                goal_handle.succeed()
                result.success = True
                result.outcome = f'arrived:{target_name}'
                return result

            if time.time() > deadline:
                break

            cmd = Twist()
            if distance > goal_radius:
                cmd.angular.z = max(-angular_speed, min(angular_speed, yaw_gain * heading_error))
                if abs(heading_error) < 0.5:
                    cmd.linear.x = min(linear_speed, distance)
            else:
                cmd.angular.z = max(-angular_speed, min(angular_speed, yaw_gain * yaw_error))
            self.cmd_vel_pub.publish(cmd)
            time.sleep(control_period)

        self.stop_robot()
        goal_handle.abort()
        result.success = False
        result.outcome = f'timeout:{target_name}'
        return result

    def execute_nav2(self, goal_handle, target_name: str, target: dict):
        result = NavigateToPose.Result()
        wait_sec = float(self.get_parameter('nav2_server_wait_sec').value)
        if not self.nav2_client.wait_for_server(timeout_sec=wait_sec):
            goal_handle.abort()
            result.success = False
            result.outcome = f'nav2_unavailable:{target_name}'
            return result

        requested_yaw = float(goal_handle.request.desired_yaw_rad)
        desired_yaw = float(
            requested_yaw if abs(requested_yaw) > 1e-6 else target.get('yaw_rad', self.get_parameter('default_goal_yaw_rad').value)
        )
        qx, qy, qz, qw = self.yaw_to_quaternion(desired_yaw)
        deadline = time.time() + float(goal_handle.request.timeout_sec or 30)
        nav2_goal_handle = None
        nav2_result_future = None
        paused_by_person = False

        while rclpy.ok():
            blocked = self.wait_while_person_blocked(goal_handle, target_name, deadline, result)
            if blocked is not None:
                if nav2_goal_handle is not None:
                    self.cancel_nav2_goal(nav2_goal_handle)
                return blocked

            if nav2_goal_handle is None:
                nav_goal = Nav2NavigateToPose.Goal()
                nav_goal.pose = PoseStamped()
                nav_goal.pose.header.frame_id = str(self.get_parameter('global_frame').value)
                nav_goal.pose.header.stamp = self.get_clock().now().to_msg()
                nav_goal.pose.pose.position.x = float(target.get('x_m', 0.0))
                nav_goal.pose.pose.position.y = float(target.get('y_m', 0.0))
                nav_goal.pose.pose.orientation.x = qx
                nav_goal.pose.pose.orientation.y = qy
                nav_goal.pose.pose.orientation.z = qz
                nav_goal.pose.pose.orientation.w = qw

                goal_response = {'handle': None, 'error': None}
                goal_event = threading.Event()

                def on_goal_response(fut):
                    try:
                        goal_response['handle'] = fut.result()
                    except Exception as exc:
                        goal_response['error'] = exc
                    finally:
                        goal_event.set()

                send_future = self.nav2_client.send_goal_async(nav_goal)
                send_future.add_done_callback(on_goal_response)

                while rclpy.ok() and not goal_event.is_set():
                    blocked = self.wait_while_person_blocked(goal_handle, target_name, deadline, result)
                    if blocked is not None:
                        return blocked
                    if self.emergency_stop_active:
                        self.stop_robot()
                        goal_handle.abort()
                        result.success = False
                        result.outcome = f'emergency_stop:{target_name}'
                        return result
                    if goal_handle.is_cancel_requested:
                        goal_handle.canceled()
                        result.success = False
                        result.outcome = f'canceled:{target_name}'
                        return result
                    if time.time() > deadline:
                        goal_handle.abort()
                        result.success = False
                        result.outcome = f'timeout:{target_name}'
                        return result
                    time.sleep(0.05)

                if goal_response['error'] is not None:
                    goal_handle.abort()
                    result.success = False
                    result.outcome = f'nav2_send_failed:{target_name}'
                    return result

                nav2_goal_handle = goal_response['handle']
                if nav2_goal_handle is None or not nav2_goal_handle.accepted:
                    goal_handle.abort()
                    result.success = False
                    result.outcome = f'nav2_rejected:{target_name}'
                    return result
                nav2_result_future = nav2_goal_handle.get_result_async()
                paused_by_person = False

            if self.person_pause_enabled_for_target(target_name) and self.person_pause_active:
                self.cancel_nav2_goal(nav2_goal_handle)
                self.stop_robot()
                nav2_goal_handle = None
                nav2_result_future = None
                paused_by_person = True
                continue

            if self.emergency_stop_active:
                self.cancel_nav2_goal(nav2_goal_handle)
                self.stop_robot()
                goal_handle.abort()
                result.success = False
                result.outcome = f'emergency_stop:{target_name}'
                return result
            if goal_handle.is_cancel_requested:
                self.cancel_nav2_goal(nav2_goal_handle)
                goal_handle.canceled()
                result.success = False
                result.outcome = f'canceled:{target_name}'
                return result
            if time.time() > deadline:
                self.cancel_nav2_goal(nav2_goal_handle)
                goal_handle.abort()
                result.success = False
                result.outcome = f'timeout:{target_name}'
                return result
            if nav2_result_future is None or not nav2_result_future.done():
                time.sleep(0.05)
                continue

            wrapped = nav2_result_future.result()
            status = int(wrapped.status)
            nav2_result = wrapped.result
            error_code = getattr(nav2_result, 'error_code', 0)
            error_msg = getattr(nav2_result, 'error_msg', '')

            if status == GoalStatus.STATUS_SUCCEEDED:
                goal_handle.succeed()
                result.success = True
                result.outcome = f'arrived:{target_name}'
                return result
            if status == GoalStatus.STATUS_CANCELED and paused_by_person:
                nav2_goal_handle = None
                nav2_result_future = None
                continue
            if status == GoalStatus.STATUS_CANCELED:
                goal_handle.canceled()
                result.success = False
                result.outcome = f'canceled:{target_name}'
                return result

            goal_handle.abort()
            suffix = f':{error_code}'
            if error_msg:
                suffix += f':{error_msg}'
            result.success = False
            result.outcome = f'nav2_failed:{target_name}{suffix}'
            return result

    def execute(self, goal_handle):
        target_name = goal_handle.request.target_name
        target = self.resolve_request_target(goal_handle.request)
        result = NavigateToPose.Result()
        if target is None:
            goal_handle.abort()
            result.success = False
            result.outcome = f'unknown_target:{target_name}'
            return result

        if 'x_m' not in target or 'y_m' not in target:
            goal_handle.abort()
            result.success = False
            result.outcome = f'unresolved_target:{target_name}'
            return result

        if self.emergency_stop_active:
            goal_handle.abort()
            result.success = False
            result.outcome = f'emergency_stop:{target_name}'
            return result

        mode = str(self.get_parameter('navigation_mode').value).strip().lower()
        if mode == 'nav2':
            return self.execute_nav2(goal_handle, target_name, target)
        return self.execute_direct(goal_handle, target_name, target)


def main(args=None):
    rclpy.init(args=args)
    node = NavigateToPoseServer()
    try:
        executor = MultiThreadedExecutor()
        executor.add_node(node)
        executor.spin()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
