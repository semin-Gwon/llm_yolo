# Test Scenarios

현재 sim 통합 검증의 기준 시나리오와 pass/fail 기준을 정리한다.
이 문서는 `plan.md`의 `Phase 3.6 운영 가시화 및 통합 검증`을 실제 실행 가능한 절차로 풀어쓴다.

## 공통 준비

기본 전제:
- Isaac Sim과 `go2_sim.py`가 실행 중이어야 함
- `llm_yolo` 스택이 실행 중이어야 함
- 기본 navigation 경로는 `nav2`
- LLM 모드를 검증할 때는 Ollama 서버가 떠 있어야 함

권장 모니터링:
- `/mission_state`
- `/perception_debug`
- `/perception/object_poses`
- `/emergency_stop`

빠른 확인:
```bash
ros2 action info /llm_navigate_to_pose
ros2 action info /navigate_to_pose
```

기대:
- `/llm_navigate_to_pose` server: `navigate_to_pose_server`
- `/navigate_to_pose` server: `bt_navigator`

## 표준 회귀 시나리오

### 1. Named Place 이동

명령:
```bash
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'center 로 가'}"
```

기대 상태 전이:
- `navigate requested: center`
- `navigate completed: arrived:center`

실패 조건:
- `nav2_unavailable:*`
- `timeout:*`
- `failed:*`

### 2. YOLO 기반 객체 탐색

사전 조건:
- `chair`가 카메라 시야 또는 fallback 이후 탐지 가능한 위치에 있어야 함

명령:
```bash
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'chair 찾아'}"
```

기대 상태 전이:
- `scan requested: chair`
- 해당 위치에서 실패 시 `navigate requested: center` 고정
- 최종적으로 `find_object success: chair` 또는 정책에 맞는 일관된 실패

보조 확인:
```bash
ros2 topic echo /perception_debug
ros2 topic echo /perception/object_poses
```

실패 조건:
- 탐색 정책과 무관한 무한 반복
- 성공 가능한 장면인데 `object_pose_unavailable` 또는 `NOT_FOUND`만 반복

### 3. 조건부 복귀

명령:
```bash
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'chair 찾고 없으면 center로 복귀'}"
```

기대 상태 전이:
- step 1: `find_object:chair`
- chair를 찾으면 복귀 step 실행 없이 종료
- chair를 못 찾으면 `return_home` 경로만 실행

성공 판정:
- 성공 시 `mission_plan completed`
- 실패 분기에서는 `mission_plan return_home: arrived:center`

실패 조건:
- chair를 찾았는데도 복귀 실행
- chair를 못 찾았는데 복귀가 빠짐

### 4. 조건부 재시도

명령:
```bash
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'chair 찾고 없으면 center로 가서 다시 찾아'}"
```

기대 상태 전이:
- step 1: `find_object:chair`
- step 2: `navigate_to_named_place:center`는 `previous_failed`일 때만 실행
- step 3: `find_object:chair`는 `previous_failed`일 때만 실행

성공 판정:
- 첫 탐색 성공 시 step 2, 3이 `skipped`
- 첫 탐색 실패 시 step 2, 3이 실행

실패 조건:
- 첫 탐색 성공인데 step 2, 3 실행
- 첫 탐색 실패인데 즉시 abort

### 5. 대체 대상 탐색

명령:
```bash
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'yellow_box 찾고 없으면 red_box 찾아'}"
```

기대 상태 전이:
- step 1: `find_object:yellow_box`
- 실패 시 step 2: `find_object:red_box`

성공 판정:
- yellow_box 실패 후 red_box 탐색으로 넘어감
- step 1 실패 즉시 abort하지 않음

실패 조건:
- yellow_box 실패 후 step 2 미실행
- `previous_failed` 분기 미동작

### 6. Perception 기반 객체 접근

사전 조건:
- `chair`가 YOLO와 depth 기반으로 pose 추정 가능한 시야 안에 있어야 함

명령:
```bash
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'chair 앞으로 가'}"
```

기대 상태 전이:
- `approach requested: chair`
- `/perception/object_poses`에 `chair` 좌표가 publish
- 최종적으로 `approach completed:*`

보조 확인:
```bash
ros2 topic echo /perception/object_poses
```

실패 조건:
- `object_pose_unavailable:chair`
- 접근 goal 생성 실패
- 접근 성공 가능 장면인데도 navigation goal 미생성

### 7. Emergency Stop / Clear

사전 조건:
- 이동 중인 미션 하나가 실행 중이어야 함

명령:
```bash
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'center 로 가'}"
ros2 topic pub --once /user_text std_msgs/msg/String "{data: '긴급 정지'}"
ros2 topic pub --once /user_text std_msgs/msg/String "{data: '정지 해제'}"
```

직접 토픽 경로:
```bash
ros2 topic pub --once /emergency_stop std_msgs/msg/Bool "{data: true}"
ros2 topic pub --once /emergency_clear std_msgs/msg/Bool "{data: true}"
```

기대 상태 전이:
- `emergency_stop engaged`
- 이동 action 중단
- clear 후 `emergency_stop cleared`

성공 판정:
- stop 중 새 mission 요청 시 `busy: emergency_stop active`
- clear 후 다시 명령 수행 가능

실패 조건:
- stop 이후에도 이동 지속
- clear 없이 새 mission 수락

## 최소 검증 세트

빠르게 회귀만 확인할 때는 아래 다섯 개만 본다.

```bash
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'center 로 가'}"
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'chair 찾아'}"
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'chair 찾고 없으면 center로 복귀'}"
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'yellow_box 찾고 없으면 red_box 찾아'}"
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'chair 앞으로 가'}"
```

## 기록 권장 토픽

bag 기록이 필요하면 아래 토픽을 우선 기록한다.
- `/intent`
- `/mission_plan`
- `/mission_state`
- `/perception_debug`
- `/perception/object_poses`
- `/emergency_stop`
- `/emergency_clear`
