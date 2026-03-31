import json
import re
import urllib.error
import urllib.request


ALLOWED_INTENTS = {'navigate_to_named_place', 'find_object', 'scan_scene', 'cancel'}
ALLOWED_TOP_LEVEL_INTENTS = ALLOWED_INTENTS | {'mission_plan'}
ALLOWED_TARGET_TYPES = {'named_place', 'object_class', 'none'}
ALLOWED_FAILURE_POLICIES = {'abort_all', 'continue', 'return_home'}
ALLOWED_SPEED_HINTS = {'slow', 'normal', 'fast'}
ALLOWED_RUN_IF = {'always', 'previous_failed', 'previous_succeeded'}


def build_prompt(text: str, named_places: list[str], object_classes: list[str]) -> str:
    return (
        'You are a strict intent parser for a mobile robot. '
        'Return only valid JSON. No prose, no markdown.\n'
        'For single actions return keys intent,target_type,target_value,max_duration_sec,speed_hint,confidence.\n'
        'For multi-step commands return keys intent,steps,failure_policy,confidence where intent must be mission_plan. Each step may include speed_hint and run_if.\n'
        f'Allowed top-level intents: {sorted(ALLOWED_TOP_LEVEL_INTENTS)}\n'
        f'Allowed step intents: {sorted(ALLOWED_INTENTS)}\n'
        f'Allowed named places: {named_places}\n'
        f'Allowed object classes: {object_classes}\n'
        f'Allowed failure_policy: {sorted(ALLOWED_FAILURE_POLICIES)}\n'
        'Rules:\n'
        '- If the user asks to go to a place, use navigate_to_named_place with target_type named_place.\n'
        '- If the user asks to find an object, use find_object with target_type object_class.\n'
        '- If the user asks to scan, use scan_scene with target_type object_class.\n'
        '- If the user asks to stop or cancel, use cancel with target_type none and empty target_value.\n'
        '- Use speed_hint slow for phrases like 천천히/느리게/slow, fast for 빠르게/빨리/fast, otherwise normal.\n'
        '- If the user asks for multiple actions in sequence, use intent mission_plan and provide ordered steps.\n'
        '- mission_plan steps may only use navigate_to_named_place, find_object, scan_scene, cancel.\n'
        '- Each mission_plan step may include run_if: always, previous_failed, previous_succeeded. Use always by default.\n'
        '- If the user says to return to center/home only when find_object fails, do NOT add a second navigate step. Use a single find_object step with failure_policy return_home.\n'
        '- Use failure_policy abort_all by default unless the user explicitly asks to continue or return home/center on failure.\n'
        '- Confidence must be a number between 0.0 and 1.0.\n'
        'Example single intent JSON: {"intent":"find_object","target_type":"object_class","target_value":"chair","max_duration_sec":30,"speed_hint":"normal","confidence":0.9}\n'
        'Example mission plan JSON: {"intent":"mission_plan","steps":[{"intent":"navigate_to_named_place","target_type":"named_place","target_value":"center","max_duration_sec":30,"speed_hint":"normal","run_if":"always","confidence":0.95},{"intent":"find_object","target_type":"object_class","target_value":"chair","max_duration_sec":30,"speed_hint":"normal","run_if":"always","confidence":0.9}],"failure_policy":"abort_all","confidence":0.92}\n'
        f'User text: {text}\n'
    )


