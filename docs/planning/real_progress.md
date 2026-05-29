# Real Plan Progress

기준 문서:
- [real_plan.md](/home/jnu/llm_yolo/docs/planning/real_plan.md)

기록 원칙:
- 이 문서는 `real_plan.md` 실행 과정만 기록한다.
- sim 구현/검증 완료 사항은 [sim_progress.md](/home/jnu/llm_yolo/docs/planning/sim_progress.md)에 기록한다.
- 실기체 계획 변경은 먼저 [real_plan.md](/home/jnu/llm_yolo/docs/planning/real_plan.md)에 반영하고, 실행/검증 결과만 이 문서에 기록한다.
- 각 항목은 `상태 / 결정사항 / 검증 결과 / 남은 이슈` 순서로 짧게 남긴다.

## 0. 현재 상태 요약
- 상태: 1차 실기체 MVP 구현 및 1차 검증 진행 중
- 결정사항:
  - 1차 실기체 제어 경로를 `/cmd_vel` 표준 속도 인터페이스 기반으로 전환
  - Go2 실구동은 프로젝트 내부 `cmd_vel_to_sport_request_node`가 `/cmd_vel`을 `/api/sport/request`로 변환
  - 외부 `/home/jnu/go2_ws/install/go2_driver` 전체 통합은 `/odom`, `/tf`, `/pointcloud` side effect 때문에 제외
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
  - 실기체 perception / direct approach / web monitor / RViz 연동까지 1차 구현 반영 완료
  - `chair` 단일 객체 기준 검출 안정화 및 접근 안정화 파라미터 반영 완료
  - `yolo11s-seg.pt` 기반 mask depth cluster 거리 추정 반영 완료
  - 실내 인지 후보 10종 반영 완료: `person`, `chair`, `couch`, `dining table`, `tv`, `laptop`, `keyboard`, `mouse`, `bottle`, `cup`
  - 자연어 접근/탐색 허용 클래스 4종 반영 완료: `chair`, `couch`, `dining table`, `tv`
  - `/cmd_vel` 출력 모드 검증 완료: 접근 중 `linear.x=0.3`, timeout/stop 시 `linear.x=0.0` 확인
  - 프로젝트 내부 `/cmd_vel -> /api/sport/request` 브릿지 구현 및 launch 통합 완료
- 남은 이슈:
  - `RequestHeader` 세부 필드 로컬 환경 미확인
  - `base_link`와 camera frame 사이 TF 연결은 1차 범위 밖으로 보류
  - `/tf` 토픽은 현재 미노출, `/tf_static`만 확인됨
  - 브릿지 통합 후 `/api/sport/request` 실기체 반복 검증 필요

## 1. 사전 준비
- 상태: 부분 완료
- 결정사항:
  - 1차 범위는 `chair 찾아`, `chair 앞으로 가`, `긴급 정지 / 정지 해제`
- 검증 결과:
  - localization / Nav2 / named place 이동 제외 결정 완료
  - 실기체 1차 검증은 `chair` 단일 객체와 direct approach 중심으로 진행하기로 고정
- 남은 이슈:
  - 운영자 개입 절차와 실기체 테스트 공간 조건 정리 필요

## 2. 인터페이스 고정
- 상태: 부분 완료
- 결정사항:
  - RGB topic: `/camera/color/image_raw`
  - RGB camera info: `/camera/color/camera_info`
  - depth topic: `/camera/depth/image_rect_raw`
  - depth camera info: `/camera/depth/camera_info`
  - robot pose topic 후보: `/utlidar/robot_pose`
  - primary command topic: `/cmd_vel`
  - final control request topic: `/api/sport/request`
