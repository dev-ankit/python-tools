"""Pytest fixtures for locust-compare tests."""
import pytest
from pathlib import Path
import tempfile
import shutil


@pytest.fixture
def sample_csv_content():
    """Sample CSV content for testing."""
    return """Type,Name,Request Count,Failure Count,Median Response Time,Average Response Time,Min Response Time,Max Response Time,Average Content Size,Requests/s,Failures/s,50%,66%,75%,80%,90%,95%,98%,99%,99.9%,99.99%,100%
GET,/api/users,1000,5,89,101.5,43.3,1317.8,2.0,190.7,0.05,89,100,120,120,150,170,210,250,830,1100,1300
POST,/api/login,500,2,45,52.3,20.1,500.0,1.5,95.5,0.02,45,50,55,60,70,80,90,100,200,300,500
,Aggregated,1500,7,75,85.2,20.1,1317.8,1.8,286.2,0.07,75,85,95,100,130,150,180,200,600,900,1300
"""


@pytest.fixture
def sample_csv_content_v2():
    """Alternative CSV content for comparison testing."""
    return """Type,Name,Request Count,Failure Count,Median Response Time,Average Response Time,Min Response Time,Max Response Time,Average Content Size,Requests/s,Failures/s,50%,66%,75%,80%,90%,95%,98%,99%,99.9%,99.99%,100%
GET,/api/users,1200,3,80,95.0,40.0,1200.0,2.1,200.0,0.03,80,90,110,115,140,160,200,240,800,1000,1200
POST,/api/login,600,1,40,48.0,18.0,450.0,1.6,100.0,0.01,40,45,50,55,65,75,85,95,180,280,450
,Aggregated,1800,4,65,78.5,18.0,1200.0,1.9,300.0,0.04,65,75,85,95,120,140,170,190,550,850,1200
"""


@pytest.fixture
def empty_csv_content():
    """Empty CSV with just headers."""
    return """Type,Name,Request Count,Failure Count,Median Response Time,Average Response Time,Min Response Time,Max Response Time,Average Content Size,Requests/s,Failures/s
"""


@pytest.fixture
def malformed_csv_content():
    """CSV with missing/malformed values."""
    return """Type,Name,Request Count,Failure Count,Median Response Time,Average Response Time
GET,/api/test,,invalid,100,
POST,/api/other,50,0,,25.5
"""


@pytest.fixture
def sample_html_template_args():
    """Sample HTML content with templateArgs."""
    return """<!DOCTYPE html>
<html>
<head><title>Locust Report</title></head>
<body>
<script>
window.templateArgs = {
    "start_time": "2024-01-15T10:00:00Z",
    "end_time": "2024-01-15T10:30:00Z",
    "requests_statistics": [
        {
            "name": "/api/users",
            "num_requests": 1000,
            "num_failures": 5,
            "avg_response_time": 101.5,
            "median_response_time": 89,
            "min_response_time": 43.3,
            "max_response_time": 1317.8,
            "avg_content_length": 2.0,
            "current_rps": 190.7,
            "response_time_percentile_0.95": 170,
            "response_time_percentile_0.99": 250
        },
        {
            "name": "Aggregated",
            "num_requests": 1000,
            "num_failures": 5,
            "avg_response_time": 101.5,
            "median_response_time": 89,
            "min_response_time": 43.3,
            "max_response_time": 1317.8,
            "avg_content_length": 2.0,
            "current_rps": 190.7,
            "response_time_percentile_0.95": 170,
            "response_time_percentile_0.99": 250
        }
    ]
};
</script>
</body>
</html>
"""


@pytest.fixture
def html_without_template_args():
    """HTML content without templateArgs."""
    return """<!DOCTYPE html>
<html>
<head><title>Empty Report</title></head>
<body><p>No data</p></body>
</html>
"""


@pytest.fixture
def temp_test_dir(sample_csv_content):
    """Create a temporary directory with test data."""
    tmpdir = tempfile.mkdtemp()
    csv_path = Path(tmpdir) / "report.csv"
    csv_path.write_text(sample_csv_content)
    yield Path(tmpdir)
    shutil.rmtree(tmpdir)


@pytest.fixture
def temp_test_dir_v2(sample_csv_content_v2):
    """Create a second temporary directory with different test data."""
    tmpdir = tempfile.mkdtemp()
    csv_path = Path(tmpdir) / "report.csv"
    csv_path.write_text(sample_csv_content_v2)
    yield Path(tmpdir)
    shutil.rmtree(tmpdir)


@pytest.fixture
def temp_dir_with_html(sample_csv_content, sample_html_template_args):
    """Create a temporary directory with CSV and HTML files."""
    tmpdir = tempfile.mkdtemp()
    base = Path(tmpdir)

    # Write CSV
    csv_path = base / "report.csv"
    csv_path.write_text(sample_csv_content)

    # Write HTML
    html_path = base / "feature_test.html"
    html_path.write_text(sample_html_template_args)

    yield base
    shutil.rmtree(tmpdir)


@pytest.fixture
def real_test_runs_path():
    """Path to the real test_runs directory if it exists."""
    path = Path(__file__).parent.parent / "test_runs"
    if path.exists():
        return path
    pytest.skip("test_runs directory not available")
