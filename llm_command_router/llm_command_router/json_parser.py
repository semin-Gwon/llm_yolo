import re
from typing import Iterable


SPEED_TOKEN_PATTERN = re.compile(r'(천천히|느리게|slow|빠르게|빨리|fast)', re.IGNORECASE)
SELECTOR_TOKEN_PATTERN = re.compile(r'(가까운|가까이|near|먼|far)', re.IGNORECASE)


OBJECT_TOKEN_PATTERN = re.compile(
    r'(red_box|pink_box|yellow_box|blue_box|의자|chair|사람|person|충전독|charging_dock|티비|tv|소파|couch|침대|bed|테이블|dining table)',
    re.IGNORECASE,
)

OBJECT_TOKEN_MAPPING = {
    '의자': 'chair',
    '사람': 'person',
    '충전독': 'charging_dock',
    '티비': 'tv',
    '소파': 'couch',
    '침대': 'bed',
    '테이블': 'dining table',
}


def extract_speed_hint(text: str) -> str:
    match = SPEED_TOKEN_PATTERN.search(text)
    if not match:
        return 'normal'
    token = match.group(1).lower()
    if token in {'천천히', '느리게', 'slow'}:
        return 'slow'
    if token in {'빠르게', '빨리', 'fast'}:
        return 'fast'
    return 'normal'


def extract_object_selector(text: str) -> str:
    match = SELECTOR_TOKEN_PATTERN.search(text)
    if not match:
        return ''
    token = match.group(1).lower()
    if token in {'가까운', '가까이', 'near'}:
        return 'near'
    if token in {'먼', 'far'}:
        return 'far'
    return ''


def parse_user_text(text: str, named_places: Iterable[str]) -> tuple[str, str, str, float, str, str]:
    lowered = text.strip().lower()
    named_places = list(named_places)
    speed_hint = extract_speed_hint(text)
    object_selector = extract_object_selector(text)
    if any(token in text for token in ['정지', '취소', 'cancel', 'stop']):
        return 'cancel', 'none', '', 1.0, 'normal', ''
    if any(token in text for token in ['앞으로', '앞에', '다가가', '접근']) or 'approach' in lowered:
        target = extract_target(text, fallback='chair')
        return 'approach_object', 'object_class', target, 0.85, speed_hint, object_selector
    for place in named_places:
        if place.lower() in lowered or place in text:
            return 'navigate_to_named_place', 'named_place', place, 0.95, speed_hint, ''
    if '찾' in text or 'find' in lowered:
        target = extract_target(text, fallback='chair')
        return 'find_object', 'object_class', target, 0.8, speed_hint, object_selector
    if '스캔' in text or 'scan' in lowered:
        target = extract_target(text, fallback='chair')
        return 'scan_scene', 'object_class', target, 0.75, speed_hint, object_selector
    return 'scan_scene', 'object_class', 'chair', 0.4, speed_hint, object_selector


def extract_target(text: str, fallback: str) -> str:
    match = OBJECT_TOKEN_PATTERN.search(text)
    if not match:
        return fallback
    token = match.group(1).lower()
    return OBJECT_TOKEN_MAPPING.get(token, token)
