from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='mission_manager',
            executable='mission_manager_node',
            name='mission_manager_node',
            parameters=['/home/jnu/llm_yolo/configs/common/mission_params.yaml'],
        ),
        Node(
            package='llm_command_router',
            executable='llm_command_router_node',
            name='llm_command_router_node',
            parameters=['/home/jnu/llm_yolo/configs/common/llm_params.yaml'],
        ),
    ])
