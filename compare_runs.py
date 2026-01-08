#!/usr/bin/env python3
import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re
import html as htmllib
from datetime import datetime
from urllib.parse import parse_qsl


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
    # Prefer the explicit assignment form
    m = re.search(r"window\.templateArgs\s*=\s*\{", html_text)
    if not m:
        return None
    brace_start = m.start() + m.group(0).rfind("{")
    if brace_start == -1:
        return None
    # Match braces to find the end of the JSON object
    depth = 0
    i = brace_start
    while i < len(html_text):
        ch = html_text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html_text[brace_start : i + 1])
                except Exception:
                    return None
        i += 1
    return None


def load_html_feature_map(dir_path: Path) -> Dict[str, Dict[str, Row]]:
    """Parse per-feature Locust HTML pages for per-endpoint metrics.

    Returns a nested mapping: { feature_name: { endpoint_name: Row(...) } }
    The special endpoint name 'Aggregated' is included if present.
    """
    features: Dict[str, Dict[str, Row]] = {}
    if not dir_path.is_dir():
        return features
    for html_path in dir_path.glob("*.html"):
        if html_path.name in {"htmlpublisher-wrapper.html"}:
            continue
        try:
            text = html_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        tmpl = _extract_template_args(text)
        if not tmpl:
            continue
        rs = tmpl.get("requests_statistics") or []
        # Compute test duration from start_time/end_time if available
        def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
            if not ts or not isinstance(ts, str):
                return None
            t = ts.strip()
            if t.endswith("Z"):
                t = t[:-1] + "+00:00"
            try:
                return datetime.fromisoformat(t)
            except Exception:
                return None

        start_dt = _parse_iso(tmpl.get("start_time"))
        end_dt = _parse_iso(tmpl.get("end_time"))
        duration_seconds: Optional[float] = None
        if start_dt and end_dt:
            try:
                duration_seconds = (end_dt - start_dt).total_seconds()
                if duration_seconds <= 0:
                    duration_seconds = None
            except Exception:
                duration_seconds = None

        # Determine the 'During' date used for label normalization.
        # Prefer end date; fallback to start date if end is missing.
        during_date = (end_dt or start_dt).date() if (end_dt or start_dt) else None

        def normalize_endpoint_name(name: str) -> str:
            if not during_date:
                return name
            if name == "Aggregated":
                return name
            # Split path and query
            if "?" not in name:
                return name
            path, qs = name.split("?", 1)
            parts = qs.split("&") if qs else []
            new_parts = []
            for part in parts:
                if not part:
                    continue
                if "=" in part:
                    k, v = part.split("=", 1)
                else:
                    k, v = part, ""
                key = k.strip()
                val = v.strip()
                if key in {"start_date", "end_date"} and re.match(r"^\d{4}-\d{2}-\d{2}$", val):
                    try:
                        y, m, d = map(int, val.split("-"))
                        dt = datetime(y, m, d).date()
                        delta = (dt - during_date).days
                        if delta == 0:
                            rel = "During"
                        else:
                            sign = "+" if delta > 0 else ""
                            rel = f"During{sign}{delta}d"
                        val = rel
                    except Exception:
                        pass
                new_parts.append(f"{key}={val}" if val != "" else key)
            return path + ("?" + "&".join(new_parts) if new_parts else "")
        if not isinstance(rs, list) or not rs:
            continue
        fmap: Dict[str, Row] = {}
        for item in rs:
            if not isinstance(item, dict):
                continue
            name = htmllib.unescape(str(item.get("name", "")).strip())
            name = normalize_endpoint_name(name)
            if not name:
                continue
            data: Dict[str, float] = {}
            def s(key_out: str, val):
                if isinstance(val, (int, float)):
                    data[key_out] = float(val)
            # Compute average RPS over the whole run when possible
            num_req = item.get("num_requests")
            if isinstance(num_req, (int, float)) and duration_seconds and duration_seconds > 0:
                data["Requests/s"] = float(num_req) / float(duration_seconds)
            else:
                # Fallback to instantaneous value if duration unavailable
                s("Requests/s", item.get("current_rps"))
            s("Request Count", item.get("num_requests"))
            s("Failure Count", item.get("num_failures"))
            s("Average Response Time", item.get("avg_response_time"))
            s("Median Response Time", item.get("median_response_time"))
            s("Min Response Time", item.get("min_response_time"))
            s("Max Response Time", item.get("max_response_time"))
            s("Average Content Size", item.get("avg_content_length"))
            # Percentiles commonly present
            s("95%", item.get("response_time_percentile_0.95"))
            s("99%", item.get("response_time_percentile_0.99"))

            fmap[name] = Row(name=name, type="HTML", data=data)

        if fmap:
            features[html_path.stem] = fmap
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


