import pytest
from backend.app.academy.blind_patterns import normalize_ohlc

def test_normalize_ohlc_bullish():
    # open=100, high=120, low=90, close=110
    # range = 30
    # body = 10 / 30 = 0.333...
    # upper = 10 / 30 = 0.333...
    # lower = 10 / 30 = 0.333...
    candle = normalize_ohlc(100.0, 120.0, 90.0, 110.0)
    assert candle.dir == 1
    assert pytest.approx(candle.body) == 0.333333
    assert pytest.approx(candle.upper) == 0.333333
    assert pytest.approx(candle.lower) == 0.333333

def test_normalize_ohlc_bearish():
    # open=110, high=120, low=90, close=100
    # range = 30
    candle = normalize_ohlc(110.0, 120.0, 90.0, 100.0)
    assert candle.dir == -1
    assert pytest.approx(candle.body) == 0.333333
    assert pytest.approx(candle.upper) == 0.333333
    assert pytest.approx(candle.lower) == 0.333333

def test_normalize_ohlc_doji_bullish_close():
    # close is slightly higher than open, but body < 0.08
    # open=100, high=110, low=90, close=101
    # range = 20, body = 1/20 = 0.05
    candle = normalize_ohlc(100.0, 110.0, 90.0, 101.0)
    assert candle.dir == 0  # Should be 0 due to body < 0.08
    assert pytest.approx(candle.body) == 0.05
    assert pytest.approx(candle.upper) == 9 / 20
    assert pytest.approx(candle.lower) == 10 / 20

def test_normalize_ohlc_doji_bearish_close():
    # close is slightly lower than open, but body < 0.08
    # open=101, high=110, low=90, close=100
    # range = 20, body = 1/20 = 0.05
    candle = normalize_ohlc(101.0, 110.0, 90.0, 100.0)
    assert candle.dir == 0  # Should be 0 due to body < 0.08
    assert pytest.approx(candle.body) == 0.05
    assert pytest.approx(candle.upper) == 9 / 20
    assert pytest.approx(candle.lower) == 10 / 20

def test_normalize_ohlc_zero_range():
    # high == low
    candle = normalize_ohlc(100.0, 100.0, 100.0, 100.0)
    assert candle.dir == 0
    assert candle.body == 0.0
    assert candle.upper == 0.0
    assert candle.lower == 0.0

def test_normalize_ohlc_zero_body_perfect_doji():
    # open == close
    # open=100, high=120, low=80, close=100
    candle = normalize_ohlc(100.0, 120.0, 80.0, 100.0)
    assert candle.dir == 0
    assert candle.body == 0.0
    assert pytest.approx(candle.upper) == 0.5
    assert pytest.approx(candle.lower) == 0.5

def test_normalize_ohlc_clamps_values():
    # Test that _clamp01 correctly restricts values to [0, 1]
    # For example, invalid OHLC where close > high
    _ = normalize_ohlc(100.0, 110.0, 90.0, 120.0)
    # range = max(110-90, 1e-12) = 20
    # body_top = 120
    # upper = (110 - 120)/20 = -0.5 -> clamped to 0
    # body = 20 / 20 = 1.0 (though it's actually 1.0 here, if it was higher it would clamp)
    # Let's make an extreme one to test body clamp
    candle2 = normalize_ohlc(100.0, 110.0, 90.0, 150.0)
    # body = 50 / 20 = 2.5 -> clamped to 1.0
    assert candle2.body == 1.0
    assert candle2.upper == 0.0 # Clamped from negative
