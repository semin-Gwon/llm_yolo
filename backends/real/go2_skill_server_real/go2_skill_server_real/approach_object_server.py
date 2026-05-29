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
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool
from std_msgs.msg import String

from llm_yolo_interfaces.action import ApproachObject


ROBOT_SPORT_API_ID_BALANCESTAND = 1002
ROBOT_SPORT_API_ID_STOPMOVE = 1003
ROBOT_SPORT_API_ID_MOVE = 1008


class ApproachObjectServer(Node):
    def __init__(self):
        super().__init__('approach_object_server')
        self.declare_parameter('object_pose_topic', '/perception/object_poses')
        self.declare_parameter('debug_topic', '/approach_object/debug')
        self.declare_parameter('command_output_mode', 'sport_request')
        self.declare_parameter('control_request_topic', '/api/sport/request')
        self.declare_parameter('cmd_vel_topic', '/cmd_vel')
        self.declare_parameter('object_pose_frame', 'camera_link')
        self.declare_parameter('default_approach_distance_m', 0.5)
        self.declare_parameter('min_approach_distance_m', 0.6)
        self.declare_parameter('max_approach_distance_m', 0.8)
        self.declare_parameter('heading_align_threshold_rad', 0.25)
        self.declare_parameter('heading_stop_threshold_rad', 0.6)
        self.declare_parameter('max_linear_speed_mps', 0.2)
        self.declare_parameter('min_linear_speed_mps', 0.0)
        self.declare_parameter('max_angular_speed_radps', 0.4)
        self.declare_parameter('near_distance_slowdown_m', 1.5)
        self.declare_parameter('near_max_linear_speed_mps', 0.12)
        self.declare_parameter('near_yaw_deadband_rad', 0.18)
        self.declare_parameter('lateral_deadband_m', 0.18)
        self.declare_parameter('linear_gain', 0.6)
        self.declare_parameter('angular_gain', 1.2)
        self.declare_parameter('control_period_sec', 0.1)
        self.declare_parameter('stale_pose_timeout_sec', 1.0)
        self.declare_parameter('target_hold_timeout_sec', 1.5)
        self.declare_parameter('lost_target_arrival_margin_m', 0.25)
        self.declare_parameter('min_tracking_confidence', 0.2)
        self.declare_parameter('lock_reacquire_radius_m', 0.75)
        self.declare_parameter('min_initial_lock_distance_m', 0.35)
        self.declare_parameter('use_odom_target_lock', False)
        self.declare_parameter('robot_odom_topic', '/utlidar/robot_odom')
        self.declare_parameter('odom_stale_timeout_sec', 0.5)
        self.declare_parameter('odom_target_update_radius_m', 0.75)
        self.declare_parameter('odom_target_refresh_while_visible', False)
        self.declare_parameter('send_balance_stand_on_start', True)
        self.declare_parameter('emergency_stop_topic', '/emergency_stop')
        self.declare_parameter('emergency_clear_topic', '/emergency_clear')
        self.declare_parameter('emergency_stop_repeat_count', 5)

        self.callback_group = ReentrantCallbackGroup()
        self.object_poses: dict[str, list[dict[str, Any]]] = {}
        self.object_pose_frame = str(self.get_parameter('object_pose_frame').value)
        self.last_pose_update_time = 0.0
        self.last_selected_targets: dict[str, dict[str, Any]] = {}
        self.locked_targets: dict[str, dict[str, Any]] = {}
        self.odom_targets: dict[str, dict[str, Any]] = {}
        self.robot_odom: dict[str, float] | None = None
        self.last_odom_update_time = 0.0
        self.emergency_stop_active = False

        self.request_msg_cls = self._load_request_cls()
        self.command_output_mode = self._normalize_output_mode(
            str(self.get_parameter('command_output_mode').value)
        )
        self.debug_pub = self.create_publisher(
            String,
            str(self.get_parameter('debug_topic').value),
            10,
        )
        self.request_pub = (
            self.create_publisher(
                self.request_msg_cls,
                str(self.get_parameter('control_request_topic').value),
                10,
            )
            if self.request_msg_cls is not None
            else None
        )
        self.cmd_vel_pub = self.create_publisher(
            Twist,
            str(self.get_parameter('cmd_vel_topic').value),
            10,
        )

        self.create_subscription(
            String,
            str(self.get_parameter('object_pose_topic').value),
            self.on_object_poses,
            10,
            callback_group=self.callback_group,
        )
        self.create_subscription(
            Odometry,
            str(self.get_parameter('robot_odom_topic').value),
            self.on_robot_odom,
            20,
            callback_group=self.callback_group,
        )
        self.create_subscription(
            Bool,
            str(self.get_parameter('emergency_stop_topic').value),
            self.on_emergency_stop,
            10,
            callback_group=self.callback_group,
        )
        self.create_subscription(
            Bool,
            str(self.get_parameter('emergency_clear_topic').value),
            self.on_emergency_clear,
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

    def _normalize_output_mode(self, mode: str) -> str:
        normalized = str(mode or '').strip().lower()
        if normalized in ('cmd_vel', 'twist'):
            return 'cmd_vel'
        if normalized not in ('sport_request', 'sport'):
            self.get_logger().warning(
                f'unknown command_output_mode={mode!r}; falling back to sport_request'
            )
        return 'sport_request'

    def on_emergency_stop(self, msg: Bool):
        if not bool(msg.data):
            return
        self.emergency_stop_active = True
        self._publish_stop_burst()
        self.get_logger().warning('emergency_stop active: StopMove requested')

    def on_emergency_clear(self, msg: Bool):
        if not bool(msg.data):
            return
        self.emergency_stop_active = False
        self.get_logger().info('emergency_stop cleared')

    def on_robot_odom(self, msg: Odometry):
        pose = msg.pose.pose
        yaw = self._yaw_from_quaternion(
            float(pose.orientation.x),
            float(pose.orientation.y),
            float(pose.orientation.z),
            float(pose.orientation.w),
        )
        self.robot_odom = {
            'x': float(pose.position.x),
            'y': float(pose.position.y),
            'z': float(pose.position.z),
            'yaw': yaw,
        }
        self.last_odom_update_time = time.time()

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
                        'bbox_area_norm': float(item.get('bbox_area_norm', 0.0)),
                        'bbox_center_x_norm': float(item.get('bbox_center_x_norm', 0.5)),
                    })
                except Exception:
                    continue
        self.object_poses = grouped
        self.last_pose_update_time = time.time()

    def _candidate_distance(self, item: dict[str, Any]) -> float:
        return math.hypot(float(item.get('x_m', 0.0)), float(item.get('y_m', 0.0)))

    def _yaw_from_quaternion(self, x: float, y: float, z: float, w: float) -> float:
        siny_cosp = 2.0 * (w * z + x * y)
        cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
        return math.atan2(siny_cosp, cosy_cosp)

    def _odom_is_fresh(self) -> bool:
        if self.robot_odom is None:
            return False
        timeout_sec = float(self.get_parameter('odom_stale_timeout_sec').value)
        return time.time() - self.last_odom_update_time <= timeout_sec

    def _camera_target_to_odom(self, item: dict[str, Any]) -> dict[str, float] | None:
        if not self._odom_is_fresh() or self.robot_odom is None:
            return None
        object_x = float(item.get('x_m', 0.0))
        object_y = float(item.get('y_m', 0.0))
        yaw = float(self.robot_odom['yaw'])
        cos_yaw = math.cos(yaw)
        sin_yaw = math.sin(yaw)
        return {
            'x': float(self.robot_odom['x']) + cos_yaw * object_x - sin_yaw * object_y,
            'y': float(self.robot_odom['y']) + sin_yaw * object_x + cos_yaw * object_y,
            'time': time.time(),
            'source_distance_m': math.hypot(object_x, object_y),
        }

    def _odom_target_to_robot(self, target_class: str) -> dict[str, float] | None:
        target = self.odom_targets.get(target_class)
        if target is None or not self._odom_is_fresh() or self.robot_odom is None:
            return None
        dx = float(target['x']) - float(self.robot_odom['x'])
        dy = float(target['y']) - float(self.robot_odom['y'])
        yaw = float(self.robot_odom['yaw'])
        cos_yaw = math.cos(yaw)
        sin_yaw = math.sin(yaw)
        return {
            'x_m': cos_yaw * dx + sin_yaw * dy,
            'y_m': -sin_yaw * dx + cos_yaw * dy,
            'z_m': 0.0,
            'confidence': 0.0,
            '_odom_fallback': True,
        }

    def _maybe_update_odom_target(self, target_class: str, selected: dict[str, Any], force: bool = False):
        if not bool(self.get_parameter('use_odom_target_lock').value):
            return
        target = self._camera_target_to_odom(selected)
        if target is None:
            return
        previous = self.odom_targets.get(target_class)
        if previous is not None and not force and not bool(self.get_parameter('odom_target_refresh_while_visible').value):
            return
        if previous is not None and not force:
            update_radius = float(self.get_parameter('odom_target_update_radius_m').value)
            drift = math.hypot(float(target['x']) - float(previous['x']), float(target['y']) - float(previous['y']))
            if drift > update_radius:
                return
        self.odom_targets[target_class] = target

    def _initial_lock_score(self, item: dict[str, Any]) -> float:
        confidence = float(item.get('confidence', 0.0))
        area = float(item.get('bbox_area_norm', 0.0))
        center_x = float(item.get('bbox_center_x_norm', 0.5))
        center_score = 1.0 - min(1.0, abs(center_x - 0.5) * 2.0)
        lateral_penalty = min(1.0, abs(float(item.get('y_m', 0.0))))
        return confidence * 2.0 + area * 4.0 + center_score * 1.5 - lateral_penalty * 0.4

    def _select_object(self, target_class: str, object_selector: str = ''):
        min_confidence = float(self.get_parameter('min_tracking_confidence').value)
        hold_timeout_sec = float(self.get_parameter('target_hold_timeout_sec').value)
        reacquire_radius_m = float(self.get_parameter('lock_reacquire_radius_m').value)
        min_initial_distance = float(self.get_parameter('min_initial_lock_distance_m').value)
        candidates = [
            item for item in self.object_poses.get(target_class, [])
            if float(item.get('confidence', 0.0)) >= min_confidence
        ]
        selector = str(object_selector or '').strip().lower()
        key_fn = self._candidate_distance
        locked = self.locked_targets.get(target_class)

        if locked is not None and candidates:
            lx = float(locked.get('x_m', 0.0))
            ly = float(locked.get('y_m', 0.0))
            lz = float(locked.get('z_m', 0.0))

            def lock_distance(item):
                dx = float(item.get('x_m', 0.0)) - lx
                dy = float(item.get('y_m', 0.0)) - ly
                dz = float(item.get('z_m', 0.0)) - lz
                return math.sqrt(dx * dx + dy * dy + dz * dz)

            near_locked = [item for item in candidates if lock_distance(item) <= reacquire_radius_m]
            if near_locked:
                selected = min(near_locked, key=lock_distance)
                self.locked_targets[target_class] = dict(selected)
                self.last_selected_targets[target_class] = {
                    'object': dict(selected),
                    'time': time.time(),
                }
                return selected

            previous = self.last_selected_targets.get(target_class)
            if previous is not None and time.time() - float(previous.get('time', 0.0)) <= hold_timeout_sec:
                held = dict(previous.get('object', {}))
                held['_held'] = True
                return held
            if selector == 'far':
                selected = max(candidates, key=key_fn)
            elif selector in ('best', 'score'):
                selected = max(candidates, key=self._initial_lock_score)
            else:
                selected = min(candidates, key=key_fn)
            self.locked_targets[target_class] = dict(selected)
            self.last_selected_targets[target_class] = {
                'object': dict(selected),
                'time': time.time(),
            }
            self.get_logger().warning(
                'relocked visible target %s selector=%s dist=%.2f x=%.2f y=%.2f conf=%.2f'
                % (
                    target_class,
                    selector or 'near',
                    self._candidate_distance(selected),
                    float(selected.get('x_m', 0.0)),
                    float(selected.get('y_m', 0.0)),
                    float(selected.get('confidence', 0.0)),
                )
            )
            return selected

        if candidates:
            initial_candidates = [
                item for item in candidates
                if self._candidate_distance(item) >= min_initial_distance
            ] or candidates
            if selector == 'far':
                selected = max(initial_candidates, key=key_fn)
            elif selector in ('best', 'score'):
                selected = max(initial_candidates, key=self._initial_lock_score)
            else:
                selected = min(initial_candidates, key=key_fn)
            self.locked_targets[target_class] = dict(selected)
            self.last_selected_targets[target_class] = {
                'object': dict(selected),
                'time': time.time(),
            }
            self.get_logger().info(
                'locked target %s selector=%s dist=%.2f x=%.2f y=%.2f conf=%.2f score=%.2f'
                % (
                    target_class,
                    selector or 'near',
                    self._candidate_distance(selected),
                    float(selected.get('x_m', 0.0)),
                    float(selected.get('y_m', 0.0)),
                    float(selected.get('confidence', 0.0)),
                    self._initial_lock_score(selected),
                )
            )
            return selected

        previous = self.last_selected_targets.get(target_class)
        if previous is None:
            return None
        if time.time() - float(previous.get('time', 0.0)) > hold_timeout_sec:
            return None
        held = dict(previous.get('object', {}))
        held['_held'] = True
        return held

    def _build_request(self, api_id: int, parameter: dict[str, Any] | None = None):
        if self.request_msg_cls is None:
            return None
        req = self.request_msg_cls()
        req.header.identity.api_id = int(api_id)
        req.parameter = json.dumps(parameter or {})
        req.binary = []
        return req

    def _publish_sport_balance_stand(self):
        if self.request_pub is None:
            return
        req = self._build_request(ROBOT_SPORT_API_ID_BALANCESTAND)
        if req is not None:
            self.request_pub.publish(req)

    def _publish_sport_stop(self):
        if self.request_pub is None:
            return
        req = self._build_request(ROBOT_SPORT_API_ID_STOPMOVE)
        if req is not None:
            self.request_pub.publish(req)

    def _publish_sport_move(self, vx: float, vyaw: float):
        if self.request_pub is None:
            return
        req = self._build_request(
            ROBOT_SPORT_API_ID_MOVE,
            {'x': float(vx), 'y': 0.0, 'z': float(vyaw)},
        )
        if req is not None:
            self.request_pub.publish(req)

    def _publish_cmd_vel(self, vx: float, vyaw: float):
        msg = Twist()
        msg.linear.x = float(vx)
        msg.angular.z = float(vyaw)
        self.cmd_vel_pub.publish(msg)

    def _publish_balance_stand(self):
        if self.command_output_mode == 'sport_request':
            self._publish_sport_balance_stand()

    def _publish_stop(self):
        if self.command_output_mode == 'cmd_vel':
            self._publish_cmd_vel(0.0, 0.0)
            return
        self._publish_sport_stop()

    def _publish_stop_burst(self):
        repeat_count = max(1, int(self.get_parameter('emergency_stop_repeat_count').value))
        for _ in range(repeat_count):
            self._publish_cmd_vel(0.0, 0.0)
            self._publish_sport_stop()
            time.sleep(0.02)

    def _publish_velocity(self, vx: float, vyaw: float):
        if self.command_output_mode == 'cmd_vel':
            self._publish_cmd_vel(vx, vyaw)
            return
        self._publish_sport_move(vx, vyaw)

    def _publish_debug(self, payload: dict[str, Any]):
        msg = String()
        msg.data = json.dumps(payload, ensure_ascii=False)
        self.debug_pub.publish(msg)

    def _clamp(self, value: float, min_value: float, max_value: float) -> float:
        return max(min_value, min(max_value, value))

    def _safe_approach_distance_m(self, requested_distance_m: float) -> float:
        default_distance = float(self.get_parameter('default_approach_distance_m').value)
        min_distance = float(self.get_parameter('min_approach_distance_m').value)
        max_distance = float(self.get_parameter('max_approach_distance_m').value)
        requested = float(requested_distance_m) if float(requested_distance_m) > 0.0 else default_distance
        return self._clamp(requested, min_distance, max_distance)

    def execute(self, goal_handle):
        result = ApproachObject.Result()
        target_class = str(goal_handle.request.target_class).strip()
        object_selector = str(goal_handle.request.object_selector).strip().lower()
        approach_distance_m = self._safe_approach_distance_m(goal_handle.request.approach_distance_m)
        timeout_sec = int(goal_handle.request.timeout_sec or 30)
        deadline = time.time() + float(timeout_sec)

        if self.command_output_mode == 'sport_request' and self.request_pub is None:
            goal_handle.abort()
            result.success = False
            result.outcome = 'unitree_request_message_unavailable'
            return result

        if self.emergency_stop_active:
            self._publish_stop_burst()
            goal_handle.abort()
            result.success = False
            result.outcome = f'emergency_stop_active:{target_class}'
            return result

        if bool(self.get_parameter('send_balance_stand_on_start').value):
            self._publish_balance_stand()
            time.sleep(0.1)

        control_period = float(self.get_parameter('control_period_sec').value)
        stale_timeout_sec = float(self.get_parameter('stale_pose_timeout_sec').value)
        align_threshold = float(self.get_parameter('heading_align_threshold_rad').value)
        stop_threshold = float(self.get_parameter('heading_stop_threshold_rad').value)
        max_linear = float(self.get_parameter('max_linear_speed_mps').value)
        min_linear = float(self.get_parameter('min_linear_speed_mps').value)
        max_angular = float(self.get_parameter('max_angular_speed_radps').value)
        near_distance_slowdown = float(self.get_parameter('near_distance_slowdown_m').value)
        near_max_linear = float(self.get_parameter('near_max_linear_speed_mps').value)
        near_yaw_deadband = float(self.get_parameter('near_yaw_deadband_rad').value)
        lateral_deadband = float(self.get_parameter('lateral_deadband_m').value)
        linear_gain = float(self.get_parameter('linear_gain').value)
        angular_gain = float(self.get_parameter('angular_gain').value)
        lost_target_arrival_margin = float(self.get_parameter('lost_target_arrival_margin_m').value)

        self.last_selected_targets.pop(target_class, None)
        self.locked_targets.pop(target_class, None)
        self.odom_targets.pop(target_class, None)
        selected = None
        while rclpy.ok():
            now = time.time()
            if self.emergency_stop_active:
                self._publish_stop_burst()
                goal_handle.abort()
                result.success = False
                result.outcome = f'emergency_stop:{target_class}'
                return result

            if now >= deadline:
                self._publish_stop()
                self._publish_debug({
                    'target_class': target_class,
                    'control_source': 'timeout',
                    'outcome': f'timeout:{target_class}',
                    'approach_distance_m': approach_distance_m,
                    'odom_available': self._odom_is_fresh(),
                    'odom_target_active': target_class in self.odom_targets,
                })
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

            odom_fallback = None
            if bool(self.get_parameter('use_odom_target_lock').value):
                odom_fallback = self._odom_target_to_robot(target_class)

            last_target = self.last_selected_targets.get(target_class)
            last_object = dict(last_target.get('object', {})) if last_target is not None else None
            last_distance = self._candidate_distance(last_object) if last_object is not None else None
            if (
                now - self.last_pose_update_time > stale_timeout_sec
                and odom_fallback is None
                and last_distance is not None
                and last_distance <= approach_distance_m + lost_target_arrival_margin
            ):
                self._publish_stop()
                self._publish_debug({
                    'target_class': target_class,
                    'control_source': 'lost_target_near_stop',
                    'outcome': f'arrived:approach:{target_class}',
                    'distance_m': last_distance,
                    'distance_error_m': last_distance - approach_distance_m,
                    'approach_distance_m': approach_distance_m,
                    'lost_target_arrival_margin_m': lost_target_arrival_margin,
                    'target_x_m': float(last_object.get('x_m', 0.0)),
                    'target_y_m': float(last_object.get('y_m', 0.0)),
                    'commanded_linear_mps': 0.0,
                    'commanded_yaw_radps': 0.0,
                    'odom_available': self._odom_is_fresh(),
                    'odom_target_active': target_class in self.odom_targets,
                })
                result.success = True
                result.outcome = f'arrived:approach:{target_class}'
                result.object_x_m = float(last_object.get('x_m', 0.0))
                result.object_y_m = float(last_object.get('y_m', 0.0))
                result.goal_x_m = approach_distance_m
                result.goal_y_m = 0.0
                goal_handle.succeed()
                return result

            if now - self.last_pose_update_time > stale_timeout_sec and odom_fallback is None:
                self._publish_stop()
                goal_handle.abort()
                result.success = False
                result.outcome = f'stale_object_pose:{target_class}'
                return result

            selected = self._select_object(target_class, object_selector)
            if selected is None:
                selected = odom_fallback
            elif bool(selected.get('_held', False)) and odom_fallback is not None:
                selected = odom_fallback
            elif bool(selected.get('_held', False)):
                last_distance = self._candidate_distance(selected)
                if last_distance <= approach_distance_m + lost_target_arrival_margin:
                    self._publish_stop()
                    self._publish_debug({
                        'target_class': target_class,
                        'control_source': 'lost_target_near_stop',
                        'outcome': f'arrived:approach:{target_class}',
                        'distance_m': last_distance,
                        'distance_error_m': last_distance - approach_distance_m,
                        'approach_distance_m': approach_distance_m,
                        'lost_target_arrival_margin_m': lost_target_arrival_margin,
                        'target_x_m': float(selected.get('x_m', 0.0)),
                        'target_y_m': float(selected.get('y_m', 0.0)),
                        'commanded_linear_mps': 0.0,
                        'commanded_yaw_radps': 0.0,
                        'odom_available': self._odom_is_fresh(),
                        'odom_target_active': target_class in self.odom_targets,
                    })
                    result.success = True
                    result.outcome = f'arrived:approach:{target_class}'
                    result.object_x_m = float(selected.get('x_m', 0.0))
                    result.object_y_m = float(selected.get('y_m', 0.0))
                    result.goal_x_m = approach_distance_m
                    result.goal_y_m = 0.0
                    goal_handle.succeed()
                    return result
                self._publish_stop()
                self._publish_debug({
                    'target_class': target_class,
                    'control_source': 'target_lost_waiting',
                    'last_distance_m': last_distance,
                    'approach_distance_m': approach_distance_m,
                    'lost_target_arrival_margin_m': lost_target_arrival_margin,
                    'odom_available': self._odom_is_fresh(),
                    'odom_target_active': target_class in self.odom_targets,
                })
                time.sleep(control_period)
                continue
            else:
                self._maybe_update_odom_target(target_class, selected, force=target_class not in self.odom_targets)
                odom_fallback = self._odom_target_to_robot(target_class)
                if odom_fallback is not None:
                    selected = odom_fallback

            if selected is None:
                self._publish_debug({
                    'target_class': target_class,
                    'control_source': 'waiting_for_target',
                    'approach_distance_m': approach_distance_m,
                    'odom_available': self._odom_is_fresh(),
                    'odom_target_active': target_class in self.odom_targets,
                })
                time.sleep(control_period)
                continue

            object_x = float(selected['x_m'])
            object_y = float(selected['y_m'])
            control_source = 'odom_lock' if bool(selected.get('_odom_fallback', False)) else 'camera_link'
            distance = math.hypot(object_x, object_y)
            heading = math.atan2(object_y, object_x)
            distance_error = distance - approach_distance_m
            near_target = distance <= near_distance_slowdown

            if distance_error <= 0.0:
                self._publish_stop()
                self._publish_debug({
                    'target_class': target_class,
                    'control_source': control_source,
                    'outcome': f'arrived:approach:{target_class}',
                    'distance_m': distance,
                    'distance_error_m': distance_error,
                    'approach_distance_m': approach_distance_m,
                    'target_x_m': object_x,
                    'target_y_m': object_y,
                    'heading_rad': heading,
                    'commanded_linear_mps': 0.0,
                    'commanded_yaw_radps': 0.0,
                    'odom_available': self._odom_is_fresh(),
                    'odom_target_active': target_class in self.odom_targets,
                })
                result.success = True
                result.outcome = f'arrived:approach:{target_class}'
                result.object_x_m = object_x
                result.object_y_m = object_y
                result.goal_x_m = approach_distance_m
                result.goal_y_m = 0.0
                goal_handle.succeed()
                return result

            heading_for_control = 0.0 if abs(heading) < near_yaw_deadband or abs(object_y) < lateral_deadband else heading
            commanded_yaw = max(-max_angular, min(max_angular, angular_gain * heading_for_control))
            linear_limit = min(max_linear, near_max_linear) if near_target else max_linear
            if abs(heading) > stop_threshold and not near_target:
                commanded_linear = 0.0
            elif abs(heading) > align_threshold and not near_target:
                commanded_linear = 0.0
            else:
                commanded_linear = max(
                    0.0,
                    min(linear_limit, linear_gain * distance_error),
                )
                if commanded_linear > 0.0 and min_linear > 0.0:
                    commanded_linear = min(linear_limit, max(min_linear, commanded_linear))

            self._publish_debug({
                'target_class': target_class,
                'control_source': control_source,
                'distance_m': distance,
                'distance_error_m': distance_error,
                'approach_distance_m': approach_distance_m,
                'target_x_m': object_x,
                'target_y_m': object_y,
                'heading_rad': heading,
                'heading_for_control_rad': heading_for_control,
                'near_target': near_target,
                'commanded_linear_mps': commanded_linear,
                'commanded_yaw_radps': commanded_yaw,
                'odom_available': self._odom_is_fresh(),
                'odom_target_active': target_class in self.odom_targets,
            })
            self._publish_velocity(commanded_linear, commanded_yaw)
            time.sleep(control_period)

        self._publish_stop()
        self._publish_debug({
            'target_class': target_class,
            'control_source': 'interrupted',
            'outcome': f'interrupted:{target_class}',
            'approach_distance_m': approach_distance_m,
            'odom_available': self._odom_is_fresh(),
            'odom_target_active': target_class in self.odom_targets,
        })
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
