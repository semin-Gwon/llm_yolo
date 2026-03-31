# Unitree Go2 Edu - Sim 우선, Real 전환 가능한 MVP 구현 계획 (Practical MVP v1.5)

## 1. 목표
이 문서의 최우선 목표는 Unitree Go2 Edu용 MVP를 먼저 시뮬레이션 환경에서 안정적으로 동작시키고, 이후 동일한 상위 구조를 유지한 채 실기체 모드로 전환 가능하게 만드는 것이다.
핵심은 공통 미션/의도 해석 계층은 유지하고, sim과 real의 차이는 backend 계층으로 분리하는 것이다.

현재 개발 전제는 다음과 같다.
- MVP는 sim 모드에서 먼저 완성한다
- 상위 계층은 sim과 real에서 공통으로 사용한다
- 하드웨어/센서 의존 부분만 backend로 분리한다
- real 모드는 이후 동일 인터페이스 위에서 연결한다
- 실기체 연결 전에 sim에서 YOLO와 실제 LLM 연결까지 먼저 검증한다

---

## 2. MVP 범위
MVP에서 반드시 동작해야 하는 기능은 아래 다섯 가지다.

1. navigate_to_named_place
- 사전 등록된 실내 위치로 이동

2. rotate_in_place
- 제자리 회전

3. scan_scene
- 현재 위치에서 주변을 스캔하고 지정 객체가 보이는지 확인
- 현재 sim MVP에서는 회전 탐색을 포함한 scan 동작을 지원
- 현재 회전 탐색은 작은 각도 스텝(기본 10도)으로 잘게 나뉘어, 물체 검출 시 더 빠르게 멈출 수 있도록 조정됨

4. 제한된 find_object
- 현재 위치에서 먼저 찾고, 실패 시 가까운 named place 1~2곳만 이동 후 재시도
- 현재 위치 탐색은 제자리 회전 탐색(기본 10도 스텝으로 최대 1바퀴)을 포함

5. cancel / emergency_stop
- 사용자 취소와 안전 정지를 항상 우선 처리

MVP에서 제외하는 기능은 본문에 넣지 않고 문서 최하단 주석 섹션으로 분리한다.

---

## 3. 시스템 사양
- 운영체제: Ubuntu 22.04
- 미들웨어: ROS 2 Humble
- 로봇 플랫폼: Unitree Go2 Edu
- sim 환경: Isaac Sim 5.1.0
- sim 실행 환경: conda 기반 Python 환경 사용
- real 환경: Go2 + 유선 LAN 연결된 오프보드 PC
- 자연어 명령 해석기:
  - 현재 MVP: rule-based parser + Ollama 기반 LLM 경로 검증 완료
  - 현재 추가 상태: `mission_plan` 2단계 복합 명령 및 조건부 복귀 검증 완료
  - 다음 단계: `run_if` 기반 3단계 이상 복합 명령과 조건부 재시도 확장
  - 이후 단계: OpenRouter 기반 클라우드 LLM 경로 추가 및 로컬/클라우드 backend 분기
- 실시간 인지:
  - 현재 MVP: sim ground truth 기반 인지 + YOLO 경로 기본 검증 완료
  - 다음 단계: YOLO 경로 안정화 및 대상 클래스 확장
  - 이후 단계: VLM API 연동, YOLO + VLM 결합, open-vocabulary 실험
- 위치추정 / 주행:
  - 현재 MVP: direct `/cmd_vel` 기반 단순 목표 추종
  - 현재 구현: `navigate_to_pose_server`는 `navigation_mode: direct | nav2` 분기를 지원하고, 기본값은 `direct`
  - 현재 판단: sim localization 안정화 전까지 기본 모드는 `direct`를 유지하고 Nav2 모드는 보류
  - 장기 목표 상태: sim nav stack 또는 real localization/navigation stack

### 3.1. 기술 선택 원칙
- 개발 단계에서는 sim을 우선 사용
- mission_manager, llm router, interface는 sim/real 공통 유지
- skill server와 perception은 sim backend / real backend로 분리
- real 안전 정지와 명령 단절 대응은 real backend 단계에서 최소한으로 추가

