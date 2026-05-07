# Real Robot Plan Draft

`plan.md` 반영 예정 위치:
- 현재는 `plan.md`에 바로 병합하지 않고, 실기체 1차 검증 범위가 확정된 뒤 별도 실기체 섹션으로 반영

진행 기록:
- 계획 실행 과정과 검증 이력은 [real_plan_progress.md](/home/jnu/llm_yolo/real_plan_progress.md)에 기록한다.

## 0. 강한 보호 원칙

- 이번 문서는 **실기체 1차 구현 전용 문서**이며, 현재 sim 운영 경로 보호를 최우선 원칙으로 둔다.
- 실기체 구현은 **반드시** `backends/real`, `configs/real`, `launch/real` 경로 안에서만 진행한다.
- `backends/sim`, `configs/sim`, `launch/sim`은 이번 단계에서 **수정 금지**로 둔다.
- `mission_manager`, `llm_command_router`, `llm_yolo_interfaces`, `configs/common` 같은 공용 경로는 **원칙적으로 수정 금지**로 둔다.
- 공용 인터페이스 변경이 정말 필요해지면, 현재 1차 범위와 분리하고 **별도 회귀 검증 계획을 먼저 작성한 뒤에만** 진행한다.
- 공용 인터페이스 변경 예외 승인 조건은 아래 3가지를 모두 만족할 때만 허용한다.
  - real 전용 경로만으로는 구현이 불가능하다는 근거가 명확할 것
  - 변경 대상 공용 파일과 예상 sim 영향 범위가 문서화될 것
  - sim 회귀 검증 항목과 복구 계획이 먼저 작성될 것
- 실기체 구현 편의를 위해 sim 경로를 임시 수정하거나 sim 설정을 덮어쓰는 방식은 사용하지 않는다.
- 실기체 구현 결과는 `mvp_real.launch.py` 및 real 전용 설정으로만 검증하고, 현재 sim launch 경로에는 영향을 주지 않아야 한다.

## 1. 실행 체크리스트

### 1.1. 사전 준비
- [ ] 실기체 1차 범위를 `chair 찾아`, `chair 앞으로 가`, `긴급 정지 / 정지 해제`로 고정
- [ ] localization / Nav2 / named place 이동은 이번 단계 범위에서 제외
- [ ] 운영자는 항상 로봇 근처에서 즉시 개입 가능한 위치에 배치
- [ ] 실기체 저속 운용 원칙 합의 (`/api/sport/request` wrapper 기반 direct control only)

### 1.2. 인터페이스 고정
- [ ] RGB topic 이름 확정
- [ ] depth image 또는 point cloud topic 이름 확정
- [ ] camera info topic 이름 확정
- [ ] `camera optical frame` 이름 확정
- [ ] 1차 로컬 제어 기준 frame을 `camera_link`로 고정
- [ ] `base_link` frame 이름은 후속 확장 검토 항목으로 분리
- [ ] `/api/sport/request` 제어 경로 확정
- [ ] sport request wrapper 출력 규칙 확정
- [ ] 위 내용을 실기체 topic 매핑 파일(`configs/real_topics.yaml`)에 반영

### 1.3. perception 구현
- [ ] `perception_node_real` 입력 연결
- [ ] YOLO 추론 경로 연결
- [ ] `/perception/visible_objects` publish 확인
- [ ] `/perception/object_poses` publish 확인
- [ ] `camera_link` 기준 상대좌표 해석 규칙 반영
- [ ] `/perception_debug` publish 확인

### 1.4. perception 검증
- [ ] 고정된 `chair`에 대해 반복 검출 테스트
- [ ] 거리 변화에 따른 bbox 흔들림 기록
- [ ] depth 정합성 확인
- [ ] `camera optical frame -> camera_link` TF 정합 확인
- [ ] 실측 거리 대비 추정 오차 기록

### 1.5. `find_object` 단독 검증
- [ ] `chair 찾아` 명령 수신 확인
- [ ] 현재 시야 기반 성공 판정 확인
- [ ] 미검출 시 실패 판정 확인
- [ ] 필요 시 제자리 소각도 회전 탐색 확인
- [ ] `find_object` 단독 검증 완료 후에만 direct 접근 backend 단계로 진행

