from llm_command_router.json_parser import parse_user_text


def test_parse_navigate():
    intent, target_type, target_value, confidence = parse_user_text('meeting_room_a 로 가', ['meeting_room_a'])
    assert intent == 'navigate_to_named_place'
    assert target_type == 'named_place'
    assert target_value == 'meeting_room_a'
    assert confidence > 0.5


def test_parse_find_pink_box():
    intent, target_type, target_value, confidence = parse_user_text('pink_box 찾아', ['meeting_room_a'])
    assert intent == 'find_object'
    assert target_type == 'object_class'
    assert target_value == 'pink_box'
    assert confidence > 0.5
