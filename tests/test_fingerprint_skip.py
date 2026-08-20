"""Tests for unchanged-result fingerprint skip (Option B)."""
from scripts.checks import CheckResult
from scripts.quality_gate import (
    compute_checks_version,
    compute_result_fingerprint,
    extract_fingerprint,
    labels_match_verdict,
    should_skip_jira_write,
    build_gate_comment,
)


LABEL_CONFIG = {
    "gate_pass": "rp-qg1-pass",
    "gate_fail": "rp-qg1-fail",
}


def _results(fail_docs=True):
    return [
        CheckResult("has_rice", True, "All 4 fields present"),
        CheckResult("has_priority", True, "All 1 fields present"),
        CheckResult("has_sign_off", True, "All required labels present"),
        CheckResult("has_components", True, "All 1 fields present"),
        CheckResult("has_release_type", True, "All 1 fields present"),
        CheckResult(
            "has_docs_required",
            not fail_docs,
            "Missing fields: customfield_10665" if fail_docs else "ok",
        ),
        CheckResult("has_target_version", True, "All 1 fields present"),
    ]


class TestFingerprint:
    def test_stable_for_same_results(self):
        a = compute_result_fingerprint(_results(), "fail", "v1")
        b = compute_result_fingerprint(_results(), "fail", "v1")
        assert a == b
        assert len(a) == 16

    def test_changes_when_check_flips(self):
        """Same verdict; only a per-check outcome changes."""
        old_fp = compute_result_fingerprint(
            _results(fail_docs=True), "fail", "v1")
        new_results = _results(fail_docs=True)
        new_results[-1] = CheckResult(
            "has_target_version", False,
            "Missing fields: customfield_10855",
        )
        new_fp = compute_result_fingerprint(new_results, "fail", "v1")
        assert old_fp != new_fp

    def test_changes_when_verdict_changes(self):
        """Identical check payload; only the verdict changes."""
        results = _results(fail_docs=False)
        assert (
            compute_result_fingerprint(results, "pass", "v1")
            != compute_result_fingerprint(results, "fail", "v1")
        )

    def test_changes_when_checks_version_changes(self):
        """Criteria bumps (Phase 1/2/…) must invalidate prior fingerprints."""
        same = _results(fail_docs=False)
        old = compute_result_fingerprint(same, "pass", "phase0")
        new = compute_result_fingerprint(same, "pass", "phase1")
        assert old != new

    def test_embedded_in_comment_and_extractable(self):
        issue = {"fields": {"labels": ["strat-creator-human-sign-off"]}}
        results = _results()
        md = build_gate_comment(
            issue, results, "fail", LABEL_CONFIG, checks_version="abc12345")
        fp = compute_result_fingerprint(results, "fail", "abc12345")
        assert f"QG1-FP: {fp}" in md
        assert extract_fingerprint(md) == fp
        assert "only if the result changes or the gate labels don't match yet" in md
        assert "only if the result changes." not in md

    def test_ambiguous_fingerprint_forces_rewrite(self):
        """Multiple QG1-FP tokens must not be trusted for skip."""
        assert extract_fingerprint(
            "QG1-FP: 1111111111111111\nQG1-FP: 2222222222222222"
        ) is None
        assert extract_fingerprint("no fingerprint here") is None

    def test_fail_fingerprint_ignores_evidence_text(self):
        """Two fails with different free-text evidence share one fingerprint."""
        a = [
            CheckResult(
                "has_acceptance_criteria",
                False,
                "No acceptance/success criteria found in description",
            ),
        ]
        b = [
            CheckResult(
                "has_acceptance_criteria",
                False,
                "Failed description criterion: missing AC bullets in strategy.md",
            ),
        ]
        assert compute_result_fingerprint(a, "fail", "v1") == (
            compute_result_fingerprint(b, "fail", "v1")
        )

    def test_na_and_error_statuses_are_stable(self):
        """Fingerprint uses na/error tokens, not free-text details."""
        na_a = CheckResult(
            "has_architectural_alignment", True,
            "Not checked — no architecture notes",
            not_applicable=True,
        )
        na_b = CheckResult(
            "has_architectural_alignment", True,
            "Not checked — different wording",
            not_applicable=True,
        )
        assert compute_result_fingerprint([na_a], "pass", "v1") == (
            compute_result_fingerprint([na_b], "pass", "v1")
        )

        err_a = CheckResult(
            "has_child_epics", False, "lookup failed: timeout",
            infra_error=True,
        )
        err_b = CheckResult(
            "has_child_epics", False, "lookup failed: 502 Bad Gateway",
            infra_error=True,
        )
        assert compute_result_fingerprint([err_a], "error", "v1") == (
            compute_result_fingerprint([err_b], "error", "v1")
        )
        # Isolate per-check status from top-level verdict.
        normal_pass = CheckResult(
            "has_architectural_alignment", True,
            "Not checked — no architecture notes",
        )
        assert compute_result_fingerprint([na_a], "pass", "v1") != (
            compute_result_fingerprint([normal_pass], "pass", "v1")
        )
        normal_fail = CheckResult(
            "has_child_epics", False, "lookup failed: timeout",
        )
        assert compute_result_fingerprint([err_a], "error", "v1") != (
            compute_result_fingerprint([normal_fail], "error", "v1")
        )


    def test_error_comment_does_not_claim_fail_label(self):
        issue = {"fields": {"labels": []}}
        results = [
            CheckResult(
                "has_child_epics", False, "lookup failed", infra_error=True),
        ]
        md = build_gate_comment(issue, results, "error", LABEL_CONFIG)
        assert "— ERROR**" in md
        assert "Label applied: unchanged (infrastructure error)" in md
        assert "rp-qg1-fail" not in md


