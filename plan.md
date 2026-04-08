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

문서 운영 규칙:
- `plan.md`는 앞으로의 계획, 우선순위, 리스크, 완료 조건만 관리한다
- 구현 및 검증이 완료된 항목은 `plan.md`에서 제거하고 [progress.md](/home/jnu/llm_yolo/progress.md)에 순서대로 기록한다
- 진행 중인 phase에는 완료 이력 대신 남은 작업과 완료 조건만 유지한다

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
  - 현재 추가 상태: `approach_object` intent와 perception 기반 객체 접근 경로 1차 검증 완료
  - 다음 단계: 객체 탐색/접근 일반화와 person 대응 정책 확장
  - 이후 단계: OpenRouter 기반 클라우드 LLM 경로 추가 및 로컬/클라우드 backend 분기
- 실시간 인지:
  - 현재 MVP: sim ground truth 기반 인지 + YOLO 경로 기본 검증 완료
  - 현재 추가 상태: YOLO bbox + depth + TF 기반 객체 위치 추정 1차 검증 완료
  - 다음 단계: 객체 pose 추정 안정화와 대상 클래스 확장
  - 이후 단계: VLM API 연동, YOLO + VLM 결합, open-vocabulary 실험
- 위치추정 / 주행:
  - 현재 MVP: Nav2 기반 goal 전달을 우선 검증 경로로 사용
  - 현재 구현: `navigate_to_pose_server`는 `navigation_mode: direct | nav2` 분기를 지원하고, 기본값은 `nav2`
  - 현재 판단: direct `/cmd_vel` 기반 경로는 fallback/비교용으로 유지하고, Nav2는 우선 검증 경로로 사용
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

## 4. 현재 운영 기준
- named place는 `center` 하나만 사용
- visible object는 `red_box`, `pink_box`, `yellow_box`, `blue_box`
- fallback 위치는 `center`
- sim navigation은 Nav2를 우선 검증 경로로 사용
- direct `/cmd_vel` 경로는 fallback/비교용으로 유지
- 완료된 구현 및 검증 이력은 [progress.md](/home/jnu/llm_yolo/progress.md)에서 관리

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
- 실제 Ollama LLM backend를 사용할 수 있어야 함
- `/mission_plan` JSON 브리지를 통해 `run_if` 기반 복합 명령을 지원해야 함
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
  "intent": "navigate_to_named_place | find_object | approach_object | scan_scene | cancel",
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

현재 추가 범위:
- 단일 intent 외에 `mission_plan` JSON 브리지를 통한 복합 명령을 지원

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

### 6.5. approach_object 정책
`approach_object`는 perception으로 추정한 객체 위치를 기준으로 접근 목표를 생성해 이동한다.

동작 순서:
1. 대상 객체가 현재 perception 결과에 존재하는지 확인
2. YOLO bbox + depth + camera_info로 객체의 3D 위치를 추정
3. TF를 사용해 객체 위치를 `map` 또는 `odom` 기준 좌표로 변환
4. 객체 중심으로부터 일정 오프셋을 둔 접근 goal pose를 생성
5. 해당 goal pose로 navigation 수행

원칙:
- 사람이 좌표를 읽어 넣는 방식은 사용하지 않음
- sim에서도 perception 기반 추정을 기본 구조로 사용
- ground-truth prim pose는 비교/디버그용 참고 경로로만 유지 가능

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
- 다음 단계에서 YOLO bbox raw 출력, depth 결합, 객체 위치 추정 경로 추가
- 그 이후 YOLO 경로 안정화와 대상 클래스 확장 진행

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

### Phase 1. 공통 인터페이스와 흐름 고정
- llm_yolo_interfaces 정의
- mission_manager_node 구현
- llm_command_router_node 구현
- 공통 launch/config 구조 정리

상태: 완료

완료 조건:
- intent -> mission -> action 흐름이 시뮬레이터 없이도 검증 가능

### Phase 2. Sim backend 완성
- go2_skill_server_sim 구현
- perception_node_sim 구현
- sim launch 연결

