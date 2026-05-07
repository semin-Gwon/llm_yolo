#!/usr/bin/env bash
set -eo pipefail

HOST="${1:-127.0.0.1}"
PORT="${2:-8765}"
AUTO_OPEN="${3:-1}"
URL="http://${HOST}:${PORT}"

source /opt/ros/humble/setup.bash
if [[ -f /home/jnu/llm_yolo/.venv_yolo/bin/activate ]]; then
  # shellcheck disable=SC1091
  source /home/jnu/llm_yolo/.venv_yolo/bin/activate
fi
if [[ -f /home/jnu/llm_yolo/install/setup.bash ]]; then
  # shellcheck disable=SC1091
  source /home/jnu/llm_yolo/install/setup.bash
fi

set -u

export ROS_DISABLE_DAEMON="${ROS_DISABLE_DAEMON:-1}"
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_cyclonedds_cpp}"
export CYCLONEDDS_URI="file:///home/jnu/llm_yolo/cyclonedds_dashboard.xml"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-0}"
unset ROS_LOCALHOST_ONLY

if [[ "$AUTO_OPEN" != "--no-open" ]] && command -v xdg-open >/dev/null 2>&1; then
  (
    sleep 2
    xdg-open "$URL" >/dev/null 2>&1 || true
  ) &
fi

exec python3 /home/jnu/llm_yolo/scripts/monitor_dashboard.py --host "$HOST" --port "$PORT"
