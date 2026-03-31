from dataclasses import dataclass


@dataclass
class MissionState:
    active: bool = False
    mode: str = 'idle'
    target: str = ''
