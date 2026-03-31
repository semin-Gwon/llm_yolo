#!/usr/bin/env bash
set -euo pipefail
source /opt/ros/humble/setup.bash
source /home/jnu/llm_yolo/install/setup.bash
ros2 bag record /intent /mission_state /offboard_heartbeat /perception_debug
