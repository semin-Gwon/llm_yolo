import json

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from std_msgs.msg import Bool, Empty, String

from llm_yolo_interfaces.action import ApproachObject, NavigateToPose, ScanScene
from llm_yolo_interfaces.msg import Intent


class MissionManagerNode(Node):
    def __init__(self):
        super().__init__('mission_manager_node')
        self.declare_parameter('fallback_places', ['hallway_corner', 'meeting_room_a'])
        self.declare_parameter('mission_timeout_sec', 30)
        self.declare_parameter('navigate_action_name', '/llm_navigate_to_pose')
        self.declare_parameter('approach_action_name', '/approach_object')
        self.fallback_places = list(self.get_parameter('fallback_places').value)
        self.intent_sub = self.create_subscription(Intent, '/intent', self.on_intent, 10)
        self.mission_plan_sub = self.create_subscription(String, '/mission_plan', self.on_mission_plan, 10)
        self.state_pub = self.create_publisher(String, '/mission_state', 10)
        self.emergency_stop_sub = self.create_subscription(Bool, '/emergency_stop', self.on_emergency_stop, 10)
        self.emergency_clear_sub = self.create_subscription(Bool, '/emergency_clear', self.on_emergency_clear, 10)
        self.heartbeat_pub = self.create_publisher(Empty, '/offboard_heartbeat', 10)
        self.heartbeat_timer = self.create_timer(0.2, self.publish_heartbeat)
        self.nav_client = ActionClient(self, NavigateToPose, self.get_parameter('navigate_action_name').value)
        self.approach_client = ActionClient(self, ApproachObject, self.get_parameter('approach_action_name').value)
        self.scan_client = ActionClient(self, ScanScene, '/scan_scene')
        self.busy = False
        self.current_goal_handle = None
        self.current_mode = 'idle'
        self.find_target = ''
        self.remaining_places = []
        self.plan_active = False
        self.plan_steps = []
        self.plan_index = 0
        self.plan_failure_policy = 'abort_all'
        self.plan_last_step_success = None
        self.plan_last_step_success = None
        self.emergency_stop_active = False

    def publish_heartbeat(self):
        self.heartbeat_pub.publish(Empty())

    def publish_state(self, text: str):
        msg = String()
        msg.data = text
        self.state_pub.publish(msg)
        self.get_logger().info(text)

    def reset_execution(self):
        self.busy = False
        self.current_goal_handle = None
        self.current_mode = 'idle'
        self.find_target = ''
        self.remaining_places = []
        self.plan_active = False
        self.plan_steps = []
        self.plan_index = 0
        self.plan_failure_policy = 'abort_all'

    def on_emergency_stop(self, msg: Bool):
        if not bool(msg.data):
            return
        self.emergency_stop_active = True
        if self.current_goal_handle is not None:
            self.current_goal_handle.cancel_goal_async()
        self.busy = False
        self.current_goal_handle = None
        self.current_mode = 'idle'
        self.plan_active = False
        self.plan_steps = []
        self.plan_index = 0
        self.publish_state('emergency_stop engaged')

    def on_emergency_clear(self, msg: Bool):
        if not bool(msg.data):
            return
        self.emergency_stop_active = False
        self.publish_state('emergency_stop cleared')

    def on_intent(self, msg: Intent):
        if self.emergency_stop_active:
            self.publish_state('busy: emergency_stop active')
            return
        if msg.intent == 'cancel':
            self.cancel_current()
            return
        if self.emergency_stop_active:
            self.publish_state('busy: emergency_stop active')
            return
        if self.busy:
            self.publish_state('busy: intent rejected')
            return
        if msg.intent == 'navigate_to_named_place':
            self.busy = True
            self.current_mode = 'navigate'
            self.send_nav(msg.target_value, msg.max_duration_sec or 30, getattr(msg, 'speed_hint', 'normal'))
        elif msg.intent == 'approach_object':
            self.busy = True
            self.current_mode = 'approach_object'
            self.send_approach(
                msg.target_value,
                getattr(msg, 'object_selector', ''),
                msg.max_duration_sec or 30,
                getattr(msg, 'approach_distance_m', 0.8),
                getattr(msg, 'speed_hint', 'normal'),
            )
        elif msg.intent == 'scan_scene':
            self.busy = True
            self.current_mode = 'scan'
            self.send_scan(msg.target_value, msg.max_duration_sec or 10)
        elif msg.intent == 'find_object':
            self.busy = True
            self.current_mode = 'find_object_scan'
            self.find_target = msg.target_value
            self.remaining_places = list(self.fallback_places[:2])
            self.send_scan(self.find_target, msg.max_duration_sec or 10)
        else:
            self.publish_state(f'unsupported intent: {msg.intent}')

    def on_mission_plan(self, msg: String):
        if self.emergency_stop_active:
            self.publish_state('busy: emergency_stop active')
            return
        if self.busy:
            self.publish_state('busy: mission_plan rejected')
            return
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError as exc:
            self.publish_state(f'mission_plan invalid_json: {exc}')
            return
        steps = payload.get('steps', [])
        if not isinstance(steps, list) or not steps:
            self.publish_state('mission_plan invalid_steps')
            return
        failure_policy = str(payload.get('failure_policy', 'abort_all')).strip() or 'abort_all'
        if failure_policy not in {'abort_all', 'continue', 'return_home'}:
            self.publish_state(f'mission_plan invalid_failure_policy: {failure_policy}')
            return
        self.busy = True
        self.plan_active = True
        self.plan_steps = steps
        self.plan_index = 0
        self.plan_failure_policy = failure_policy
        self.plan_last_step_success = None
        self.publish_state(f'mission_plan started: steps={len(steps)} failure_policy={failure_policy}')
        self.start_next_plan_step()

    def cancel_current(self):
        if self.current_goal_handle is not None:
            self.current_goal_handle.cancel_goal_async()
        self.reset_execution()
        self.publish_state('mission canceled')

    def start_next_plan_step(self):
        if not self.plan_active:
            return
        if self.plan_index >= len(self.plan_steps):
            self.publish_state('mission_plan completed')
            self.reset_execution()
            return
        step = self.plan_steps[self.plan_index]
        run_if = str(step.get('run_if', 'always')).strip() or 'always'
        if run_if == 'previous_failed' and self.plan_last_step_success is not False:
            self.publish_state(f'mission_plan step {self.plan_index + 1} skipped: run_if=previous_failed')
            self.plan_index += 1
            self.start_next_plan_step()
            return
        if run_if == 'previous_succeeded' and self.plan_last_step_success is not True:
            self.publish_state(f'mission_plan step {self.plan_index + 1} skipped: run_if=previous_succeeded')
            self.plan_index += 1
            self.start_next_plan_step()
            return
        intent = str(step.get('intent', '')).strip()
        target_value = str(step.get('target_value', '')).strip()
        timeout_sec = int(step.get('max_duration_sec', 30))
        self.publish_state(
            f'mission_plan step {self.plan_index + 1}/{len(self.plan_steps)}: {intent}:{target_value}'
        )
        if intent == 'navigate_to_named_place':
            self.current_mode = 'plan_navigate'
            self.send_nav(target_value, timeout_sec, str(step.get('speed_hint', 'normal')))
            return
        if intent == 'approach_object':
            self.current_mode = 'plan_approach_object'
            self.send_approach(
                target_value,
                str(step.get('object_selector', '')),
                timeout_sec,
                float(step.get('approach_distance_m', 0.8)),
                str(step.get('speed_hint', 'normal')),
            )
            return
        if intent == 'scan_scene':
            self.current_mode = 'plan_scan'
            self.send_scan(target_value, timeout_sec)
            return
        if intent == 'find_object':
            self.current_mode = 'plan_find_object_scan'
            self.find_target = target_value
            self.remaining_places = list(self.fallback_places[:2])
            self.send_scan(target_value, timeout_sec)
            return
        if intent == 'cancel':
            self.publish_state('mission_plan canceled by step')
            self.reset_execution()
            return
        self.finish_plan_step(False, f'unsupported plan step: {intent}')

    def finish_plan_step(self, success: bool, outcome: str):
        if not self.plan_active:
            return
        status_text = 'success' if success else 'failed'
        self.publish_state(
            f'mission_plan step {self.plan_index + 1} {status_text}: {outcome}'
        )
        self.plan_last_step_success = bool(success)
        if success:
            self.plan_index += 1
            self.start_next_plan_step()
            return

        remaining_steps = self.plan_steps[self.plan_index + 1:]
        has_failure_branch = any(
            str(step.get('run_if', 'always')).strip() == 'previous_failed'
            for step in remaining_steps
        )
        if has_failure_branch:
            self.plan_index += 1
            self.start_next_plan_step()
            return
        if self.plan_failure_policy == 'continue':
            self.plan_index += 1
            self.start_next_plan_step()
            return
        if self.plan_failure_policy == 'return_home' and self.fallback_places:
            self.current_mode = 'plan_return_home'
            self.send_nav(self.fallback_places[0], 30, 'normal')
            return
        self.publish_state(f'mission_plan aborted: {outcome}')
        self.reset_execution()

    def send_nav(self, target_name: str, timeout_sec: int = 30, speed_hint: str = 'normal'):
        self.nav_client.wait_for_server()
        goal = NavigateToPose.Goal()
        goal.target_name = target_name
        goal.desired_yaw_rad = 0.0
        goal.timeout_sec = int(timeout_sec)
        goal.speed_hint = str(speed_hint or 'normal')
        future = self.nav_client.send_goal_async(goal)
        future.add_done_callback(self._on_nav_goal_response)
        self.publish_state(f'navigate requested: {target_name}')

    def send_scan(self, target_class: str, timeout_sec: int = 10):
        self.scan_client.wait_for_server()
        goal = ScanScene.Goal()
        goal.target_class = target_class
        goal.timeout_sec = int(timeout_sec)
        future = self.scan_client.send_goal_async(goal)
        future.add_done_callback(self._on_scan_goal_response)
        self.publish_state(f'scan requested: {target_class}')

    def send_approach(self, target_class: str, object_selector: str = '', timeout_sec: int = 30, approach_distance_m: float = 0.8, speed_hint: str = 'normal'):
        self.approach_client.wait_for_server()
        goal = ApproachObject.Goal()
        goal.target_class = target_class
        goal.object_selector = str(object_selector or '')
        goal.timeout_sec = int(timeout_sec)
        goal.approach_distance_m = float(approach_distance_m)
        goal.speed_hint = str(speed_hint or 'normal')
        future = self.approach_client.send_goal_async(goal)
        future.add_done_callback(self._on_approach_goal_response)
        suffix = f' ({goal.object_selector})' if goal.object_selector else ''
        self.publish_state(f'approach requested: {target_class}{suffix}')

    def _on_nav_goal_response(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            if self.current_mode.startswith('plan_'):
                self.finish_plan_step(False, 'navigate goal rejected')
                return
            self.publish_state('navigate goal rejected')
            self.reset_execution()
            return
        self.current_goal_handle = goal_handle
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self._on_nav_result)

    def _on_scan_goal_response(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            if self.current_mode.startswith('plan_'):
                self.finish_plan_step(False, 'scan goal rejected')
                return
            self.publish_state('scan goal rejected')
            self.reset_execution()
            return
        self.current_goal_handle = goal_handle
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self._on_scan_result)

    def _on_approach_goal_response(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            if self.current_mode.startswith('plan_'):
                self.finish_plan_step(False, 'approach goal rejected')
                return
            self.publish_state('approach goal rejected')
            self.reset_execution()
            return
        self.current_goal_handle = goal_handle
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self._on_approach_result)

    def _on_nav_result(self, future):
        result = future.result().result
        if self.current_mode == 'navigate':
            self.publish_state(f'navigate completed: {result.outcome}')
            self.reset_execution()
            return
        if self.current_mode == 'find_object_navigate':
            self.current_mode = 'find_object_scan'
            self.send_scan(self.find_target)
            return
        if self.current_mode == 'plan_navigate':
            self.finish_plan_step(bool(result.success), result.outcome)
            return
        if self.current_mode == 'plan_find_object_navigate':
            self.current_mode = 'plan_find_object_scan'
            self.send_scan(self.find_target)
            return
        if self.current_mode == 'plan_return_home':
            self.publish_state(f'mission_plan return_home: {result.outcome}')
            self.reset_execution()
            return
        self.reset_execution()

    def _on_scan_result(self, future):
        result = future.result().result
        if self.current_mode == 'scan':
            self.publish_state(f'scan completed: {result.detection_state}')
            self.reset_execution()
            return
        if self.current_mode == 'find_object_scan':
            if result.found:
                self.publish_state(f'find_object success: {self.find_target}')
                self.reset_execution()
                return
            if self.remaining_places:
                next_place = self.remaining_places.pop(0)
                self.current_mode = 'find_object_navigate'
                self.send_nav(next_place)
                return
            self.publish_state(f'find_object failed: {self.find_target}')
            self.reset_execution()
            return
        if self.current_mode == 'plan_scan':
            self.finish_plan_step(bool(result.found), result.detection_state)
            return
        if self.current_mode == 'plan_find_object_scan':
            if result.found:
                self.finish_plan_step(True, f'find_object success: {self.find_target}')
                return
            if self.remaining_places:
                next_place = self.remaining_places.pop(0)
                self.current_mode = 'plan_find_object_navigate'
                self.send_nav(next_place)
                return
            self.finish_plan_step(False, f'find_object failed: {self.find_target}')
            return

    def _on_approach_result(self, future):
        result = future.result().result
        if self.current_mode == 'approach_object':
            self.publish_state(f'approach completed: {result.outcome}')
            self.reset_execution()
            return
        if self.current_mode == 'plan_approach_object':
            self.finish_plan_step(bool(result.success), result.outcome)
            return


def main(args=None):
    rclpy.init(args=args)
    node = MissionManagerNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
