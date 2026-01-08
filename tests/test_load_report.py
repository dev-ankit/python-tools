"""Integration tests for load_report function."""
import pytest
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from compare_runs import load_report, Row


class TestLoadReport:
    """Tests for load_report function."""

    def test_load_from_directory(self, temp_test_dir):
        rows = load_report(temp_test_dir)
        assert len(rows) == 3  # GET, POST, Aggregated

    def test_load_from_csv_file(self, temp_test_dir):
        csv_path = temp_test_dir / "report.csv"
        rows = load_report(csv_path)
        assert len(rows) == 3

    def test_load_parses_names(self, temp_test_dir):
        rows = load_report(temp_test_dir)
        names = [r.name for r in rows]
        assert "/api/users" in names
        assert "/api/login" in names
        assert "Aggregated" in names

    def test_load_parses_types(self, temp_test_dir):
        rows = load_report(temp_test_dir)
        types = {r.name: r.type for r in rows}
        assert types["/api/users"] == "GET"
        assert types["/api/login"] == "POST"

    def test_load_parses_numeric_fields(self, temp_test_dir):
        rows = load_report(temp_test_dir)
        users_row = next(r for r in rows if r.name == "/api/users")

        assert "Request Count" in users_row.data
        assert users_row.data["Request Count"] == 1000
        assert "Failure Count" in users_row.data
        assert users_row.data["Failure Count"] == 5
        assert "Average Response Time" in users_row.data
        assert users_row.data["Average Response Time"] == 101.5

    def test_load_parses_percentiles(self, temp_test_dir):
        rows = load_report(temp_test_dir)
        users_row = next(r for r in rows if r.name == "/api/users")

        assert "50%" in users_row.data
        assert "95%" in users_row.data
        assert "99%" in users_row.data

    def test_load_missing_directory_raises(self):
        with pytest.raises(FileNotFoundError):
            load_report(Path("/nonexistent/path"))

    def test_load_directory_without_csv_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(FileNotFoundError, match="report.csv not found"):
                load_report(Path(tmpdir))

    def test_load_non_csv_file_raises(self):
        with tempfile.NamedTemporaryFile(suffix=".txt") as f:
            with pytest.raises(ValueError, match="does not look like a CSV"):
                load_report(Path(f.name))

    def test_load_empty_csv(self, empty_csv_content):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(empty_csv_content)
            f.flush()
            rows = load_report(Path(f.name))
            assert rows == []

    def test_load_handles_malformed_values(self, malformed_csv_content):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(malformed_csv_content)
            f.flush()
            rows = load_report(Path(f.name))

            # Should still parse rows, just skip invalid numeric values
            assert len(rows) == 2
            test_row = next(r for r in rows if r.name == "/api/test")
            # "invalid" should be skipped for Failure Count
            assert "Failure Count" not in test_row.data
            # Empty Request Count should be skipped
            assert "Request Count" not in test_row.data

    def test_load_real_test_data(self, real_test_runs_path):
        """Test with real test data if available."""
        test_dir = real_test_runs_path / "HTML-Report-394"
        if test_dir.exists():
            rows = load_report(test_dir)
            assert len(rows) > 0
            # Should have an Aggregated row
            agg = [r for r in rows if r.name == "Aggregated"]
            assert len(agg) == 1


class TestLoadReportEdgeCases:
    """Edge case tests for load_report."""

    def test_csv_with_extra_columns(self):
        """CSV with columns not in NUMERIC_FIELDS should be ignored."""
        content = """Type,Name,Request Count,CustomField,Average Response Time
GET,/api/test,100,ignored,50.0
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(content)
            f.flush()
            rows = load_report(Path(f.name))
            assert len(rows) == 1
            assert "CustomField" not in rows[0].data

    def test_csv_with_whitespace_values(self):
        """Values with whitespace should be trimmed."""
        content = """Type,Name,Request Count,Average Response Time
GET,  /api/test  ,  100  ,  50.5
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(content)
            f.flush()
            rows = load_report(Path(f.name))
            assert rows[0].name == "/api/test"
            assert rows[0].data["Request Count"] == 100

    def test_csv_file_named_differently(self):
        """A CSV file not named report.csv should still work."""
        content = """Type,Name,Request Count
GET,/api/test,100
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(content)
            f.flush()
            rows = load_report(Path(f.name))
            assert len(rows) == 1
