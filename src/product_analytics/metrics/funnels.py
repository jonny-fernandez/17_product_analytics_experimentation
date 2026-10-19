from dataclasses import dataclass

@dataclass(frozen=True)
class FunnelStep:
    name: str
    users: int

def conversion_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator

def step_dropoff(previous_users: int, current_users: int) -> float:
    if previous_users <= 0:
        return 0.0
    return 1.0 - (current_users / previous_users)
