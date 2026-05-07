#!/usr/bin/env bash
set -euo pipefail

cd /home/jnu/llm_yolo

set +u
source /home/jnu/llm_yolo/.venv_yolo/bin/activate
source /home/jnu/unitree_ros2/setup.sh
source /home/jnu/llm_yolo/install/setup.bash
set -u

export PYTHONPATH="/home/jnu/llm_yolo/.venv_yolo/lib/python3.10/site-packages:${PYTHONPATH:-}"

ros2 launch /home/jnu/llm_yolo/launch/real/mvp_real.launch.py
