# llm_yolo

`llm_yolo`는 Unitree Go2용 sim-first ROS 2 MVP 프로젝트입니다. 현재 기준선은 Isaac Sim 5.1.0에서 먼저 동작시키는 것이고, 이후 같은 상위 구조를 유지한 채 real backend로 전환하는 것을 목표로 합니다.

## 현재 완료된 MVP
- 자연어 `center 로 가` -> named place navigation 동작 확인
- 자연어 `red_box`, `pink_box`, `yellow_box 찾아` -> ground-truth 기반 `find_object` 동작 확인
- 자연어 `chair 찾아` -> YOLO 기반 `find_object` 동작 확인
- 실제 LLM 모드에서 자연어 명령 해석 경로 동작 확인
- 실제 LLM 모드에서 `mission_plan` 2단계 복합 명령 생성 및 순차 실행 검증 완료
- 실제 LLM 모드에서 `찾고 없으면 center로 복귀` 조건부 복귀 명령 검증 완료
- 실제 LLM 모드에서 `run_if` 기반 3단계 일반화(`조건부 재시도`, `대체 대상 탐색`) 검증 완료
- Nav2 모드에서 액션 이름 분리(`/llm_navigate_to_pose` vs `/navigate_to_pose`) 및 `center 로 가` 이동 검증 완료
- Nav2 모드에서 `긴급 정지` / `정지 해제` 동작 검증 완료
- 객체를 못 찾았을 때 fallback 이동 후 종료 흐름 확인
- `/sim/visible_objects` 자동 publish 확인
- sim perception을 수동 좌표 입력 방식이 아니라 Isaac Sim prim path 기반 ground-truth 방식으로 전환 완료

## 현재 구성요소와 역할
- `mission_manager`
  - `/intent`를 받아 실제 mission 실행 흐름을 관리합니다.
  - `navigate`, `scan`, `find_object`, fallback, 종료를 담당합니다.
  - 현재 `find_object`는 현재 위치에서 먼저 제자리 회전 탐색(기본 10도 스텝으로 최대 1바퀴)을 수행한 뒤, 실패 시 fallback 위치로 이동합니다.
- `llm_command_router`
  - `/user_text`를 제한된 intent 또는 `mission_plan`으로 변환합니다.
  - 현재는 `rule_based`와 `llm` 두 모드를 모두 지원합니다.
  - `llm` 모드에서는 Ollama 기반 모델 호출 후, 실패 시 rule-based fallback이 가능합니다.
- `mission_plan`
  - 복합 명령을 JSON step list로 표현하는 임시 브리지 토픽입니다.
  - 현재 `navigate_to_named_place`, `find_object`, `scan_scene`, `cancel` step을 순차 실행할 수 있습니다.
  - step별 `run_if=always | previous_failed | previous_succeeded` 조건 실행을 지원합니다.
  - `찾고 없으면 center로 복귀` 유형 문장은 `failure_policy=return_home`로 정규화합니다.
- `llm_yolo_interfaces`
  - `Intent.msg`, `NavigateToPose.action`, `RotateInPlace.action`, `ScanScene.action`를 정의합니다.
- `go2_skill_server_sim`
  - sim backend action server입니다.
  - named place 이동, 회전, 스캔을 처리합니다.
  - 현재 navigation은 `direct`와 `nav2` 두 모드를 모두 지원합니다.
  - Nav2 모드에서도 `긴급 정지` / `정지 해제`가 동작하도록 연결되어 있습니다.
- `perception_node_sim`
  - `/sim/visible_objects`를 받아 `/perception/visible_objects`로 넘깁니다.
- `backends/real/*`
  - real 전환용 backend 영역입니다.

## 현재 유효한 설정
### Named place
파일: [sim_named_places.yaml](/home/jnu/llm_yolo/configs/sim/sim_named_places.yaml)

현재 유효한 named place는 `center` 하나입니다.

### Visible object
파일: [sim_visible_objects.json](/home/jnu/llm_yolo/configs/sim/sim_visible_objects.json)

현재 visible object는 아래 4개입니다.
- `red_box` -> `/World/ground/terrain/Box_B`
- `pink_box` -> `/World/ground/terrain/Pillar_1`
- `yellow_box` -> `/World/ground/terrain/Pillar_4`
- `blue_box` -> `/World/ground/terrain/Box_A`