### 1.6. direct 접근 backend 구현
- [ ] `go2_skill_server_real` 경로 분리 유지
- [ ] `approach_object`용 실기체 backend 연결
- [ ] `linear/angular` 제어 의도를 `/api/sport/request`로 변환하는 wrapper 구현
- [ ] yaw 정렬 우선 제어 구현
- [ ] 저속 전진 제어 구현
- [ ] 전진 중 yaw 보정 구현
- [ ] 목표 거리 도달 시 정지 구현
- [ ] stale pose / target loss 시 abort 구현

### 1.7. 단일 접근 검증
- [ ] `chair 앞으로 가` 명령 수신 확인
- [ ] YOLO 검출 성공 확인
- [ ] object pose 생성 확인
- [ ] 상대 접근 제어 시작 확인
- [ ] 실기체 저속 이동 확인
- [ ] 목표 거리 근처 정지 확인
- [ ] 최소 3회 연속 성공 확인

### 1.8. safety 검증
- [ ] `emergency_stop` 최우선 동작 확인
- [ ] stale object pose timeout abort 확인
- [ ] confidence threshold 미만 접근 차단 확인
- [ ] 최대 접근 거리 제한 확인
- [ ] 속도 상한 적용 확인
- [ ] person 검출 시 pause 또는 stop 확인
- [ ] object pose unavailable 시 abort 확인

### 1.9. 1차 완료 판정
- [ ] `detect success rate >= 90%`
- [ ] `pose usable rate >= 80%`
- [ ] `approach completion rate >= 80%`
- [ ] 최종 정지 거리 `0.3m ~ 0.7m`
- [ ] web monitor 또는 `/user_text` 경로에서 명령 수신 가능
- [ ] 안전 정지 경로까지 함께 검증 완료

## 2. 목표
- 현재 sim에서 검증된 `LLM -> mission_manager -> perception -> approach_object` 흐름을 실기체 Go2로 이식한다.
- 1차 목표는 **실기체에서 `chair 앞으로 가`를 `/api/sport/request` wrapper 기반 저속 접근으로 재현**하는 것이다.
- 현재 단계에서는 localization / Nav2 / named place 이동은 실기체 범위에서 제외한다.

## 3. 현재 전제

### 3.1. 이미 sim에서 검증된 상위 구조
- `llm_command_router`
- `mission_manager`
- `approach_object`
- `mission_plan`
- web `SIM MONITOR`

### 3.2. 실기체 전환 시 새로 필요한 것
- 실기체 RGB / depth 입력 연결
- 실기체 TF 정합
- 실기체용 perception adapter
- 실기체용 `/api/sport/request` wrapper 기반 접근 backend
- 실기체 safety 계층 보강

## 4. 1차 범위

### 4.1. 포함
- 자연어 `chair 앞으로 가`
- 자연어 `chair 찾아`
- 긴급 정지 / 정지 해제
- 저속 접근
- 단일 검증 대상 클래스 `chair`
- `/api/sport/request` wrapper 기반 단거리 이동
- 1차 제외 항목은 문서 하단 `보류 범위`에 정리

## 5. 설계 원칙

### 5.1. 상위 로직은 유지
- `Intent`
- `mission_manager`
- `mission_plan`
- `approach_object`
- web monitor

위 구조는 최대한 유지하고, 하위 perception / locomotion만 실기체용으로 치환한다.

### 5.2. 실기체 1차는 global navigation 없이 근거리 접근만 수행
- 현재 시야에 보이는 객체만 대상으로 한다
- `map` 기준 절대 목표를 쓰지 않는다
- perception으로 추정한 객체 상대 위치를 바탕으로 짧은 거리 접근만 수행한다

### 5.3. 주행은 `/api/sport/request` wrapper 기반 direct control만 사용
- Nav2 미사용
- localization 미사용
- 접근 제어는 저속 / 짧은 시간 / 운영자 감시 하에서만 수행
- `/cmd_vel`은 이번 1차 범위에서 직접 사용하지 않는다

