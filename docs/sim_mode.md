# Sim Mode

Sim mode는 현재 `llm_yolo`의 주 개발 대상이다.
상위 계층은 공통으로 유지하고, perception / navigation / skill server만 sim backend로 연결한다.

## 실행 구성

권장 터미널 구성:

### 터미널 1: Isaac Sim
```bash
source /opt/ros/humble/setup.bash
conda activate isaaclab
cd /home/jnu/go2_sim
python -u /home/jnu/go2_sim/scripts/go2_sim.py
```

### 터미널 2: Nav2 / localization
```bash
source /opt/ros/humble/setup.bash
cd /home/jnu/go2_sim
ros2 launch launch/go2_navigation.launch.py
```

### 터미널 3: llm_yolo
```bash
cd /home/jnu/llm_yolo
source .venv_yolo/bin/activate
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch launch/sim/mvp_sim.launch.py
```

## 표준 모니터 토픽

운영/회귀 검증 시 아래를 기본 관측 대상으로 사용한다.
- `/mission_state`
- `/perception_debug`
- `/perception/object_poses`
- `/emergency_stop`
- `/mission_plan`

Nav2 확인:
```bash
ros2 action info /llm_navigate_to_pose
ros2 action info /navigate_to_pose
```

기대:
- `/llm_navigate_to_pose` server: `navigate_to_pose_server`
- `/navigate_to_pose` server: `bt_navigator`

## 보조 스크립트

표준 모니터링:
```bash
/home/jnu/llm_yolo/scripts/monitor_sim.sh core
/home/jnu/llm_yolo/scripts/monitor_sim.sh perception
/home/jnu/llm_yolo/scripts/monitor_sim.sh object
/home/jnu/llm_yolo/scripts/monitor_sim.sh safety
/home/jnu/llm_yolo/scripts/monitor_sim.sh all
```

bag 기록:
```bash
/home/jnu/llm_yolo/scripts/record_bag.sh
```

## 기본 회귀 명령

```bash
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'center 로 가'}"
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'chair 찾아'}"
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'chair 찾고 없으면 center로 복귀'}"
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'yellow_box 찾고 없으면 red_box 찾아'}"
ros2 topic pub --once /user_text std_msgs/msg/String "{data: 'chair 앞으로 가'}"
```

자세한 시나리오는 [test_scenarios.md](/home/jnu/llm_yolo/docs/test_scenarios.md)를 따른다.

## 운영 원칙

- Nav2는 현재 sim에서 `우선 검증 경로`로 사용한다.
- direct `/cmd_vel` 경로는 fallback/비교용으로 유지한다.
- VLM 1차 결과는 이후 추가되더라도 debug/observability 용도로만 사용한다.
- mission 성공/실패 판정의 기준은 현재 `mission_state`와 action 결과이다.
