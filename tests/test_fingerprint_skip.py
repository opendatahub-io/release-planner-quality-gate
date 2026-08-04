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
        fail_fp = compute_result_fingerprint(
            _results(fail_docs=True), "fail", "v1")
        pass_fp = compute_result_fingerprint(
            _results(fail_docs=False), "pass", "v1")
        assert fail_fp != pass_fp

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
            ["rp-qg1-pass"], "pass", LABEL_CONFIG) is True
        assert labels_match_verdict(
            ["rp-qg1-fail"], "fail", LABEL_CONFIG) is True
        assert labels_match_verdict(
            ["rp-qg1-pass", "rp-qg1-fail"], "pass", LABEL_CONFIG) is False