### 5.4. safety 우선
- 속도 제한
- emergency stop 최우선
- stale pose abort
- person 검출 pause는 옵션으로 두되, 1차는 보수적으로 정지 우선

## 6. 단계별 계획

## 6-1. 실기체 인터페이스 명세 고정

### 목표
- 실기체에서 사용할 센서 입력과 제어 입력을 확정한다.

### 확인 항목
- RGB 이미지 topic
- depth 이미지 또는 point cloud topic
- camera info topic
- `/tf`
- `camera_link`
- camera optical frame
- 실제 이동 명령 입력 방식
  - `/api/sport/request`
  - sport API wrapper
  - 필요 시 향후 `/cmd_vel` 브리지

### 완료 기준
- 실기체 ROS graph 명세 문서화 완료
- `chair 앞으로 가`에 필요한 최소 topic set 확정 및 **실기체 topic 매핑 파일(`configs/real_topics.yaml`)에 반영 완료**
- 실기체에서 `/api/sport/request` 입력 경로가 실제로 동작하는지 확인 완료

## 6-2. 실기체 perception adapter 구현

### 목표
- 현재 `perception_node_sim`의 출력 인터페이스를 유지한 채, 입력만 실기체 센서로 교체한다.

### 구현 방향
- 새 노드: `perception_node_real`
- 입력:
  - RGB
  - depth
  - camera info
  - TF
- 출력:
  - `/perception/visible_objects`
  - `/perception/object_poses`
  - `/perception_debug`

### 요구사항
- 현재 sim과 동일한 JSON schema 최대한 유지
- 최소 메타데이터 포함:
  - `frame_id`
  - `stamp`
  - `class_name`
  - `confidence`
  - `x_m`, `y_m`, `z_m`
- 접근 제어 해석 기준 명시:
  - 1차 기준 object pose는 `camera_link` 기준 상대좌표를 우선 사용
  - `x_m`: 전방 거리
  - `y_m`: 좌우 오프셋
  - `z_m`: 높이 정보(1차 접근 제어에는 직접 사용하지 않음)
  - heading 오차는 `(x_m, y_m)`에서 계산
- bbox + depth + TF 기반 pose 추정 로직 재사용
- 1차는 global `map`이 아니라 `camera_link` 로컬 기준 pose여도 허용

### 완료 기준
- 실기체에서 `chair` 검출 결과가 `/perception/visible_objects`에 publish
- `chair` pose가 `/perception/object_poses`에 publish

## 6-3. 실기체 perception 정확도 검증

### 목표
- 주행 없이 object pose 안정성부터 검증한다.

### 검증 항목
- `chair` 검출 안정성
- bbox 흔들림
- depth 정합성
- `camera optical frame -> camera_link` TF 정합성
- 실거리 대비 상대 위치 오차

### 측정 방식
- 고정된 `chair`를 두고 반복 측정
- 로봇-객체 실제 거리와 대시보드 거리 비교
- 시야각 / 거리 변화에 따른 오차 기록

### 완료 기준
- 근거리 / 중거리에서 `chair` 거리 추정이 일관적
- 접근용 prior로 쓸 수 있는 수준의 pose 안정성 확보

## 6-4. 실기체 `find_object` 단독 검증

### 목표
- 접근과 분리해서 `chair 찾아`의 실기체 동작을 먼저 검증한다.

### 1차 방식
- 현재 시야 기반 검출 확인
- 필요 시 제자리 소각도 회전 탐색만 허용
- 장거리 fallback 이동 없음

### 완료 기준
- `chair 찾아`가 실기체에서 안정적으로 성공/실패 판정

## 6-5. 실기체 direct 접근 backend 연결

### 목표
- `approach_object` 상위 인터페이스를 유지하면서 실제 로봇을 `/api/sport/request` wrapper로 움직일 수 있게 한다.

