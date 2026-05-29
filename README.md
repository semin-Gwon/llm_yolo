# llm_yolo

Unitree Go2 Edu를 대상으로 한 ROS 2 Humble 기반 연구 프로젝트입니다.

목표는 자연어 명령을 구조화된 mission으로 변환하고, YOLO 기반 perception과 sim/real backend를 통해 로봇 행동으로 연결하는 것입니다. 현재 구조는 **sim-first**로 개발되었고, 상위 mission 계층은 공통으로 유지한 채 `backends/sim`과 `backends/real`만 교체하는 방식입니다.

```text
user text
  -> llm_command_router
  -> mission_manager
  -> llm_yolo_interfaces actions
  -> sim backend 또는 real backend
```

## Project Status

이 README는 현재까지 구현 및 확인된 내용만 기록합니다.

| 영역 | 현재 상태 |
|---|---|
| Sim | MVP 기능 구현 및 대표 회귀 시나리오 검증 완료 |
| Real | 1차 실기체 backend 구현 및 일부 end-to-end 경로 1차 확인 완료 |
| LLM | Rule-based parser와 Ollama backend 공존 |
| Perception | Sim은 YOLO11n, Real은 YOLO11s-seg 기반 |
| Navigation | Sim은 Nav2 우선, direct `/cmd_vel` fallback 유지 |
| Real control | `/cmd_vel`을 내부 bridge에서 `/api/sport/request`로 변환 |

## Architecture

```text
llm_yolo/
├── llm_command_router      # 자연어 -> Intent 또는 mission_plan
├── mission_manager         # mission 실행, 조건 분기, timeout, cancel
├── llm_yolo_interfaces     # Intent.msg 및 Navigate/Rotate/Scan/Approach actions
├── backends/
│   ├── sim                 # Isaac Sim / Nav2 / sim perception
│   └── real                # Go2 camera/depth / direct approach / sport request bridge
├── launch/
│   ├── common              # 공통 mission stack
│   ├── sim                 # sim launch
│   └── real                # real launch
├── configs/
│   ├── common              # mission, LLM, named places
│   ├── sim                 # sim topics, nav, perception
│   └── real                # real topics, perception, approach, bridge, watchdog
├── scripts                 # 실행/모니터링 helper
└── docs                    # 운영 문서, 계획, 참조 문서
```

자세한 흐름도는 [docs/overview/architecture.md](docs/overview/architecture.md)를 참고합니다.

## Implemented Features

### Common

- `/user_text` 자연어 명령 수신
- Rule-based parser와 Ollama LLM backend
- `Intent.msg` 기반 단일 명령 실행
- `mission_plan` JSON 기반 복합 명령 실행
- `run_if=always | previous_failed | previous_succeeded` 조건 실행
- mission timeout, cancel, emergency stop/clear
- web monitor dashboard

### Sim

- named place 이동
- `scan_scene`
- 회전 탐색 기반 `find_object`
- YOLO 기반 객체 탐지
- YOLO bbox + depth + camera info + TF 기반 object pose 추정
- `/perception/object_poses` publish
- `approach_object`
- `chair 앞으로 가`, `tv 앞으로 가` 검증
- Nav2 action bridge
- direct `/cmd_vel` fallback
- `speed_hint` (`slow`, `normal`, `fast`)
- `person` 검출 기반 pause/resume 및 거리 조건
- 대표 회귀 시나리오 실검증

### Real

- real 전용 perception node 구현
- real 전용 approach backend 구현
- onboard watchdog node 연결
- `/cmd_vel -> /api/sport/request` bridge 구현
- real launch에 perception, approach, bridge, watchdog 통합
- 실기체 camera/depth/camera_info topic 확인
- `camera_link` 기준 object pose publish
- YOLO11s-seg mask 기반 depth cluster 적용
- `/perception/visible_objects`, `/perception/object_poses`, `/perception/object_markers`, `/perception_debug` publish 경로 구현
- `chair 앞으로 가` 경로에서 1차 성공 흐름 확인
- approach 중 `/cmd_vel` 출력 확인
- emergency stop 관련 stop/abort 경로 반영

## Requirements

| 항목 | 기준 |
|---|---|
| OS | Ubuntu 22.04 |
| ROS 2 | Humble |
| Python | 3.10 |
| Sim | Isaac Sim 5.1.0 + 외부 Go2 sim 환경 |
| YOLO | Ultralytics 8.4.14 |
| LLM | Ollama + `qwen2.5:latest` |
| Real robot | Unitree Go2 Edu + `unitree_ros2` |

Isaac Sim용 conda 환경과 `llm_yolo`용 `.venv_yolo`는 분리해서 사용합니다.

## Model Files

모델 가중치는 GitHub에 포함하지 않습니다. 실행 전 프로젝트 루트에 배치합니다.

