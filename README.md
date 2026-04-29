# llm_yolo

> **Unitree Go2 Edu**를 위한 **Sim-First Agentic VLA 파이프라인** (ROS 2 Humble + Isaac Sim 5.1.0)  
> 자연어 명령 → LLM/Rule-Based 파싱 → Mission 실행 → YOLO 기반 Perception → Nav2 주행

---

## 🗺️ 시스템 개요

```
[자연어 입력] → llm_command_router → mission_manager → go2_skill_server_sim
                  (Rule-Based / LLM)       (Mission 흐름)    (Navigate / Scan / Approach)
                                                               ↕
                                                    perception_node_sim
                                                  (YOLO / Ground-Truth)
```

| 구성 요소 | 역할 |
|---|---|
| `llm_command_router` | `/user_text` 자연어를 Intent 또는 `mission_plan` JSON으로 변환 |
| `mission_manager` | Intent 수신 → Mission 실행/취소/재시도/Timeout 관리 |
| `go2_skill_server_sim` | NavigateToPose / RotateInPlace / ScanScene Action 서버 (Sim Backend) |
| `perception_node_sim` | YOLO 또는 Ground-Truth 기반 객체 탐지, `/perception/visible_objects` 발행 |
| `llm_yolo_interfaces` | Intent.msg / NavigateToPose.action / RotateInPlace.action / ScanScene.action 정의 |

---

## ✅ 현재 구현 완료 기능

- [x] Named Place 이동 (`center 로 가`)
- [x] 객체 탐색 + Scan 회전 탐색 (`chair 찾아`)
- [x] Ground-Truth Perception (Prim Path 기반)
- [x] YOLO 기반 Perception (`chair`, `tv`)
- [x] Ollama LLM 기반 자연어 해석
- [x] `mission_plan` 복합 명령 & 조건 실행 (`run_if`)
- [x] `approach_object` — YOLO + Depth + TF 기반 객체 접근
- [x] `speed_hint` 속도 조절 (천천히 / 빠르게)
- [x] 긴급 정지 / 정지 해제 (`emergency_stop`)
- [x] Nav2 / Direct 이중 주행 경로
- [x] Person 검출 기반 Pause / Resume

---

## 📋 요구 환경

| 항목 | 버전 |
|---|---|
| OS | Ubuntu 22.04 |
| ROS 2 | Humble |
| Python | 3.10 |
| Isaac Sim | 5.1.0 (conda `isaaclab` 환경) |
| YOLO | Ultralytics 8.4.14 |
| LLM (선택) | Ollama + `qwen2.5:latest` |

---

## ⚙️ 최초 환경 설정

> [!WARNING]
> Isaac Sim용 `isaaclab` conda 환경과 llm_yolo용 `.venv_yolo` Python 가상환경은 **반드시 분리**하여 사용하세요.

### 1. Python 가상환경 생성

```bash
cd /home/jnu/llm_yolo
python3 -m venv .venv_yolo
source .venv_yolo/bin/activate
```

> 오류 발생 시: `sudo apt install python3.10-venv`

### 2. 의존성 패키지 설치

```bash
python -m pip install --upgrade pip setuptools wheel
pip install pyyaml jinja2 typeguard
pip install torch torchvision torchaudio
pip install ultralytics==8.4.14
```

### 3. ROS 2 패키지 빌드

```bash
cd /home/jnu/llm_yolo
source .venv_yolo/bin/activate
source /opt/ros/humble/setup.bash
colcon build
source install/setup.bash
```

---

## 🚀 실행 방법

### 1단계 — Isaac Sim 실행

```bash
source /opt/ros/humble/setup.bash
conda activate isaaclab
python /home/jnu/go2_sim/scripts/go2_sim.py
```

### 2단계 — llm_yolo 스택 실행 (새 터미널)

```bash
cd /home/jnu/llm_yolo
source .venv_yolo/bin/activate
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch launch/sim/mvp_sim.launch.py
```

> [!NOTE]
> 코드 변경 후에는 항상 `colcon build && source install/setup.bash`를 먼저 실행하세요.

