# Object Memory Plan Draft

`plan.md` 반영 예정 위치:
- 새 `Phase 4-5. Graph-aware Map Frame Object Memory`
- 삽입 위치: 현재 [plan.md](/home/jnu/llm_yolo/plan.md)의 `Phase 4-4. Person 대응 및 동적 객체 정책` 바로 다음
- 반영 시 현재 `Phase 4-5. VLM 기반 의미 인지 확장`과 이후 phase 번호는 한 단계씩 뒤로 이동

## 1. 목표
- 현재 시야에 보이는 객체만 접근 가능한 구조를 확장해, 한 번 본 `chair`, `tv`의 위치를 기억하고 시야 밖에서도 재접근 가능하게 만든다.
- 객체 메모리는 `정확한 절대 truth`가 아니라, **재획득(reacquisition)을 위한 prior**로 사용한다.
- 실기체 전환을 고려해 `map` frame 기반 구조를 유지하되, loop closure / relocalization 시 좌표 재보정이 가능하도록 설계한다.

## 2. 범위
### 2.1. 1차 대상
- `chair`
- `tv`

### 2.2. 1차 제외 대상
- `person`
- `couch`, `dining table`, `bed`
- semantic relation (`문 옆`, `테이블 앞`) 기반 질의

### 2.3. 사용 목적
- live perception이 없을 때 기억된 객체 위치 **근처**로 이동
- 도착 후 `scan_scene` 또는 `find_object`로 재획득
- 재획득 성공 시 최종 접근

## 3. 설계 원칙
### 3.1. map frame memory를 기본으로 사용
- 운영 중에는 객체를 `map` 기준 절대좌표처럼 사용한다.
- 즉시 조회/이동은 단순 object memory처럼 빠르게 처리한다.

### 3.2. graph-aware metadata를 내부에 같이 저장
- 다음 관측 메타데이터를 함께 저장한다.
  - `observer_pose_map_at_observation`
  - `relative_object_pose_from_observer`
  - `observation_time`
  - `source_frame`
  - `localization_quality_snapshot`
- 핵심은 **node_id 의존 설계를 피하는 것**이다.
- `node_id`가 필요하면 참고용으로만 유지하고, 메모리 엔트리의 유일 식별자로 사용하지 않는다.
- 중요한 원칙:
  - `relative_object_pose_from_observer`는 **object_memory_node에서 나중에 역산하지 않는다**
  - 이 값은 `/perception/object_poses`를 생성하는 perception 계층에서 **관측 생성 시점 보행 베이스(`base_link`) 기준으로 함께 계산해 전달**한다
  - 즉 object memory는 `abs_pos`만 받는 구조가 아니라, `observer pose snapshot + relative observation`을 직접 수신하는 구조로 확장한다

### 3.3. memory는 최종 목표가 아니라 근처 탐색 prior
- memory 좌표로 바로 최종 접근하지 않는다.
- memory 좌표 **근처**로 이동 후, live perception으로 재획득한 뒤 최종 접근한다.

### 3.4. live-first, memory-second
- 현재 perception에서 객체 pose가 보이면 항상 live pose를 우선 사용한다.
- live pose가 없을 때만 memory fallback을 사용한다.

## 4. 새 노드
### 4.1. `object_memory_node`
역할:
- `/perception/object_poses`를 구독
- `chair`, `tv`의 memory를 저장/병합/만료 관리
- loop closure / relocalization 신호가 오면 저장된 object pose를 재보정
- memory 조회 결과를 publish

입력:
- `/perception/object_poses` 또는 그 확장 인터페이스
  - 최소 요구사항:
    - `abs_pos`
    - `observer_pose_map_at_observation`
    - `relative_object_pose_from_observer`
    - `observation_time`
- `map -> base_link` 또는 `odom` / TF
- RTAB-Map loop closure 관련 정보

출력:
- `/semantic_map/objects` 또는 `/object_memory/objects`

## 5. 저장 구조
각 memory 엔트리는 최소한 아래 필드를 가진다.