상태: 완료

완료 조건:
- sim에서 navigate, scan, find_object, cancel 시퀀스가 동작

### Phase 3. Sim 기반 미션 검증
- named place 이동
- scan_scene
- find_object fallback 시퀀스
- abort/cancel 검증
- prim path 기반 visible object publish 검증
- scan_scene 회전 탐색 검증

상태: 완료

완료 조건:
- sim에서 MVP 시나리오를 반복 재현 가능

### Phase 4. Sim에서 실제 YOLO + 실제 LLM 연결
- perception_node_sim을 sim 카메라 입력 기반 YOLO로 확장
- llm_command_router_node를 실제 LLM backend에 연결
- ground-truth perception과 YOLO perception을 launch/config로 선택 가능하게 유지
- 현재 rule-based parser와 실제 LLM parser를 비교 검증
- core 안정화와 운영/통합 검증(Phase 4-10)은 병행할 수 있으나, 4-10은 회귀 방지와 관측 가능성 확보 목적에 가깝다

상태: core 구현 및 1차 검증 완료, 안정화/확장 항목 잔존

남은 항목:
- LLM 경로 안정화
- YOLO 대상 클래스 확장 또는 custom object 학습 전략 정리
- 기존 MVP 시나리오를 YOLO + LLM 경로 중심으로 재정리

완료 조건:
- sim에서 YOLO 기반 `scan_scene`가 반복적으로 동작
- sim에서 실제 LLM 기반 intent 생성이 반복적으로 동작
- 단일 명령뿐 아니라 확장 가능한 schema 기반으로 발전 가능한 구조가 확보될 것

### Phase 4-1. Perception 기반 객체 접근
- `approach_object` intent 추가
- `chair 앞으로 가` 같은 명령을 perception 기반으로 처리
- YOLO bbox + depth + camera_info + TF를 사용해 객체 위치를 직접 추정
- 추정된 객체 위치를 기준으로 접근 goal pose를 생성
- 생성된 goal pose를 기존 navigation backend(direct 또는 nav2)에 전달

상태: 1차 구현 및 검증 완료

원칙:
- 사람이 sim에서 객체 좌표를 읽어 수동 입력하는 방식은 사용하지 않음
- sim에서도 real로 이어질 수 있도록 perception 기반 추정 구조를 채택
- ground-truth prim pose는 upper bound 비교 또는 디버그용으로만 제한

완료 조건:
- `chair 앞으로 가`와 동등한 명령이 perception 기반으로 goal pose를 생성할 수 있음
- 생성된 goal pose가 `map` 또는 `odom` 기준으로 확인 가능
- 객체가 보이는 상태에서 접근 목표 생성과 이동이 재현 가능
- 이 경로가 사람 수동 좌표 입력 없이 동작

남은 항목:
- 접근 정확도 튜닝
- 더 많은 객체 클래스에 대한 pose 추정 안정화
- typed message 승격 여부 검토

### Phase 4-2. 객체 탐색/접근 일반화
- `approach_object`를 `chair` 단일 시나리오에서 더 넓은 맵/더 다양한 객체로 확장
- `find_object -> object pose 추정 -> approach_object` 흐름을 하나의 운영 시나리오로 재검증
- 접근 거리, 접근 yaw, 접근 실패 조건을 객체 종류별로 조정 가능한 구조로 정리
- fallback 탐색 후 pose 재획득과 접근 재시도 흐름을 정리

상태: 최우선순위