---

## 💬 명령어 가이드

### 기본 명령

```bash
# Named Place 이동
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'center 로 가'}"

# 속도 조절 이동
ros2 topic pub --once /user_text std_msgs/msg/String "{data: '천천히 center 로 가'}"
ros2 topic pub --once /user_text std_msgs/msg/String "{data: '빠르게 center 로 가'}"
```

### 객체 탐색

```bash
# YOLO 기반 객체 탐색 (현재 운영 클래스: chair, tv)
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'chair 찾아'}"
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'tv 찾아'}"
```

### 객체 접근 (Approach)

```bash
# YOLO + Depth + TF 기반 객체 위치 추정 후 접근
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'chair 앞으로 가'}"
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'tv 앞으로 가'}"
```

### 복합 명령 (mission_plan)

```bash
# 순차 실행
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'center로 가서 chair 찾아'}"

# 조건부 복귀 (찾지 못하면 돌아오기)
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'chair 찾고 없으면 center로 돌아와'}"
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'chair 찾고 없으면 center로 복귀'}"

# 조건부 재시도 (이동 후 다시 탐색)
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'chair 찾고 없으면 center로 가서 다시 찾아'}"

# 대체 대상 탐색
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'yellow_box 찾고 없으면 red_box 찾아'}"
```

### 안전 제어

```bash
# 긴급 정지
ros2 topic pub --once /user_text std_msgs/msg/String "{data: '긴급 정지'}"

# 정지 해제 (이후 명령 다시 수행 가능)
ros2 topic pub --once /user_text std_msgs/msg/String "{data: '정지 해제'}"
```

---

## 🔍 상태 모니터링

### 핵심 토픽 확인

```bash
# Mission 상태 확인
ros2 topic echo /mission_state

# Visible Object 목록 확인 (Ground-Truth)
ros2 topic echo /sim/visible_objects

# Perception 결과 확인
ros2 topic echo /perception/visible_objects

# 객체 Pose 추정 결과 확인 (approach_object용)
ros2 topic echo /perception/object_poses

# 긴급 정지 상태 확인
ros2 topic echo /emergency_stop

# mission_plan 수신 확인 (복합 명령)
ros2 topic echo /mission_plan
```

### 표준 모니터링 스크립트

```bash
# 미션/주행/안전 상태 통합 모니터링
/home/jnu/llm_yolo/scripts/monitor_sim.sh core

# Perception 상태 모니터링
/home/jnu/llm_yolo/scripts/monitor_sim.sh perception

# 객체 Pose 모니터링
/home/jnu/llm_yolo/scripts/monitor_sim.sh object
```

---

## ⚙️ 주요 설정 파일

| 파일 | 설명 |
|---|---|
| [`configs/sim/sim_named_places.yaml`](configs/sim/sim_named_places.yaml) | Named Place 좌표 정의 (현재: `center` 1개) |
| [`configs/sim/sim_visible_objects.json`](configs/sim/sim_visible_objects.json) | Ground-Truth 객체와 Prim Path 매핑 |
| [`configs/common/llm_params.yaml`](configs/common/llm_params.yaml) | LLM 모드 / 모델 / Timeout 설정 |
| [`configs/common/mission_params.yaml`](configs/common/mission_params.yaml) | Fallback 위치 등 Mission 파라미터 |

### LLM 모드 전환

`configs/common/llm_params.yaml` 수정:

```yaml
mode: llm            # "rule_based" (기본) 또는 "llm" (Ollama 사용)
ollama_model: qwen2.5:latest
ollama_timeout_sec: 15.0
```

> [!NOTE]
> `llm` 모드 사용 시 Ollama 서버가 미리 실행 중이어야 합니다.
> ```bash
> ollama run qwen2.5:latest
> ```

### 주행 모드 전환

`launch/sim/mvp_sim.launch.py` 내 파라미터 수정:

```yaml
navigation_mode: nav2    # "nav2" (기본) 또는 "direct" (cmd_vel 직접 제어)
```

---

