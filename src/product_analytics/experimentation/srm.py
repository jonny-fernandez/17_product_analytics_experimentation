from scipy.stats import chisquare

def sample_ratio_mismatch(observed: list[int], expected_ratio: list[float]) -> float:
    total = sum(observed)
    expected = [total * ratio for ratio in expected_ratio]
    _, pvalue = chisquare(observed, f_exp=expected)
    return float(pvalue)
