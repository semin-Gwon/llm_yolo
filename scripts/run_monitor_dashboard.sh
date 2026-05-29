#!/usr/bin/env bash
set -eo pipefail

HOST="127.0.0.1"
PORT="8765"
AUTO_OPEN="1"
MODE="auto"
EFFECTIVE_MODE=""

if [[ $# -ge 1 ]]; then
  HOST="$1"
fi
if [[ $# -ge 2 ]]; then
  PORT="$2"
fi
shift $(( $# >= 2 ? 2 : $# ))

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-open)
      AUTO_OPEN="--no-open"
      ;;
    --mode)
      shift
      MODE="${1:-auto}"
      ;;
    *)
      echo "usage: $0 [host] [port] [--no-open] [--mode auto|sim|real]" >&2
      exit 1
      ;;
  esac
  shift
done

URL="http://${HOST}:${PORT}"

interface_is_up() {
  local iface="$1"
  [[ -d "/sys/class/net/${iface}" ]] || return 1
  [[ "$(cat "/sys/class/net/${iface}/operstate" 2>/dev/null || true)" == "up" ]] && return 0
  [[ "$(cat "/sys/class/net/${iface}/carrier" 2>/dev/null || true)" == "1" ]] && return 0
  return 1
}

cyclonedds_uri_for_interface() {
  local iface="$1"
  printf '<CycloneDDS><Domain><General><Interfaces><NetworkInterface name="%s" priority="default" multicast="default" /></Interfaces></General></Domain></CycloneDDS>' "$iface"
}

if [[ "$MODE" == "auto" ]]; then
  if interface_is_up "eno1"; then
    EFFECTIVE_MODE="real"
  else
    EFFECTIVE_MODE="sim"
  fi
else
  EFFECTIVE_MODE="$MODE"
fi

source /opt/ros/humble/setup.bash
if [[ -f /home/jnu/llm_yolo/.venv_yolo/bin/activate ]]; then
  # shellcheck disable=SC1091
  source /home/jnu/llm_yolo/.venv_yolo/bin/activate
fi
if [[ "$EFFECTIVE_MODE" == "real" ]]; then
  if [[ -f /home/jnu/unitree_ros2/setup.sh ]]; then
    # shellcheck disable=SC1091
    source /home/jnu/unitree_ros2/setup.sh
  fi
fi
if [[ -f /home/jnu/llm_yolo/install/setup.bash ]]; then
  # shellcheck disable=SC1091
  source /home/jnu/llm_yolo/install/setup.bash
fi

set -u

export ROS_DISABLE_DAEMON="${ROS_DISABLE_DAEMON:-1}"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-0}"
export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-0}"

if [[ "$EFFECTIVE_MODE" == "sim" ]]; then
  export RMW_IMPLEMENTATION="rmw_cyclonedds_cpp"
  export CYCLONEDDS_URI="$(cyclonedds_uri_for_interface "lo")"
elif [[ "$EFFECTIVE_MODE" == "real" && -z "${CYCLONEDDS_URI:-}" ]]; then
  export RMW_IMPLEMENTATION="rmw_cyclonedds_cpp"
  export CYCLONEDDS_URI="$(cyclonedds_uri_for_interface "eno1")"
fi

echo "monitor mode: ${MODE} -> ${EFFECTIVE_MODE} (CYCLONEDDS_URI=${CYCLONEDDS_URI:-default})"

if [[ "$AUTO_OPEN" != "--no-open" ]] && command -v xdg-open >/dev/null 2>&1; then
  (
    sleep 2
    xdg-open "$URL" >/dev/null 2>&1 || true
  ) &
fi

exec python3 /home/jnu/llm_yolo/scripts/monitor_dashboard.py --host "$HOST" --port "$PORT" --mode "$MODE"
