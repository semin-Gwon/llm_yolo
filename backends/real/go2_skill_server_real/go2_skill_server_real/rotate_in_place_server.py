import rclpy
from rclpy.action import ActionServer
from rclpy.node import Node
from llm_yolo_interfaces.action import RotateInPlace

class RotateInPlaceServer(Node):
    def __init__(self):
        super().__init__('rotate_in_place_server_real')
        self.server = ActionServer(self, RotateInPlace, '/rotate_in_place', self.execute)

    def execute(self, goal_handle):
        self.get_logger().warn('real backend not connected yet')
        result = RotateInPlace.Result()
        result.success = False
        result.outcome = 'real backend not implemented'
        goal_handle.abort()
        return result

def main(args=None):
    rclpy.init(args=args)
    node = RotateInPlaceServer()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
