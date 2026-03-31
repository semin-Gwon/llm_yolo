from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='onboard_min_guard',
            executable='deadman_stop_node',
            name='deadman_stop_node',
            parameters=['/home/jnu/llm_yolo/configs/real/watchdog_params.yaml'],
        ),
    ])