세부 작업:
- 현재 운영 객체 목록(`chair`, `tv`) 기준으로 탐지/pose 추정/접근 경로를 안정화
- `chair`, `tv`에 대해 `/perception/object_poses`가 반복적으로 안정적으로 나오는지 검증
- `couch`, `dining table`, `bed`는 후속 perception 모델 변경 또는 튜닝 전까지 운영 대상에서 제외
- bbox 중심 depth 기반 pose 추정의 노이즈/오차 특성을 클래스별로 정리
- 접근 거리와 최종 yaw를 클래스별 파라미터로 분리
- `chair 찾아서 앞으로 가`, `tv 찾아서 앞으로 가` 같은 `find -> approach` 시나리오를 `mission_plan`으로 연결
- fallback 탐색 후 재획득한 객체에 대해서도 pose 재추정과 접근이 이어지는지 검증
- 넓은 맵에서 탐색 후 접근까지의 통합 시나리오와 실패 조건을 문서화

완료 조건:
- `chair`, `tv` 두 클래스에서 pose 추정과 접근이 반복 재현 가능
- `찾고 -> 접근` 흐름이 동일한 mission 경로에서 반복 동작
- 접근 거리와 yaw가 config로 조정 가능
- 객체가 보이는 상태와 fallback 후 재획득 상태 모두에서 접근 가능
- 현재 후보 클래스 중 어떤 클래스가 `운영 가능`, `추가 튜닝 필요`, `현재 제외`인지 표 형태로 정리 가능

### Phase 4-3. 속성 기반 개체 선택
- 동일 클래스 객체가 여러 개 있을 때 `가장 가까운 것` 외의 기준으로 대상을 선택할 수 있게 확장
- `가까운 chair`, `먼 chair` 같은 표현을 처리
- 현재 클래스 기반 접근 구조 위에 후보 속성 계산과 disambiguation layer를 추가

상태: 예정

세부 작업:
- 객체 후보별 속성 계산 경로 추가
  - 상대 거리(`near` / `far`)
- 자연어 parser / LLM schema에 object qualifier 추가
- 여러 후보 중 qualifier에 가장 잘 맞는 대상을 고르는 ranking 로직 추가
- qualifier가 없을 때는 현재와 동일하게 기본 선택 정책(가장 가까운 후보) 유지
- 1차 범위는 관계 기반 표현(`문 옆`, `테이블 앞`), 색 기반 표현, 좌우/크기 구분을 제외하고 거리 속성부터 지원

완료 조건:
- 같은 클래스 객체가 2개 이상 있을 때 `near/far` 기반 선택 가능
- qualifier가 없는 기존 명령은 회귀 없이 기존 정책으로 동작
- `chair 앞으로 가`와 `가까운 chair 앞으로 가`가 회귀 없이 동작

### Phase 4-4. Person 대응 및 동적 객체 정책
- `person` 검출 시 로봇이 취할 안전 정책을 추가
- 기본 장애물 회피는 navigation stack이 담당하고, 사람 검출은 상위 안전 트리거로 사용
- `pause`, `emergency_stop`, `approach 중단` 중 어떤 정책을 언제 쓸지 정리
- 사람 검출 시 미션 지속/중단/재개 조건을 정의

상태: 1차/2차 구현 및 검증 완료, 추가 고도화 항목만 남음

세부 작업:
- 사람 검출 시 `pause`와 `emergency_stop` 정책 분리 유지
- 접근 중 사람 개입 시 현재 goal hold / resume 정책 추가 고도화
- person pose 기반 거리 조건과 히스테리시스 조건 추가 튜닝
- 필요 시 시야 중심/경로 전방 기준 추가

완료 조건:
- 이동 또는 접근 중 `person` 검출 시 정책에 맞게 멈춤 또는 중단
- 사람 사라짐 이후 재개 정책이 일관되게 동작
- `person` 대응이 기존 mission 흐름을 깨지 않음