### 5.1. 운영용 필드
- `class_name`
- `map_x_m`
- `map_y_m`
- `map_z_m`
- `confidence`
- `last_seen_time`
- `seen_count`
- `stale`

### 5.2. 보정용 필드
- `observer_pose_map_at_observation` (관측 생성 시점 snapshot)
- `relative_object_pose_from_observer` (관측 생성 시점 계산)
- `observation_time`
- `source_frame`
- `last_loop_closure_age_sec`
- `pose_jump_recent`
- `localization_score`

품질 지표 원칙:
- `is_localized_well` 같은 단순 boolean 대신 수치형 힌트를 우선 사용
- 1차 구현에서는 완전한 covariance가 없더라도 다음을 조합해 score를 만든다.
  - 최근 loop closure 발생 시각
  - 최근 pose jump 여부
  - 관측 당시 odom 안정성 proxy
- 1차 계산식 예시:
  - `localization_score = 1.0`
  - 최근 `loopClosureId != 0`가 짧은 시간 내 발생했으면 `+0.2`
  - 최근 pose jump가 감지됐으면 `-0.3`
  - 관측 당시 선속도/각속도가 낮으면 `+0.1`
  - 최종 score는 `0.0 ~ 1.0` 범위로 clamp
- 목적:
  - 정교한 uncertainty 모델이 아니라, 병합/우선순위 결정에 쓸 **단순한 quality hint**를 제공하는 것

## 6. 병합 정책
### 6.1. 병합 조건
- 같은 `class_name`
- 현재 memory 엔트리와 거리 `merge_distance_m` 이내

보조 조건:
- 시간 차이가 너무 크지 않을 것
- bbox 크기 proxy 또는 관측 거리 proxy가 급격히 다르지 않을 것
- 필요 시 view direction 차이가 너무 크지 않을 것

### 6.2. 병합 방식
- 최근 관측일수록 더 크게 반영
- localization quality가 좋은 관측일수록 가중치 증가
- 단순 overwrite보다는 가중 업데이트를 우선 고려
- 같은 클래스가 가까이 여러 개 있는 환경에서는 병합을 보수적으로 수행한다

## 7. 만료 / staleness 정책
### 7.1. TTL
- `memory_ttl_sec`를 넘긴 엔트리는 `stale=true`

### 7.2. stale object 사용 규칙
- stale object는 직접 최종 접근 대상으로 쓰지 않음
- stale object는 “근처 재탐색 후보”로만 사용

### 7.3. 동적 객체 제외
- `person`은 memory에 넣지 않음

### 7.4. 초기 파라미터 권장값
- `merge_distance_m = 0.8`
- `memory_ttl_sec = 300`
- `stale_ttl_sec = 120`
- `memory_reacquire_radius_m = 1.0`
- `memory_reacquire_standoff_m = 0.8`

## 8. 재보정 트리거
### 8.1. loop closure 이벤트 기반
- RTAB-Map의 loop closure 신호를 받아 재보정 수행
- 예: `/rtabmap/info` 계열 메시지의 `loopClosureId != 0`

### 8.2. pose jump threshold 기반
- `map -> base_link` 또는 `map -> odom`가 임계값 이상 급변하면 relocalization으로 간주
- 이때 memory 재보정 수행

### 8.3. 설계 원칙
- loop closure direct signal이 있으면 그걸 우선 사용 (`/rtabmap/info`의 `loopClosureId != 0`)
- direct signal이 없거나 불안정할 때는 pose jump를 보조 트리거로 사용
- pose jump 기반 재보정은 오탐 방지를 위해 다음 조건을 추가한다.
  - 로봇 선속도/각속도가 낮은 시점에만 유효
  - 짧은 시간 안의 반복 jump는 debounce 처리
- **Graceful Degradation**: RTAB-Map이 실행되지 않거나 `/rtabmap/info` 토픽이 발행되지 않는 경우(Silent Failure 방지), 재보정을 비활성화하고 순수 map frame memory로 동작하도록 fallback 로직 구현

