# llm_yolo

`llm_yolo`는 Unitree Go2용 sim-first ROS 2 MVP 프로젝트입니다. 현재 기준선은 Isaac Sim 5.1.0에서 먼저 동작시키는 것이고, 이후 같은 상위 구조를 유지한 채 real backend로 전환하는 것을 목표로 합니다.

## 프로젝트 진행 체크리스트 (Roadmap)

### ✅ 완료된 태스크 (Completed)
- [x] **Phase 0~2. 공통 인터페이스 및 Sim 기반 기초 미션 검증**
  - 공통 `mission_manager`, `llm_command_router` 베이스 구축
  - 자연어 `center 로 가` -> named place 이동 검증
  - 자연어 `red_box` 등 -> ground-truth 기반 객체 탐색 및 fallback 검증
  - `scan_scene` 제자리 회전 탐색 로직 및 취소/에러 흐름 검증
  - sim perception을 Isaac Sim prim path 기반 ground-truth로 전환 완료
- [x] **Phase 3. Sim 기반 실제 YOLO + 실제 LLM 연결**
  - `chair 찾아` -> YOLO 기반 탐지 검증 완료
  - 실제 LLM 모드 전환 후 자연어 명령 해석 검증 완료
- [x] **Phase 3.25. Direct 주행 제어 확장 및 안전 강화**
  - `speed_hint` 반영 (천천히, 빠르게 등 속도 조절)
  - `긴급 정지` 및 `정지 해제` (`emergency_stop`, `clear`) 기능 검증 완료 (Nav2 모드 포함)
- [x] **Phase 3.3. `mission_plan` 일반화 및 복합 명령 지원**
  - `run_if` 조건 실행 (`always`, `previous_failed` 등)
  - 3단계 이상 순차 명령 (`center로 가서 chair 찾고...`)
  - 조건부 재시도 및 대체 대상 탐색 (`chair 찾고 없으면 center로 복귀/다시 찾아`)

### ⬜ 진행 예정 태스크 (To-Do)
- [ ] **Phase 3.1. VLM API 연동 및 YOLO 보완** (의미론적 장면 설명 추가)
- [ ] **Phase 3.2. OpenRouter 기반 클라우드 LLM 연동** (오픈소스 로컬/클라우드 분기)
- [ ] **Phase 3.6. 운영 가시화 및 통합 테스트 체계화** (RViz2 대시보드 고도화)
- [ ] **Phase 3.5. Sim Nav2 기반 주행 전환** (현재는 localization 안정화 전까지 보류)
- [ ] **Phase 4~5. Real Backend 연결 및 실기체(Go2 하드웨어) 검증**
- [ ] **Phase 6. 배포 준비 및 엣지 최적화** (ONNX export 및 Jetson 배포 준비)

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

## 환경 설정 (YOLO venv Guide)
`llm_yolo` 프로젝트에서 YOLO 객체 탐지를 구동하기 위해서는 로컬 가상환경(`.venv_yolo`) 기반의 실행 환경 구성이 권장됩니다. 
> [!WARNING]
> Isaac Sim 컨테이너 실행에 쓰이는 `isaaclab` conda 가상환경과 본 ROS 2 패키지용 가상환경은 철저히 분리해서 사용해야 합니다.

**1. 파이썬 가상환경 생성 및 활성화**
```bash
cd /home/jnu/llm_yolo
python3 -m venv .venv_yolo
source .venv_yolo/bin/activate
```
*(에러 시 터미널에서 `sudo apt install python3.10-venv`를 먼저 설치하세요.)*

**2. YOLO 및 코어 의존성 패키지 설치**
터미널 프롬프트 앞에 `(.venv_yolo)`가 표시된 것을 확인하고 아래 패키지를 설치합니다.
```bash
python -m pip install --upgrade pip setuptools wheel
pip install pyyaml jinja2 typeguard
pip install torch torchvision torchaudio
pip install ultralytics==8.4.14
```

**3. 필수 환경 변수 Source 체계**
터미널을 새로 열어 `llm_yolo` 명령을 수행할 때는 항상 아래 순서대로 환경을 로드해야 정상 동작합니다.
```bash
cd /home/jnu/llm_yolo
source .venv_yolo/bin/activate
source /opt/ros/humble/setup.bash
source install/setup.bash
```

## 빌드
ROS 2 패키지 코드가 변경되면 가상환경 내에서 `colcon build` 명령을 통해 재빌드해야 반영됩니다. (외부 스크립트인 `go2_sim.py` 등은 재빌드가 필요 없습니다.)
```bash
cd /home/jnu/llm_yolo
source .venv_yolo/bin/activate
source /opt/ros/humble/setup.bash
colcon build
source install/setup.bash
```

## 실행
### Isaac Sim
```bash
source /opt/ros/humble/setup.bash
conda activate isaaclab
cd /home/jnu/go2_sim
python /home/jnu/go2_sim/scripts/go2_sim.py
```

### llm_yolo
```bash
cd /home/jnu/llm_yolo
source .venv_yolo/bin/activate
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch launch/sim/mvp_sim.launch.py
```

## 빠른 검증
상태 확인:
```bash
ros2 topic echo /mission_state
```

표준 모니터링:
```bash
/home/jnu/llm_yolo/scripts/monitor_sim.sh core
/home/jnu/llm_yolo/scripts/monitor_sim.sh perception
/home/jnu/llm_yolo/scripts/monitor_sim.sh object
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

객체 접근:
```bash
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'chair 앞으로 가'}"
```

LLM 모드 사용 시에는 [llm_params.yaml](/home/jnu/llm_yolo/configs/common/llm_params.yaml) 의 `mode: llm`, `ollama_model: qwen2.5:latest`, `ollama_timeout_sec: 15.0` 과 Ollama 서버가 준비되어 있어야 합니다.

Visible object 확인:
```bash
ros2 topic echo /sim/visible_objects
```

운영/회귀 기준 문서:
- [sim_mode.md](/home/jnu/llm_yolo/docs/sim_mode.md)
- [test_scenarios.md](/home/jnu/llm_yolo/docs/test_scenarios.md)