### 구현 방향
- 1차는 **별도 `go2_skill_server_real` 추가**를 기본안으로 한다.
- sim용 `go2_skill_server_sim`과 실기체용 backend를 분리해 디버깅 경계를 유지한다.
- 기존 `navigate_to_pose_server`에 실기체 분기를 섞는 방식은 1차에서 사용하지 않는다.
- 실기체 출력은 `linear/angular` 제어 의도를 `/api/sport/request` 메시지로 변환하는 wrapper 계층으로 고정한다.

### 요구사항
- `/api/sport/request` wrapper 기반 저속 제어
- forward / yaw 보정 중심의 단순 접근
- 정지 조건 우선
- 장거리 경로 계획 없음

### 제어 방식
- 객체가 시야 내에 있을 때만 접근
- 객체까지의 거리 오차와 heading 오차 기반으로 단순 제어
- 제어 루프 주기(Control Loop Frequency, 예: 10Hz)를 명시적으로 설정하여 명령 지연 및 급발진 방지
- 계산된 전진/회전 제어값은 직접 `/cmd_vel` publish하지 않고, sport API request 포맷으로 변환해 publish
- 1차 상대 접근 제어는 `camera_link` 기준 pose를 그대로 사용한다
- 제어 규칙 고정:
  - 1단계: heading 오차가 큰 경우 yaw 정렬 우선
  - 2단계: heading 오차가 허용 범위 안에 들어오면 저속 전진
  - 3단계: 전진 중에도 작은 yaw 보정 허용
  - 4단계: 목표 정지 거리 도달 시 정지
  - 5단계: target 상실 또는 stale pose 시 즉시 정지 / abort
- 초기 권장 제어값:
  - `approach_distance_m = 0.5`
  - `heading_align_threshold_rad = 0.25`
  - `heading_stop_threshold_rad = 0.6`
  - `max_linear_speed_mps = 0.2`
  - `max_angular_speed_radps = 0.4`
- 목표 정지 거리(`approach_distance_m`) 도달 시 정지

### 완료 기준
- 실기체에서 짧은 거리 `/api/sport/request` wrapper 접근 가능
- 객체 시야 유지 상태에서 저속 접근 가능

## 6-6. 단일 접근 시나리오 검증

### 목표
- `chair 앞으로 가`를 실기체에서 end-to-end 검증한다.

### 시나리오
1. 실기체 센서 / TF 정상
2. `chair`가 시야에 존재
3. `/user_text` 또는 web monitor로 `chair 앞으로 가`
4. YOLO 검출
5. object pose 생성
6. 상대 접근 제어 시작
7. 실기체 저속 이동
8. target 앞에서 정지

### 측정 지표
- detect success rate
- pose usable rate
- approach completion rate
- final standoff error

### 완료 기준
- 최소 3회 이상 연속 성공
- 명령 수신 -> 검출 -> 접근 -> 정지까지 전체 흐름 재현
- 정량 기준:
  - `detect success rate >= 90%`
  - `pose usable rate >= 80%`
  - `approach completion rate >= 80%`
  - `final standoff error`는 목표 `0.5m` 기준 `+-0.2m` 이내
  - 즉 최종 정지 거리는 대략 `0.3m ~ 0.7m`

## 6-7. 안전 계층 보강

### 목표
- sim보다 강한 안전 제약을 실기체용으로 추가한다.

### 최소 필요 항목
- `emergency_stop` 최우선
- stale object pose timeout **(예: 2~3초 경과 시 즉시 abort)**
- object confidence minimum threshold **(예: 0.6 이상만 신뢰)**
- 접근 최대 거리 제한 **(예: 3.0m 이내만 접근 시작 허용)**
- 접근 속도 상한 **(예: Linear 0.3m/s, Angular 0.5rad/s 이하로 하드 리미트)**
- person 검출 시 pause 또는 즉시 stop
- object pose unavailable 시 즉시 abort

### 주의
- 1차는 vision-based safety만으로 과신하지 않는다
- 필요하면 실기체 자체 e-stop / 저수준 stop 경로를 병행한다

### 완료 기준
- 오검출 / pose loss / 사람 개입 시 안전하게 정지 또는 abort

## 6. 구현 우선순위

### 우선순위 1
- 실기체 topic / frame / `/api/sport/request` 입력 명세 고정
- `perception_node_real` 구현