### 3.2. Sim 우선 구현의 장점
- 하드웨어 없이 미션 흐름과 액션 계약을 먼저 검증 가능
- mission manager와 상태 전이 디버깅이 쉬움
- UI, launch, rosbag, 토픽 설계를 먼저 안정화 가능
- 실제 하드웨어 연결 전에 실패 지점을 많이 제거 가능

### 3.3. Sim으로 대체되지 않는 것
- 실제 Go2 통신 경로 검증
- 실제 stop/cancel/command timeout 검증
- 실제 센서 노이즈와 하드웨어 지연
- 실제 런타임 안정성

---

## 4. 현재 완료 상태
현재 sim 우선 MVP 기준으로 아래 항목은 구현 및 검증이 완료됐다.

- `center 로 가` 자연어 명령으로 named place 이동 검증 완료
- `red_box`, `pink_box`, `yellow_box`, `blue_box 찾아` 자연어 명령 검증 완료
- `chair 찾아` 자연어 명령의 YOLO 기반 검증 완료
- 실제 LLM 모드 전환 후 자연어 명령 해석 경로 검증 완료
- 실제 LLM 모드에서 `mission_plan` 2단계 복합 명령 생성 및 순차 실행 검증 완료
- 실제 LLM 모드에서 `찾고 없으면 center로 복귀` 조건부 복귀 명령 검증 완료
- 실제 LLM 모드에서 `run_if` 기반 조건 실행(`조건부 재시도`, `대체 대상 탐색`) 검증 완료
- `scan_scene` 단독 호출 및 `find_object` 경로 검증 완료
- `scan_scene`의 회전 탐색 방식 반영 완료
- `찾아` 명령 시 현재 위치에서 제자리 회전 탐색 후 fallback 이동하는 흐름 검증 완료
- `find_object` 실패 시 fallback 이동 후 종료 검증 완료
- `/sim/visible_objects` 자동 publish 검증 완료
- Isaac Sim prim path 기반 ground-truth perception 검증 완료
- `mission_manager -> action server -> result` 흐름 검증 완료
- 현재 navigation은 direct `/cmd_vel` 기반이 기본이며, Nav2 모드도 액션 이름 분리(`/llm_navigate_to_pose` vs `/navigate_to_pose`) 후 `center 로 가` 검증 완료
- Nav2 모드에서 `긴급 정지` / `정지 해제` 검증 완료

현재 유효한 운영 기준은 다음과 같다.
- named place는 `center` 하나만 사용
- visible object는 `red_box`, `pink_box`, `yellow_box`, `blue_box`
- fallback 위치는 `center`
- sim navigation 기본 모드는 `direct`
- Nav2 모드는 localization이 확보된 경우 선택적으로 활성화 가능하며, `center 로 가` 기준 기본 goal 전달 검증 완료
- Nav2 모드에서 `긴급 정지` / `정지 해제`도 확인 완료

---

## 5. Sim 우선 아키텍처

### 5.1. 공통 계층
1. mission_manager_node
- 명령 접수
- mission 실행/취소
- 재시도 및 timeout 처리

2. llm_command_router_node
- 자연어를 제한된 intent JSON으로 변환
- 현재 MVP는 rule-based parser를 기본값으로 사용
- 현재는 실제 Ollama LLM backend도 연결 가능하며 검증 완료
- 현재는 `/mission_plan` JSON 브리지를 통해 `run_if` 기반 복합 명령까지 실행 가능
- 현재는 `always`, `previous_failed`, `previous_succeeded` 조건 실행을 지원
- 정식 인터페이스 승격은 그 이후 검토

3. llm_yolo_interfaces
- Intent.msg
- NavigateToPose.action
- RotateInPlace.action
- ScanScene.action

### 5.2. Backend 분리 원칙
sim backend:
- go2_skill_server_sim
- perception_node_sim
- sim launch/config

real backend:
- go2_skill_server_real
- perception_node_real
- onboard_min_guard
- real launch/config

핵심 원칙:
- mission_manager는 backend를 몰라야 함
- sim과 real은 동일 action/interface를 사용해야 함
- launch에서 어떤 backend를 연결할지만 바꾼다

### 5.3. 제어권 우선순위
sim 모드:
1. emergency_stop
2. mission_manager_node
3. go2_skill_server_sim
4. llm_command_router_node

