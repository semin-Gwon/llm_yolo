# Mission Plan Schema Draft

이 문서는 현재 단일 `Intent` 기반 구조를 복합 명령까지 확장하기 위한 초안이다.
현재 시스템은 아래 단일 intent만 직접 실행할 수 있다.
- `navigate_to_named_place`
- `find_object`
- `scan_scene`
- `cancel`

복합 명령을 처리하려면, LLM 출력이 단일 intent가 아니라 `mission_plan` 형태를 지원해야 한다.

## 1. 현재 한계
예를 들어 아래 문장은 현재 schema로 충분히 표현되지 않는다.
- `center로 가서 chair 찾아`
- `chair 찾고 없으면 center로 돌아와`
- `center에서 chair를 스캔하고 사람도 찾아`

이유는 현재 [Intent.msg](/home/jnu/llm_yolo/llm_yolo_interfaces/msg/Intent.msg)가 단일 액션만 담기 때문이다.

## 2. 목표
확장 후에도 아래 원칙은 유지한다.
- action server 계약은 최대한 유지
- mission_manager가 실행 순서를 책임짐
- LLM은 계획을 제안하고, 실행은 mission_manager가 담당
- 실패 정책은 mission_manager가 결정

## 3. Draft JSON Schema
```json
{
  "intent": "mission_plan",
  "steps": [
    {
      "intent": "navigate_to_named_place",
      "target_type": "named_place",
      "target_value": "center",
      "max_duration_sec": 30,
      "confidence": 0.95
    },
    {
      "intent": "find_object",
      "target_type": "object_class",
      "target_value": "chair",
      "max_duration_sec": 20,
      "confidence": 0.88
    }
  ],
  "failure_policy": "abort_all",
  "confidence": 0.91
}
```

## 4. Step 규칙
각 step은 현재 단일 intent와 거의 같은 필드를 가진다. 추가로 `run_if`를 사용할 수 있다.

허용 intent:
- `navigate_to_named_place`
- `find_object`
- `scan_scene`
- `cancel`

허용 target_type:
- `named_place`
- `object_class`
- `none`

허용 run_if:
- `always`
- `previous_failed`
- `previous_succeeded`

## 5. Failure Policy 초안
초기 버전에서는 아래 세 가지만 허용하는 것이 현실적이다.
- `abort_all`
  - 어떤 step이 실패하면 전체 미션 종료
- `continue`
  - step 실패를 기록하고 다음 step 진행
- `return_home`
  - 실패 시 `center` 같은 지정 위치로 복귀 후 종료

현재 MVP 기준으로는 `abort_all`이 기본값이어야 한다.

## 6. 예시
### 예시 1
입력:
- `center로 가서 chair 찾아`

출력:
```json
{
  "intent": "mission_plan",
  "steps": [
    {
      "intent": "navigate_to_named_place",
      "target_type": "named_place",
      "target_value": "center",
      "max_duration_sec": 30,
      "confidence": 0.95
    },
    {
      "intent": "find_object",
      "target_type": "object_class",
      "target_value": "chair",
      "max_duration_sec": 20,
      "confidence": 0.9
    }
  ],
  "failure_policy": "abort_all",
  "confidence": 0.92
}
```

### 예시 2
입력:
- `chair 찾고 없으면 center로 돌아와`

출력:
```json
{
  "intent": "mission_plan",
  "steps": [
    {
      "intent": "find_object",
      "target_type": "object_class",
      "target_value": "chair",
      "max_duration_sec": 20,
      "run_if": "always",
      "confidence": 0.9
    }
  ],
  "failure_policy": "return_home",
  "confidence": 0.88
}
```

### 예시 3
입력:
- `chair 찾고 없으면 center로 가서 다시 찾아`

출력:
```json
{
  "intent": "mission_plan",
  "steps": [
    {
      "intent": "find_object",
      "target_type": "object_class",
      "target_value": "chair",
      "max_duration_sec": 20,
      "run_if": "always",
      "confidence": 0.9
    },
    {
      "intent": "navigate_to_named_place",
      "target_type": "named_place",
      "target_value": "center",
      "max_duration_sec": 30,
      "run_if": "previous_failed",
      "confidence": 0.9
    },
    {
      "intent": "find_object",
      "target_type": "object_class",
      "target_value": "chair",
      "max_duration_sec": 20,
      "run_if": "previous_failed",
      "confidence": 0.9
    }
  ],
  "failure_policy": "abort_all",
  "confidence": 0.9
}
```

### 예시 4
입력:
- `yellow_box 찾고 없으면 red_box 찾아`

출력:
```json
{
  "intent": "mission_plan",
  "steps": [
    {
      "intent": "find_object",
      "target_type": "object_class",
      "target_value": "yellow_box",
      "max_duration_sec": 20,
      "run_if": "always",
      "confidence": 0.9
    },
    {
      "intent": "find_object",
      "target_type": "object_class",
      "target_value": "red_box",
      "max_duration_sec": 20,
      "run_if": "previous_failed",
      "confidence": 0.9
    }
  ],
  "failure_policy": "abort_all",
  "confidence": 0.9
}
```

## 7. 구현 전략
### 7.1. 1단계
- 문서 수준 schema 확정
- LLM prompt에 `mission_plan` 형식 추가
- 현재 `Intent.msg`는 유지
- `mission_manager`는 우선 단일 intent만 계속 지원

### 7.2. 2단계
- 새 메시지 추가 검토
  - 예: `MissionPlan.msg`
  - 또는 JSON string 기반 임시 bridge
- `mission_manager`를 sequence executor로 확장

### 7.3. 3단계
- 복합 명령의 실패 정책 구현
- fallback, return_home, continue 지원

## 8. 권장 방향
바로 ROS 메시지를 크게 바꾸기보다, 먼저 문서와 LLM 출력 schema를 확정하는 게 맞다.
그 다음 `mission_manager`를 확장하고, 마지막에 인터페이스를 정식 메시지로 올리는 순서가 안전하다.
