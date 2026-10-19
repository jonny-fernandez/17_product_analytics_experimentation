import numpy as np

def cuped_adjust(outcome: np.ndarray, pre_period: np.ndarray) -> np.ndarray:
    if len(outcome) != len(pre_period):
        raise ValueError("Outcome and pre-period arrays must have equal length.")
    variance = np.var(pre_period)
    if variance == 0:
        return outcome.copy()
    theta = np.cov(outcome, pre_period, ddof=0)[0, 1] / variance
    return outcome - theta * (pre_period - np.mean(pre_period))
