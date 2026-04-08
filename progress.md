# Progress

## 1. Sim MVP 기반 구축 완료
- `go2_skill_server_sim` 구현 완료
- `perception_node_sim` 구현 완료
- sim launch 연결 완료
- sim에서 `navigate`, `scan`, `find_object`, `cancel` 기본 시퀀스 동작 확인

## 2. Sim 기반 미션 검증 완료
- named place 이동 검증 완료
- `scan_scene` 단독 호출 검증 완료
- `find_object` fallback 시퀀스 검증 완료
- abort / cancel 검증 완료
- prim path 기반 visible object publish 검증 완료
- `scan_scene` 회전 탐색 검증 완료

## 3. Ground-truth perception 및 named place 구성 완료
- Isaac Sim prim path 기반 ground-truth perception 검증 완료
- `/sim/visible_objects` 자동 publish 검증 완료
- named place `center` 기반 이동 검증 완료
- fallback 위치를 `center`로 고정한 제한 탐색 흐름 검증 완료

## 4. YOLO 기반 perception 1차 완료
- `perception_node_sim`의 YOLO 모드 구현 완료
- sim 카메라 입력 기반 YOLO 경로 검증 완료
- `chair` 클래스 YOLO 기반 탐지 검증 완료
- `chair 찾아` 자연어 명령의 YOLO 기반 성공 검증 완료

## 5. 실제 LLM 경로 연결 완료
- Ollama 기반 실제 LLM backend 연결 완료
- 실제 LLM 모드 전환 및 자연어 명령 해석 검증 완료
- rule-based / LLM 경로 공존 구조 정리 완료

## 6. mission_plan 1차 구현 및 검증 완료
- `mission_plan` 2단계 복합 명령 생성 및 순차 실행 검증 완료
- `찾고 없으면 center로 복귀` 조건부 복귀 명령 검증 완료
- `run_if=always | previous_failed | previous_succeeded` 기반 조건 실행 구현 완료
- `chair 찾고 없으면 center로 가서 다시 찾아` 조건부 재시도 검증 완료
- `yellow_box 찾고 없으면 red_box 찾아` 대체 대상 탐색 검증 완료
- 조건이 맞지 않는 step skip 동작 검증 완료

## 7. scan / find 동작 확장 완료
- `scan_scene` 회전 탐색 방식 반영 완료
- `찾아` 명령 시 현재 위치에서 제자리 회전 탐색 후 fallback 이동 흐름 검증 완료
- 작은 각도 스텝 기반 회전 탐색으로 조정 완료
- `find_object` 실패 시 fallback 이동 후 종료 검증 완료

## 8. Direct 주행 제어 확장 완료
- `speed_hint`(slow | normal | fast) 전달 경로 구현 완료
- direct 모드 속도 스케일 반영 완료
- `emergency_stop` / `emergency_clear` 토픽 경로 구현 완료
- 자연어 `긴급 정지` / `정지 해제` 연결 완료
- direct 모드에서 긴급 정지 및 해제 검증 완료

## 9. Nav2 연동 구조 검증 완료
- `navigate_to_pose_server`의 `direct | nav2` 모드 분기 구현 완료
- 액션 이름 분리 완료
  - 내부 서버: `/llm_navigate_to_pose`
  - Nav2 서버: `/navigate_to_pose`
- Nav2 goal 전달 wiring 검증 완료
- `center 로 가` 기준 Nav2 경유 이동 검증 완료
- Nav2 모드에서 `긴급 정지` / `정지 해제` 검증 완료

## 10. Perception 기반 객체 접근 1차 완료
- `approach_object` intent / action 추가 완료
- `chair 앞으로 가` 자연어 명령 처리 경로 구현 완료
- YOLO bbox + depth + camera_info + TF 기반 객체 위치 추정 경로 구현 완료
- `/perception/object_poses` publish 경로 구현 완료
- perception 기반 접근 goal pose 생성 로직 구현 완료
- 기존 navigation backend를 재사용한 객체 접근 경로 구현 완료
- `chair 앞으로 가` 기준 접근 동작 검증 완료
- `tv` 클래스에 대해서도 탐지 / pose 추정 / 접근 검증 완료
- `couch`, `dining table`, `bed`는 현재 YOLO 경로에서 탐지/pose 추정이 불안정해 운영 대상에서 제외

## 11. 현재 운영 기준 정리 완료
- named place는 `center` 하나로 운영
- visible object는 `red_box`, `pink_box`, `yellow_box`, `blue_box` 기준 정리
- 현재 YOLO/LLM 운영 객체 클래스는 `chair`, `tv` 기준으로 유지
- direct `/cmd_vel` 경로는 fallback / 비교용으로 유지
- Nav2는 우선 검증 경로로 유지

## 12. 문서화 완료
- `README.md` 업데이트 완료
- `plan.md` 업데이트 완료
- `mission_plan_schema.md` 업데이트 완료
- 현재 구현/검증 완료 항목을 `progress.md`로 정리 완료

## 13. 운영 가시화 및 통합 검증 1차 문서화 완료
- 현재 sim 구조에 맞는 운영 가이드 정리 완료
- 표준 회귀 시나리오 및 pass/fail 기준 문서화 완료
- `monitor_sim.sh` 표준 모니터링 스크립트 추가 완료
- `record_bag.sh` 기록 대상 토픽 확장 완료
- README / sim_mode / test_scenarios 간 실행 절차 정합성 보강 완료

## 14. 운영 가시화 및 통합 검증 실검증 완료
- 대표 회귀 시나리오 세트를 실제 sim 환경에서 재검증 완료
- 문서화된 절차와 실제 실행 흐름의 일치 확인 완료
- 표준 모니터링 절차의 재사용 가능성 확인 완료
- `center 로 가`, `chair 찾아`, 조건부 복귀, 조건부 재시도, 대체 대상 탐색, `chair 앞으로 가`, `긴급 정지`/`정지 해제` 경로 재검증 완료

## 15. Person 대응 및 동적 객체 정책 1차/2차 완료
- `navigate_to_pose_server`에 `person` 검출 기반 pause / resume 로직 구현 완료
- 이동/접근 중 `/perception/visible_objects`에 `person`이 포함되면 일시정지하도록 구현 완료
- `person` 미검출이 연속적으로 확인되면 동일 goal로 자동 재개하도록 구현 완료
- 목표 자체가 `person`인 경우 pause 정책을 적용하지 않도록 예외 처리 완료
- 관련 sim 파라미터(`person_pause_enabled`, trigger / clear count) 추가 완료
- `person` pose 기반 거리 조건(`person_pause_distance_m`) 추가 완료
- 가까운 `person`일 때만 pause, 먼 `person`은 무시하는 정책 검증 완료
- `chair 앞으로 가` 도중 person 개입 / 이탈 시 pause / resume 실검증 완료
- Python 문법 검사 및 `go2_skill_server_sim` 패키지 빌드 검증 완료

## 현재 시점 요약
- sim MVP 완료
- YOLO 1차 완료
- 실제 LLM 1차 완료
- `mission_plan` 일반화 1차 완료
- perception 기반 `approach_object` 1차 완료
- direct / Nav2 두 주행 경로 구조 검증 완료
- emergency stop / clear 검증 완료
- person 검출 기반 pause / resume 및 거리 조건 검증 완료
- 운영/통합 검증 1차 문서화 및 도구화 완료
- 운영/통합 검증 실검증 완료
