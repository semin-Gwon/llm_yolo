#!/usr/bin/env bash
set -euo pipefail
source /opt/ros/humble/setup.bash
source /home/jnu/llm_yolo/install/setup.bash
ros2 launch /home/jnu/llm_yolo/launch/real/onboard_min.launch.py