### 자연어 라우팅 설정
파일: [llm_params.yaml](/home/jnu/llm_yolo/configs/common/llm_params.yaml)

현재 named place로 인식하는 이름은 `center`만 남겨 둔 상태입니다. 객체 클래스는 `chair`, `person`, `red_box`, `pink_box`, `yellow_box`, `blue_box`를 사용합니다.

### Fallback 설정
파일: [mission_params.yaml](/home/jnu/llm_yolo/configs/common/mission_params.yaml)

현재 `find_object` 실패 시 fallback 위치는 `center` 하나입니다.

## 현재 sim perception 방식
Isaac Sim 쪽 [go2_sim.py](/home/jnu/go2_sim/scripts/go2_sim.py)가 각 객체 prim의 world pose를 직접 읽고, 로봇과의 거리를 계산해서 `/sim/visible_objects`를 publish합니다. `llm_yolo`는 이 토픽을 받아 `scan_scene`와 `find_object`에 사용합니다.

현재 sim perception은 두 경로를 모두 지원합니다.
- ground-truth 경로: prim path 기반 `/sim/visible_objects`
- YOLO 경로: `camera/color/image_raw` 기반 Ultralytics 추론

현재 `chair 찾아`는 YOLO 기반으로 검증 완료된 상태입니다. 또한 `llm` 모드로 전환한 뒤 자연어 명령 해석 경로, `center로 가서 chair 찾아` 같은 2단계 복합 명령, `chair 찾고 없으면 center로 복귀` 같은 조건부 복귀 명령의 `mission_plan` 경로도 검증 완료된 상태입니다. 현재 `찾아` 명령은 현재 위치에서 먼저 제자리 회전 탐색(기본 10도 스텝으로 최대 1바퀴)을 수행하고, 그래도 실패하면 fallback으로 `center`를 사용합니다. 조건부 복귀 문장은 `find_object` step + `failure_policy=return_home`로 정규화됩니다.

## 빌드
```bash
cd /home/jnu/llm_yolo
source /opt/ros/humble/setup.bash
colcon build
source install/setup.bash
```

## 실행
### Isaac Sim
```bash
source /opt/ros/humble/setup.bash
export ROS_DISABLE_DAEMON=1
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=file:///home/jnu/llm_yolo/cyclonedds_local.xml
export ROS_DOMAIN_ID=0
export ROS_LOCALHOST_ONLY=0
conda activate isaaclab
cd /home/jnu/go2_sim
python -u /home/jnu/go2_sim/scripts/go2_sim.py
```

### llm_yolo
```bash
cd /home/jnu/llm_yolo
source /opt/ros/humble/setup.bash
source install/setup.bash
export ROS_DISABLE_DAEMON=1
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=file:///home/jnu/llm_yolo/cyclonedds_local.xml
export ROS_DOMAIN_ID=0
export ROS_LOCALHOST_ONLY=0
ros2 launch launch/sim/mvp_sim.launch.py
```

## 빠른 검증
상태 확인:
```bash
ros2 topic echo /mission_state
```

Named place 이동:
```bash
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'center 로 가'}"
```

객체 탐색:
```bash
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'red_box 찾아'}"
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'pink_box 찾아'}"
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'yellow_box 찾아'}"
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'chair 찾아'}"
```

복합 명령:
```bash
ros2 topic echo /mission_plan
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'center로 가서 chair 찾아'}"
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'chair 찾고 없으면 center로 돌아와'}"
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'chair 찾고 없으면 center로 복귀'}"
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'chair 찾고 없으면 center로 가서 다시 찾아'}"
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'yellow_box 찾고 없으면 red_box 찾아'}"
```

LLM 모드 사용 시에는 [llm_params.yaml](/home/jnu/llm_yolo/configs/common/llm_params.yaml) 의 `mode: llm`, `ollama_model: qwen2.5:latest`, `ollama_timeout_sec: 15.0` 과 Ollama 서버가 준비되어 있어야 합니다.

Visible object 확인:
```bash
ros2 topic echo /sim/visible_objects
```
