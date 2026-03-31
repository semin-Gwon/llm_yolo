import rclpy
from rclpy.node import Node
from std_msgs.msg import String

class PerceptionNode(Node):
    def __init__(self):
        super().__init__('perception_node_real')
        self.pub = self.create_publisher(String, '/perception_debug', 10)
        self.timer = self.create_timer(1.0, self.on_timer)

    def on_timer(self):
        msg = String()
        msg.data = 'real perception backend not connected'
        self.pub.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = PerceptionNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