### Phase 4-5. VLM 기반 의미 인지 확장
- sim 카메라 이미지를 입력으로 사용하는 VLM backend 경로 추가
- 1차 범위는 장면 설명과 질의응답 기반의 설명 전용 계층으로 제한
- YOLO 결과를 VLM이 설명 텍스트로 보완하는 구조만 우선 검토
- `scan_scene` / `find_object`의 결정 로직에는 즉시 연결하지 않음
- 1차 단계에서는 `mission_manager`, `scan_scene`, `find_object`의 성공/실패 판정에 VLM 결과를 사용하지 않음
- 1차 단계의 VLM 출력은 debug / observability 용도로만 소비하며, mission 실행 경로의 의사결정에는 사용하지 않음
- 텍스트 질의 기반 장면 설명과 의미론적 객체 확인 경로 추가
- **[아키텍처 제언]** VLM API의 높은 네트워크 Latency(수 초)로 인한 메인 스레드 블로킹 방지를 위해, 해당 계층을 반드시 **비동기(Async) 액션 서버 구조**로 설계할 것

상태: 후순위

세부 작업:
- VLM API 후보 선정 및 backend 추상화
- sim 이미지 입력 포맷과 질의/응답 포맷 정의
- YOLO 결과 + 원본 이미지 결합 입력 실험
- 설명 전용 출력 토픽(`/vlm/scene_description`, `/vlm/answers`) 정의
- periodic 호출이 아니라 manual trigger 또는 저주기 호출을 기본값으로 설계
- 비용/지연 완화를 위한 cache, rate limit, timeout 정책 정의
- decision path 연결은 2차 단계로 유보

완료 조건:
- sim에서 VLM 단독 장면 설명 호출 가능
- YOLO 결과를 VLM이 보조 설명하는 경로 확인
- 최소 1개 시나리오에서 장면 설명과 질의응답이 재현 가능

### Phase 4-6. OpenRouter 기반 클라우드 LLM 경로
- Ollama 외에 OpenRouter 기반 클라우드 LLM backend 추가
- 로컬(Ollama) / 클라우드(OpenRouter) backend를 launch/config로 선택 가능하게 유지
- 네트워크 실패, timeout, invalid JSON에 대한 fallback 정책 정리
- 보안 중요도가 낮은 sim 환경에서만 우선 검증

상태: 예정

비고:
- VLM 1차와 운영/통합 검증 체계 정리가 끝난 뒤에 착수
- backend matrix 확장에 따른 회귀 리스크를 줄이기 위해 우선순위를 낮춤

세부 작업:
- OpenRouter API 설정 및 backend adapter 추가
- `llm_command_router`에서 backend 선택 파라미터 추가
- 로컬/클라우드 응답 형식 차이 보정
- fallback_to_rule_based / fallback_to_ollama 정책 정리
- API key 주입 경로와 기본 비활성 상태 유지
- 네트워크 불능 시 클라우드 경로를 자동 강등하거나 명시적으로 비활성화하는 정책 정리

완료 조건:
- OpenRouter backend로 단일 명령 intent 생성 성공
- OpenRouter backend로 최소 1개 `mission_plan` 생성 성공
- backend 전환이 launch/config만으로 가능
- timeout / invalid JSON / fallback 경로가 기존 Ollama 경로를 깨지 않고 동작
- 기본값이 로컬 경로를 유지하고, 실수로 클라우드 호출이 기본 활성화되지 않음

### Phase 4-7. mission_plan 일반화
- 3단계 이상 순차 명령 지원
- `run_if` 기반 조건 실행(`always`, `previous_failed`, `previous_succeeded`) 추가
- `chair 찾고 없으면 center로 가서 다시 찾아` 같은 조건부 재시도 패턴 지원
- `red_box 찾고 없으면 yellow_box 찾아` 같은 대체 대상 패턴 지원
- LLM prompt와 후처리 정규화를 함께 확장

상태: 1차 구현 및 검증 완료

완료 조건:
- `center로 가서 chair 찾고 person도 찾아` 처리 가능
- `chair 찾고 없으면 center로 가서 다시 찾아` 처리 가능
- `red_box 찾고 없으면 yellow_box 찾아` 처리 가능
- step 조건에 따라 불필요한 이동/탐색이 수행되지 않음