- 검증 결과:
  - `/utlidar/robot_pose` 샘플 확인, `frame_id=odom`
  - `/api/sport/request` 타입 확인: `unitree_api/msg/Request`
  - `/cmd_vel` 타입 확인: `geometry_msgs/msg/Twist`
  - color camera frame 확인: `camera_color_optical_frame`
  - depth frame 확인: `camera_depth_optical_frame`
  - 1차 로컬 제어 frame을 `camera_link`로 사용하기로 결정
  - `camera_color_optical_frame` camera_info 수신 정상 확인
  - 공식 `unitree_ros2` `ros2_sport_client.cpp` 기준 request 생성 규칙 확인
    - `Move`: `parameter = {\"x\": vx, \"y\": vy, \"z\": vyaw}`
    - `StopMove`: `parameter` 없이 API ID만 사용
  - `/home/jnu/go2_ws/src/go2_driver`의 `cmd_vel_callback` 확인
    - `Twist.linear.x -> parameter["x"]`
    - `Twist.linear.y -> parameter["y"]`
    - `Twist.angular.z -> parameter["z"]`
    - `api_id=1008 Move`
  - 1차 시각화 기준 frame은 `camera_link`로 유지, RViz도 동일 기준으로 구성
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
- 상태: 구현 완료, 안정화 진행 완료
- 결정사항:
  - 1차 출력은 global `map`이 아니라 `camera_link` 기준 상대좌표로 publish
  - 대표 depth는 YOLO segmentation mask 내부 depth cluster 기반으로 산출
- 검증 결과:
  - [perception_node.py](/home/jnu/llm_yolo/backends/real/perception_node_real/perception_node_real/perception_node.py)에 실기체 RGB/depth/camera_info subscribe 추가
  - YOLO 추론 경로와 bbox+depth 기반 상대 pose 계산 뼈대 추가
  - `/perception/visible_objects`, `/perception/object_poses`, `/perception_debug` publish 경로 추가
  - [real_perception_params.yaml](/home/jnu/llm_yolo/configs/real/real_perception_params.yaml) 확장
  - `object_pose_frame=camera_link` 전제로 조정 완료
  - `py_compile` 문법 확인 완료
  - 실기체 marker 시각화용 `/perception/object_markers` publish 추가 완료
  - 같은 객체 중복 검출 억제 로직 추가 완료
  - `max_objects_per_class=0`, `same_object_distance_threshold_m=0.45` 반영 완료
  - `max_objects_per_class=0`은 클래스별 객체 수 제한 없음으로 해석
  - `yolo11s-seg.pt`, `depth_mode=mask_cluster`, `yolo_conf_threshold=0.25` 반영 완료
  - 실내 인지 후보 10종 반영 완료
- 남은 이슈:
  - `fallback_camera_frame`에 `camera_color_optical_frame` 반영 완료
  - perception 쪽도 `ultralytics` 런타임 패키지 확인 필요
  - `camera optical frame -> camera_link` 정적 TF 체인 확인 완료
  - `cv_bridge`와 NumPy ABI 충돌로 `/perception/debug_image`는 현재 비활성화 상태

## 5. perception 정확도 검증
- 상태: 1차 검증 진행 중
- 결정사항:
  - `chair` 기준 1차 안정화 완료 후 실내 후보 10종으로 인지 범위 확장
- 검증 결과:
  - 동일 의자 다중 인식 문제를 후처리와 파라미터 조정으로 완화
  - distance/pose가 웹 대시보드와 RViz marker 기준으로 일관되게 보이도록 조정
  - YOLO11s-seg mask 기반 depth cluster 방식에서 의자 segmentation 및 거리 추정 개선 확인
  - 여러 의자 표시를 위해 클래스별 객체 수 제한 해제 완료
- 남은 이슈:
  - `chair` 외 클래스별 검출 안정성 측정 필요
  - 실거리 대비 pose 오차 반복 측정 필요

## 6. `find_object` 단독 검증
- 상태: 미완료
- 결정사항:
  - real 1차 범위에서는 현재 시야 내 객체 접근을 우선하고, 탐색 동작은 후순위로 둠
- 검증 결과:
  - `chair 찾아` 경로는 실기체에서 아직 placeholder 성격이 남아 있어 full success 판정 단계 아님
- 남은 이슈:
  - `chair 찾아` 실기체 성공/실패 판정 확인 필요

## 7. direct 접근 backend 구현
- 상태: 구현 완료, 안정화 진행 완료
- 결정사항:
  - 접근 판단은 `camera_link` 기준 상대 pose 기반으로 유지
  - 접근 서버 출력은 `command_output_mode`로 분리
  - 현재 real 기본 출력은 `/cmd_vel`
  - 프로젝트 내부 브릿지가 `/cmd_vel`을 `/api/sport/request`로 변환
