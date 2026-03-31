from mission_manager.state_machine import MissionState


def test_default_mission_state():
    state = MissionState()
    assert state.active is False
    assert state.mode == 'idle'
