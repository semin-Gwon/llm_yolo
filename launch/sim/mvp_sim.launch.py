from launch import LaunchDescription
from launch.actions import ExecuteProcess, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource('/home/jnu/llm_yolo/launch/common/mission_stack.launch.py')
        ),
        Node(
            package='go2_skill_server_sim',
            executable='navigate_to_pose_server',
            name='navigate_to_pose_server',
            parameters=['/home/jnu/llm_yolo/configs/sim/sim_topics.yaml'],
        ),
        Node(
            package='go2_skill_server_sim',
            executable='approach_object_server',
            name='approach_object_server',
            parameters=['/home/jnu/llm_yolo/configs/sim/sim_topics.yaml'],
        ),
        Node(
            package='go2_skill_server_sim',
            executable='rotate_in_place_server',
            name='rotate_in_place_server',
            parameters=['/home/jnu/llm_yolo/configs/sim/sim_topics.yaml'],
        ),
        Node(
            package='go2_skill_server_sim',
            executable='scan_scene_server',
            name='scan_scene_server',
            parameters=[
                '/home/jnu/llm_yolo/configs/sim/sim_topics.yaml',
                '/home/jnu/llm_yolo/configs/sim/sim_perception_params.yaml',
            ],
        ),
        ExecuteProcess(
            cmd=[
                '/home/jnu/llm_yolo/.venv_yolo/bin/python',
                '-m',
                'perception_node_sim.perception_node',
                '--ros-args',
                '-r',
                '__node:=perception_node_sim',
                '--params-file',
                '/home/jnu/llm_yolo/configs/sim/sim_topics.yaml',
                '--params-file',
                '/home/jnu/llm_yolo/configs/sim/sim_perception_params.yaml',
            ],
            output='screen',
        ),
    ])
