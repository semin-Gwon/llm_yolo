#!/usr/bin/env bash
set -euo pipefail

cd /home/jnu/llm_yolo
set +u
source .venv_yolo/bin/activate
source /opt/ros/humble/setup.bash
source install/setup.bash
set -u
ros2 launch launch/sim/mvp_sim.launch.py
