"""Run report generation for the quality gate pipeline.

Produces run-data.json (structured, for pipeline-data repo) and
run-report.yaml (human-readable summary).
"""
import json
import os
from datetime import datetime, timezone

import yaml


def generate_run_report(run_data: dict) -> dict:
    """Generate a human-readable YAML report from run-data."""
    report = {
        "title": "Release Quality Gate 1: Feature Definition of Ready for Planning",
        "generated_at": run_data.get("generated_at"),
        "dry_run": run_data.get("dry_run"),
        "mode": run_data.get("mode"),
        "summary": run_data.get("summary", {}),
    }

    if run_data.get("issue_key"):
        report["issue_key"] = run_data["issue_key"]

    passed = []
    failed = []
    errored = []
    for issue in run_data.get("issues", []):
        entry = {
            "key": issue["key"],
            "checks": {},
        }
        for check_name, check_data in issue.get("checks", {}).items():
            entry["checks"][check_name] = {
                "passed": check_data["passed"],
                "details": check_data["details"],
            }

        if issue["verdict"] == "pass":
            passed.append(entry)
        elif issue["verdict"] == "error":
            errored.append(entry)
        else:
            failed.append(entry)

    if failed:
        report["failed_issues"] = failed
    if errored:
        report["error_issues"] = errored
    if passed:
        report["passed_issues"] = passed

    return report


def write_reports(run_data: dict, output_dir: str = None) -> tuple[str, str]:
    """Write both run-data.json and run-report.yaml to output_dir."""
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(__file__), "..", "artifacts")
    os.makedirs(output_dir, exist_ok=True)

    json_path = os.path.join(output_dir, "run-data.json")
    with open(json_path, "w") as f:
        json.dump(run_data, f, indent=2)

    report = generate_run_report(run_data)
    yaml_path = os.path.join(output_dir, "run-report.yaml")
    with open(yaml_path, "w") as f:
        yaml.dump(report, f, default_flow_style=False, sort_keys=False,
                  allow_unicode=True)

    return json_path, yaml_path