### Phase 4-8. Direct 주행 제어 확장
- `navigate_to_pose_server` direct 모드에 `speed_hint`(slow | normal | fast) 반영
- `Intent`/`mission_plan step`에 속도 힌트 전달 경로 추가
- rule-based / LLM 모두 속도 관련 자연어를 speed_hint로 정규화
- direct `/cmd_vel` 기반에서 latched `emergency_stop` / `emergency_clear` 경로 추가
- stop 상태에서는 현재 action 즉시 abort, `/cmd_vel=0` 강제, 새 mission reject

상태: 구현 및 검증 완료

완료 조건:
- `center 로 가`, `천천히 center 로 가`, `빠르게 center 로 가`가 서로 다른 속도로 동작
- 이동 중 `emergency_stop=true` 시 즉시 정지
- stop 상태에서는 새 mission이 reject
- `emergency_clear=true` 후 다시 명령 수행 가능

비고:
- `speed_hint`의 실질 반영은 direct 모드에서 가장 명확함
- Nav2 모드에서는 현재 goal 전달 구조상 속도 힌트 활용이 제한적이며, 추후 controller 파라미터 연계가 필요함

### Phase 4-9. Sim Nav2 전환
- sim Nav2 bringup 가능 여부 확인
- Nav2 입력으로 사용할 sim odom/tf/obstacle source 정리
- `navigate_to_pose_server`를 direct `/cmd_vel` 제어기에서 Nav2 goal bridge로 전환
- `mvp_sim.launch.py`와 Nav2 bringup launch를 함께 띄우는 구조 정리
- named place는 현재와 동일하게 유지하고, goal 전송 backend만 교체

상태: 구조 검증 완료, 기본 실험 경로

현재 판단:
- 액션 wiring, 기본 goal 전달, stop/clear까지 구조 검증은 완료
- localization 품질은 추가 안정화가 필요하며, 현 시점의 Nav2는 기본 실험 경로로 유지
- direct `/cmd_vel` 경로는 localization 문제가 심해질 때의 fallback/비교 기준으로 남겨둠

완료 조건:
- `center로 가`가 Nav2 goal 경유로 동작
- Nav2 모드에서 `긴급 정지` / `정지 해제`가 동작
- 장애물이 있는 경로에서 direct `/cmd_vel`가 아니라 Nav2 planner/controller가 경로를 선택
- 상위 계층(`llm_command_router`, `mission_manager`, `mission_plan`) 수정은 최소화될 것

### Phase 4-10. 운영 가시화 및 통합 검증
- RViz2 기반 상태 모니터링과 최소 커스텀 패널 구성 검토
- mission / perception / navigation / safety 상태를 한 화면에서 확인 가능한 구조 정리
- 시나리오별 통합 테스트 세트와 기대 결과를 문서화
- 회귀 검증용 자연어 명령 세트 정리

상태: 문서화 / 모니터링 / 대표 회귀 시나리오 실검증 완료

세부 작업:
- `/mission_state`, `/perception_debug`, nav 상태 토픽 시각화
- 주요 액션 상태 및 emergency 상태 표시
- 성공/실패/재시도/조건부 분기 테스트 세트 정리
- README / guide / test 문서 간 실행 절차 정합성 맞추기

완료 조건:
- 최소 1개 운영 모니터링 화면 또는 절차 문서 확보
- 핵심 시나리오 테스트 세트 문서화
- 기능 추가 후 재검증 절차가 일관되게 재사용 가능
- README / sim_mode / test_scenarios / helper script 간 절차 불일치가 없어야 함

최소 산출물:
- 표준 모니터 토픽 목록 고정
  - `/mission_state`
  - `/perception_debug`
  - `/navigate_to_pose/_action/status` 또는 Nav2 상태에 준하는 관측 경로
  - `/emergency_stop`
- 회귀 테스트 자연어 명령 세트 5~10개 고정
- 각 명령별 기대 상태 전이와 성공/실패 판정 기준 문서화

대표 회귀 시나리오:
- `center 로 가`
- `chair 찾아`
- `chair 찾고 없으면 center로 복귀`
- `chair 찾고 없으면 center로 가서 다시 찾아`
- `yellow_box 찾고 없으면 red_box 찾아`

