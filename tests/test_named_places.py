import yaml
from pathlib import Path


def test_named_places_file_has_entries():
    data = yaml.safe_load(Path('/home/jnu/llm_yolo/configs/named_places.yaml').read_text())
    assert 'named_places' in data
    assert 'meeting_room_a' in data['named_places']
