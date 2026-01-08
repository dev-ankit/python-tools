"""Unit tests for Row dataclass and index_rows function."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from compare_runs import Row, index_rows


class TestRow:
    """Tests for Row dataclass."""

    def test_row_creation(self):
        row = Row(name="test", type="GET", data={"key": 1.0})
        assert row.name == "test"
        assert row.type == "GET"
        assert row.data == {"key": 1.0}

    def test_row_is_frozen(self):
        row = Row(name="test", type="GET", data={"key": 1.0})
        with pytest.raises(Exception):  # FrozenInstanceError
            row.name = "modified"

    def test_row_equality(self):
        row1 = Row(name="test", type="GET", data={"key": 1.0})
        row2 = Row(name="test", type="GET", data={"key": 1.0})
        assert row1 == row2

    def test_row_inequality(self):
        row1 = Row(name="test1", type="GET", data={})
        row2 = Row(name="test2", type="GET", data={})
        assert row1 != row2

    def test_row_with_empty_data(self):
        row = Row(name="empty", type="POST", data={})
        assert row.data == {}


class TestIndexRows:
    """Tests for index_rows function."""

    def test_index_single_row(self):
        rows = [Row(name="/api/users", type="GET", data={"key": 1.0})]
        idx = index_rows(rows)
        assert "/api/users" in idx
        assert idx["/api/users"].name == "/api/users"

    def test_index_aggregated_row(self):
        rows = [Row(name="Aggregated", type="", data={"key": 1.0})]
        idx = index_rows(rows)
        assert "__Aggregated__" in idx
        assert "Aggregated" not in idx

    def test_index_multiple_rows(self):
        rows = [
            Row(name="/api/users", type="GET", data={}),
            Row(name="/api/login", type="POST", data={}),
            Row(name="Aggregated", type="", data={}),
        ]
        idx = index_rows(rows)
        assert len(idx) == 3
        assert "/api/users" in idx
        assert "/api/login" in idx
        assert "__Aggregated__" in idx

    def test_index_empty_rows(self):
        idx = index_rows([])
        assert idx == {}

    def test_index_duplicate_names_last_wins(self):
        rows = [
            Row(name="/api/users", type="GET", data={"version": 1.0}),
            Row(name="/api/users", type="GET", data={"version": 2.0}),
        ]
        idx = index_rows(rows)
        assert len(idx) == 1
        assert idx["/api/users"].data["version"] == 2.0