대표 시나리오 pass/fail 기준:
- `center 로 가`: `navigate requested` 이후 `navigate completed`가 도달해야 함
- `chair 찾아`: `scan requested` 이후 `find_object success` 또는 정책에 맞는 최종 실패가 일관되게 나와야 함
- `chair 찾고 없으면 center로 복귀`: `find_object` 실패 후 `return_home` 경로만 실행되고, 성공 시 복귀 step은 실행되지 않아야 함
- `chair 찾고 없으면 center로 가서 다시 찾아`: 첫 탐색 실패 시에만 이동/재탐색 step이 실행되어야 함
- `yellow_box 찾고 없으면 red_box 찾아`: 첫 대상 실패 후 대체 대상 탐색으로 넘어가고, 즉시 abort하지 않아야 함

### Phase 5. Real backend 연결
- go2_skill_server_real 구현
- perception_node_real 연결
- onboard_min_guard 연결
- real launch/config 연결

완료 조건:
- same mission flow가 real backend에서도 동작

### Phase 6. 실기체 검증
- stop/cancel/deadman 우선 검증
- 짧은 이동 검증
- scan_scene와 제한된 find_object 검증

완료 조건:
- real 모드에서 MVP 핵심 기능 검증 완료

### Phase 7. 배포 준비 및 엣지 최적화
- YOLO 계열 모델의 ONNX export 가능성 사전 검토
- 추후 TensorRT / Jetson 배포를 위한 입력/출력 인터페이스 정리
- sim2real 전환 시 latency 병목 지점 정리
- Ollama 경량화 또는 대체 경량 LLM 후보 검토
- **[아키텍처 제언]** Real/Edge(Jetson) 배포 시 카메라 이미지 직렬화(Serialization) 통신 지연을 막기 위해, 비전 파이프라인에 **ROS 2 Shared Memory 통신(또는 Isaac ROS Nitros Zero-copy)** 아키텍처를 사전에 구상할 것

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
2. 객체 탐색/접근 일반화(`find_object -> pose 추정 -> approach_object`)
3. 속성 기반 개체 선택(`left/right/near/far/large/small`)
4. person 대응 및 동적 객체 정책
5. 운영 가시화 및 통합 테스트 체계화 유지
6. sim에서 YOLO 연결 안정화 및 대상 클래스 확장
7. sim에서 실제 LLM 연결 안정화
8. sim에서 YOLO + LLM 조합 검증 고도화
9. mission_plan 일반화(`run_if`, 3단계 이상, 조건부 재시도)
10. VLM API 연동 및 YOLO + VLM 결합
11. OpenRouter 기반 클라우드 LLM 경로 추가
12. sim 환경 feature 확장 및 localization 안정화
13. real backend 연결
14. 마지막에 real 하드웨어 세부 튜닝
15. Nav2 기반 goal bridge 전환은 localization 안정화 이후 재개

---

## 12. 결론
현재 단계의 핵심은 sim MVP를 끝낸 상태에서 바로 real로 넘어가는 것이 아니라, sim 안에서 YOLO와 실제 LLM까지 먼저 붙여 상위 기능 완성도를 높이는 것이다.
현재 navigation 기본 경로는 Nav2 후보이며, direct `/cmd_vel` 경로는 fallback/비교용으로 유지한다.
단기 다음 우선순위였던 speed_hint 기반 속도 제어와 latched emergency_stop / clear 경로는 구현 및 검증이 완료됐다.
`mission_plan` 일반화 1차와 `approach_object` 1차 구현/검증도 완료됐으므로, 이제 다음 단계는 `객체 탐색/접근 일반화`와 그 위의 `속성 기반 개체 선택`이다.
그 다음 `person 대응 정책`, `운영 가시화/통합 테스트 체계 유지`, `YOLO 대상 클래스 안정화`, `VLM API 연동`, `OpenRouter 기반 클라우드 LLM 경로` 순서로 확장한다.

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
