#!/usr/bin/env python3
"""
Run multiple YAML scenarios and produce an aggregated JSON/HTML report.

This script imports the existing `run_scenario` from `run_yaml_log_check.py`
and runs it for each YAML file found in a directory (or an explicit list of
files). It captures the per-scenario stdout and exit code and writes a
combined report to disk.
"""

import argparse
import json
import sys
import time
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import List

import yaml

from run_yaml_log_check import run_scenario


def collect_scenarios(paths: List[str]) -> List[Path]:
    result = []
    for p in paths:
        pp = Path(p)
        if pp.is_dir():
            for f in sorted(pp.glob("*.yaml")):
                result.append(f)
        elif pp.is_file():
            result.append(pp)
        else:
            # allow glob-like patterns
            for f in sorted(Path('.').glob(p)):
                result.append(f)
    return result


def read_scenario_name(path: Path) -> str:
    try:
        d = yaml.safe_load(path.read_text()) or {}
        return d.get("name") or path.name
    except Exception:
        return path.name


def make_html_report(report: dict) -> str:
    rows = []
    for t in report["tests"]:
        status = "PASS" if t["rc"] == 0 else "FAIL"
        rows.append(f"<tr><td>{t['scenario']}</td><td>{t['name']}</td><td>{status}</td><td>{t['rc']}</td><td>{t['duration']:.2f}s</td></tr>")

    html = f"""
<html>
<head><meta charset="utf-8"><title>Test Report</title></head>
<body>
<h1>Aggregated Scenario Report</h1>
<p>Ran {len(report['tests'])} scenarios. Passed: {report['summary']['passed']}, Failed: {report['summary']['failed']}</p>
<table border="1" cellpadding="4" cellspacing="0">
<thead><tr><th>Path</th><th>Name</th><th>Status</th><th>RC</th><th>Duration</th></tr></thead>
<tbody>
{''.join(rows)}
</tbody>
</table>
</body>
</html>
"""
    return html


def main():
    ap = argparse.ArgumentParser(description="Run multiple YAML scenarios and create an aggregated report")
    ap.add_argument("scenarios", nargs="+", help="Scenario files or directories containing YAML files (supports multiple)")
    ap.add_argument("--log-file", help="path to bot events log (jsonl)", default="bot_events.log")
    ap.add_argument("--report", help="output JSON report path", default="report.json")
    ap.add_argument("--html-report", help="output HTML report path (optional)")
    ap.add_argument("--delay", type=float, help="seconds to wait between scenarios", default=0.5)
    args = ap.parse_args()

    scenario_paths = collect_scenarios(args.scenarios)
    if not scenario_paths:
        print("No scenario files found")
        sys.exit(1)

    tests = []
    passed = 0
    failed = 0

    for sp in scenario_paths:
        print(f"Running: {sp}")
        name = read_scenario_name(sp)
        buf = StringIO()
        start = time.time()
        with redirect_stdout(buf):
            try:
                rc = run_scenario(str(sp), args.log_file)
            except Exception as e:
                rc = 3
                print(f"Error running scenario: {e}")
        duration = time.time() - start
        out = buf.getvalue()

        tests.append({
            "scenario": str(sp),
            "name": name,
            "rc": rc,
            "duration": duration,
            "output": out,
        })

        if rc == 0:
            passed += 1
        else:
            failed += 1

        # small delay to avoid tight loops
        time.sleep(args.delay)

    report = {"tests": tests, "summary": {"total": len(tests), "passed": passed, "failed": failed}}

    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Wrote JSON report to {args.report}")

    if args.html_report:
        html = make_html_report(report)
        Path(args.html_report).write_text(html)
        print(f"Wrote HTML report to {args.html_report}")

    # exit non-zero if any failed
    sys.exit(0 if failed == 0 else 2)


if __name__ == "__main__":
    main()
