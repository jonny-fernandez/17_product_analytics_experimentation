from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize

def required_sample_per_group(
    baseline_rate: float,
    treatment_rate: float,
    alpha: float = 0.05,
    power: float = 0.80,
) -> int:
    effect = proportion_effectsize(baseline_rate, treatment_rate)
    result = NormalIndPower().solve_power(
        effect_size=effect,
        alpha=alpha,
        power=power,
        ratio=1.0,
        alternative="two-sided",
    )
    return int(result) + 1
