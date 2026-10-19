from statsmodels.stats.proportion import proportions_ztest

def two_proportion_test(
    control_conversions: int,
    control_total: int,
    treatment_conversions: int,
    treatment_total: int,
) -> dict[str, float]:
    counts = [treatment_conversions, control_conversions]
    totals = [treatment_total, control_total]
    stat, pvalue = proportions_ztest(counts, totals)
    control_rate = control_conversions / control_total
    treatment_rate = treatment_conversions / treatment_total
    return {
        "control_rate": control_rate,
        "treatment_rate": treatment_rate,
        "absolute_lift": treatment_rate - control_rate,
        "z_stat": float(stat),
        "p_value": float(pvalue),
    }
