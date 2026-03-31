#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-core}"

source /opt/ros/humble/setup.bash
if [[ -f /home/jnu/llm_yolo/.venv_yolo/bin/activate ]]; then
  # shellcheck disable=SC1091
  source /home/jnu/llm_yolo/.venv_yolo/bin/activate
fi
if [[ -f /home/jnu/llm_yolo/install/setup.bash ]]; then
  # shellcheck disable=SC1091
  source /home/jnu/llm_yolo/install/setup.bash
fi

export ROS_DISABLE_DAEMON="${ROS_DISABLE_DAEMON:-1}"
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_cyclonedds_cpp}"
export CYCLONEDDS_URI="${CYCLONEDDS_URI:-file:///home/jnu/llm_yolo/cyclonedds_local.xml}"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-0}"
export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-0}"

cleanup() {
  jobs -p | xargs -r kill >/dev/null 2>&1 || true
}

case "$MODE" in
  core)
    exec ros2 topic echo /mission_state
    ;;
  perception)
    exec ros2 topic echo /perception_debug
    ;;
  object)
    exec ros2 topic echo /perception/object_poses
    ;;
  safety)
    exec ros2 topic echo /emergency_stop
    ;;
  plan)
    exec ros2 topic echo /mission_plan
    ;;
  nav)
    ros2 action info /llm_navigate_to_pose
    echo
    ros2 action info /navigate_to_pose
    ;;
  all)
    trap cleanup INT TERM EXIT
    ros2 topic echo /mission_state | sed 's/^/[mission_state] /' &
    ros2 topic echo /perception_debug | sed 's/^/[perception_debug] /' &
    ros2 topic echo /perception/object_poses | sed 's/^/[object_poses] /' &
    ros2 topic echo /emergency_stop | sed 's/^/[emergency_stop] /' &
    wait
    ;;
  *)
    echo "usage: $0 {core|perception|object|safety|plan|nav|all}"
    exit 1
    ;;
esac
