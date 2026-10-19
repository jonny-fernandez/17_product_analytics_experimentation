def last_touch(touches: list[str]) -> str | None:
    return touches[-1] if touches else None

def first_touch(touches: list[str]) -> str | None:
    return touches[0] if touches else None