## 9. 재보정 방식
각 memory 엔트리에 대해:
1. 저장된 `observer_pose_map_at_observation`를 기준으로
2. 저장된 `relative_object_pose_from_observer`를 다시 펼쳐서
3. 현재 보정된 pose 기준 object map pose를 다시 계산

의도:
- 평상시에는 `map_x_m`, `map_y_m`만 빠르게 사용
- 보정이 필요할 때만 relative observation을 사용해 재투영
- **Non-blocking Execution**: 재보정 연산은 비동기(asynchronous) 혹은 짧은 주기 타이머로 실행하여, `approach_object_server` 등 다른 시스템의 탐색 명령 응답 지연을 유발하지 않아야 한다.

## 9.1. reacquisition 목표 정책
- memory fallback 시 객체 절대좌표를 최종 접근 goal로 직접 사용하지 않는다
- 다음 파라미터를 명시적으로 둔다.
  - `memory_reacquire_radius_m`
  - `memory_reacquire_standoff_m`
  - `memory_reacquire_yaw_policy`
- 1차 구현 기본안:
  - memory object 좌표 근처 `1.0m` 반경의 재탐색 지점으로 이동
  - yaw는 객체 추정 방향 또는 최근 관측 방향을 우선 사용
  - 도착 후 local reacquire를 수행

## 9.2. local_reacquire 인터페이스
1차 구현에서는 **새 action을 만들지 않고**, 기존 `scan_scene`에 local mode를 추가한다.

권장 확장:
- `scan_scene` goal에 다음 필드 추가
  - `bool local_mode`
  - `float32 local_scan_radius_m`
  - `float32 local_reference_x_m`
  - `float32 local_reference_y_m`

1차 local reacquire 동작:
- 현재 위치에서 회전 탐색 수행
- 기존 광범위 fallback named place 이동은 수행하지 않음
- 필요 시 `local_reference_*` 기준 반경 내부에서만 성공 판정 힌트로 사용

설계 원칙:
- memory fallback 이후에는 `scan_scene(local_mode=true)`를 호출
- 기존 `find_object`의 전역 fallback 정책과 분리

## 10. 한계와 대응
### 10.1. observer pose 정확도 의존
한계:
- localization 오차는 object memory에도 그대로 전달된다.

대응:
- memory 좌표를 최종 truth가 아니라 재획득 prior로 사용
- memory로 근처까지 이동 후 live perception 재확인 필수

### 10.2. loop closure 전 drift 누적
한계:
- loop closure 전에는 저장 좌표에 drift가 누적될 수 있다.

대응:
- localization quality snapshot 저장
- confidence / recency / localization quality를 함께 사용해 memory 우선순위 결정
- stale하거나 품질 낮은 memory는 직접 접근 금지
- memory fallback은 최종 goal이 아니라 reacquire waypoint로만 사용

### 10.3. node_id lifecycle 의존성
한계:
- SLAM node lifecycle에 강하게 묶이면 깨질 수 있다.

대응:
- `node_id` 중심 설계를 피하고 pose snapshot 중심 설계를 사용

### 10.4. 객체 이동 여부 미판별
한계:
- 물체가 실제로 옮겨졌는지 memory만으로 알 수 없다.

대응:
- TTL / stale 정책 추가
- `person` 같은 동적 객체 제외
- 최종 접근 전 live reacquire 필수

### 10.5. loop closure 없는 환경
한계:
- loop closure가 없으면 순수 map frame memory에 가까워진다.

대응:
- 기본은 map frame memory로도 동작 가능하게 유지
- loop closure가 있는 경우에만 보정 이득을 추가로 얻는 구조로 수용

## 11. 접근 경로 확장
현재:
- `approach_object_server`는 live `/perception/object_poses`만 사용

확장 후:
1. live pose 조회
2. 없으면 object memory 조회
3. memory 위치 근처의 reacquire waypoint로 이동
4. 도착 후 **local_reacquire** 수행
5. 재획득 성공 시 최종 접근
6. 재획득 실패 시 **Mission Manager로 즉시 `ABORTED` 반환 및 fallback 종료 방침 적용** (목표지점 근처에서 이동 불가 상태로 맴도는 방치 현상 예방)