def call_ollama(base_url: str, model: str, prompt: str, timeout_sec: float) -> dict:
    payload = {
        'model': model,
        'prompt': prompt,
        'stream': False,
        'format': 'json',
    }
    req = urllib.request.Request(
        url=base_url.rstrip('/') + '/api/generate',
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        raw = json.loads(resp.read().decode('utf-8'))
    response_text = raw.get('response', '{}')
    return json.loads(response_text)


def validate_step(step: dict, named_places: list[str], object_classes: list[str]) -> dict:
    intent = str(step.get('intent', '')).strip()
    target_type = str(step.get('target_type', '')).strip()
    target_value = str(step.get('target_value', '')).strip()
    confidence = float(step.get('confidence', 0.0))
    max_duration_sec = int(step.get('max_duration_sec', 30))
    speed_hint = str(step.get('speed_hint', 'normal')).strip().lower() or 'normal'
    run_if = str(step.get('run_if', 'always')).strip().lower() or 'always'

    if intent not in ALLOWED_INTENTS:
        raise ValueError(f'invalid intent: {intent}')
    if target_type not in ALLOWED_TARGET_TYPES:
        raise ValueError(f'invalid target_type: {target_type}')
    if not 0.0 <= confidence <= 1.0:
        raise ValueError(f'invalid confidence: {confidence}')
    if max_duration_sec <= 0:
        raise ValueError(f'invalid max_duration_sec: {max_duration_sec}')
    if speed_hint not in ALLOWED_SPEED_HINTS:
        raise ValueError(f'invalid speed_hint: {speed_hint}')
    if run_if not in ALLOWED_RUN_IF:
        raise ValueError(f'invalid run_if: {run_if}')

    if intent == 'navigate_to_named_place':
        if target_type != 'named_place' or target_value not in named_places:
            raise ValueError('invalid named place target')
    elif intent in {'find_object', 'scan_scene'}:
        if target_type != 'object_class' or target_value not in object_classes:
            raise ValueError('invalid object target')
    elif intent == 'cancel':
        target_type = 'none'
        target_value = ''

    return {
        'intent': intent,
        'target_type': target_type,
        'target_value': target_value,
        'confidence': confidence,
        'max_duration_sec': max_duration_sec,
        'speed_hint': speed_hint,
        'run_if': run_if,
    }


def _has_failure_condition(text: str) -> bool:
    lowered = text.lower()
    patterns = [
        r'없으면',
        r'못\s*찾',
        r'실패하',
        r'if\s+not\s+found',
        r'if\s+fail',
    ]
    return any(re.search(pattern, lowered) for pattern in patterns)


def _has_return_home_request(text: str) -> bool:
    lowered = text.lower()
    patterns = [
        r'복귀',
        r'돌아가',
        r'return',
        r'go\s+back',
        r'home',
        r'center',
    ]
    return any(re.search(pattern, lowered) for pattern in patterns)


def _normalize_retry_at_center(text: str, routed: dict) -> dict:
    if routed.get('kind') != 'mission_plan':
        return routed
    lowered = text.lower()
    if '다시' not in text and 'again' not in lowered:
        return routed
    if not _has_failure_condition(text):
        return routed
    steps = list(routed.get('steps', []))
    if len(steps) != 2:
        return routed
    first, second = steps
    if first.get('intent') != 'find_object':
        return routed
    if second.get('intent') != 'navigate_to_named_place' or second.get('target_value') != 'center':
        return routed
    retry_step = dict(first)
    retry_step['run_if'] = 'previous_failed'
    center_step = dict(second)
    center_step['run_if'] = 'previous_failed'
    first_step = dict(first)
    first_step['run_if'] = 'always'
    normalized = dict(routed)
    normalized['steps'] = [first_step, center_step, retry_step]
    normalized['failure_policy'] = 'abort_all'
    return normalized


def _normalize_alternative_target(text: str, routed: dict) -> dict:
    if routed.get('kind') != 'mission_plan':
        return routed
    if not _has_failure_condition(text):
        return routed
    steps = list(routed.get('steps', []))
    if len(steps) != 2:
        return routed
    first, second = steps
    if first.get('intent') != 'find_object' or second.get('intent') != 'find_object':
        return routed
    first_step = dict(first)
    first_step['run_if'] = 'always'
    second_step = dict(second)
    second_step['run_if'] = 'previous_failed'
    normalized = dict(routed)
    normalized['steps'] = [first_step, second_step]
    normalized['failure_policy'] = 'abort_all'
    return normalized


def _normalize_followup_on_success(routed: dict) -> dict:
    if routed.get('kind') != 'mission_plan':
        return routed
    steps = list(routed.get('steps', []))
    if len(steps) < 2:
        return routed
    normalized = dict(routed)
    first = dict(steps[0])
    first.setdefault('run_if', 'always')
    normalized_steps = [first]
    for step in steps[1:]:
        s = dict(step)
        s.setdefault('run_if', 'previous_succeeded')
        normalized_steps.append(s)
    normalized['steps'] = normalized_steps
    return normalized


def normalize_mission_plan_for_conditionals(text: str, routed: dict) -> dict:
    if routed.get('kind') != 'mission_plan':
        return routed
    normalized = _normalize_retry_at_center(text, routed)
    if normalized is not routed:
        return normalized
    normalized = _normalize_alternative_target(text, routed)
    if normalized is not routed:
        return normalized
    steps = list(routed.get('steps', []))
    if len(steps) == 2:
        first, second = steps
        if (
            first.get('intent') == 'find_object'
            and second.get('intent') == 'navigate_to_named_place'
            and second.get('target_value') == 'center'
            and _has_failure_condition(text)
            and _has_return_home_request(text)
        ):
            normalized = dict(routed)
            first_step = dict(first)
            first_step['run_if'] = 'always'
            normalized['steps'] = [first_step]
            normalized['failure_policy'] = 'return_home'
            return normalized
    return _normalize_followup_on_success(routed)


def validate_llm_result(result: dict, named_places: list[str], object_classes: list[str]) -> dict:
    top_intent = str(result.get('intent', '')).strip()
    if top_intent not in ALLOWED_TOP_LEVEL_INTENTS:
        raise ValueError(f'invalid top-level intent: {top_intent}')

    if top_intent == 'mission_plan':
        raw_steps = result.get('steps', [])
        if not isinstance(raw_steps, list) or not raw_steps:
            raise ValueError('mission_plan requires non-empty steps')
        failure_policy = str(result.get('failure_policy', 'abort_all')).strip() or 'abort_all'
        if failure_policy not in ALLOWED_FAILURE_POLICIES:
            raise ValueError(f'invalid failure_policy: {failure_policy}')
        confidence = float(result.get('confidence', 0.0))
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f'invalid confidence: {confidence}')
        steps = [validate_step(step, named_places, object_classes) for step in raw_steps]
        return {
            'kind': 'mission_plan',
            'intent': 'mission_plan',
            'steps': steps,
            'failure_policy': failure_policy,
            'confidence': confidence,
        }

    step = validate_step(result, named_places, object_classes)
    step['kind'] = 'intent'
    return step