real 모드:
1. emergency_stop
2. onboard_min_guard 또는 real fail-safe
3. mission_manager_node
4. go2_skill_server_real
5. llm_command_router_node

LLM은 항상 실행 권한이 없고, intent 제안만 한다.

---

## 6. MVP 인터페이스

### 6.1. 허용 Intent
```json
{
  "intent": "navigate_to_named_place | find_object | scan_scene | cancel",
  "target": {
    "type": "named_place | object_class",
    "value": "string"
  },
  "constraints": {
    "max_duration_sec": 30
  },
  "confidence": 0.0
}
```

현재 추가 검증 상태:
- 단일 intent 외에 `mission_plan` JSON 브리지도 1차 동작 확인
- 검증 완료 문장: `center로 가서 chair 찾아`, `chair 찾고 없으면 center로 돌아와`, `chair 찾고 없으면 center로 복귀`, `chair 찾고 없으면 center로 가서 다시 찾아`, `yellow_box 찾고 없으면 red_box 찾아`

### 6.2. 명령 전달 방식
- LLM 또는 parser는 JSON 구조의 intent를 생성
- 실제 시스템 전달은 ROS 2 메시지 또는 action을 사용
- mission manager는 sim/real backend에 같은 action 계약으로 요청

### 6.3. Named Place 정책
- 현재 MVP에서는 `center`만 사용
- MVP에서는 자유 형식 좌표 입력 금지
- 위치마다 접근 반경과 기본 yaw를 저장

### 6.4. find_object 정책
MVP의 find_object는 아래 순서로만 동작한다.

1. 현재 위치에서 scan_scene 1회 수행
2. 이 scan_scene는 제자리 회전 탐색(기본 10도 스텝, 최대 1바퀴)을 포함
3. 객체를 찾지 못하면 fallback named place로 이동
4. 해당 위치에서 다시 scan_scene 수행
5. 그래도 실패하면 즉시 종료하고 실패 반환

금지 사항:
- 무제한 순회
- 전 맵 탐색
- 추적 모드 자동 진입

---

## 7. 노드별 최소 책임

### 7.1. mission_manager_node
- 새 명령 수신 시 현재 mission 상태 확인
- 실행 중이면 queue 또는 reject
- timeout 시 종료
- 실패 사유 기록
- backend를 직접 알지 않고 action server 호출만 담당

### 7.2. go2_skill_server_sim
- NavigateToPose.action
- RotateInPlace.action
- ScanScene.action
- sim 위치/상태 또는 mock 환경에 연결
- `ScanScene.action`은 현재 위치에서 perception 확인 후, 필요 시 `RotateInPlace.action`을 내부 호출하여 회전 탐색 수행
- success, abort, cancel 사유를 명확히 반환

### 7.3. go2_skill_server_real
- NavigateToPose.action
- RotateInPlace.action
- ScanScene.action
- 실제 Go2 제어 경로 또는 nav stack에 연결
- success, abort, cancel 사유를 명확히 반환

### 7.4. perception_node_sim
- 현재 MVP: sim object state 기반 객체 존재 여부 판단
- 현재는 prim path 기반 ground-truth adapter와 sim 카메라 + YOLO 경로를 둘 다 지원
- `chair` 클래스는 YOLO 기반 검증 완료
- 다음 단계에서 YOLO 경로 안정화와 대상 클래스 확장 진행

### 7.5. perception_node_real
- YOLO 기반 객체 존재 여부 판단
- MVP에서는 정교한 3D object association 필수 아님
- perception 결과는 FOUND | NOT_FOUND | UNCERTAIN 정도로 단순화 가능

### 7.6. llm_command_router_node
- 현재는 rule-based parser와 실제 LLM 모드를 둘 다 지원
- LLM 실패 시 rule-based fallback 가능
- 다음 단계: speed_hint 지원과 emergency_stop / clear 경로 추가
- 그 다음 단계: 복합 명령 schema 확장
- 자연어를 제한 intent로 변환
- timeout 시 NACK 반환
- 허용되지 않은 행동은 생성 금지

### 7.7. onboard_min_guard
- real 모드에서만 사용
- heartbeat 또는 command timeout 감시
- 명령 끊김 시 정지

---

## 8. 프로젝트 디렉토리 구조
아래 구조는 sim 우선 개발 후 real backend를 붙일 수 있도록 나눈 권장 예시다.