## 🗂️ 운영 현황

### Named Place

현재 운영 Named Place: **`center` 1개**

### YOLO 운영 객체 클래스

| 클래스 | 탐지 | Pose 추정 | 접근 |
|---|---|---|---|
| `chair` | ✅ | ✅ | ✅ |
| `tv` | ✅ | ✅ | ✅ |

---

## 🔁 회귀 테스트 시나리오

아래 명령으로 핵심 기능 회귀 검증을 수행합니다.

```bash
# 1. Named Place 이동
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'center 로 가'}"
# 기대: navigate requested → navigate completed

# 2. 객체 탐색 (YOLO)
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'chair 찾아'}"
# 기대: scan requested → find_object success 또는 fallback 종료

# 3. 조건부 복귀 (찾으면 복귀 skip)
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'chair 찾고 없으면 center로 복귀'}"
# 기대: 탐색 실패 시에만 복귀 step 실행

# 4. 조건부 재시도
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'chair 찾고 없으면 center로 가서 다시 찾아'}"
# 기대: 첫 탐색 실패 시에만 이동 + 재탐색 실행

# 5. 대체 대상 탐색
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'yellow_box 찾고 없으면 red_box 찾아'}"
# 기대: 첫 대상 실패 후 red_box 탐색으로 전환 (즉시 abort 아님)

# 6. 객체 접근
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'chair 앞으로 가'}"
# 기대: YOLO bbox → pose 추정 → goal 생성 → 접근 이동

# 7. 긴급 정지 / 정지 해제
ros2 topic pub --once /user_text std_msgs/msg/String "{data: '긴급 정지'}"
ros2 topic pub --once /user_text std_msgs/msg/String "{data: '정지 해제'}"
# 기대: 정지 → reject → 해제 후 명령 재수행 가능
```

---

## 📁 디렉토리 구조

```
llm_yolo/
├── configs/
│   ├── common/          # llm_params.yaml, mission_params.yaml, named_places.yaml
│   └── sim/             # sim_named_places.yaml, sim_visible_objects.json
├── launch/
│   ├── common/          # mission_stack.launch.py
│   └── sim/             # mvp_sim.launch.py
├── backends/
│   ├── sim/             # go2_skill_server_sim, perception_node_sim
│   └── real/            # go2_skill_server_real (예정), perception_node_real (예정)
├── llm_yolo_interfaces/ # Intent.msg, NavigateToPose/RotateInPlace/ScanScene.action
├── mission_manager/
├── llm_command_router/
├── scripts/             # monitor_sim.sh, record_bag.sh
├── docs/                # sim_mode.md, test_scenarios.md, architecture.md
├── maps/
├── bags/
└── tests/
```

---

## 📚 참고 문서

| 문서 | 설명 |
|---|---|
| [`docs/sim_mode.md`](docs/sim_mode.md) | Sim 모드 운영 가이드 |
| [`docs/test_scenarios.md`](docs/test_scenarios.md) | 테스트 시나리오 및 Pass/Fail 기준 |
| [`plan.md`](plan.md) | 전체 구현 계획 및 우선순위 |
| [`progress.md`](progress.md) | 완료 이력 |

---

## 🛣️ 다음 단계 (Roadmap)

| Phase | 내용 | 상태 |
|---|---|---|
| Phase 4-2 | 객체 탐색/접근 일반화 (`find → approach` 통합 시나리오) | 🔴 최우선 |
| Phase 4-3 | 속성 기반 개체 선택 (`가까운 chair`, `먼 tv`) | 예정 |
| Phase 4-4 | Person 대응 정책 고도화 | 고도화 예정 |
| Phase 4-5 | VLM 기반 의미 인지 (장면 설명 계층) | 후순위 |
| Phase 4-6 | OpenRouter 클라우드 LLM 경로 | 후순위 |
| Phase 5 | Real Backend 연결 (Go2 실기체) | 예정 |
| Phase 6 | 실기체 검증 | 예정 |
| Phase 7 | ONNX Export / Jetson 배포 준비 | 예정 |
