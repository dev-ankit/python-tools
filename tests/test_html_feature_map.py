"""Integration tests for load_html_feature_map function."""
import pytest
import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from compare_runs import load_html_feature_map


class TestLoadHtmlFeatureMap:
    """Tests for load_html_feature_map function."""

    def test_load_from_directory_with_html(self, temp_dir_with_html):
        features = load_html_feature_map(temp_dir_with_html)
        assert "feature_test" in features

    def test_load_parses_endpoints(self, temp_dir_with_html):
        features = load_html_feature_map(temp_dir_with_html)
        feature = features["feature_test"]
        assert "/api/users" in feature
        assert "Aggregated" in feature

    def test_load_parses_metrics(self, temp_dir_with_html):
        features = load_html_feature_map(temp_dir_with_html)
        endpoint = features["feature_test"]["/api/users"]

        assert "Request Count" in endpoint.data
        assert endpoint.data["Request Count"] == 1000
        assert "Failure Count" in endpoint.data
        assert endpoint.data["Failure Count"] == 5
        assert "Average Response Time" in endpoint.data

    def test_load_parses_percentiles(self, temp_dir_with_html):
        features = load_html_feature_map(temp_dir_with_html)
        endpoint = features["feature_test"]["/api/users"]

        assert "95%" in endpoint.data
        assert endpoint.data["95%"] == 170
        assert "99%" in endpoint.data
        assert endpoint.data["99%"] == 250

    def test_load_calculates_rps_from_duration(self, temp_dir_with_html):
        """RPS should be calculated from request count / duration."""
        features = load_html_feature_map(temp_dir_with_html)
        endpoint = features["feature_test"]["/api/users"]

        # Duration is 30 minutes = 1800 seconds
        # 1000 requests / 1800 seconds = ~0.556 RPS
        assert "Requests/s" in endpoint.data
        expected_rps = 1000 / 1800
        assert endpoint.data["Requests/s"] == pytest.approx(expected_rps, rel=0.01)

    def test_load_non_directory_returns_empty(self):
        with tempfile.NamedTemporaryFile() as f:
            features = load_html_feature_map(Path(f.name))
            assert features == {}

    def test_load_nonexistent_path_returns_empty(self):
        features = load_html_feature_map(Path("/nonexistent/path"))
        assert features == {}

    def test_load_skips_htmlpublisher_wrapper(self):
        """htmlpublisher-wrapper.html should be skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            # Create the wrapper file
            wrapper = base / "htmlpublisher-wrapper.html"
            wrapper.write_text("""<script>window.templateArgs = {"requests_statistics": [{"name": "test", "num_requests": 1}]};</script>""")

            features = load_html_feature_map(base)
            assert "htmlpublisher-wrapper" not in features

    def test_load_skips_html_without_template_args(self, html_without_template_args):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            html_path = base / "empty_report.html"
            html_path.write_text(html_without_template_args)

            features = load_html_feature_map(base)
            assert "empty_report" not in features

    def test_load_multiple_html_files(self, sample_html_template_args):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            # Create multiple HTML files
            for name in ["feature1", "feature2", "feature3"]:
                html_path = base / f"{name}.html"
                html_path.write_text(sample_html_template_args)

            features = load_html_feature_map(base)
            assert len(features) == 3
            assert "feature1" in features
            assert "feature2" in features
            assert "feature3" in features

    def test_row_type_is_html(self, temp_dir_with_html):
        features = load_html_feature_map(temp_dir_with_html)
        endpoint = features["feature_test"]["/api/users"]
        assert endpoint.type == "HTML"


class TestLoadHtmlFeatureMapEdgeCases:
    """Edge case tests for load_html_feature_map."""

    def test_html_with_empty_requests_statistics(self):
        """HTML with empty requests_statistics array should be skipped."""
        html = """<script>window.templateArgs = {"requests_statistics": []};</script>"""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            html_path = base / "empty.html"
            html_path.write_text(html)

            features = load_html_feature_map(base)
            assert "empty" not in features

    def test_html_with_invalid_requests_statistics(self):
        """HTML with non-list requests_statistics should be skipped."""
        html = """<script>window.templateArgs = {"requests_statistics": "not a list"};</script>"""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            html_path = base / "invalid.html"
            html_path.write_text(html)

            features = load_html_feature_map(base)
            assert "invalid" not in features

    def test_html_with_missing_endpoint_name(self):
        """Endpoints without names should be skipped."""
        html = """<script>window.templateArgs = {
            "requests_statistics": [
                {"num_requests": 100}
            ]
        };</script>"""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            html_path = base / "missing_name.html"
            html_path.write_text(html)

            features = load_html_feature_map(base)
            assert "missing_name" not in features

    def test_html_entity_unescaping(self):
        """HTML entities in endpoint names should be unescaped."""
        html = """<script>window.templateArgs = {
            "requests_statistics": [
                {"name": "/api/users?filter=a&amp;b", "num_requests": 100}
            ]
        };</script>"""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            html_path = base / "entities.html"
            html_path.write_text(html)

            features = load_html_feature_map(base)
            endpoint_names = list(features["entities"].keys())
            assert "/api/users?filter=a&b" in endpoint_names

    def test_real_test_data(self, real_test_runs_path):
        """Test with real test data if available."""
        test_dir = real_test_runs_path / "HTML-Report-394"
        if test_dir.exists():
            features = load_html_feature_map(test_dir)
            # Should have parsed some HTML files
            assert len(features) > 0
