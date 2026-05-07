from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource('/home/jnu/llm_yolo/launch/common/mission_stack.launch.py')
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource('/home/jnu/llm_yolo/launch/real/onboard_min.launch.py')
        ),
        Node(
            package='go2_skill_server_real',
            executable='approach_object_server',
            name='approach_object_server',
            parameters=['/home/jnu/llm_yolo/configs/real/real_nav_params.yaml'],
        ),
        Node(
            package='go2_skill_server_real',
            executable='navigate_to_pose_server',
            name='navigate_to_pose_server',
        ),
        Node(
            package='go2_skill_server_real',
            executable='rotate_in_place_server',
            name='rotate_in_place_server',
        ),
        Node(
            package='go2_skill_server_real',
            executable='scan_scene_server',
            name='scan_scene_server',
        ),
        Node(
            package='perception_node_real',
            executable='perception_node',
            name='perception_node_real',
            parameters=['/home/jnu/llm_yolo/configs/real/real_perception_params.yaml'],
        ),
    ])
