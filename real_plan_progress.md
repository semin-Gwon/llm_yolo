# Real Plan Progress

기준 문서:
- [real_plan.md](/home/jnu/llm_yolo/real_plan.md)

기록 원칙:
- 이 문서는 `real_plan.md` 실행 과정만 기록한다.
- sim 구현/검증 완료 사항은 기존 [progress.md](/home/jnu/llm_yolo/progress.md)에 기록한다.
- 실기체 계획 변경은 먼저 [real_plan.md](/home/jnu/llm_yolo/real_plan.md)에 반영하고, 실행/검증 결과만 이 문서에 기록한다.
- 각 항목은 `상태 / 결정사항 / 검증 결과 / 남은 이슈` 순서로 짧게 남긴다.

## 0. 현재 상태 요약
- 상태: 초기 구현 진행 중
- 결정사항:
  - 1차 실기체 제어 경로는 `/api/sport/request` wrapper 기반으로 진행
  - `/cmd_vel` 직접 제어는 1차 범위에서 제외
  - sim 보호 원칙 유지
- 검증 결과:
  - 실기체 ROS graph에서 camera/depth 토픽 확인 완료
  - `/utlidar/robot_pose` frame_id=`odom` 확인 완료
  - `/cmd_vel` 미노출 확인
  - `/api/sport/request` 활성 확인
  - `/camera/color/camera_info` frame_id=`camera_color_optical_frame` 확인 완료
  - `/tf_static`에서 `camera_link -> camera_color_frame -> camera_color_optical_frame` 확인 완료
  - `/tf_static`에서 `camera_link -> camera_depth_frame -> camera_depth_optical_frame` 확인 완료
  - `camera_color_optical_frame -> camera_link` 역방향 변환에 필요한 정적 TF 체인 존재 확인 완료
  - 공식 `unitree_ros2` 예제 기준 sport request 핵심 API 확인 완료
    - `Move(req, vx, vy, vyaw)` / API ID `1008`
    - `StopMove(req)` / API ID `1003`
    - `BalanceStand(req)` / API ID `1002`
  - `/home/jnu/unitree_ros2/setup.sh` source 시 `unitree_api.msg` import 가능 확인
  - `.venv_yolo` 활성화 시 `ultralytics` import 가능 확인
- 남은 이슈:
  - `RequestHeader` 세부 필드 로컬 환경 미확인
  - `base_link`와 camera frame 사이 TF 연결은 1차 범위 밖으로 보류
  - `/tf` 토픽은 현재 미노출, `/tf_static`만 확인됨

## 1. 사전 준비
- 상태: 진행 중
- 결정사항:
  - 1차 범위는 `chair 찾아`, `chair 앞으로 가`, `긴급 정지 / 정지 해제`
- 검증 결과:
  - localization / Nav2 / named place 이동 제외 결정 완료
- 남은 이슈:
  - 운영자 개입 절차와 실기체 테스트 공간 조건 정리 필요

## 2. 인터페이스 고정
- 상태: 진행 중
- 결정사항:
  - RGB topic: `/camera/color/image_raw`
  - RGB camera info: `/camera/color/camera_info`
  - depth topic: `/camera/depth/image_rect_raw`
  - depth camera info: `/camera/depth/camera_info`
  - robot pose topic 후보: `/utlidar/robot_pose`
  - control request topic: `/api/sport/request`
- 검증 결과:
  - `/utlidar/robot_pose` 샘플 확인, `frame_id=odom`
  - `/api/sport/request` 타입 확인: `unitree_api/msg/Request`
  - color camera frame 확인: `camera_color_optical_frame`
  - depth frame 확인: `camera_depth_optical_frame`
  - 1차 로컬 제어 frame을 `camera_link`로 사용하기로 결정
  - `camera_color_optical_frame` camera_info 수신 정상 확인
  - 공식 `unitree_ros2` `ros2_sport_client.cpp` 기준 request 생성 규칙 확인
    - `Move`: `parameter = {\"x\": vx, \"y\": vy, \"z\": vyaw}`
    - `StopMove`: `parameter` 없이 API ID만 사용