| 파일 | 용도 |
|---|---|
| `yolo11n.pt` | sim YOLO perception |
| `yolo11s-seg.pt` | real YOLO segmentation perception |

`.gitignore`에서 `*.pt`는 제외되어 있습니다.

## Setup

```bash
cd /home/jnu/llm_yolo
python3 -m venv .venv_yolo
source .venv_yolo/bin/activate

python -m pip install --upgrade pip setuptools wheel
pip install pyyaml jinja2 typeguard
pip install torch torchvision torchaudio
pip install ultralytics==8.4.14
```

빌드:

```bash
cd /home/jnu/llm_yolo
source .venv_yolo/bin/activate
source /opt/ros/humble/setup.bash
colcon build
source install/setup.bash
```

YOLO venv 세부 기록은 [docs/setup/yolo_venv_guide.md](docs/setup/yolo_venv_guide.md)를 참고합니다.

## Run: Sim

Sim은 외부 Go2 Isaac Sim 환경이 먼저 실행되어 있어야 합니다.

### 1. Isaac Sim / Go2 Sim

```bash
source /opt/ros/humble/setup.bash
conda activate isaaclab
python /home/jnu/go2_sim/scripts/go2_sim.py
```

Nav2를 사용하는 경우 별도 터미널에서 Go2 sim navigation stack을 실행합니다.

### 2. llm_yolo Sim Stack

```bash
bash /home/jnu/llm_yolo/scripts/run_sim.sh
```

동일한 실행을 수동으로 풀면:

```bash
cd /home/jnu/llm_yolo
source .venv_yolo/bin/activate
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch launch/sim/mvp_sim.launch.py
```

### 3. Web Monitor

자동 모드:

```bash
bash /home/jnu/llm_yolo/scripts/run_monitor_dashboard.sh
```

브라우저 자동 열기 없이:

```bash
bash /home/jnu/llm_yolo/scripts/run_monitor_dashboard.sh 127.0.0.1 8765 --no-open --mode auto
```

sim으로 고정:

```bash
bash /home/jnu/llm_yolo/scripts/run_monitor_dashboard.sh 127.0.0.1 8765 --no-open --mode sim
```

현재 `auto` 모드는 `eno1`이 살아 있으면 real, 아니면 sim으로 동작합니다. sim 모드에서는 CycloneDDS interface를 `lo`로 설정합니다.

## Run: Real

Real 실행은 Go2 실기체, `unitree_ros2`, 카메라/depth topic, `/api/sport/request`가 준비된 상태를 전제로 합니다.

```bash
bash /home/jnu/llm_yolo/scripts/run_real.sh
```

수동 실행:

```bash
cd /home/jnu/llm_yolo
source /home/jnu/llm_yolo/.venv_yolo/bin/activate
source /home/jnu/unitree_ros2/setup.sh
source /home/jnu/llm_yolo/install/setup.bash
export PYTHONPATH="/home/jnu/llm_yolo/.venv_yolo/lib/python3.10/site-packages:${PYTHONPATH:-}"
ros2 launch /home/jnu/llm_yolo/launch/real/mvp_real.launch.py
```

onboard guard만 실행:

```bash
bash /home/jnu/llm_yolo/scripts/run_onboard_min.sh
```

real 모니터:

```bash
bash /home/jnu/llm_yolo/scripts/run_monitor_dashboard.sh 127.0.0.1 8765 --no-open --mode real
```

## Command Examples

명령은 `/user_text` topic으로 보냅니다.

### Navigation

```bash
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'center 로 가'}"
ros2 topic pub --once /user_text std_msgs/msg/String "{data: '천천히 center 로 가'}"
ros2 topic pub --once /user_text std_msgs/msg/String "{data: '빠르게 center 로 가'}"
```

### Find / Scan

```bash
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'chair 찾아'}"
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'tv 찾아'}"
```

### Approach

```bash
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'chair 앞으로 가'}"
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'tv 앞으로 가'}"
```

### Mission Plan

```bash
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'center로 가서 chair 찾아'}"
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'chair 찾고 없으면 center로 복귀'}"
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'chair 찾고 없으면 center로 가서 다시 찾아'}"
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'yellow_box 찾고 없으면 red_box 찾아'}"
```

### Safety

```bash
ros2 topic pub --once /user_text std_msgs/msg/String "{data: '긴급 정지'}"
ros2 topic pub --once /user_text std_msgs/msg/String "{data: '정지 해제'}"
```

## Monitoring Commands

```bash
ros2 topic echo /mission_state
ros2 topic echo /mission_plan
ros2 topic echo /perception/visible_objects
ros2 topic echo /perception/object_poses
ros2 topic echo /perception_debug
ros2 topic echo /emergency_stop
```

Sim helper:

