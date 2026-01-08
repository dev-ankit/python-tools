"""Integration tests for compare_reports function."""
import pytest
import sys
import json
import tempfile
from pathlib import Path
from io import StringIO
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))
from compare_runs import compare_reports


class TestCompareReportsJson:
    """Tests for compare_reports with JSON output."""

    def test_json_output_structure(self, temp_test_dir, temp_test_dir_v2, capsys):
        result = compare_reports(temp_test_dir, temp_test_dir_v2, as_json=True)
        assert result == 0

        captured = capsys.readouterr()
        data = json.loads(captured.out)

        # Should have aggregated and endpoint keys
        assert "__Aggregated__" in data
        assert "/api/users" in data
        assert "/api/login" in data

    def test_json_output_metrics(self, temp_test_dir, temp_test_dir_v2, capsys):
        compare_reports(temp_test_dir, temp_test_dir_v2, as_json=True)

        captured = capsys.readouterr()
        data = json.loads(captured.out)

        # Check metric structure
        users_data = data["/api/users"]
        assert "Request Count" in users_data
        metric = users_data["Request Count"]
        assert "base" in metric
        assert "current" in metric
        assert "diff" in metric
        assert "pct_change" in metric

    def test_json_output_values(self, temp_test_dir, temp_test_dir_v2, capsys):
        compare_reports(temp_test_dir, temp_test_dir_v2, as_json=True)

        captured = capsys.readouterr()
        data = json.loads(captured.out)

        users_data = data["/api/users"]
        req_count = users_data["Request Count"]

        # Base had 1000, current has 1200
        assert req_count["base"] == 1000
        assert req_count["current"] == 1200
        assert req_count["diff"] == 200
        assert req_count["pct_change"] == pytest.approx(20.0)


class TestCompareReportsHuman:
    """Tests for compare_reports with human-readable output."""

    def test_human_output_includes_sections(self, temp_test_dir, temp_test_dir_v2, capsys):
        result = compare_reports(temp_test_dir, temp_test_dir_v2, as_json=False)
        assert result == 0

        captured = capsys.readouterr()
        output = captured.out

        # Should have section headers
        assert "Aggregated" in output
        assert "Endpoint:" in output

    def test_human_output_includes_metrics(self, temp_test_dir, temp_test_dir_v2, capsys):
        compare_reports(temp_test_dir, temp_test_dir_v2, as_json=False)

        captured = capsys.readouterr()
        output = captured.out

        # Should have metric names
        assert "Requests/s" in output
        assert "Request Count" in output
        assert "Average Response Time" in output

    def test_human_output_includes_verdict(self, temp_test_dir, temp_test_dir_v2, capsys):
        compare_reports(temp_test_dir, temp_test_dir_v2, as_json=False, show_verdict=True)

        captured = capsys.readouterr()
        output = captured.out

        # Should have verdict column
        assert "Verdict" in output
        # Should have verdict values (better/worse/same)
        assert "better" in output or "worse" in output or "same" in output

    def test_human_output_no_verdict(self, temp_test_dir, temp_test_dir_v2, capsys):
        compare_reports(temp_test_dir, temp_test_dir_v2, as_json=False, show_verdict=False)

        captured = capsys.readouterr()
        output = captured.out

        # Should NOT have verdict column header
        lines = output.split('\n')
        header_line = [l for l in lines if 'Metric' in l and 'Base' in l][0]
        assert "Verdict" not in header_line

    def test_human_output_colorize(self, temp_test_dir, temp_test_dir_v2, capsys):
        compare_reports(temp_test_dir, temp_test_dir_v2, as_json=False, colorize=True)

        captured = capsys.readouterr()
        output = captured.out

        # Should have ANSI color codes
        assert "\033[32m" in output or "\033[31m" in output  # green or red