```text
llm_yolo/
├── plan.md
├── README.md
├── docs/
│   ├── architecture.md
│   ├── sim_mode.md
│   ├── real_mode.md
│   ├── named_places.md
│   └── test_scenarios.md
├── configs/
│   ├── common/
│   │   ├── named_places.yaml
│   │   ├── mission_params.yaml
│   │   └── llm_params.yaml
│   ├── sim/
│   │   ├── sim_named_places.yaml
│   │   ├── sim_visible_objects.json
│   │   ├── sim_nav_params.yaml
│   │   └── sim_perception_params.yaml
│   └── real/
│       ├── watchdog_params.yaml
│       ├── real_nav_params.yaml
│       └── real_perception_params.yaml
├── launch/
│   ├── common/
│   │   └── mission_stack.launch.py
│   ├── sim/
│   │   └── mvp_sim.launch.py
│   └── real/
│       ├── mvp_real.launch.py
│       └── onboard_min.launch.py
├── maps/
│   ├── sim/
│   └── real/
├── bags/
│   └── .gitkeep
├── scripts/
│   ├── run_sim.sh
│   ├── run_real.sh
│   ├── run_onboard_min.sh
│   ├── record_bag.sh
│   └── check_link.sh
├── llm_yolo_interfaces/
│   ├── package.xml
│   ├── CMakeLists.txt
│   ├── msg/
│   │   └── Intent.msg
│   └── action/
│       ├── NavigateToPose.action
│       ├── RotateInPlace.action
│       └── ScanScene.action
├── mission_manager/
├── llm_command_router/
├── backends/
│   ├── sim/
│   │   ├── go2_skill_server_sim/
│   │   └── perception_node_sim/
│   └── real/
│       ├── go2_skill_server_real/
│       ├── perception_node_real/
│       └── onboard_min_guard/
├── robot_bringup/
└── tests/
    ├── test_mission_manager.py
    ├── test_intent_parser.py
    ├── test_named_places.py
    └── test_deadman_stop.md
```

### 8.1. 디렉토리 구조 원칙
- 공통 계층과 backend 계층을 분리
- sim과 real은 launch와 config도 분리
- interface와 mission flow는 한 벌만 유지
- 실제 교체가 필요한 건 backend 디렉토리 안으로 한정

---

## 9. MVP 성공 기준
MVP는 아래 조건을 만족하면 성공으로 본다.

sim 기준:
- named place 이동 시퀀스가 반복적으로 성공할 것
- cancel이 항상 동작할 것
- scan_scene와 find_object가 종료 가능한 형태로 동작할 것
- 실패 시 무한 루프 없이 종료할 것
- sim perception 입력이 자동으로 publish될 것

real 기준:
- named place 이동이 반복적으로 성공할 것
- 정지해, 취소해가 항상 동작할 것
- 명령 단절 시 정지할 것
- 현재 위치 또는 가까운 1~2개 장소에서 지정 객체 탐색이 가능할 것

---

## 10. 구현 단계

### Phase 0. 공통 인터페이스와 흐름 고정
- llm_yolo_interfaces 정의
- mission_manager_node 구현
- llm_command_router_node 구현
- 공통 launch/config 구조 정리

상태: 완료

완료 조건:
- intent -> mission -> action 흐름이 시뮬레이터 없이도 검증 가능

### Phase 1. Sim backend 완성
- go2_skill_server_sim 구현
- perception_node_sim 구현
- sim launch 연결

상태: 완료

완료 조건:
- sim에서 navigate, scan, find_object, cancel 시퀀스가 동작

### Phase 2. Sim 기반 미션 검증
- named place 이동
- scan_scene
- find_object fallback 시퀀스
- abort/cancel 검증
- prim path 기반 visible object publish 검증
- scan_scene 회전 탐색 검증

상태: 완료

완료 조건:
- sim에서 MVP 시나리오를 반복 재현 가능

### Phase 3. Sim에서 실제 YOLO + 실제 LLM 연결
- perception_node_sim을 sim 카메라 입력 기반 YOLO로 확장
- llm_command_router_node를 실제 LLM backend에 연결
- ground-truth perception과 YOLO perception을 launch/config로 선택 가능하게 유지
- 현재 rule-based parser와 실제 LLM parser를 비교 검증

