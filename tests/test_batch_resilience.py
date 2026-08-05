"""Tests for batch write resilience (edit-denied fallback + per-issue isolation)."""
import urllib.error

import pytest

from scripts.checks import CheckResult
from scripts import quality_gate
from scripts.quality_gate import (
    post_gate_comment,
    write_issue_gate_result,
    _find_gate_comment,
    GATE_COMMENT_MARKER,
)


LABEL_CONFIG = {
    "gate_pass": "rp-qg1-pass",
    "gate_fail": "rp-qg1-fail",
}


def _http_error(code, body="permission denied"):
    return urllib.error.HTTPError(
        url="https://example.test/rest/api/3/issue/X/comment/1",
        code=code,
        msg="error",
        hdrs=None,
        fp=None,
    )


class TestPostGateCommentFallback:
    def test_update_success_no_add(self, monkeypatch):
        calls = {"update": 0, "add": 0}

        def fake_update(*_a, **_k):
            calls["update"] += 1

        def fake_add(*_a, **_k):
            calls["add"] += 1

        monkeypatch.setattr(
            "scripts.quality_gate._update_comment", fake_update)
        monkeypatch.setattr("scripts.quality_gate.add_comment", fake_add)
        monkeypatch.setattr(
            "scripts.quality_gate.markdown_to_adf", lambda md: {"md": md})

        post_gate_comment("s", "u", "t", "RHAISTRAT-1", "body", existing_id="99")
        assert calls == {"update": 1, "add": 0}

    @pytest.mark.parametrize("code", [400, 403])
    def test_edit_denied_falls_back_to_add(self, monkeypatch, code):
        calls = {"update": 0, "add": 0}

        def fake_update(*_a, **_k):
            calls["update"] += 1
            raise _http_error(code)

        def fake_add(*_a, **_k):
            calls["add"] += 1

        monkeypatch.setattr(
            "scripts.quality_gate._update_comment", fake_update)
        monkeypatch.setattr("scripts.quality_gate.add_comment", fake_add)
        monkeypatch.setattr(
            "scripts.quality_gate.markdown_to_adf", lambda md: {"md": md})

        post_gate_comment("s", "u", "t", "RHAISTRAT-1", "body", existing_id="99")
        assert calls == {"update": 1, "add": 1}

    def test_other_http_errors_propagate(self, monkeypatch):
        monkeypatch.setattr(
            "scripts.quality_gate._update_comment",
            lambda *_a, **_k: (_ for _ in ()).throw(_http_error(500)),
        )
        monkeypatch.setattr(
            "scripts.quality_gate.markdown_to_adf", lambda md: {"md": md})

        with pytest.raises(urllib.error.HTTPError) as exc:
            post_gate_comment(
                "s", "u", "t", "RHAISTRAT-1", "body", existing_id="99")
        assert exc.value.code == 500