원칙:
- memory fallback 이후에는 기존 `scan_scene`의 광범위 fallback 정책을 그대로 재사용하지 않는다
- memory fallback 이후 재획득은 별도 좁은 범위의 `local_reacquire` 정책으로 분리한다
- 이유:
  - memory fallback과 기존 `find_object` fallback이 중첩되면 실행 경로가 과도하게 길어질 수 있음

## 12. 선택 정책
같은 클래스 memory 엔트리가 여러 개면:
- 1차는 거리 우선
- 이후 필요 시 최근성 / confidence / localization quality 가중치 추가
- 1차에서도 동일 클래스가 밀집된 환경을 고려해 `거리 + 최근성 + localization_score`의 단순 가중 합을 기본 후보 점수로 고려한다

1차 후보 점수 예시:
- **`stale == true`인 경우:**
  - `score = -9999.0` (접근 대상으로 계산 완전 배제)
- **`stale == false`인 경우:**
  - `score = -distance_to_robot`
  - `+ recent_bonus`
  - `+ localization_score * 0.5`

목적:
- 완벽한 data association이 아니라, 1차 운영 가능한 우선순위 규칙 확보

## 13. 구현 순서
1. perception 계층에서 관측 메타데이터(`observer_pose snapshot`, `relative observation`)를 함께 publish하도록 확장
2. `object_memory_node` 추가
3. memory 저장/병합 로직 구현
4. `/object_memory/objects` publish
5. `approach_object_server`에 memory fallback 연결
6. `scan_scene(local_mode)` 추가
7. TTL / stale 정책 추가
8. `chair`, `tv` 기준 memory fallback 실검증
9. loop closure / pose jump 트리거 추가
10. memory 재보정 로직 추가
11. 재보정 포함 실검증

구현 순서 원칙:
- 먼저 **보정 없는 map frame memory fallback**을 완성
- 그 다음 **graph-aware 재보정**을 얹는다
- 즉 “기본 기능 먼저, 보정은 그 다음” 순서를 따른다

## 14. 검증 계획
### 14.0. 필수 선행 검증 (실구현 이전)
- Isaac Sim + RTAB-Map 환경에서 `/rtabmap/info` 토픽의 `loopClosureId` 필드가 명확하게 발행되는지 실검증 (이 기능이 동작하지 않으면 14.4 재보정 로직 검증은 보류)

### 14.1. 저장
- `chair`, `tv`를 시야에서 본 뒤 memory에 저장되는지 확인
- 관측 메타데이터가 perception 시점 기준으로 함께 저장되는지 확인
- 같은 클래스 객체가 멀리 떨어져 있을 때 별도 엔트리로 저장되는지 확인

### 14.2. fallback
- 시야에서 사라진 뒤 `"chair 앞으로 가"`가 memory fallback으로 reacquire waypoint까지 이동하는지 확인

### 14.3. 재획득
- memory fallback 후 local reacquire로 재획득 가능한지 확인
- 기존 `find_object` fallback policy가 호출되지 않고 local mode만 쓰는지 확인

### 14.4. 재보정
- loop closure 또는 pose jump 이후 memory 좌표가 재계산되는지 확인
- 낮은 속도 구간의 pose jump에서만 재보정이 트리거되는지 확인

### 14.5. stale
- 오래된 memory가 stale 처리되고 직접 접근 대상에서 제외되는지 확인

### 14.6. 밀집 동일 클래스
- 같은 클래스 객체 두 개가 가까이 있는 환경에서 잘못 병합되지 않는지 확인
- 병합이 일어나도 추후 재관측으로 안정적으로 분리/갱신 가능한지 확인

## 15. 완료 조건
- `chair`, `tv` memory 저장 가능
- live pose가 없을 때 memory fallback 이동 가능
- memory는 최종 목표가 아니라 reacquisition prior로만 사용
- stale object는 직접 최종 접근 대상이 아님
- loop closure / relocalization 후 좌표 재보정 가능
- 기존 live perception 기반 접근 경로는 회귀 없음