def print_section(title: str):
    print("")
    print(title)
    print("-" * len(title))


def _metric_direction(metric: str) -> str:
    """Return 'higher', 'lower', or 'neutral' for a metric's desirable direction.

    - 'Requests/s' -> higher is better
    - Failures and response times / percentiles -> lower is better
    - others -> neutral
    """
    m = metric.lower()
    if metric == "Requests/s" or metric == "Request Count":
        return "higher"
    if metric in {"Failure Count", "Failures/s"}:
        return "lower"
    if "response time" in m:
        return "lower"
    if metric.endswith("%"):
        return "lower"
    return "neutral"


def _verdict_for(metric: str, b: Optional[float], c: Optional[float]) -> Optional[str]:
    if b is None or c is None:
        return None
    if b == c:
        return "same"
    direction = _metric_direction(metric)
    if direction == "higher":
        return "better" if c > b else "worse"
    if direction == "lower":
        return "better" if c < b else "worse"
    return None


def render_comparison(
    base_row: Optional[Row],
    curr_row: Optional[Row],
    important_fields: List[str],
    *,
    colorize: bool = False,
    show_verdict: bool = True,
):
    headers = [
        "Metric",
        "Base",
        "Current",
        "Diff",
        "% Change",
    ]
    if show_verdict:
        headers.append("Verdict")
    rows: List[List[str]] = []

    base_data = base_row.data if base_row else {}
    curr_data = curr_row.data if curr_row else {}

    fields = important_fields[:]
    # Also include any extra percentile columns present in data
    extra_fields = [k for k in curr_data.keys() | base_data.keys() if k.endswith("%") and k not in fields]
    fields.extend(sorted(extra_fields))

    for field in fields:
        b = base_data.get(field)
        c = curr_data.get(field)
        d = diff(b, c)
        p = pct_change(b, c)
        p_str = "-" if p is None else f"{p:+.1f}%"
        row = [
            field,
            format_number(b),
            format_number(c),
            ("-" if d is None else (f"{d:+.3f}" if abs(d - round(d)) > 1e-9 else f"{int(d):+d}")),
            p_str,
        ]
        if show_verdict:
            v = _verdict_for(field, b, c)
            row.append("-" if v is None else v)
        rows.append(row)

    # Determine column widths
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(headers)]

    # Print header
    header_line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    sep_line = "  ".join("-" * widths[i] for i in range(len(headers)))
    print(header_line)
    print(sep_line)
    for r in rows:
        line = "  ".join(r[i].ljust(widths[i]) for i in range(len(headers)))
        if colorize:
            # color whole row based on verdict
            v = r[-1] if show_verdict else None
            if v == "better":
                line = "\033[32m" + line + "\033[0m"  # green
            elif v == "worse":
                line = "\033[31m" + line + "\033[0m"  # red
        print(line)


