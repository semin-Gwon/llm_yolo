#!/usr/bin/env bash
set -euo pipefail
source /opt/ros/humble/setup.bash
source /home/jnu/llm_yolo/install/setup.bash
ros2 bag record \
  /intent \
  /mission_plan \
  /mission_state \
  /perception_debug \
  /perception/object_poses \
  /emergency_stop \
  /emergency_clear \
  /offboard_heartbeat