- 남은 이슈:
  - `base_link` frame 이름 확인은 후속 확장 항목으로 보류
  - 기본 `/opt/ros/humble` 환경만으로는 `unitree_api` 로컬 import 불가
  - 기본 시스템 python만으로는 `ultralytics` 로컬 import 불가
  - 실실행 시 `/home/jnu/unitree_ros2/setup.sh` + `.venv_yolo` 조합 필요

## 3. 실기체 topic 매핑 파일
- 상태: 완료
- 결정사항:
  - [real_topics.yaml](/home/jnu/llm_yolo/configs/real/real_topics.yaml) 초안 생성
- 검증 결과:
  - 센서 입력 / pose 입력 / 제어 출력 후보 반영 완료
  - `camera_frame`, `depth_frame` 실측값 반영 완료
- 남은 이슈:
  - `base_frame` 실측값 확인 필요

## 4. perception adapter 구현
- 상태: 진행 중
- 결정사항:
  - 1차 출력은 global `map`이 아니라 `camera_link` 기준 상대좌표로 publish
- 검증 결과:
  - [perception_node.py](/home/jnu/llm_yolo/backends/real/perception_node_real/perception_node_real/perception_node.py)에 실기체 RGB/depth/camera_info subscribe 추가
  - YOLO 추론 경로와 bbox+depth 기반 상대 pose 계산 뼈대 추가
  - `/perception/visible_objects`, `/perception/object_poses`, `/perception_debug` publish 경로 추가
  - [real_perception_params.yaml](/home/jnu/llm_yolo/configs/real/real_perception_params.yaml) 확장
  - `object_pose_frame=camera_link` 전제로 조정 완료
  - `py_compile` 문법 확인 완료
- 남은 이슈:
  - `fallback_camera_frame`에 `camera_color_optical_frame` 반영 완료
  - perception 쪽도 `ultralytics` 런타임 패키지 확인 필요
  - `camera optical frame -> camera_link` 정적 TF 체인 확인 완료

## 5. perception 정확도 검증
- 상태: 미착수
- 결정사항: -
- 검증 결과: -
- 남은 이슈:
  - `chair` 검출 안정성 측정 필요
  - 실거리 대비 pose 오차 측정 필요

## 6. `find_object` 단독 검증
- 상태: 미착수
- 결정사항: -
- 검증 결과: -
- 남은 이슈:
  - `chair 찾아` 실기체 성공/실패 판정 확인 필요

## 7. direct 접근 backend 구현
- 상태: 진행 중
- 결정사항:
  - `/cmd_vel` 대신 `/api/sport/request` wrapper 기반으로 구현
- 검증 결과:
  - [approach_object_server.py](/home/jnu/llm_yolo/backends/real/go2_skill_server_real/go2_skill_server_real/approach_object_server.py) 신설
  - [mvp_real.launch.py](/home/jnu/llm_yolo/launch/real/mvp_real.launch.py)에 `approach_object_server` wiring 추가
  - [real_nav_params.yaml](/home/jnu/llm_yolo/configs/real/real_nav_params.yaml)에 1차 접근 파라미터 초안 반영
  - [setup.py](/home/jnu/llm_yolo/backends/real/go2_skill_server_real/setup.py) entry point 추가
  - `camera_link` 기준 상대 pose를 사용하도록 1차 제어 경로 정렬 완료
  - `py_compile` 문법 확인 완료
- 남은 이슈:
  - `BalanceStand` 선행 필요 여부 실기체 확인 필요

## 8. 단일 접근 검증
- 상태: 미착수
- 결정사항: -
- 검증 결과: -
- 남은 이슈:
  - `chair 앞으로 가` end-to-end 실기체 검증 필요

## 9. safety 검증
- 상태: 미착수
- 결정사항: -
- 검증 결과: -
- 남은 이슈:
  - emergency stop
  - stale pose abort
  - person 개입 시 stop/pause
  - confidence/거리 제한 검증 필요

## 10. 후속 예정
- `/cmd_vel` 브리지 또는 표준 속도 인터페이스 전환 검토
- `chair 찾아서 앞으로 가` 복합 명령 실기체 검증
- 추가 객체 클래스 확장
- localization / Nav2 기반 장거리 이동 검토