def compare_reports(
    base_path: Path,
    curr_path: Path,
    as_json: bool = False,
    *,
    colorize: bool = False,
    show_verdict: bool = True,
) -> int:
    base_rows = load_report(base_path)
    curr_rows = load_report(curr_path)

    base_idx = index_rows(base_rows)
    curr_idx = index_rows(curr_rows)

    all_keys = sorted(set(base_idx.keys()) | set(curr_idx.keys()))

    important_fields = [
        "Requests/s",
        "Request Count",
        "Failure Count",
        "Average Response Time",
        "Median Response Time",
        "Min Response Time",
        "Max Response Time",
        "95%",
    ]

    # Also parse per-feature HTML pages if directories are given
    base_html_map = load_html_feature_map(base_path if base_path.is_dir() else base_path.parent)
    curr_html_map = load_html_feature_map(curr_path if curr_path.is_dir() else curr_path.parent)

    if as_json:
        # Produce a structured JSON dict
        out: Dict[str, Dict[str, Dict[str, Optional[float]]]] = {}
        for key in all_keys:
            b = base_idx.get(key)
            c = curr_idx.get(key)
            # Combine fields present
            fields = set(important_fields)
            if b:
                fields.update(b.data.keys())
            if c:
                fields.update(c.data.keys())
            entry: Dict[str, Dict[str, Optional[float]]] = {}
            for f in sorted(fields):
                bb = b.data.get(f) if b else None
                cc = c.data.get(f) if c else None
                entry[f] = {
                    "base": bb,
                    "current": cc,
                    "diff": diff(bb, cc),
                    "pct_change": pct_change(bb, cc),
                }
            out[key] = entry
        # Add HTML features per endpoint
        feature_names = sorted(set(base_html_map.keys()) | set(curr_html_map.keys()))
        for feat in feature_names:
            b_map = base_html_map.get(feat, {})
            c_map = curr_html_map.get(feat, {})
            endpoint_names = sorted(set(b_map.keys()) | set(c_map.keys()))
            for ep in endpoint_names:
                b = b_map.get(ep)
                c = c_map.get(ep)
                fields = set(important_fields)
                if b:
                    fields.update(b.data.keys())
                if c:
                    fields.update(c.data.keys())
                entry: Dict[str, Dict[str, Optional[float]]] = {}
                for f in sorted(fields):
                    bb = b.data.get(f) if b else None
                    cc = c.data.get(f) if c else None
                    entry[f] = {
                        "base": bb,
                        "current": cc,
                        "diff": diff(bb, cc),
                        "pct_change": pct_change(bb, cc),
                    }
                out[f"HTML:{feat}:{ep}"] = entry
        print(json.dumps(out, indent=2))
        return 0

    # Human readable output
    print_section("Aggregated")
    render_comparison(
        base_idx.get("__Aggregated__"),
        curr_idx.get("__Aggregated__"),
        important_fields,
        colorize=colorize,
        show_verdict=show_verdict,
    )

    endpoint_keys = [k for k in all_keys if k != "__Aggregated__"]
    for ek in endpoint_keys:
        title = f"Endpoint: {ek}"
        print_section(title)
        render_comparison(
            base_idx.get(ek),
            curr_idx.get(ek),
            important_fields,
            colorize=colorize,
            show_verdict=show_verdict,
        )

    # Render HTML features
    feature_keys = sorted(set(base_html_map.keys()) | set(curr_html_map.keys()))
    if feature_keys:
        print_section("HTML Features")
        for fk in feature_keys:
            print_section(f"Feature: {fk}")
            b_map = base_html_map.get(fk, {})
            c_map = curr_html_map.get(fk, {})
            ep_keys = sorted(set(b_map.keys()) | set(c_map.keys()))
            for ep in ep_keys:
                print_section(f"Endpoint: {ep}")
                render_comparison(
                    b_map.get(ep),
                    c_map.get(ep),
                    important_fields,
                    colorize=colorize,
                    show_verdict=show_verdict,
                )

    return 0


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Compare Locust performance reports between a base and current run.\n"
            "Provide either directories containing report.csv or direct CSV file paths."
        )
    )
    parser.add_argument("base", type=Path, help="Base run directory or report.csv path")
    parser.add_argument("current", type=Path, help="Current run directory or report.csv path")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument(
        "--color",
        action="store_true",
        help="Colorize rows: green if better, red if worse",
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
            as_json=args.json,
            colorize=args.color,
            show_verdict=args.show_verdict,
        )
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