class TestChecksVersion:
    def test_stable_for_same_config(self):
        cfg = [
            {"name": "has_rice", "type": "field_present",
             "fields": ["customfield_10862"]},
            {"name": "has_pm", "type": "field_present",
             "fields": ["customfield_10469"]},
        ]
        assert compute_checks_version(cfg) == compute_checks_version(cfg)
        assert len(compute_checks_version(cfg)) == 8

    def test_changes_when_check_added(self):
        base = [{"name": "has_rice", "type": "field_present",
                 "fields": ["customfield_10862"]}]
        expanded = base + [
            {"name": "has_pm", "type": "field_present",
             "fields": ["customfield_10469"]},
        ]
        assert compute_checks_version(base) != compute_checks_version(expanded)


class TestShouldSkipJiraWrite:
    def test_skip_when_fp_and_labels_match(self):
        fp = compute_result_fingerprint(_results(), "fail")
        assert should_skip_jira_write(
            fp, fp, ["rp-qg1-fail"], "fail", LABEL_CONFIG) is True

    def test_write_when_no_existing_fp(self):
        fp = compute_result_fingerprint(_results(), "fail")
        assert should_skip_jira_write(
            None, fp, ["rp-qg1-fail"], "fail", LABEL_CONFIG) is False

    def test_write_when_fp_changed(self):
        old = compute_result_fingerprint(_results(fail_docs=True), "fail")
        new = compute_result_fingerprint(_results(fail_docs=False), "pass")
        assert should_skip_jira_write(
            old, new, ["rp-qg1-fail"], "pass", LABEL_CONFIG) is False

    def test_write_when_labels_wrong_even_if_fp_matches(self):
        fp = compute_result_fingerprint(_results(), "fail")
        assert should_skip_jira_write(
            fp, fp, [], "fail", LABEL_CONFIG) is False
        assert labels_match_verdict([], "fail", LABEL_CONFIG) is False

    def test_labels_match_helpers(self):
        assert labels_match_verdict(
            ["existing-label", "rp-qg1-pass"], "pass", LABEL_CONFIG) is True
        assert labels_match_verdict(
            ["existing-label", "rp-qg1-fail"], "fail", LABEL_CONFIG) is True
        assert labels_match_verdict(
            ["existing-label", "rp-qg1-pass", "rp-qg1-fail"],
            "pass", LABEL_CONFIG) is False