class TestCompareReportsEdgeCases:
    """Edge case tests for compare_reports."""

    def test_compare_same_report(self, temp_test_dir, capsys):
        """Comparing a report to itself should show no changes."""
        compare_reports(temp_test_dir, temp_test_dir, as_json=True)

        captured = capsys.readouterr()
        data = json.loads(captured.out)

        # All diffs should be 0 or None
        for endpoint, metrics in data.items():
            for metric, values in metrics.items():
                if values["base"] is not None and values["current"] is not None:
                    assert values["diff"] == 0

    def test_compare_with_missing_endpoint(self, sample_csv_content, sample_csv_content_v2, capsys):
        """Test comparison when an endpoint exists only in one report."""
        # Create CSV with extra endpoint in base
        base_csv = sample_csv_content + "DELETE,/api/delete,10,0,50,55,20,100,1.0,5.0,0.0,50,55,60,65,75,85,95,100,150,200,100\n"

        with tempfile.TemporaryDirectory() as base_dir, tempfile.TemporaryDirectory() as curr_dir:
            base_path = Path(base_dir) / "report.csv"
            curr_path = Path(curr_dir) / "report.csv"
            base_path.write_text(base_csv)
            curr_path.write_text(sample_csv_content_v2)

            compare_reports(Path(base_dir), Path(curr_dir), as_json=True)

            captured = capsys.readouterr()
            data = json.loads(captured.out)

            # The DELETE endpoint should be in output
            assert "/api/delete" in data
            # Current values should be None
            delete_data = data["/api/delete"]
            for metric, values in delete_data.items():
                assert values["current"] is None

    def test_compare_with_new_endpoint(self, sample_csv_content, sample_csv_content_v2, capsys):
        """Test comparison when a new endpoint appears in current."""
        # Create CSV with extra endpoint in current
        curr_csv = sample_csv_content_v2 + "DELETE,/api/new,20,0,40,45,15,90,1.2,10.0,0.0,40,45,50,55,65,75,85,95,140,190,90\n"

        with tempfile.TemporaryDirectory() as base_dir, tempfile.TemporaryDirectory() as curr_dir:
            base_path = Path(base_dir) / "report.csv"
            curr_path = Path(curr_dir) / "report.csv"
            base_path.write_text(sample_csv_content)
            curr_path.write_text(curr_csv)

            compare_reports(Path(base_dir), Path(curr_dir), as_json=True)

            captured = capsys.readouterr()
            data = json.loads(captured.out)

            # The new endpoint should be in output
            assert "/api/new" in data
            # Base values should be None
            new_data = data["/api/new"]
            for metric, values in new_data.items():
                assert values["base"] is None


class TestCompareReportsWithHtml:
    """Tests for compare_reports with HTML features."""

    def test_json_includes_html_features(self, temp_dir_with_html, capsys):
        """JSON output should include HTML features."""
        # Need two dirs for comparison
        with tempfile.TemporaryDirectory() as other_dir:
            other = Path(other_dir)
            (other / "report.csv").write_text("""Type,Name,Request Count
GET,/api/test,100
,Aggregated,100
""")
            # Copy the HTML file
            import shutil
            for html_file in temp_dir_with_html.glob("*.html"):
                if html_file.name != "htmlpublisher-wrapper.html":
                    shutil.copy(html_file, other / html_file.name)

            compare_reports(temp_dir_with_html, other, as_json=True)

            captured = capsys.readouterr()
            data = json.loads(captured.out)

            # Should have HTML feature keys
            html_keys = [k for k in data.keys() if k.startswith("HTML:")]
            assert len(html_keys) > 0

    def test_human_output_includes_html_section(self, temp_dir_with_html, capsys):
        """Human output should include HTML Features section."""
        with tempfile.TemporaryDirectory() as other_dir:
            other = Path(other_dir)
            (other / "report.csv").write_text("""Type,Name,Request Count
GET,/api/test,100
,Aggregated,100
""")
            # Copy the HTML file
            import shutil
            for html_file in temp_dir_with_html.glob("*.html"):
                if html_file.name != "htmlpublisher-wrapper.html":
                    shutil.copy(html_file, other / html_file.name)

            compare_reports(temp_dir_with_html, other, as_json=False)

            captured = capsys.readouterr()
            output = captured.out

            assert "HTML Features" in output
            assert "Feature:" in output


class TestCompareReportsRealData:
    """Tests using real test data."""

    def test_compare_real_reports(self, real_test_runs_path, capsys):
        """Compare two real test reports."""
        base = real_test_runs_path / "HTML-Report-394"
        curr = real_test_runs_path / "HTML-Report-395"

        if not base.exists() or not curr.exists():
            pytest.skip("Real test data not available")

        result = compare_reports(base, curr, as_json=True)
        assert result == 0

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert len(data) > 0
