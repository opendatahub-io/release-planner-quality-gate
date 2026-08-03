"""Release Quality Gate 1: Feature Definition of Ready for Planning.

Main orchestrator: discovers issues, evaluates checks, manages labels.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
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
    add_comment,
    markdown_to_adf,
)
from scripts.rice_invoker import (
    generate_rice_scores,
    write_rice_to_jira,
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
    return sorted(fields)


def discover_issues(config, server, user, token, issue_key=None):
    """Discover issues to evaluate — single key or JQL batch."""
    fields = collect_required_fields(config)
    if issue_key:
        issue = get_issue(server, user, token, issue_key, fields=fields)
        return [issue] if issue else []
    jql = build_jql(config)
    return search_issues(server, user, token, jql, fields=fields)


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


CHECK_LABELS = {
    "has_rice": "RICE Score",
    "has_priority": "Priority",
    "has_sign_off": "Human Sign-off",
    "has_components": "Components",
    "has_release_type": "Release Type",
    "has_docs_required": "Product Docs Required",
    "has_target_version": "Target Version",
}

FIELD_FRIENDLY_NAMES = {
    "customfield_10862": "Reach",
    "customfield_10836": "Impact",
    "customfield_10838": "Confidence",
    "customfield_10637": "Effort",
    "customfield_10851": "Release Type",
    "customfield_10665": "Product Documentation Required",
    "customfield_10855": "Target Version",
    "priority": "Priority",
    "components": "Components",
}


def _extract_field_detail(issue, check_name):
    """Extract a human-readable value for a check from the issue fields."""
    f = issue.get("fields", {})
    if check_name == "has_rice":
        r = f.get("customfield_10862", "?")
        i = f.get("customfield_10836", "?")
        c_obj = f.get("customfield_10838")
        c = c_obj.get("value", "?") if isinstance(c_obj, dict) else "?"
        e = f.get("customfield_10637", "?")
        return f"R={r}, I={i}, C={c}, E={e}"
    if check_name == "has_priority":
        p = f.get("priority")
        return p.get("name", "?") if isinstance(p, dict) else str(p or "?")
    if check_name == "has_sign_off":
        return "strat-creator-human-sign-off label present"
    if check_name == "has_components":
        comps = f.get("components", [])
        return ", ".join(c.get("name", "?") for c in comps) if comps else "?"
    if check_name == "has_release_type":
        rt = f.get("customfield_10851")
        return rt.get("value", "?") if isinstance(rt, dict) else str(rt or "?")
    if check_name == "has_docs_required":
        dr = f.get("customfield_10665")
        return dr.get("value", "?") if isinstance(dr, dict) else str(dr or "?")
    if check_name == "has_target_version":
        tv = f.get("customfield_10855", [])
        if isinstance(tv, list):
            return ", ".join(v.get("name", "?") for v in tv) if tv else "?"
        if isinstance(tv, dict):
            return tv.get("name", "?")
        return str(tv or "?")
    return "?"


def _friendly_fail_details(details):
    """Replace custom field IDs with human-readable names in failure details."""
    result = details
    for field_id, name in FIELD_FRIENDLY_NAMES.items():
        result = result.replace(field_id, name)
    return result


def build_gate_comment(issue, check_results, verdict, label_config):
    """Build a deterministic gate result comment in markdown."""
    status = "PASS" if verdict == "pass" else "FAIL"
    label = label_config["gate_pass"] if verdict == "pass" else label_config["gate_fail"]

    lines = [
        f"**Release Quality Gate 1: Feature Definition of Ready for Planning — {status}**",
        "",
    ]

    if verdict == "pass":
        lines.append("All hard checks passed for this feature.")
    else:
        failed = [r for r in check_results if not r.passed]
        lines.append(f"{len(failed)} check(s) failed.")
    lines.append("")

    issue_labels = issue.get("fields", {}).get("labels", [])
    has_auto_rice = "rp-qg1-auto-rice" in issue_labels

    lines.append("| Check | Status | Details |")
    lines.append("|-------|--------|---------|")
    for r in check_results:
        check_label = CHECK_LABELS.get(r.name, r.name)
        if r.name == "has_rice" and has_auto_rice:
            check_label = "RICE Score (Auto-generated)"
        status_icon = "PASS" if r.passed else "FAIL"
        if r.passed:
            detail = _extract_field_detail(issue, r.name)
        else:
            detail = _friendly_fail_details(r.details)
        lines.append(f"| {check_label} | {status_icon} | {detail} |")

    lines.append("")
    lines.append(f"Label applied: {label}")
    lines.append(f"QG1-FP: {compute_result_fingerprint(check_results, verdict)}")

    if verdict == "fail":
        lines.append("")
        lines.append(
            "To resolve: fix the failing checks above in Jira. "
            "The next pipeline run will re-evaluate automatically and "
            "update this comment and labels only if the result changes or "
            "the gate labels don't match yet."
        )

    return "\n".join(lines)


GATE_COMMENT_MARKER = "Release Quality Gate 1: Feature Definition of Ready for Planning"
FINGERPRINT_RE = re.compile(r"QG1-FP:\s*([a-f0-9]{16,64})", re.IGNORECASE)


def compute_result_fingerprint(check_results, verdict):
    """Stable hash of verdict + per-check outcomes for change detection."""
    data = {
        "verdict": verdict,
        "checks": [
            {
                "name": r.name,
                "status": "pass" if r.passed else "fail",
                "detail": "ok" if r.passed else _friendly_fail_details(r.details),
            }
            for r in check_results
        ],
    }
    payload = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def extract_fingerprint(comment_text):
    """Pull QG1-FP hash from a gate comment body, if present."""
    match = FINGERPRINT_RE.search(comment_text or "")
    return match.group(1).lower() if match else None


def labels_match_verdict(current_labels, verdict, label_config):
    """True when pass/fail labels already match the verdict (no swap needed)."""
    pass_label = label_config["gate_pass"]
    fail_label = label_config["gate_fail"]
    labels = current_labels or []
    if verdict == "pass":
        return pass_label in labels and fail_label not in labels
    return fail_label in labels and pass_label not in labels


def _find_gate_comment(server, user, token, issue_key):
    """Find an existing gate comment.

    Returns (comment_id, markdown_text) or (None, None).
    """
    from scripts.jira_utils import get_comments, adf_to_markdown
    comments = get_comments(server, user, token, issue_key)
    for comment in comments:
        body = comment.get("body", {})
        text = adf_to_markdown(body) if isinstance(body, dict) else str(body)
        if GATE_COMMENT_MARKER in text:
            return comment.get("id"), text
    return None, None


def _update_comment(server, user, token, issue_key, comment_id, body_adf):
    """PUT to update an existing comment."""
    from scripts.jira_utils import api_call_with_retry
    path = f"/issue/{issue_key}/comment/{comment_id}"
    return api_call_with_retry(server, path, user, token,
                               body={"body": body_adf}, method="PUT")


def post_gate_comment(server, user, token, issue_key, comment_md,
                      existing_id=None):
    """Post or update the gate result comment on Jira.

    If updating an existing comment fails with 400/403 (e.g. bot cannot edit
    a comment it no longer owns), fall back to posting a new comment so the
    batch can continue.
    """
    comment_adf = markdown_to_adf(comment_md)
    if existing_id is None:
        existing_id, _ = _find_gate_comment(server, user, token, issue_key)
    if existing_id:
        try:
            _update_comment(server, user, token, issue_key, existing_id,
                            comment_adf)
        except urllib.error.HTTPError as e:
            if e.code not in (400, 403):
                raise
            print(
                f"  {issue_key}: cannot edit comment {existing_id} "
                f"(HTTP {e.code}); posting a new comment instead",
                file=sys.stderr,
            )
            add_comment(server, user, token, issue_key, comment_adf)
    else:
        add_comment(server, user, token, issue_key, comment_adf)


def write_issue_gate_result(server, user, token, issue, results, label_config):
    """Apply labels + gate comment for one issue.

    Returns "skipped" when fingerprint/labels are unchanged, else "written".
    """
    key = issue["key"]
    verdict = compute_verdict(results)
    current_labels = issue.get("fields", {}).get("labels", [])
    new_fp = compute_result_fingerprint(results, verdict)
    existing_id, existing_text = _find_gate_comment(
        server, user, token, key)
    existing_fp = extract_fingerprint(existing_text)
    if should_skip_jira_write(
            existing_fp, new_fp, current_labels, verdict, label_config):
        return "skipped"
    apply_verdict_label(
        server, user, token, key, current_labels, verdict, label_config)
    comment_md = build_gate_comment(
        issue, results, verdict, label_config)
    post_gate_comment(
        server, user, token, key, comment_md, existing_id=existing_id)
    return "written"


def should_skip_jira_write(existing_fingerprint, new_fingerprint,
                           current_labels, verdict, label_config):
    """Skip comment/label writes when result fingerprint and labels are unchanged."""
    if not existing_fingerprint:
        return False
    if existing_fingerprint.lower() != new_fingerprint.lower():
        return False
    return labels_match_verdict(current_labels, verdict, label_config)


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
    fields = collect_required_fields(config)
    results_by_issue = {}

    for issue in issues:
        key = issue["key"]
        results = evaluate_issue(issue, checks)
        results_by_issue[key] = results

    # Auto-fix: generate RICE for issues missing it
    needs_rice = [
        key for key, results in results_by_issue.items()
        if any(r.name == "has_rice" and not r.passed and r.auto_fixable
               for r in results)
    ]

    rice_generated = {}
    if needs_rice:
        timeout = config.get("rice_scorer", {}).get("timeout_seconds", 300)
        print(f"\nGenerating RICE for {len(needs_rice)} issue(s)...")
        rice_result = generate_rice_scores(needs_rice, timeout=timeout)

        for rec in rice_result.succeeded:
            rice_generated[rec.ticket] = rec
            if not args.dry_run:
                print(f"  Writing RICE to Jira for {rec.ticket}...")
                write_rice_to_jira(rec, server, user, token)

        # Re-fetch and re-evaluate issues that got RICE written
        if not args.dry_run and rice_result.succeeded:
            print(f"\nRe-evaluating {len(rice_result.succeeded)} RICE'd issues...")
            for rec in rice_result.succeeded:
                issue = get_issue(server, user, token, rec.ticket,
                                 fields=fields)
                results_by_issue[rec.ticket] = evaluate_issue(issue, checks)
                # Update the issue in the list for label management
                for i, orig in enumerate(issues):
                    if orig["key"] == rec.ticket:
                        issues[i] = issue
                        break

    print_summary(results_by_issue)

    # Emit artifacts before Jira writes so CI still gets run-data.json if a
    # later comment/label write crashes the process.
    run_data = build_run_data(
        results_by_issue, config, args.dry_run, mode, args.issue)
    artifact_path = write_artifacts(run_data)
    print(f"Artifacts written to {artifact_path}")

    # Apply verdict labels and post gate comment (full run only).
    # Skip Jira writes when the result fingerprint is unchanged and labels
    # already match — avoids daily comment churn on sticky fails.
    # Isolate per-issue failures so one HTTP error cannot abort the batch.
    if not args.dry_run:
        label_config = config["labels"]
        for issue in issues:
            key = issue["key"]
            results = results_by_issue[key]
            verdict = compute_verdict(results)
            try:
                outcome = write_issue_gate_result(
                    server, user, token, issue, results, label_config)
                if outcome == "skipped":
                    print(f"  {key}: {verdict.upper()}"
                          f" (unchanged, skip write)")
                else:
                    print(f"  {key}: {verdict.upper()}"
                          f" → label + comment applied")
            except Exception as exc:
                print(f"  {key}: Jira write failed: {exc}", file=sys.stderr)
    else:
        for key, results in results_by_issue.items():
            verdict = compute_verdict(results)
            rice_note = ""
            if key in rice_generated:
                rec = rice_generated[key]
                rice_note = (f" | RICE generated: R={rec.reach} I={rec.impact}"
                             f" C={rec.confidence}% E={rec.effort}"
                             f" → {rec.expected_rice}")
            print(f"  {key}: {verdict.upper()}"
                  f" (dry-run, no Jira writes){rice_note}")


if __name__ == "__main__":
    main()
