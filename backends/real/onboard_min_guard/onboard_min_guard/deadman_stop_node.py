import rclpy
from rclpy.duration import Duration
from rclpy.node import Node
from std_msgs.msg import Empty, String


class DeadmanStopNode(Node):
    def __init__(self):
        super().__init__('deadman_stop_node')
        self.declare_parameter('timeout_sec', 1.0)
        self.timeout_sec = float(self.get_parameter('timeout_sec').value)
        self.last_heartbeat = self.get_clock().now()
        self.sub = self.create_subscription(Empty, '/offboard_heartbeat', self.on_heartbeat, 10)
        self.pub = self.create_publisher(String, '/deadman_state', 10)
        self.timer = self.create_timer(0.1, self.on_timer)

    def on_heartbeat(self, _msg: Empty):
        self.last_heartbeat = self.get_clock().now()

    def on_timer(self):
        now = self.get_clock().now()
        timed_out = (now - self.last_heartbeat) > Duration(seconds=self.timeout_sec)
        msg = String()
        msg.data = 'TIMEOUT_STOP' if timed_out else 'HEARTBEAT_OK'
        self.pub.publish(msg)
        if timed_out:
            self.get_logger().warn('offboard heartbeat timeout: stop should be applied here')


def main(args=None):
    rclpy.init(args=args)
    node = DeadmanStopNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