```bash
/home/jnu/llm_yolo/scripts/monitor_sim.sh core
/home/jnu/llm_yolo/scripts/monitor_sim.sh perception
/home/jnu/llm_yolo/scripts/monitor_sim.sh object
/home/jnu/llm_yolo/scripts/monitor_sim.sh safety
/home/jnu/llm_yolo/scripts/monitor_sim.sh plan
/home/jnu/llm_yolo/scripts/monitor_sim.sh nav
```

ROS bag 기록:

```bash
bash /home/jnu/llm_yolo/scripts/record_bag.sh
```

## Current Sim Notes

| 항목 | 상태 |
|---|---|
| Named places | `center`, `chair_room`, `commode_room`, `tv_room`, `living_room` |
| YOLO model | `yolo11n.pt` |
| Sim perception mode | `yolo` |
| Depth mode | `bbox_cluster` |
| Operational object classes | `chair`, `tv` |
| Person safety | pause/resume and distance threshold verified |
| Navigation | Nav2 path verified, direct path retained |

대표 검증 명령:

```text
center 로 가
chair 찾아
chair 찾고 없으면 center로 복귀
chair 찾고 없으면 center로 가서 다시 찾아
yellow_box 찾고 없으면 red_box 찾아
chair 앞으로 가
긴급 정지
정지 해제
```

## Current Real Notes

| 항목 | 상태 |
|---|---|
| YOLO model | `/home/jnu/llm_yolo/yolo11s-seg.pt` |
| Depth mode | `mask_cluster` |
| Object pose frame | `camera_link` |
| Camera image | `/camera/color/image_raw` |
| Depth image | `/camera/depth/image_rect_raw` |
| Camera info | `/camera/color/camera_info` |
| Command output | `/cmd_vel` |
| Final robot command | `/api/sport/request` |
| Bridge | `cmd_vel_to_sport_request_node` |
| Visual markers | `/perception/object_markers` |

Real perception candidate classes:

```text
person, chair, couch, dining table, tv, laptop, keyboard, mouse, bottle, cup
```

Natural-language command target classes currently configured:

```text
chair, couch, dining table, tv
```

## Important Config Files

| 파일 | 설명 |
|---|---|
| [configs/common/llm_params.yaml](configs/common/llm_params.yaml) | LLM backend, named places, object classes |
| [configs/common/mission_params.yaml](configs/common/mission_params.yaml) | mission timeout, fallback, approach distance |
| [configs/sim/sim_topics.yaml](configs/sim/sim_topics.yaml) | sim action/topic wiring |
| [configs/sim/sim_perception_params.yaml](configs/sim/sim_perception_params.yaml) | sim YOLO/depth parameters |
| [configs/sim/sim_named_places.yaml](configs/sim/sim_named_places.yaml) | sim named place coordinates |
| [configs/real/real_topics.yaml](configs/real/real_topics.yaml) | real sensor/control topic mapping |
| [configs/real/real_perception_params.yaml](configs/real/real_perception_params.yaml) | real YOLO segmentation/depth parameters |
| [configs/real/real_nav_params.yaml](configs/real/real_nav_params.yaml) | real approach control parameters |
| [configs/real/cmd_vel_bridge_params.yaml](configs/real/cmd_vel_bridge_params.yaml) | `/cmd_vel` to `/api/sport/request` bridge |
| [configs/real/watchdog_params.yaml](configs/real/watchdog_params.yaml) | real watchdog/deadman guard |

## Documentation

| 문서 | 설명 |
|---|---|
| [docs/README.md](docs/README.md) | 문서 목차 |
| [docs/overview/architecture.md](docs/overview/architecture.md) | 전체 구조 |
| [docs/operation/sim_mode.md](docs/operation/sim_mode.md) | sim 운영 |
| [docs/operation/real_mode.md](docs/operation/real_mode.md) | real 운영 |
| [docs/operation/test_scenarios.md](docs/operation/test_scenarios.md) | sim 회귀 시나리오 |
| [docs/reference/mission_plan_schema.md](docs/reference/mission_plan_schema.md) | mission plan schema |
| [docs/reference/sim_ros2_contract.md](docs/reference/sim_ros2_contract.md) | Isaac Sim ROS 2 contract |
| [docs/planning/sim_progress.md](docs/planning/sim_progress.md) | sim 완료 기록 |
| [docs/planning/real_progress.md](docs/planning/real_progress.md) | real 진행 기록 |

## Repository Notes

GitHub에는 다음 산출물을 포함하지 않습니다.

```text
.venv_yolo/
build/
install/
log/
bags/
*.pt
mobileclip_blt.ts
```

현재 모델 파일은 로컬에 직접 배치해서 사용합니다. `mobileclip_blt.ts`는 현재 코드 경로에서 사용하지 않는 open-vocabulary 실험용 모델 아티팩트로 분류했습니다.