class TestWriteIssueGateResult:
    def test_skipped_when_unchanged(self, monkeypatch):
        results = [CheckResult("has_rice", False, "Missing fields: x")]
        issue = {
            "key": "RHAISTRAT-1",
            "fields": {"labels": ["rp-qg1-fail"]},
        }

        monkeypatch.setattr(
            "scripts.jira_utils.get_comments", lambda *_a, **_k: [])
        monkeypatch.setattr(
            "scripts.quality_gate.compute_verdict", lambda _r: "fail")
        monkeypatch.setattr(
            "scripts.quality_gate.compute_result_fingerprint",
            lambda *_a, **_k: "abcd1234abcd1234",
        )
        monkeypatch.setattr(
            "scripts.quality_gate._find_gate_comment",
            lambda *_a, **k: ("1", "QG1-FP: abcd1234abcd1234"),
        )
        monkeypatch.setattr(
            "scripts.quality_gate.should_skip_jira_write",
            lambda *_a, **_k: True,
        )

        assert write_issue_gate_result(
            "s", "u", "t", issue, results, LABEL_CONFIG) == "skipped"

    def test_written_applies_label_and_comment(self, monkeypatch):
        calls = []
        results = [CheckResult("has_rice", True, "ok")]
        issue = {
            "key": "RHAISTRAT-1",
            "fields": {"labels": []},
        }

        monkeypatch.setattr(
            "scripts.jira_utils.get_comments", lambda *_a, **_k: [])
        monkeypatch.setattr(
            "scripts.quality_gate.compute_verdict", lambda _r: "pass")
        monkeypatch.setattr(
            "scripts.quality_gate.compute_result_fingerprint",
            lambda *_a, **_k: "ffff0000ffff0000",
        )
        monkeypatch.setattr(
            "scripts.quality_gate._find_gate_comment",
            lambda *_a, **k: (None, None),
        )
        monkeypatch.setattr(
            "scripts.quality_gate.should_skip_jira_write",
            lambda *_a, **_k: False,
        )
        monkeypatch.setattr(
            "scripts.quality_gate.apply_verdict_label",
            lambda *a, **k: calls.append(("label", a[3])),
        )
        monkeypatch.setattr(
            "scripts.quality_gate.build_gate_comment",
            lambda *_a, **_k: "comment body",
        )
        monkeypatch.setattr(
            "scripts.quality_gate.post_gate_comment",
            lambda *a, **k: calls.append(("comment", a[3], k.get("existing_id"))),
        )

        assert write_issue_gate_result(
            "s", "u", "t", issue, results, LABEL_CONFIG) == "written"
        assert calls == [
            ("label", "RHAISTRAT-1"),
            ("comment", "RHAISTRAT-1", None),
        ]

    def test_updates_only_own_comment_id(self, monkeypatch):
        """Human-authored marker comments must not be passed as existing_id."""
        posted = {}
        results = [CheckResult("has_rice", True, "ok")]
        issue = {"key": "RHAISTRAT-1", "fields": {"labels": []}}

        monkeypatch.setattr(
            "scripts.jira_utils.get_comments", lambda *_a, **_k: [{"id": "x"}])
        monkeypatch.setattr(
            "scripts.quality_gate.compute_verdict", lambda _r: "pass")
        monkeypatch.setattr(
            "scripts.quality_gate.compute_result_fingerprint",
            lambda *_a, **_k: "cafe0000cafe0000",
        )
        monkeypatch.setattr(
            "scripts.quality_gate._find_gate_comment",
            lambda *_a, **k: (None, None),
        )
        monkeypatch.setattr(
            "scripts.quality_gate.should_skip_jira_write",
            lambda *_a, **_k: False,
        )
        monkeypatch.setattr(
            "scripts.quality_gate.apply_verdict_label", lambda *_a, **_k: None)
        monkeypatch.setattr(
            "scripts.quality_gate.build_gate_comment",
            lambda *_a, **_k: "new body",
        )
        monkeypatch.setattr(
            "scripts.quality_gate.post_gate_comment",
            lambda *a, **k: posted.update(
                {"key": a[3], "existing_id": k.get("existing_id")}),
        )

        assert write_issue_gate_result(
            "s", "u", "t", issue, results, LABEL_CONFIG) == "written"
        assert posted == {"key": "RHAISTRAT-1", "existing_id": None}

    def test_human_fingerprint_does_not_skip(self, monkeypatch):
        """Skip only when a bot-authored comment carries the matching FP."""
        calls = {"find": 0, "get_comments": 0}
        results = [CheckResult("has_rice", False, "Missing fields: x")]
        issue = {
            "key": "RHAISTRAT-499",
            "fields": {"labels": ["rp-qg1-fail"]},
        }
        human_comments = [{"id": "17758731"}]

        def fake_get_comments(*_a, **_k):
            calls["get_comments"] += 1
            return human_comments

        def fake_find(*_a, **k):
            calls["find"] += 1
            assert k.get("comments") is human_comments
            assert k.get("owned_by_self") is True
            return None, None  # no bot-authored gate comment

        monkeypatch.setattr(
            "scripts.jira_utils.get_comments", fake_get_comments)
        monkeypatch.setattr(
            "scripts.quality_gate.compute_verdict", lambda _r: "fail")
        monkeypatch.setattr(
            "scripts.quality_gate.compute_result_fingerprint",
            lambda *_a, **_k: "abcd1234abcd1234",
        )
        monkeypatch.setattr(
            "scripts.quality_gate._find_gate_comment", fake_find)
        monkeypatch.setattr(
            "scripts.quality_gate.apply_verdict_label", lambda *_a, **_k: None)
        monkeypatch.setattr(
            "scripts.quality_gate.build_gate_comment",
            lambda *_a, **_k: "body",
        )
        monkeypatch.setattr(
            "scripts.quality_gate.post_gate_comment", lambda *_a, **_k: None)

        assert write_issue_gate_result(
            "s", "u", "t", issue, results, LABEL_CONFIG) == "written"
        assert calls == {"find": 1, "get_comments": 1}


class TestFindGateCommentOwnership:
    def test_skips_other_authors_when_owned_by_self(self, monkeypatch):
        monkeypatch.setattr(quality_gate, "_current_account_id", "bot-account")

        comments = [
            {
                "id": "111",
                "author": {"accountId": "human-account",
                           "emailAddress": "human@redhat.com"},
                "body": GATE_COMMENT_MARKER + "\nold",
            },
            {
                "id": "222",
                "author": {"accountId": "bot-account",
                           "emailAddress": "bot@redhat.com"},
                "body": GATE_COMMENT_MARKER + "\nbot",
            },
        ]
        monkeypatch.setattr(
            "scripts.jira_utils.get_comments",
            lambda *_a, **_k: comments,
        )
        monkeypatch.setattr(
            "scripts.jira_utils.adf_to_markdown",
            lambda body: body if isinstance(body, str) else "",
        )

        own_id, own_text = _find_gate_comment(
            "s", "bot@redhat.com", "t", "RHAISTRAT-1",
            owned_by_self=True, comments=comments)
        any_id, _ = _find_gate_comment(
            "s", "bot@redhat.com", "t", "RHAISTRAT-1",
            owned_by_self=False, comments=comments)

        assert own_id == "222"
        assert "bot" in own_text
        assert any_id == "222"

    def test_no_owned_comment_when_only_human_authored(self, monkeypatch):
        monkeypatch.setattr(quality_gate, "_current_account_id", "bot-account")
        comments = [
            {
                "id": "17758731",
                "author": {"accountId": "human-account",
                           "emailAddress": "emarion@redhat.com"},
                "body": GATE_COMMENT_MARKER + "\nfail",
            },
        ]
        monkeypatch.setattr(
            "scripts.jira_utils.adf_to_markdown",
            lambda body: body if isinstance(body, str) else "",
        )

        own_id, own_text = _find_gate_comment(
            "s", "bot@redhat.com", "t", "RHAISTRAT-499",
            owned_by_self=True, comments=comments)
        assert own_id is None and own_text is None
