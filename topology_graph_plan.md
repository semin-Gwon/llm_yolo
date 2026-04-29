# Topology Graph Plan Draft

> 이 문서는 [object_memory_plan.md](/home/jnu/llm_yolo/object_memory_plan.md)의 **확장 계획**이다.  
> 선행 조건: [object_memory_plan.md](/home/jnu/llm_yolo/object_memory_plan.md)의 구현/검증 완료 이후에만 진행한다.

## 1. 목표
- 객체 메모리(무엇/대략 어디)를 기반으로, 방-문-통로 연결 그래프를 추가해 탐색 순서와 실패 복구를 최적화한다.
- 기존 Nav2를 대체하지 않고, 상위 레벨의 전역 탐색 순서 결정기로 동작시킨다.
- 다중 방 환경에서 `"chair 찾아"`, `"tv 찾아"` 같은 명령의 평균 탐색 시간과 성공률을 개선한다.

## 2. 범위
### 2.1. 1차 대상
- Room node + Doorway node 기반 Topology Graph 생성
- Graph 기반 room 방문 순서 계획기(`topology_planner_node`)
- Object Memory와 room_id 연결을 이용한 후보 room 우선순위화
- Mission Manager와의 비침투형 연동(feature flag)

### 2.2. 1차 제외
- 의미 이름 자동 생성(VLM 기반 room naming)
- 멀티 로봇 분산 탐색
- 학습 기반 edge cost 자동 튜닝

## 3. 설계 원칙
### 3.1. 계층 분리
- Topology Graph: 전역 순서(어느 방부터 방문할지)만 결정
- Nav2: 각 구간의 로컬/전역 경로 주행 담당
- Object Memory: 객체 후보 위치 prior 제공

### 3.2. Fail-safe 기본값 유지
- `topology_enabled=false`가 기본값
- 그래프 사용 중 오류/불확실 상황에서는 즉시 기존 경로(메모리+Nav2)로 fallback

### 3.3. 동적 비용 업데이트
- 문 통과 실패, 반복 재계획, 장애물 혼잡도 등을 edge cost에 반영
- 일시 차단(edge blocked TTL) 지원

## 4. 노드 구성
### 4.1. `topology_graph_builder_node`
역할:
- occupancy 기반 room 분할 결과를 받아 graph 생성/갱신
- room/doorway/edge 메타데이터 publish

입력:
- room segmentation 결과(라벨 맵 또는 room polygon 집합)
- map/TF 정보

출력:
- `/topology/graph` (노드/엣지 구조)
- `/topology/rooms` (room polygon + centroid)

### 4.2. `topology_planner_node`
역할:
- 현재 room + 목표(객체 class/room)를 받아 room 방문 시퀀스 생성
- Dijkstra/A* 기반 최저 비용 room 경로 계산

입력:
- `/topology/graph`
- `/object_memory/objects`
- 현재 로봇 위치(map frame)

출력:
- `/topology/plan` (room sequence + doorway sequence)

### 4.3. `topology_executor` (Mission Manager 연동 계층)
역할:
- `/topology/plan`을 waypoint 시퀀스로 변환해 Nav2 goal 순차 실행
- room 도착 시 local search 수행(`scan_scene(local_mode)` 재사용)

## 5. 데이터 모델
### 5.1. Node
- `node_id`
- `type`: `room | doorway | waypoint`
- `room_id` (doorway/waypoint는 소속 room 참조)
- `x, y`
- `metadata` (최종 통과 시간, 실패 카운트 등)

### 5.2. Edge
- `from_node_id`, `to_node_id`
- `distance_cost`
- `risk_cost`
- `blocked_until` (선택)
- `last_success_time`, `last_fail_time`, `consecutive_fail_count`

### 5.3. Room
- `room_id`
- `polygon`
- `centroid`
- `object_hints` (해당 room에서 관측된 class 통계)

## 6. Object Memory 연동
### 6.1. room_id 할당
- Object Memory 엔트리(`map_x,map_y`)를 room polygon에 point-in-polygon으로 매핑
- 저장/업데이트 시 `room_id` 동기화

### 6.2. 후보 room 점수
- class 일치 엔트리의 `confidence`, `recency`, `localization_score` 합산
- 가까운 room 가중치 우선
- stale object는 점수에서 제외 또는 큰 패널티

### 6.3. 탐색 전략
- 1순위 room 먼저 방문 후 local reacquire
- 실패 시 그래프 경로 기준 다음 후보 room 순회

## 7. 실행 흐름
1. 사용자 명령: `"chair 찾아"`
2. 라우터는 `find_object(chair)` 또는 mission_plan 생성
3. executor가 topology 사용 가능 여부 확인
4. 가능하면 planner가 room 방문 시퀀스 생성
5. Nav2로 첫 room 진입 지점 이동
6. room 내 local scan/reacquire 수행
7. 성공 시 approach 단계로 전환, 실패 시 다음 room으로 이동
8. 전체 실패 시 기존 정책(abort_all/return_home) 적용

## 8. 파라미터(초기안)
- `topology_enabled: false`
- `topology_plan_timeout_sec: 3.0`
- `edge_fail_penalty: 2.0`
- `edge_block_ttl_sec: 30.0`
- `room_search_timeout_sec: 20.0`
- `max_rooms_per_search: 5`
- `replan_on_edge_fail: true`

## 9. 검증 계획
### 9.1. 그래프 생성 검증
- room/doorway가 맵과 일치하게 생성되는지 확인
- 잘못 연결된 edge(벽 관통)가 없는지 확인

### 9.2. 탐색 효율 검증
- baseline(그래프 미사용) 대비 평균 탐색 시간 비교
- 다중 방 시나리오에서 성공률 비교

### 9.3. 실패 복구 검증
- 문 앞 장애물로 edge 실패 유도
- 다른 경로로 재계획되는지 확인

### 9.4. 회귀 검증
- `topology_enabled=false`일 때 기존 동작 완전 동일성 확인

## 10. 완료 조건
- 그래프 기반 room 순회 탐색이 실제로 동작
- edge 실패 시 자동 재계획 동작
- baseline 대비 다중 방 탐색 성능 개선(시간 또는 성공률)
- 기존 object memory + Nav2 경로 회귀 없음

## 11. 리스크와 대응
### 11.1. room 분할 품질 저하
- 대응: 수동 seed/merge 도구 또는 최소 휴리스틱 후처리 제공

### 11.2. doorway 검출 오류
- 대응: doorway node confidence, 실패 빈도 기반 edge cost 자동 상승

### 11.3. 그래프-실주행 불일치
- 대응: 실행 실패를 edge 상태에 반영하고 빠르게 재계획

## 12. 구현 순서
1. graph 데이터 구조/토픽 스키마 정의
2. `topology_graph_builder_node` 구현(오프라인/정적 갱신부터)
3. `topology_planner_node` 구현(Dijkstra/A*)
4. object memory `room_id` 매핑 연결
5. mission_manager 연동(feature flag)
6. 다중 방 시나리오 검증 및 cost 튜닝
