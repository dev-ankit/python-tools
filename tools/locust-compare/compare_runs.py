#!/usr/bin/env python3
"""Compare Locust performance reports between a base and current run."""

import argparse
import atexit
import csv
import html as htmllib
import json
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Track temporary directories for cleanup
_temp_dirs: List[str] = []


def _cleanup_temp_dirs():
    """Clean up temporary directories created for zip extraction."""
    for d in _temp_dirs:
        try:
            shutil.rmtree(d)
        except Exception:
            pass


atexit.register(_cleanup_temp_dirs)


NUMERIC_FIELDS = {
    "Request Count",
    "Failure Count",
    "Median Response Time",
    "Average Response Time",
    "Min Response Time",
    "Max Response Time",
    "Average Content Size",
    "Requests/s",
    "Failures/s",
    # Percentile columns (if present)
    "50%",
    "66%",
    "75%",
    "80%",
    "90%",
    "95%",
    "98%",
    "99%",
    "99.9%",
    "99.99%",
    "100%",
}


@dataclass(frozen=True)
class Row:
    name: str
    type: str
    data: Dict[str, float]


def _as_float(value: str) -> Optional[float]:
    if value is None:
        return None
    value = value.strip()
    if value == "":
        return None
    try:
        # Most values are numeric; ints are fine as floats too
        return float(value)
    except ValueError:
        return None


def _resolve_path(path: Path) -> Path:
    """Resolve a path, extracting zip files to a temporary directory if needed.

    If `path` is a zip file, extracts it to a temporary directory and returns
    the path to the extracted contents. The temporary directory is automatically
    cleaned up when the program exits.

    If `path` is not a zip file, returns it unchanged.
    """
    if path.is_file() and path.suffix.lower() == ".zip":
        if not zipfile.is_zipfile(path):
            raise ValueError(f"File has .zip extension but is not a valid zip file: {path}")

        tmpdir = tempfile.mkdtemp(prefix="locust-compare-")
        _temp_dirs.append(tmpdir)

        with zipfile.ZipFile(path, "r") as zf:
            zf.extractall(tmpdir)

        extracted = Path(tmpdir)

        # If the zip contains a single directory, use that as the root
        contents = list(extracted.iterdir())
        if len(contents) == 1 and contents[0].is_dir():
            return contents[0]

        return extracted

    return path


def load_report(path: Path) -> List[Row]:
    """Load a Locust report.csv and return parsed rows.

    If `path` is a directory, attempts to read `path / 'report.csv'`.
    If `path` is a file, uses it directly.
    """
    report_path = path
    if path.is_dir():
        candidate = path / "report.csv"
        if not candidate.exists():
            raise FileNotFoundError(f"report.csv not found in directory: {path}")
        report_path = candidate
    elif path.is_file():
        if path.name != "report.csv" and not path.name.endswith(".csv"):
            raise ValueError(f"Provided file does not look like a CSV report: {path}")
    else:
        raise FileNotFoundError(f"Path not found: {path}")

    rows: List[Row] = []
    with report_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            name = (raw.get("Name") or "").strip()
            rtype = (raw.get("Type") or "").strip()
            data: Dict[str, float] = {}
            for k, v in raw.items():
                if k in ("Name", "Type"):
                    continue
                if k in NUMERIC_FIELDS:
                    fv = _as_float(v)
                    if fv is not None:
                        data[k] = fv
            rows.append(Row(name=name, type=rtype, data=data))
    return rows


def index_rows(rows: List[Row]) -> Dict[str, Row]:
    """Index rows by their name, with a synthetic key '__Aggregated__' for the Aggregated row."""
    idx: Dict[str, Row] = {}
    for r in rows:
        key = "__Aggregated__" if r.name == "Aggregated" else r.name
        idx[key] = r
    return idx


