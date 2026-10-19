"""Conservative causal language gate for portfolio evidence.

Documented assumptions alone are not enough to identify an observational effect.
The current synthetic pipeline demonstrates known randomized assignment only.
"""

def causal_claim_allowed(randomized_experiment: bool, assumptions_documented: bool) -> bool:
    """Require BOTH credible randomization and documented assumptions; never prove them."""
    return bool(randomized_experiment and assumptions_documented)
