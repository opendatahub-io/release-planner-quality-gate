"""Release Quality Gate 1: Feature Definition of Ready for Planning.

Main orchestrator: discovers issues, evaluates checks, manages labels.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.checks import instantiate_checks, compute_verdict, CheckResult
import scripts.checks.hard_checks  # noqa: F401 — registers check types
from scripts.jira_utils import (
    require_env,
    search_issues,
    get_issue,
    add_labels,
    remove_labels,
)


CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "config", "pipeline-settings.yaml"
)


def load_config(path=None):
    """Load pipeline settings from YAML."""
    path = path or CONFIG_PATH
    with open(path) as f:
        return yaml.safe_load(f)


def build_jql(config):
    """Build JQL from pipeline-settings config."""
    jql_cfg = config["jql"]
    clauses = [f'project = {jql_cfg["project"]}']

    for label in jql_cfg.get("required_labels", []):
        clauses.append(f'labels = "{label}"')

    versions = jql_cfg.get("target_versions", [])
    if versions:
        version_list = ", ".join(f'"{v}"' for v in versions)
        clauses.append(f"cf[10855] IN ({version_list})")

    for status in jql_cfg.get("excluded_statuses", []):
        clauses.append(f'status != "{status}"')

    for label in jql_cfg.get("skip_labels", []):
        clauses.append(f'labels != "{label}"')

    jql = " AND ".join(clauses)
    order = jql_cfg.get("order_by", "key ASC")
    return f"{jql} ORDER BY {order}"


def collect_required_fields(config):
    """Gather all Jira field names needed by the configured checks."""
    fields = {"key", "summary", "labels", "priority"}
    for check_cfg in config.get("checks", {}).get("hard_checks", []):
        for f in check_cfg.get("fields", []):
            fields.add(f)
        for _ in check_cfg.get("labels", []):
            fields.add("labels")
    rice = config.get("rice_fields", {})
    for field_id in rice.values():
        fields.add(field_id)
    return ",".join(sorted(fields))


def discover_issues(config, server, user, token, issue_key=None):
    """Discover issues to evaluate — single key or JQL batch."""
    fields_str = collect_required_fields(config)
    if issue_key:
        issue = get_issue(server, user, token, issue_key, fields=fields_str)
        return [issue] if issue else []
    jql = build_jql(config)
    return search_issues(server, user, token, jql, fields=fields_str)


def evaluate_issue(issue, checks):
    """Run all checks against a single issue, return list of CheckResult."""
    return [check.evaluate(issue) for check in checks]


def apply_verdict_label(server, user, token, issue_key, current_labels,
                        verdict, label_config):
    """Apply pass/fail label based on verdict. Atomic swap."""
    pass_label = label_config["gate_pass"]
    fail_label = label_config["gate_fail"]

    new_label = pass_label if verdict == "pass" else fail_label
    old_label = fail_label if verdict == "pass" else pass_label

    has_new = new_label in current_labels
    has_old = old_label in current_labels

    if has_new and not has_old:
        return  # already correct

    labels_to_add = [] if has_new else [new_label]
    labels_to_remove = [old_label] if has_old else []

    if labels_to_add:
        add_labels(server, user, token, issue_key, labels_to_add)
    if labels_to_remove:
        remove_labels(server, user, token, issue_key, labels_to_remove)


def build_run_data(results_by_issue, config, dry_run, mode, issue_key=None):
    """Build the run-data.json structure."""
    issues_data = []
    pass_count = 0
    fail_count = 0

    for key, results in results_by_issue.items():
        verdict = compute_verdict(results)
        if verdict == "pass":
            pass_count += 1
        else:
            fail_count += 1
        issues_data.append({
            "key": key,
            "verdict": verdict,
            "checks": {
                r.name: {
                    "passed": r.passed,
                    "details": r.details,
                    "auto_fixable": r.auto_fixable,
                }
                for r in results
            },
        })

    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "mode": mode,
        "summary": {
            "total": len(results_by_issue),
            "pass": pass_count,
            "fail": fail_count,
        },
        "issues": issues_data,
    }
    if issue_key:
        data["issue_key"] = issue_key
    return data


def write_artifacts(run_data):
    """Write run-data.json to artifacts/."""
    art_dir = os.path.join(os.path.dirname(__file__), "..", "artifacts")
    os.makedirs(art_dir, exist_ok=True)
    path = os.path.join(art_dir, "run-data.json")
    with open(path, "w") as f:
        json.dump(run_data, f, indent=2)
    return path


def print_summary(results_by_issue):
    """Print a human-readable summary table."""
    print(f"\n{'='*70}")
    print(f"{'Key':<20} {'Verdict':<10} {'Details'}")
    print(f"{'-'*70}")
    for key, results in results_by_issue.items():
        verdict = compute_verdict(results)
        failed = [r for r in results if not r.passed]
        if failed:
            details = "; ".join(f"{r.name}: {r.details}" for r in failed)
        else:
            details = "all checks passed"
        status = "PASS" if verdict == "pass" else "FAIL"
        print(f"{key:<20} {status:<10} {details}")

    total = len(results_by_issue)
    passed = sum(1 for r in results_by_issue.values()
                 if compute_verdict(r) == "pass")
    print(f"{'-'*70}")
    print(f"Total: {total}  |  Pass: {passed}  |  Fail: {total - passed}")
    print(f"{'='*70}\n")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Release Quality Gate 1: Feature Definition of Ready for Planning"
    )
    parser.add_argument(
        "--issue", metavar="KEY",
        help="Evaluate a single issue (e.g., RHAISTRAT-1745)")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Generate RICE recommendations but write NOTHING to Jira")
    parser.add_argument(
        "--config", metavar="PATH",
        help="Path to pipeline-settings.yaml (default: config/pipeline-settings.yaml)")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    server, user, token = require_env()

    mode = "single" if args.issue else "batch"
    print(f"Release Quality Gate 1 — mode={mode}, dry_run={args.dry_run}")

    issues = discover_issues(config, server, user, token,
                             issue_key=args.issue)
    if not issues:
        print("No issues found to evaluate.")
        run_data = build_run_data({}, config, args.dry_run, mode, args.issue)
        write_artifacts(run_data)
        return

    print(f"Found {len(issues)} issue(s) to evaluate.")

    checks = instantiate_checks(config["checks"]["hard_checks"])
    results_by_issue = {}

    for issue in issues:
        key = issue["key"]
        results = evaluate_issue(issue, checks)
        results_by_issue[key] = results

    # TODO Phase 4: auto-fix RICE via Claude skill for issues missing RICE
    # For now, just evaluate and report.

    if not args.dry_run:
        label_config = config["labels"]
        for issue in issues:
            key = issue["key"]
            verdict = compute_verdict(results_by_issue[key])
            current_labels = issue.get("fields", {}).get("labels", [])
            apply_verdict_label(
                server, user, token, key, current_labels,
                verdict, label_config)
            print(f"  {key}: {verdict.upper()}"
                  f" → label applied")
    else:
        for key, results in results_by_issue.items():
            verdict = compute_verdict(results)
            print(f"  {key}: {verdict.upper()} (dry-run, no labels applied)")

    print_summary(results_by_issue)

    run_data = build_run_data(
        results_by_issue, config, args.dry_run, mode, args.issue)
    artifact_path = write_artifacts(run_data)
    print(f"Artifacts written to {artifact_path}")


if __name__ == "__main__":
    main()
