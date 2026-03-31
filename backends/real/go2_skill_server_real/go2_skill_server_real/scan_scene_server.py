import rclpy
from rclpy.action import ActionServer
from rclpy.node import Node
from llm_yolo_interfaces.action import ScanScene

class ScanSceneServer(Node):
    def __init__(self):
        super().__init__('scan_scene_server_real')
        self.server = ActionServer(self, ScanScene, '/scan_scene', self.execute)

    def execute(self, goal_handle):
        self.get_logger().warn('real backend not connected yet')
        result = ScanScene.Result()
        result.found = False
        result.detection_state = 'NOT_CONNECTED'
        result.message = 'real backend not implemented'
        goal_handle.abort()
        return result

def main(args=None):
    rclpy.init(args=args)
    node = ScanSceneServer()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
