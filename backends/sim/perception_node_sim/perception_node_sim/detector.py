def detect(target: str, available: list[str]) -> str:
    if target in available:
        return 'FOUND'
    return 'NOT_FOUND'