상태: 진행 중

현재 완료된 항목:
- YOLO 모드 perception_node_sim 구현
- `chair` 클래스 YOLO 기반 검증 완료
- 실제 LLM 모드 전환 및 자연어 명령 해석 검증 완료

남은 항목:
- LLM 경로 안정화
- YOLO 대상 클래스 확장 또는 custom object 학습 전략 정리
- 복합 명령용 schema 설계
- 기존 MVP 시나리오를 YOLO + LLM 경로 중심으로 재정리

완료 조건:
- sim에서 YOLO 기반 `scan_scene`가 반복적으로 동작
- sim에서 실제 LLM 기반 intent 생성이 반복적으로 동작
- 단일 명령뿐 아니라 확장 가능한 schema 기반으로 발전 가능한 구조가 확보될 것

### Phase 3.1. VLM 기반 의미 인지 확장
- sim 카메라 이미지를 입력으로 사용하는 VLM backend 경로 추가
- YOLO 결과를 VLM이 보조 검증하거나 장면 설명으로 보완하는 구조 설계
- `scan_scene` 실패 시 VLM 기반 semantic fallback 가능성 검토
- 텍스트 질의 기반 장면 설명과 의미론적 객체 확인 경로 추가

상태: 예정

세부 작업:
- VLM API 후보 선정 및 backend 추상화
- sim 이미지 입력 포맷과 질의/응답 포맷 정의
- YOLO 결과 + 원본 이미지 결합 입력 실험
- `find(object)` / `scan(area)`에서 VLM 보조 판단 조건 정의

완료 조건:
- sim에서 VLM 단독 장면 설명 호출 가능
- YOLO 결과를 VLM이 보조 설명/검증하는 경로 확인
- 최소 1개 시나리오에서 `scan_scene` 또는 `find_object` 보조 판단 검증

### Phase 3.2. OpenRouter 기반 클라우드 LLM 경로
- Ollama 외에 OpenRouter 기반 클라우드 LLM backend 추가
- 로컬(Ollama) / 클라우드(OpenRouter) backend를 launch/config로 선택 가능하게 유지
- 네트워크 실패, timeout, invalid JSON에 대한 fallback 정책 정리
- 보안 중요도가 낮은 sim 환경에서만 우선 검증

상태: 예정

세부 작업:
- OpenRouter API 설정 및 backend adapter 추가
- `llm_command_router`에서 backend 선택 파라미터 추가
- 로컬/클라우드 응답 형식 차이 보정
- fallback_to_rule_based / fallback_to_ollama 정책 정리

완료 조건:
- OpenRouter backend로 단일 명령 intent 생성 성공
- OpenRouter backend로 최소 1개 `mission_plan` 생성 성공
- backend 전환이 launch/config만으로 가능

### Phase 3.3. mission_plan 일반화
- 3단계 이상 순차 명령 지원
- `run_if` 기반 조건 실행(`always`, `previous_failed`, `previous_succeeded`) 추가
- `chair 찾고 없으면 center로 가서 다시 찾아` 같은 조건부 재시도 패턴 지원
- `red_box 찾고 없으면 yellow_box 찾아` 같은 대체 대상 패턴 지원
- LLM prompt와 후처리 정규화를 함께 확장

상태: 1차 구현 및 검증 완료

구현 순서:
- `mission_plan` step에 `run_if` 필드 추가
- LLM prompt에 3단계/조건부 재시도 예시 추가
- 후처리 규칙으로 대표 패턴을 정규화
- mission_manager가 `run_if`를 보고 step 실행 여부를 결정하도록 확장
- 3단계 이상 문장 세트로 반복 검증

완료 조건:
- `center로 가서 chair 찾고 person도 찾아` 처리 가능
- `chair 찾고 없으면 center로 가서 다시 찾아` 처리 가능
- `red_box 찾고 없으면 yellow_box 찾아` 처리 가능
- step 조건에 따라 불필요한 이동/탐색이 수행되지 않음

현재 검증 상태:
- `chair 찾고 없으면 center로 가서 다시 찾아`에서 실패 분기만 실행되는 것 확인
- `yellow_box 찾고 없으면 red_box 찾아`에서 대체 대상 탐색이 실행되는 것 확인
- `chair`를 바로 찾았을 때 실패 분기 step이 skip되는 것 확인

