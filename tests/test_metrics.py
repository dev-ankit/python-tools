"""Unit tests for metric direction and verdict functions."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from compare_runs import _metric_direction, _verdict_for


class TestMetricDirection:
    """Tests for _metric_direction function."""

    def test_requests_per_second_higher_is_better(self):
        assert _metric_direction("Requests/s") == "higher"

    def test_request_count_higher_is_better(self):
        assert _metric_direction("Request Count") == "higher"

    def test_failure_count_lower_is_better(self):
        assert _metric_direction("Failure Count") == "lower"

    def test_failures_per_second_lower_is_better(self):
        assert _metric_direction("Failures/s") == "lower"

    def test_average_response_time_lower_is_better(self):
        assert _metric_direction("Average Response Time") == "lower"

    def test_median_response_time_lower_is_better(self):
        assert _metric_direction("Median Response Time") == "lower"

    def test_min_response_time_lower_is_better(self):
        assert _metric_direction("Min Response Time") == "lower"

    def test_max_response_time_lower_is_better(self):
        assert _metric_direction("Max Response Time") == "lower"

    def test_percentile_95_lower_is_better(self):
        assert _metric_direction("95%") == "lower"

    def test_percentile_99_lower_is_better(self):
        assert _metric_direction("99%") == "lower"

    def test_percentile_50_lower_is_better(self):
        assert _metric_direction("50%") == "lower"

    def test_average_content_size_neutral(self):
        assert _metric_direction("Average Content Size") == "neutral"

    def test_unknown_metric_neutral(self):
        assert _metric_direction("Some Random Metric") == "neutral"


class TestVerdictFor:
    """Tests for _verdict_for function."""

    # Tests for higher-is-better metrics
    def test_requests_per_second_increase_is_better(self):
        assert _verdict_for("Requests/s", 100, 150) == "better"

    def test_requests_per_second_decrease_is_worse(self):
        assert _verdict_for("Requests/s", 150, 100) == "worse"

    def test_request_count_increase_is_better(self):
        assert _verdict_for("Request Count", 1000, 1200) == "better"

    # Tests for lower-is-better metrics
    def test_response_time_decrease_is_better(self):
        assert _verdict_for("Average Response Time", 100, 80) == "better"

    def test_response_time_increase_is_worse(self):
        assert _verdict_for("Average Response Time", 80, 100) == "worse"

    def test_failure_count_decrease_is_better(self):
        assert _verdict_for("Failure Count", 10, 5) == "better"

    def test_failure_count_increase_is_worse(self):
        assert _verdict_for("Failure Count", 5, 10) == "worse"

    def test_percentile_decrease_is_better(self):
        assert _verdict_for("95%", 200, 150) == "better"

    def test_percentile_increase_is_worse(self):
        assert _verdict_for("95%", 150, 200) == "worse"

    # Tests for same values
    def test_same_value_returns_same(self):
        assert _verdict_for("Requests/s", 100, 100) == "same"

    def test_same_response_time_returns_same(self):
        assert _verdict_for("Average Response Time", 50, 50) == "same"

    # Tests for None values
    def test_base_none_returns_none(self):
        assert _verdict_for("Requests/s", None, 100) is None

    def test_curr_none_returns_none(self):
        assert _verdict_for("Requests/s", 100, None) is None

    def test_both_none_returns_none(self):
        assert _verdict_for("Requests/s", None, None) is None

    # Tests for neutral metrics
    def test_neutral_metric_increase_returns_none(self):
        assert _verdict_for("Average Content Size", 100, 150) is None

    def test_neutral_metric_decrease_returns_none(self):
        assert _verdict_for("Average Content Size", 150, 100) is None
