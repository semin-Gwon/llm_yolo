import rclpy
from rclpy.action import ActionServer
from rclpy.node import Node
from llm_yolo_interfaces.action import NavigateToPose

class NavigateToPoseServer(Node):
    def __init__(self):
        super().__init__('navigate_to_pose_server_real')
        self.server = ActionServer(self, NavigateToPose, '/navigate_to_pose', self.execute)

    def execute(self, goal_handle):
        self.get_logger().warn('real backend not connected yet')
        result = NavigateToPose.Result()
        result.success = False
        result.outcome = 'real backend not implemented'
        goal_handle.abort()
        return result

def main(args=None):
    rclpy.init(args=args)
    node = NavigateToPoseServer()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