### Phase 3.25. Direct 주행 제어 확장
- `navigate_to_pose_server` direct 모드에 `speed_hint`(slow | normal | fast) 반영
- `Intent`/`mission_plan step`에 속도 힌트 전달 경로 추가
- rule-based / LLM 모두 속도 관련 자연어를 speed_hint로 정규화
- direct `/cmd_vel` 기반에서 latched `emergency_stop` / `emergency_clear` 경로 추가
- stop 상태에서는 현재 action 즉시 abort, `/cmd_vel=0` 강제, 새 mission reject

상태: 구현 및 검증 완료

구현 순서:
- `speed_hint` schema 추가
- router(rule-based + llm) 속도 파싱 추가
- mission_manager 전달 경로 확장
- direct navigation backend에 속도 스케일 반영
- `/emergency_stop`, `/emergency_clear` 토픽 추가
- mission_manager / navigate_to_pose_server / rotate_in_place_server에 latched stop 상태 반영
- 자연어 `긴급 정지`, `정지 해제` 연결

완료 조건:
- `center 로 가`, `천천히 center 로 가`, `빠르게 center 로 가`가 서로 다른 속도로 동작
- 이동 중 `emergency_stop=true` 시 즉시 정지
- stop 상태에서는 새 mission이 reject
- `emergency_clear=true` 후 다시 명령 수행 가능

현재 검증 상태:
- direct 모드에서 `speed_hint` 전달 경로 구현 완료
- `긴급 정지` / `정지 해제` 자연어 및 토픽 경로 구현 완료
- Nav2 모드에서도 `긴급 정지` / `정지 해제` 검증 완료

### Phase 3.5. Sim Nav2 전환
- sim Nav2 bringup 가능 여부 확인
- Nav2 입력으로 사용할 sim odom/tf/obstacle source 정리
- `navigate_to_pose_server`를 direct `/cmd_vel` 제어기에서 Nav2 goal bridge로 전환
- `mvp_sim.launch.py`와 Nav2 bringup launch를 함께 띄우는 구조 정리
- named place는 현재와 동일하게 유지하고, goal 전송 backend만 교체

상태: 보류

현재 구현 상태:
- `navigate_to_pose_server`는 `direct | nav2` 모드 분기를 지원
- `llm_yolo` 내부 액션 서버는 `/llm_navigate_to_pose`, Nav2는 기본 `/navigate_to_pose`를 사용
- 기본값은 `direct`이고, Nav2 모드는 localization 안정화 이후 활성화
- Nav2 모드에서 `center 로 가` 기준 action wiring 및 goal 전달 검증 완료

보류 사유:
- 현재 sim 환경의 RTAB-Map localization 품질이 intermittent하여 Nav2의 안정적 activation 전제 조건을 아직 만족하지 못함
- 따라서 현 단계에서는 direct `/cmd_vel` 기반 MVP를 유지하고, Nav2 전환은 sim 환경 feature 확장 또는 localization 안정화 이후에 재개함

재개 조건:
- sim에서 `map -> odom -> base_link` 경로가 안정적으로 유지될 것
- `/nav2_navigate_to_pose` action server가 반복적으로 active 상태를 유지할 것

완료 조건:
- `center로 가`가 Nav2 goal 경유로 동작
- Nav2 모드에서 `긴급 정지` / `정지 해제`가 동작
- 장애물이 있는 경로에서 direct `/cmd_vel`가 아니라 Nav2 planner/controller가 경로를 선택
- 상위 계층(`llm_command_router`, `mission_manager`, `mission_plan`) 수정은 최소화될 것

### Phase 3.6. 운영 가시화 및 통합 검증
- RViz2 기반 상태 모니터링과 최소 커스텀 패널 구성 검토
- mission / perception / navigation / safety 상태를 한 화면에서 확인 가능한 구조 정리
- 시나리오별 통합 테스트 세트와 기대 결과를 문서화
- 회귀 검증용 자연어 명령 세트 정리

상태: 예정

세부 작업:
- `/mission_state`, `/perception_debug`, nav 상태 토픽 시각화
- 주요 액션 상태 및 emergency 상태 표시
- 성공/실패/재시도/조건부 분기 테스트 세트 정리
- README / guide / test 문서 간 실행 절차 정합성 맞추기

