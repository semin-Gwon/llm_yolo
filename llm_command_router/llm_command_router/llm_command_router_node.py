import json
import urllib.error

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String

from llm_yolo_interfaces.msg import Intent
from llm_command_router.json_parser import parse_user_text
from llm_command_router.llm_backend import (
    build_prompt,
    call_ollama,
    normalize_mission_plan_for_conditionals,
    validate_llm_result,
)


class LLMCommandRouterNode(Node):
    def __init__(self):
        super().__init__('llm_command_router_node')
        self.declare_parameter('mode', 'rule_based')
        self.declare_parameter('named_places', ['center'])
        self.declare_parameter('object_classes', ['chair', 'person', 'red_box', 'pink_box', 'yellow_box', 'blue_box'])
        self.declare_parameter('ollama_base_url', 'http://127.0.0.1:11434')
        self.declare_parameter('ollama_model', 'qwen2.5:7b')
        self.declare_parameter('ollama_timeout_sec', 5.0)
        self.declare_parameter('fallback_to_rule_based', True)

        self.mode = str(self.get_parameter('mode').value)
        self.named_places = list(self.get_parameter('named_places').value)
        self.object_classes = list(self.get_parameter('object_classes').value)
        self.ollama_base_url = str(self.get_parameter('ollama_base_url').value)
        self.ollama_model = str(self.get_parameter('ollama_model').value)
        self.ollama_timeout_sec = float(self.get_parameter('ollama_timeout_sec').value)
        self.fallback_to_rule_based = bool(self.get_parameter('fallback_to_rule_based').value)

        self.intent_pub = self.create_publisher(Intent, '/intent', 10)
        self.emergency_stop_pub = self.create_publisher(Bool, '/emergency_stop', 10)
        self.emergency_clear_pub = self.create_publisher(Bool, '/emergency_clear', 10)
        self.mission_plan_pub = self.create_publisher(String, '/mission_plan', 10)
        self.user_sub = self.create_subscription(String, '/user_text', self.on_user_text, 10)

    def parse_with_rule_based(self, text: str):
        intent_name, target_type, target_value, confidence, speed_hint = parse_user_text(text, self.named_places)
        return {
            'kind': 'intent',
            'intent': intent_name,
            'target_type': target_type,
            'target_value': target_value,
            'confidence': float(confidence),
            'max_duration_sec': 30,
            'speed_hint': speed_hint,
        }

    def parse_with_llm(self, text: str):
        prompt = build_prompt(text, self.named_places, self.object_classes)
        result = call_ollama(self.ollama_base_url, self.ollama_model, prompt, self.ollama_timeout_sec)
        routed = validate_llm_result(result, self.named_places, self.object_classes)
        return normalize_mission_plan_for_conditionals(text, routed)

    def route_text(self, text: str):
        if self.mode == 'rule_based':
            return self.parse_with_rule_based(text)
        if self.mode == 'llm':
            try:
                return self.parse_with_llm(text)
            except (ValueError, urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
                if self.fallback_to_rule_based:
                    self.get_logger().warning(f'llm route failed, fallback to rule_based: {exc}')
                    return self.parse_with_rule_based(text)
                raise
        raise ValueError(f'unsupported llm router mode: {self.mode}')

    def is_emergency_stop_text(self, text: str) -> bool:
        lowered = text.strip().lower()
        return any(token in lowered for token in ['긴급 정지', '긴급정지', 'emergency stop', '즉시 멈춰', '즉시멈춰'])

    def is_emergency_clear_text(self, text: str) -> bool:
        lowered = text.strip().lower()
        return any(token in lowered for token in ['정지 해제', '정지해제', '긴급 정지 해제', '긴급정지 해제', 'emergency clear', 'clear stop'])

    def publish_emergency_stop(self):
        msg = Bool()
        msg.data = True
        self.emergency_stop_pub.publish(msg)
        self.get_logger().warning('published emergency_stop')

    def publish_emergency_clear(self):
        msg = Bool()
        msg.data = True
        self.emergency_clear_pub.publish(msg)
        self.get_logger().info('published emergency_clear')

    def publish_intent(self, routed: dict):
        intent = Intent()
        intent.stamp = self.get_clock().now().to_msg()
        intent.intent = routed['intent']
        intent.target_type = routed['target_type']
        intent.target_value = routed['target_value']
        intent.max_duration_sec = int(routed.get('max_duration_sec', 30))
        intent.speed_hint = str(routed.get('speed_hint', 'normal'))
        intent.confidence = float(routed['confidence'])
        intent.require_confirmation = False
        self.intent_pub.publish(intent)
        self.get_logger().info(f"published intent={intent.intent} target={intent.target_value}")

    def publish_mission_plan(self, routed: dict):
        msg = String()
        msg.data = json.dumps({
            'intent': 'mission_plan',
            'steps': routed['steps'],
            'failure_policy': routed.get('failure_policy', 'abort_all'),
            'confidence': float(routed.get('confidence', 0.0)),
        }, ensure_ascii=False)
        self.mission_plan_pub.publish(msg)
        self.get_logger().info(
            'published mission_plan steps=%d failure_policy=%s'
            % (len(routed['steps']), routed.get('failure_policy', 'abort_all'))
        )

    def on_user_text(self, msg: String):
        if self.is_emergency_clear_text(msg.data):
            self.publish_emergency_clear()
            return
        if self.is_emergency_stop_text(msg.data):
            self.publish_emergency_stop()
            return
        routed = self.route_text(msg.data)
        if routed['kind'] == 'mission_plan':
            self.publish_mission_plan(routed)
            return
        self.publish_intent(routed)


def main(args=None):
    rclpy.init(args=args)
    node = LLMCommandRouterNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
