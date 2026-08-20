"""Tests for label management — apply_verdict_label transitions."""
import pytest

from scripts.quality_gate import apply_verdict_label


LABEL_CONFIG = {
    "gate_pass": "rp-qg1-pass",
    "gate_fail": "rp-qg1-fail",
}


class FakeJira:
    """Track label add/remove calls for testing."""

    def __init__(self):
        self.added = []
        self.removed = []

    def add_labels(self, server, user, token, key, labels):
        self.added.extend(labels)

    def remove_labels(self, server, user, token, key, labels):
        self.removed.extend(labels)


@pytest.fixture
def fake_jira(monkeypatch):
    fake = FakeJira()
    monkeypatch.setattr(
        "scripts.quality_gate.add_labels", fake.add_labels)
    monkeypatch.setattr(
        "scripts.quality_gate.remove_labels", fake.remove_labels)
    return fake


class TestApplyVerdictLabel:
    def test_no_labels_to_pass(self, fake_jira):
        apply_verdict_label(
            "s", "u", "t", "RHAISTRAT-100",
            current_labels=[], verdict="pass",
            label_config=LABEL_CONFIG)
        assert "rp-qg1-pass" in fake_jira.added
        assert fake_jira.removed == []

    def test_no_labels_to_fail(self, fake_jira):
        apply_verdict_label(
            "s", "u", "t", "RHAISTRAT-100",
            current_labels=[], verdict="fail",
            label_config=LABEL_CONFIG)
        assert "rp-qg1-fail" in fake_jira.added
        assert fake_jira.removed == []

    def test_error_verdict_leaves_labels_unchanged(self, fake_jira):
        apply_verdict_label(
            "s", "u", "t", "RHAISTRAT-100",
            current_labels=["rp-qg1-pass"], verdict="error",
            label_config=LABEL_CONFIG)
        assert fake_jira.added == []
        assert fake_jira.removed == []

    def test_fail_to_pass_swaps(self, fake_jira):
        apply_verdict_label(
            "s", "u", "t", "RHAISTRAT-100",
            current_labels=["rp-qg1-fail"], verdict="pass",
            label_config=LABEL_CONFIG)
        assert "rp-qg1-pass" in fake_jira.added
        assert "rp-qg1-fail" in fake_jira.removed

    def test_pass_to_fail_swaps(self, fake_jira):
        """Defensive: shouldn't happen but handle it."""
        apply_verdict_label(
            "s", "u", "t", "RHAISTRAT-100",
            current_labels=["rp-qg1-pass"], verdict="fail",
            label_config=LABEL_CONFIG)
        assert "rp-qg1-fail" in fake_jira.added
        assert "rp-qg1-pass" in fake_jira.removed

    def test_already_pass_noop(self, fake_jira):
        apply_verdict_label(
            "s", "u", "t", "RHAISTRAT-100",
            current_labels=["rp-qg1-pass"], verdict="pass",
            label_config=LABEL_CONFIG)
        assert fake_jira.added == []
        assert fake_jira.removed == []

    def test_already_fail_noop(self, fake_jira):
        apply_verdict_label(
            "s", "u", "t", "RHAISTRAT-100",
            current_labels=["rp-qg1-fail"], verdict="fail",
            label_config=LABEL_CONFIG)
        assert fake_jira.added == []
        assert fake_jira.removed == []

    def test_both_labels_present_pass_verdict(self, fake_jira):
        """Edge case: both labels exist. Remove the wrong one."""
        apply_verdict_label(
            "s", "u", "t", "RHAISTRAT-100",
            current_labels=["rp-qg1-pass", "rp-qg1-fail"], verdict="pass",
            label_config=LABEL_CONFIG)
        assert fake_jira.added == []
        assert "rp-qg1-fail" in fake_jira.removed

    def test_labels_among_others(self, fake_jira):
        """Other labels on the issue are not affected."""
        apply_verdict_label(
            "s", "u", "t", "RHAISTRAT-100",
            current_labels=["strat-creator-human-sign-off", "rp-qg1-fail"],
            verdict="pass",
            label_config=LABEL_CONFIG)
        assert "rp-qg1-pass" in fake_jira.added
        assert "rp-qg1-fail" in fake_jira.removed
        assert "strat-creator-human-sign-off" not in fake_jira.removed