### 우선순위 2
- object pose 실측 검증
- `chair 찾아` 단독 검증

### 우선순위 3
- 실기체 direct 접근 backend 연결
- `chair 앞으로 가` 실기체 단일 검증
- safety 강화

### 우선순위 4
- 1차 범위 완료 후 후속 확장 검토

## 7. 리스크

### 7.1. depth 정합 불안정
- sim보다 실기체 depth 노이즈가 큼
- bbox 중심 기반 접근은 오차가 커질 수 있음

대응:
- 현재 `bbox_cluster` depth 모드 유지
- 필요 시 median / foreground cluster 파라미터 실기체용 재튜닝

### 7.2. TF / frame mismatch
- camera frame, local control frame 이름 차이로 object pose가 틀릴 수 있음

대응:
- 1단계에서 frame 명세 고정
- 실기체에서 TF tree 먼저 검증

### 7.3. `cmd_vel` 제어 입력 불일치
- 실기체에서 `/cmd_vel`이 직접 안 먹고, 현재 활성 제어 경로가 sport API 계열일 수 있음
- `/api/sport/request` 포맷 이해와 wrapper 구현이 필요할 수 있음

대응:
- 1단계에서 control path를 `/api/sport/request`로 먼저 고정
- `go2_skill_server_real` 내부에 sport request wrapper를 추가

### 7.4. 실기체 safety 부족
- sim에서 허용되던 timeout/오검출이 실기체에서는 위험할 수 있음

대응:
- 속도 제한
- person pause 또는 stop
- emergency stop
- stale abort

## 8. 검증 체크리스트

### 8.1. 센서 / TF
- RGB 수신 정상
- depth 수신 정상
- camera info 수신 정상
- TF tree 정상
- `camera optical frame -> camera_link` 정상

### 8.2. perception
- `chair` 검출 정상
- `/perception/visible_objects` 정상
- `/perception/object_poses` 정상
- 거리 추정 대체로 일관

### 8.3. control
- 저속 `/api/sport/request` wrapper 이동 가능
- 접근 중 정지 가능
- timeout / abort 처리 정상

### 8.4. end-to-end
- `chair 앞으로 가`
- `chair 찾아`
- `긴급 정지`
- `정지 해제`

## 9. 1차 성공 정의
- 실기체에서 `chair 앞으로 가`가 안정적으로 재현됨
- web monitor 또는 `/user_text` 경로로 명령 수신 가능
- YOLO 검출 + object pose + 실제 `/api/sport/request` wrapper 접근이 end-to-end로 연결됨
- 안전 정지 경로가 함께 검증됨
- 정량 기준:
  - `detect success rate >= 90%`
  - `pose usable rate >= 80%`
  - `approach completion rate >= 80%`
  - 최종 정지 거리는 `0.3m ~ 0.7m`

## 10. 보류 범위

### 10.1. 1차 제외 항목
- Nav2
- localization
- named place 이동
- `/cmd_vel` 직접 제어 경로 사용
- `base_link` 기준 로컬 접근 제어
- `tv` 실기체 1차 운용
- 복수 객체 disambiguation
- 시야 밖 object memory 재접근
- topological 탐색
- VLM / open-vocabulary
- 장시간 무감독 운용

### 10.2. 후속 확장 항목

#### 목표
- 1차 `cmd_vel` 기반 단일 객체 접근이 안정화된 뒤, 상위 기능을 단계적으로 확장한다.

#### 후속 대상
- `chair 찾아서 앞으로 가`
- 복합 명령 기반 `mission_plan` 실기체 검증
- 추가 객체 클래스 확장(`tv` 등)
- `/cmd_vel` 브리지 또는 `/cmd_vel` 표준 인터페이스 전환
- `camera_link` 기준 로컬 제어에서 `base_link` 기준 로컬 제어로 재정렬
- localization / Nav2 기반 장거리 이동

#### 후속 완료 기준
- `find -> approach` 흐름 실기체 재현
- 단일 접근 경로를 깨지 않고 복합 명령으로 확장 가능