- 검증 결과:
  - [approach_object_server.py](/home/jnu/llm_yolo/backends/real/go2_skill_server_real/go2_skill_server_real/approach_object_server.py) 신설
  - [mvp_real.launch.py](/home/jnu/llm_yolo/launch/real/mvp_real.launch.py)에 `approach_object_server` wiring 추가
  - [real_nav_params.yaml](/home/jnu/llm_yolo/configs/real/real_nav_params.yaml)에 1차 접근 파라미터 초안 반영
  - [setup.py](/home/jnu/llm_yolo/backends/real/go2_skill_server_real/setup.py) entry point 추가
  - `camera_link` 기준 상대 pose를 사용하도록 1차 제어 경로 정렬 완료
  - `py_compile` 문법 확인 완료
  - `stale_pose_timeout_sec=2.5`, `target_hold_timeout_sec=1.5`, `min_tracking_confidence=0.20` 안정화 파라미터 반영 완료
  - 최근 유효 target hold 로직 반영으로 순간 미검출 시 즉시 abort하지 않도록 완화
  - [cmd_vel_to_sport_request_node.py](/home/jnu/llm_yolo/backends/real/go2_skill_server_real/go2_skill_server_real/cmd_vel_to_sport_request_node.py) 추가 완료
  - [cmd_vel_bridge_params.yaml](/home/jnu/llm_yolo/configs/real/cmd_vel_bridge_params.yaml) 추가 완료
  - [mvp_real.launch.py](/home/jnu/llm_yolo/launch/real/mvp_real.launch.py)에 `cmd_vel_to_sport_request_node` 자동 실행 반영 완료
  - `command_output_mode=cmd_vel` 반영 완료
  - `/cmd_vel` publish 단독 검증 완료
  - `go2_skill_server_real` 빌드 및 `cmd_vel_to_sport_request_node` entry point 확인 완료
- 남은 이슈:
  - 브릿지 포함 상태에서 실제 `/api/sport/request` 변환 및 실기체 이동 재검증 필요
  - `BalanceStand` 선행 필요 여부는 현재 접근 서버 직접 전송 유지

## 8. 단일 접근 검증
- 상태: 1차 검증 진행 중
- 결정사항:
  - 현재 시야 내 `chair` 접근을 우선 검증
- 검증 결과:
  - `chair 앞으로 가` 경로에서 `arrived:approach:chair`까지의 1차 성공 흐름 확인
  - stale target 문제를 파라미터 및 hold 로직으로 완화
  - 접근 서버 `/cmd_vel` 출력 확인 완료
- 남은 이슈:
  - `/cmd_vel` 브릿지 포함 상태에서 반복 3회 이상 정량 검증과 최종 정지 거리 측정 필요

## 9. safety 검증
- 상태: 부분 구현, 검증 미완료
- 결정사항:
  - 1차는 보수적으로 stop/abort 우선
- 검증 결과:
  - watchdog heartbeat 경로 정상 확인
  - stale pose timeout / confidence threshold / target hold 관련 보호 로직 반영
  - 접근 서버 emergency stop 시 StopMove burst 유지
  - cmd_vel 브릿지에 속도 clamp / cmd_vel timeout watchdog / emergency stop gate / zero cmd StopMove 반영
- 남은 이슈:
  - emergency stop 반복 검증
  - stale pose abort 정식 실기체 반복 검증
  - person 개입 시 stop/pause
  - confidence/거리 제한 검증 필요

## 10. 후속 예정
- `/cmd_vel` 브릿지 포함 상태에서 `/api/sport/request` 변환 검증
- `/cmd_vel` 기반 실기체 접근 반복 검증
- `chair 찾아서 앞으로 가` 복합 명령 실기체 검증
- `person` 인지 결과를 실제 safety stop/pause 정책에 연결
- localization / Nav2 기반 장거리 이동 검토
- RViz `camera_link` 기준 시각화는 완료, `odom`/정식 TF 체인 정리는 후속 검토
- web monitor real 전용 개선은 1차 완료, 추가 UI 미세조정은 후속 선택 과제