완료 조건:
- 최소 1개 운영 모니터링 화면 또는 절차 문서 확보
- 핵심 시나리오 테스트 세트 문서화
- 기능 추가 후 재검증 절차가 일관되게 재사용 가능

### Phase 4. Real backend 연결
- go2_skill_server_real 구현
- perception_node_real 연결
- onboard_min_guard 연결
- real launch/config 연결

완료 조건:
- same mission flow가 real backend에서도 동작

### Phase 5. 실기체 검증
- stop/cancel/deadman 우선 검증
- 짧은 이동 검증
- scan_scene와 제한된 find_object 검증

완료 조건:
- real 모드에서 MVP 핵심 기능 검증 완료

### Phase 6. 배포 준비 및 엣지 최적화
- YOLO 계열 모델의 ONNX export 가능성 사전 검토
- 추후 TensorRT / Jetson 배포를 위한 입력/출력 인터페이스 정리
- sim2real 전환 시 latency 병목 지점 정리
- Ollama 경량화 또는 대체 경량 LLM 후보 검토

상태: 예정

세부 작업:
- 현재 perception 모델 export 경로 조사
- ONNX 변환 후 입력 shape / 후처리 경로 점검
- Jetson 환경 배포 시 필요한 dependency 목록 정리
- edge 배포 전제 조건과 제외 항목 문서화

완료 조건:
- 최소 1개 모델의 export 가능성 검토 결과 문서화
- 배포 전제 조건과 병목 목록 정리
- 실기체 배포 전 준비 항목이 계획에 고정됨

---

## 11. 개발 우선순위
1. sim MVP 완료 상태 유지
2. sim에서 YOLO 연결
3. sim에서 실제 LLM 연결
4. sim에서 YOLO + LLM 조합 검증
5. speed_hint 기반 속도 제어 추가
6. emergency_stop / emergency_clear 추가
7. mission_plan 일반화(`run_if`, 3단계 이상, 조건부 재시도)
8. VLM API 연동 및 YOLO + VLM 결합
9. OpenRouter 기반 클라우드 LLM 경로 추가
10. 운영 가시화 및 통합 테스트 체계화
11. sim 환경 feature 확장 및 localization 안정화
12. real backend 연결
13. 마지막에 real 하드웨어 세부 튜닝
14. Nav2 기반 goal bridge 전환은 localization 안정화 이후 재개

---

## 12. 결론
현재 단계의 핵심은 sim MVP를 끝낸 상태에서 바로 real로 넘어가는 것이 아니라, sim 안에서 YOLO와 실제 LLM까지 먼저 붙여 상위 기능 완성도를 높이는 것이다.
다만 Nav2 전환은 localization 안정화가 선행되어야 하므로, 현 단계에서는 direct `/cmd_vel` 기반 MVP를 유지한다.
단기 다음 우선순위였던 speed_hint 기반 속도 제어와 latched emergency_stop / clear 경로는 구현 및 검증이 완료됐다.
`mission_plan` 일반화 1차 구현과 검증도 완료됐으므로, 이제 다음 단계는 `VLM API 연동`, `YOLO + VLM 결합`, `OpenRouter 기반 클라우드 LLM 경로`, `운영 가시화/통합 테스트 체계화` 순서로 확장하는 것이다.
그 이후에 sim 환경 feature 확장 및 localization 안정화, 더 긴 복합 명령 확장을 진행한다.

---

## 주석: MVP 이후 단계
아래 항목들은 MVP 이후 확장 단계이며, 본문 구현 범위에서 제외한다.

- TrackObject.action
- VLM 기반 semantic disambiguation
- OpenRouter 기반 클라우드 LLM 세부 운영 정책
- LiDAR 기반 정교한 object association
- GOOD/DEGRADED/LOST 같은 정교한 perception quality state
- budget을 넓힌 다중 지점 탐색
- 사람 추적
- 자유 형식 목적지 생성
- 야외 운용
- 연속 VLM 스트리밍 분석
- RViz2 커스텀 운영 대시보드 고도화
- ONNX / TensorRT / Jetson 실배포 세부 튜닝
- 더 강한 온보드 autonomy 계층
- 카메라, 로봇 상태, LiDAR 간 정밀 시간 동기화 조정
