import numpy as np
from product_analytics.metrics.funnels import conversion_rate, step_dropoff
from product_analytics.metrics.cohorts import retention_rate
from product_analytics.experimentation.cuped import cuped_adjust
from product_analytics.attribution.baselines import first_touch, last_touch

def test_conversion_rate():
    assert conversion_rate(20, 100) == 0.20

def test_dropoff():
    assert step_dropoff(100, 75) == 0.25

def test_retention():
    assert retention_rate(40, 100) == 0.40

def test_cuped_shape():
    y = np.array([1.0, 2.0, 3.0])
    x = np.array([1.0, 1.5, 2.0])
    assert cuped_adjust(y, x).shape == y.shape

def test_touch_attribution():
    touches = ["organic", "email", "paid_search"]
    assert first_touch(touches) == "organic"
    assert last_touch(touches) == "paid_search"