def _extract_template_args(html_text: str) -> Optional[dict]:
    """Extract JSON assigned to window.templateArgs in a Locust HTML file.

    Uses a brace-matching approach to safely capture the JSON object.
    Returns a parsed dict or None if not found/invalid.
    """
    match = re.search(r"window\.templateArgs\s*=\s*\{", html_text)
    if not match:
        return None

    brace_start = match.start() + match.group(0).rfind("{")
    if brace_start == -1:
        return None

    depth = 0
    for i in range(brace_start, len(html_text)):
        char = html_text[i]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html_text[brace_start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _parse_iso_timestamp(timestamp: Optional[str]) -> Optional[datetime]:
    """Parse an ISO timestamp string into a datetime object."""
    if not timestamp or not isinstance(timestamp, str):
        return None

    cleaned = timestamp.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def _normalize_endpoint_name(name: str, during_date: Optional[datetime]) -> str:
    """Normalize endpoint names by converting date parameters to relative offsets.

    Converts start_date and end_date query parameters to relative offsets
    (e.g., "During", "During+1d", "During-2d") based on the test run date.
    """
    if not during_date or name == "Aggregated" or "?" not in name:
        return name

    path, query_string = name.split("?", 1)
    parts = query_string.split("&") if query_string else []
    normalized_parts = []

    for part in parts:
        if not part:
            continue

        if "=" in part:
            key, value = part.split("=", 1)
        else:
            key, value = part, ""

        key = key.strip()
        value = value.strip()

        if key in {"start_date", "end_date"} and re.match(r"^\d{4}-\d{2}-\d{2}$", value):
            try:
                year, month, day = map(int, value.split("-"))
                date_value = datetime(year, month, day).date()
                delta = (date_value - during_date.date()).days

                if delta == 0:
                    value = "During"
                else:
                    sign = "+" if delta > 0 else ""
                    value = f"During{sign}{delta}d"
            except ValueError:
                pass

        if value:
            normalized_parts.append(f"{key}={value}")
        else:
            normalized_parts.append(key)

    if normalized_parts:
        return f"{path}?{'&'.join(normalized_parts)}"
    return path


def _extract_metric_value(item: dict, key: str) -> Optional[float]:
    """Extract a numeric metric value from an HTML statistics item."""
    value = item.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _parse_html_endpoint_metrics(
    item: dict,
    duration_seconds: Optional[float],
) -> Dict[str, float]:
    """Parse metrics from an HTML statistics item into a data dictionary."""
    data: Dict[str, float] = {}

    # Compute average RPS over the whole run when possible
    num_requests = item.get("num_requests")
    if isinstance(num_requests, (int, float)) and duration_seconds and duration_seconds > 0:
        data["Requests/s"] = float(num_requests) / float(duration_seconds)
    else:
        rps = _extract_metric_value(item, "current_rps")
        if rps is not None:
            data["Requests/s"] = rps

    # Map HTML field names to our standard metric names
    metric_mappings = {
        "Request Count": "num_requests",
        "Failure Count": "num_failures",
        "Average Response Time": "avg_response_time",
        "Median Response Time": "median_response_time",
        "Min Response Time": "min_response_time",
        "Max Response Time": "max_response_time",
        "Average Content Size": "avg_content_length",
        "95%": "response_time_percentile_0.95",
        "99%": "response_time_percentile_0.99",
    }

    for output_key, input_key in metric_mappings.items():
        value = _extract_metric_value(item, input_key)
        if value is not None:
            data[output_key] = value

    return data


def _compute_duration_seconds(start_dt: Optional[datetime], end_dt: Optional[datetime]) -> Optional[float]:
    """Compute test duration in seconds from start and end timestamps."""
    if not start_dt or not end_dt:
        return None

    duration = (end_dt - start_dt).total_seconds()
    return duration if duration > 0 else None


def load_html_feature_map(dir_path: Path) -> Dict[str, Dict[str, Row]]:
    """Parse per-feature Locust HTML pages for per-endpoint metrics.

    Returns a nested mapping: { feature_name: { endpoint_name: Row(...) } }
    The special endpoint name 'Aggregated' is included if present.
    """
    if not dir_path.is_dir():
        return {}

    features: Dict[str, Dict[str, Row]] = {}

    for html_path in dir_path.glob("*.html"):
        if html_path.name == "htmlpublisher-wrapper.html":
            continue

        try:
            text = html_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        template_args = _extract_template_args(text)
        if not template_args:
            continue

        requests_statistics = template_args.get("requests_statistics") or []
        if not isinstance(requests_statistics, list) or not requests_statistics:
            continue

        start_dt = _parse_iso_timestamp(template_args.get("start_time"))
        end_dt = _parse_iso_timestamp(template_args.get("end_time"))
        duration_seconds = _compute_duration_seconds(start_dt, end_dt)

        # Use end date for normalization, fallback to start date
        during_date = end_dt or start_dt

        feature_map: Dict[str, Row] = {}

        for item in requests_statistics:
            if not isinstance(item, dict):
                continue

            raw_name = str(item.get("name", "")).strip()
            name = htmllib.unescape(raw_name)
            name = _normalize_endpoint_name(name, during_date)

            if not name:
                continue

            data = _parse_html_endpoint_metrics(item, duration_seconds)
            feature_map[name] = Row(name=name, type="HTML", data=data)

        if feature_map:
            features[html_path.stem] = feature_map

    return features


def pct_change(base: Optional[float], curr: Optional[float]) -> Optional[float]:
    if base is None or curr is None:
        return None
    if base == 0:
        return None
    return (curr - base) / base * 100.0


def diff(base: Optional[float], curr: Optional[float]) -> Optional[float]:
    if base is None or curr is None:
        return None
    return curr - base


def format_number(v: Optional[float]) -> str:
    if v is None:
        return "-"
    # Heuristic: show integers without decimals when close to int
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    # Else show with up to 3 decimals
    return f"{v:.3f}"


def print_section(title: str) -> None:
    """Print a plain text section header with underline."""
    print("")
    print(title)
    print("-" * len(title))


def print_section_markdown(title: str, level: int = 2) -> None:
    """Print a markdown section header."""
    print("")
    print(f"{'#' * level} {title}")
    print("")


HIGHER_IS_BETTER_METRICS = {"Requests/s", "Request Count"}
LOWER_IS_BETTER_METRICS = {"Failure Count", "Failures/s"}


def _metric_direction(metric: str) -> str:
    """Return 'higher', 'lower', or 'neutral' for a metric's desirable direction.

    - Throughput metrics (Requests/s, Request Count) -> higher is better
    - Failure metrics -> lower is better
    - Response time metrics and percentiles -> lower is better
    - Others -> neutral (no preference)
    """
    if metric in HIGHER_IS_BETTER_METRICS:
        return "higher"

    if metric in LOWER_IS_BETTER_METRICS:
        return "lower"

    # Response time metrics (case-insensitive check)
    if "response time" in metric.lower():
        return "lower"

    # Percentile metrics (e.g., "95%", "99%")
    if metric.endswith("%"):
        return "lower"

    return "neutral"


def _verdict_for(metric: str, base_val: Optional[float], curr_val: Optional[float]) -> Optional[str]:
    """Determine the verdict (better/worse/same) for a metric comparison."""
    if base_val is None or curr_val is None:
        return None

    if base_val == curr_val:
        return "same"

    direction = _metric_direction(metric)

    if direction == "higher":
        return "better" if curr_val > base_val else "worse"

    if direction == "lower":
        return "better" if curr_val < base_val else "worse"

    return None


def _verdict_to_emoji(verdict: Optional[str]) -> str:
    """Convert verdict to emoji for markdown output."""
    verdict_emoji_map = {
        "better": "✅",
        "worse": "❌",
        "same": "➖",
    }
    return verdict_emoji_map.get(verdict, "")


def _format_diff(d: Optional[float]) -> str:
    """Format a diff value for display."""
    if d is None:
        return "-"
    if abs(d - round(d)) > 1e-9:
        return f"{d:+.3f}"
    return f"{int(d):+d}"


def _get_comparison_fields(
    base_row: Optional[Row],
    curr_row: Optional[Row],
    important_fields: List[str],
) -> List[str]:
    """Get the list of fields to compare, including extra percentile columns."""
    base_data = base_row.data if base_row else {}
    curr_data = curr_row.data if curr_row else {}

    fields = important_fields[:]
    extra_percentiles = [
        k for k in (curr_data.keys() | base_data.keys())
        if k.endswith("%") and k not in fields
    ]
    fields.extend(sorted(extra_percentiles))
    return fields


def _build_comparison_rows(
    base_row: Optional[Row],
    curr_row: Optional[Row],
    fields: List[str],
    show_verdict: bool,
    use_emoji: bool,
) -> List[List[str]]:
    """Build comparison data rows for rendering."""
    base_data = base_row.data if base_row else {}
    curr_data = curr_row.data if curr_row else {}

    rows: List[List[str]] = []
    for field in fields:
        base_val = base_data.get(field)
        curr_val = curr_data.get(field)
        diff_val = diff(base_val, curr_val)
        pct = pct_change(base_val, curr_val)
        pct_str = "-" if pct is None else f"{pct:+.1f}%"

        row = [
            field,
            format_number(base_val),
            format_number(curr_val),
            _format_diff(diff_val),
            pct_str,
        ]

        if show_verdict:
            verdict = _verdict_for(field, base_val, curr_val)
            if use_emoji:
                row.append(_verdict_to_emoji(verdict))
            else:
                row.append("-" if verdict is None else verdict)

        rows.append(row)

    return rows


def render_comparison_markdown(
    base_row: Optional[Row],
    curr_row: Optional[Row],
    important_fields: List[str],
    *,
    show_verdict: bool = True,
) -> None:
    """Render comparison as markdown table with emoji indicators."""
    headers = ["Metric", "Base", "Current", "Diff", "% Change"]
    if show_verdict:
        headers.append("Verdict")

    fields = _get_comparison_fields(base_row, curr_row, important_fields)
    rows = _build_comparison_rows(base_row, curr_row, fields, show_verdict, use_emoji=True)

    print("| " + " | ".join(headers) + " |")
    print("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        print("| " + " | ".join(row) + " |")


def render_comparison(
    base_row: Optional[Row],
    curr_row: Optional[Row],
    important_fields: List[str],
    *,
    colorize: bool = False,
    show_verdict: bool = True,
) -> None:
    """Render comparison as a plain text table."""
    headers = ["Metric", "Base", "Current", "Diff", "% Change"]
    if show_verdict:
        headers.append("Verdict")

    fields = _get_comparison_fields(base_row, curr_row, important_fields)
    rows = _build_comparison_rows(base_row, curr_row, fields, show_verdict, use_emoji=False)

    # Calculate column widths
    widths = [
        max(len(headers[i]), *(len(row[i]) for row in rows))
        for i in range(len(headers))
    ]

    # Print header
    header_line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    separator_line = "  ".join("-" * w for w in widths)
    print(header_line)
    print(separator_line)

    # Print data rows
    for row in rows:
        line = "  ".join(row[i].ljust(widths[i]) for i in range(len(headers)))

        if colorize and show_verdict:
            verdict = row[-1]
            if verdict == "better":
                line = f"\033[32m{line}\033[0m"
            elif verdict == "worse":
                line = f"\033[31m{line}\033[0m"

        print(line)


IMPORTANT_FIELDS = [
    "Requests/s",
    "Request Count",
    "Failure Count",
    "Average Response Time",
    "Median Response Time",
    "Min Response Time",
    "Max Response Time",
    "95%",
]


def _build_json_entry(
    base_row: Optional[Row],
    curr_row: Optional[Row],
    important_fields: List[str],
) -> Dict[str, Dict[str, Optional[float]]]:
    """Build a JSON entry for a single endpoint comparison."""
    fields = set(important_fields)
    if base_row:
        fields.update(base_row.data.keys())
    if curr_row:
        fields.update(curr_row.data.keys())

    entry: Dict[str, Dict[str, Optional[float]]] = {}
    for field in sorted(fields):
        base_val = base_row.data.get(field) if base_row else None
        curr_val = curr_row.data.get(field) if curr_row else None
        entry[field] = {
            "base": base_val,
            "current": curr_val,
            "diff": diff(base_val, curr_val),
            "pct_change": pct_change(base_val, curr_val),
        }
    return entry


def _output_json(
    base_idx: Dict[str, Row],
    curr_idx: Dict[str, Row],
    base_html_map: Dict[str, Dict[str, Row]],
    curr_html_map: Dict[str, Dict[str, Row]],
    important_fields: List[str],
) -> None:
    """Output comparison results as JSON."""
    output: Dict[str, Dict[str, Dict[str, Optional[float]]]] = {}

    # Add CSV report entries
    all_keys = sorted(set(base_idx.keys()) | set(curr_idx.keys()))
    for key in all_keys:
        output[key] = _build_json_entry(
            base_idx.get(key),
            curr_idx.get(key),
            important_fields,
        )

    # Add HTML feature entries
    feature_names = sorted(set(base_html_map.keys()) | set(curr_html_map.keys()))
    for feature in feature_names:
        base_feature = base_html_map.get(feature, {})
        curr_feature = curr_html_map.get(feature, {})
        endpoint_names = sorted(set(base_feature.keys()) | set(curr_feature.keys()))

        for endpoint in endpoint_names:
            output[f"HTML:{feature}:{endpoint}"] = _build_json_entry(
                base_feature.get(endpoint),
                curr_feature.get(endpoint),
                important_fields,
            )

    print(json.dumps(output, indent=2))


def _output_human_readable(
    base_idx: Dict[str, Row],
    curr_idx: Dict[str, Row],
    base_html_map: Dict[str, Dict[str, Row]],
    curr_html_map: Dict[str, Dict[str, Row]],
    important_fields: List[str],
    *,
    use_markdown: bool,
    colorize: bool,
    show_verdict: bool,
) -> None:
    """Output comparison results in human-readable format (text or markdown)."""
    all_keys = sorted(set(base_idx.keys()) | set(curr_idx.keys()))
    endpoint_keys = [k for k in all_keys if k != "__Aggregated__"]
    feature_keys = sorted(set(base_html_map.keys()) | set(curr_html_map.keys()))

    if use_markdown:
        print("# Locust Performance Comparison")
        print("")

    # Render aggregated section
    if use_markdown:
        print_section_markdown("Aggregated", 2)
        render_comparison_markdown(
            base_idx.get("__Aggregated__"),
            curr_idx.get("__Aggregated__"),
            important_fields,
            show_verdict=show_verdict,
        )
    else:
        print_section("Aggregated")
        render_comparison(
            base_idx.get("__Aggregated__"),
            curr_idx.get("__Aggregated__"),
            important_fields,
            colorize=colorize,
            show_verdict=show_verdict,
        )

    # Render endpoint sections
    for endpoint_key in endpoint_keys:
        title = f"Endpoint: {endpoint_key}"
        if use_markdown:
            print_section_markdown(title, 3)
            render_comparison_markdown(
                base_idx.get(endpoint_key),
                curr_idx.get(endpoint_key),
                important_fields,
                show_verdict=show_verdict,
            )
        else:
            print_section(title)
            render_comparison(
                base_idx.get(endpoint_key),
                curr_idx.get(endpoint_key),
                important_fields,
                colorize=colorize,
                show_verdict=show_verdict,
            )

    # Render HTML features
    if feature_keys:
        if use_markdown:
            print_section_markdown("HTML Features", 2)
        else:
            print_section("HTML Features")

        for feature_key in feature_keys:
            if use_markdown:
                print_section_markdown(f"Feature: {feature_key}", 3)
            else:
                print_section(f"Feature: {feature_key}")

            base_feature = base_html_map.get(feature_key, {})
            curr_feature = curr_html_map.get(feature_key, {})
            ep_keys = sorted(set(base_feature.keys()) | set(curr_feature.keys()))

            for ep in ep_keys:
                if use_markdown:
                    print_section_markdown(f"Endpoint: {ep}", 4)
                    render_comparison_markdown(
                        base_feature.get(ep),
                        curr_feature.get(ep),
                        important_fields,
                        show_verdict=show_verdict,
                    )
                else:
                    print_section(f"Endpoint: {ep}")
                    render_comparison(
                        base_feature.get(ep),
                        curr_feature.get(ep),
                        important_fields,
                        colorize=colorize,
                        show_verdict=show_verdict,
                    )


def compare_reports(
    base_path: Path,
    curr_path: Path,
    output_format: str = "text",
    *,
    colorize: bool = False,
    show_verdict: bool = True,
) -> int:
    """Compare two Locust performance reports and output the results.

    Args:
        base_path: Path to the base report directory, CSV file, or zip file.
        curr_path: Path to the current report directory, CSV file, or zip file.
        output_format: Output format - "text", "json", or "markdown".
        colorize: Whether to colorize text output (green=better, red=worse).
        show_verdict: Whether to show the verdict column.

    Returns:
        0 on success, non-zero on error.
    """
    # Resolve paths (extract zip files if needed)
    base_path = _resolve_path(base_path)
    curr_path = _resolve_path(curr_path)

    # Load CSV reports
    base_rows = load_report(base_path)
    curr_rows = load_report(curr_path)
    base_idx = index_rows(base_rows)
    curr_idx = index_rows(curr_rows)

    # Load HTML feature maps
    base_html_dir = base_path if base_path.is_dir() else base_path.parent
    curr_html_dir = curr_path if curr_path.is_dir() else curr_path.parent
    base_html_map = load_html_feature_map(base_html_dir)
    curr_html_map = load_html_feature_map(curr_html_dir)

    if output_format == "json":
        _output_json(base_idx, curr_idx, base_html_map, curr_html_map, IMPORTANT_FIELDS)
    else:
        _output_human_readable(
            base_idx,
            curr_idx,
            base_html_map,
            curr_html_map,
            IMPORTANT_FIELDS,
            use_markdown=(output_format == "markdown"),
            colorize=colorize,
            show_verdict=show_verdict,
        )

    return 0


def main() -> int:
    """CLI entry point for locust-compare."""
    parser = argparse.ArgumentParser(
        description=(
            "Compare Locust performance reports between a base and current run. "
            "Provide either directories containing report.csv or direct CSV file paths."
        )
    )
    parser.add_argument(
        "base",
        type=Path,
        help="Base run directory, report.csv path, or zip file",
    )
    parser.add_argument(
        "current",
        type=Path,
        help="Current run directory, report.csv path, or zip file",
    )
    parser.add_argument(
        "-o",
        "--output",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format: text (default), json, or markdown",
    )
    parser.add_argument(
        "--color",
        action="store_true",
        help="Colorize rows: green if better, red if worse (only for text output)",
    )
    parser.add_argument(
        "--no-verdict",
        dest="show_verdict",
        action="store_false",
        help="Hide the 'Verdict' column",
    )

    args = parser.parse_args()

    try:
        return compare_reports(
            args.base,
            args.current,
            output_format=args.output,
            colorize=args.color,
            show_verdict=args.show_verdict,
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
