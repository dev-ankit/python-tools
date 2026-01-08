"""Tests for HTML template extraction functions."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from compare_runs import _extract_template_args


class TestExtractTemplateArgs:
    """Tests for _extract_template_args function."""

    def test_extract_simple_template_args(self):
        html = """<script>window.templateArgs = {"key": "value"};</script>"""
        result = _extract_template_args(html)
        assert result == {"key": "value"}

    def test_extract_nested_object(self):
        html = """<script>window.templateArgs = {"outer": {"inner": 42}};</script>"""
        result = _extract_template_args(html)
        assert result == {"outer": {"inner": 42}}

    def test_extract_with_array(self):
        html = """<script>window.templateArgs = {"items": [1, 2, 3]};</script>"""
        result = _extract_template_args(html)
        assert result == {"items": [1, 2, 3]}

    def test_extract_with_whitespace(self):
        html = """<script>
        window.templateArgs   =   {
            "key": "value"
        };
        </script>"""
        result = _extract_template_args(html)
        assert result == {"key": "value"}

    def test_no_template_args_returns_none(self):
        html = """<html><body>No template args here</body></html>"""
        result = _extract_template_args(html)
        assert result is None

    def test_empty_string_returns_none(self):
        result = _extract_template_args("")
        assert result is None

    def test_malformed_json_returns_none(self):
        html = """<script>window.templateArgs = {invalid json};</script>"""
        result = _extract_template_args(html)
        assert result is None

    def test_extract_complex_locust_data(self, sample_html_template_args):
        result = _extract_template_args(sample_html_template_args)
        assert result is not None
        assert "start_time" in result
        assert "end_time" in result
        assert "requests_statistics" in result
        assert len(result["requests_statistics"]) == 2

    def test_extract_with_special_characters(self):
        html = """<script>window.templateArgs = {"path": "/api/users?id=1&name=test"};</script>"""
        result = _extract_template_args(html)
        assert result == {"path": "/api/users?id=1&name=test"}

    def test_extract_with_numeric_values(self):
        html = """<script>window.templateArgs = {"int": 42, "float": 3.14, "negative": -10};</script>"""
        result = _extract_template_args(html)
        assert result["int"] == 42
        assert result["float"] == 3.14
        assert result["negative"] == -10

    def test_extract_with_boolean_values(self):
        html = """<script>window.templateArgs = {"flag": true, "disabled": false};</script>"""
        result = _extract_template_args(html)
        assert result["flag"] is True
        assert result["disabled"] is False

    def test_extract_with_null_values(self):
        html = """<script>window.templateArgs = {"empty": null};</script>"""
        result = _extract_template_args(html)
        assert result["empty"] is None

    def test_deeply_nested_braces(self):
        html = """<script>window.templateArgs = {"a": {"b": {"c": {"d": 1}}}};</script>"""
        result = _extract_template_args(html)
        assert result == {"a": {"b": {"c": {"d": 1}}}}
