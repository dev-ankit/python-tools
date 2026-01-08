"""Unit tests for utility functions."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from compare_runs import _as_float, pct_change, diff, format_number


class TestAsFloat:
    """Tests for _as_float function."""

    def test_valid_integer(self):
        assert _as_float("42") == 42.0

    def test_valid_float(self):
        assert _as_float("3.14") == 3.14

    def test_negative_number(self):
        assert _as_float("-100.5") == -100.5

    def test_scientific_notation(self):
        assert _as_float("1e-5") == 1e-5

    def test_empty_string(self):
        assert _as_float("") is None

    def test_whitespace_string(self):
        assert _as_float("   ") is None

    def test_none_value(self):
        assert _as_float(None) is None

    def test_invalid_string(self):
        assert _as_float("not a number") is None

    def test_string_with_whitespace(self):
        assert _as_float("  42.5  ") == 42.5

    def test_zero(self):
        assert _as_float("0") == 0.0

    def test_large_number(self):
        assert _as_float("999999999999.999") == 999999999999.999


class TestPctChange:
    """Tests for pct_change function."""

    def test_positive_increase(self):
        # 100 to 150 = 50% increase
        assert pct_change(100, 150) == 50.0

    def test_positive_decrease(self):
        # 100 to 50 = -50% decrease
        assert pct_change(100, 50) == -50.0

    def test_no_change(self):
        assert pct_change(100, 100) == 0.0

    def test_double_value(self):
        # 50 to 100 = 100% increase
        assert pct_change(50, 100) == 100.0

    def test_base_is_none(self):
        assert pct_change(None, 100) is None

    def test_curr_is_none(self):
        assert pct_change(100, None) is None

    def test_both_none(self):
        assert pct_change(None, None) is None

    def test_base_is_zero(self):
        # Division by zero protection
        assert pct_change(0, 100) is None

    def test_curr_is_zero(self):
        # 100 to 0 = -100%
        assert pct_change(100, 0) == -100.0

    def test_small_values(self):
        # 0.1 to 0.2 = 100% increase
        assert pct_change(0.1, 0.2) == pytest.approx(100.0)

    def test_negative_base(self):
        # -100 to -50: change=50, pct_change = 50/-100 * 100 = -50%
        # Mathematically correct, though semantically counterintuitive
        assert pct_change(-100, -50) == -50.0


class TestDiff:
    """Tests for diff function."""

    def test_positive_diff(self):
        assert diff(100, 150) == 50

    def test_negative_diff(self):
        assert diff(150, 100) == -50

    def test_zero_diff(self):
        assert diff(100, 100) == 0

    def test_base_is_none(self):
        assert diff(None, 100) is None

    def test_curr_is_none(self):
        assert diff(100, None) is None

    def test_both_none(self):
        assert diff(None, None) is None

    def test_float_diff(self):
        assert diff(10.5, 15.3) == pytest.approx(4.8)

    def test_negative_values(self):
        assert diff(-10, -5) == 5


class TestFormatNumber:
    """Tests for format_number function."""

    def test_none_value(self):
        assert format_number(None) == "-"

    def test_integer_value(self):
        assert format_number(42.0) == "42"

    def test_float_value(self):
        assert format_number(3.14159) == "3.142"

    def test_negative_integer(self):
        assert format_number(-100.0) == "-100"

    def test_negative_float(self):
        assert format_number(-3.14159) == "-3.142"

    def test_zero(self):
        assert format_number(0.0) == "0"

    def test_very_close_to_integer(self):
        # Should round to integer
        assert format_number(42.0000000001) == "42"

    def test_small_decimal(self):
        assert format_number(0.001) == "0.001"

    def test_large_integer(self):
        assert format_number(1000000.0) == "1000000"
