def retention_rate(returning_users: int, cohort_size: int) -> float:
    if cohort_size <= 0:
        return 0.0
    return returning_users / cohort_size
