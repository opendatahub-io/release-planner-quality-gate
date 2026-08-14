"""Tests for FPDoR description invoker — output parsing and helpers."""
import subprocess

import pytest

import scripts.description_invoker as description_invoker
from scripts.description_invoker import (
    CRITERION_KEYS,
    DescriptionInvocationError,
    evaluate_descriptions,
    invoke_description_skill,
    is_error,
    parse_description_output,
)


def _valid_block(ticket="RHAISTRAT-1745", **overrides):
    values = {
        "REQUIREMENTS_CLARITY": "pass",
        "REQUIREMENTS_CLARITY_EVIDENCE": "Requirements section present.",
        "ACCEPTANCE_CRITERIA": "fail",
        "ACCEPTANCE_CRITERIA_EVIDENCE": "-",
        "RISKS_ASSUMPTIONS": "pass",
        "RISKS_ASSUMPTIONS_EVIDENCE": "Risks listed.",
        "ARCHITECTURAL_ALIGNMENT": "na",
        "ARCHITECTURAL_ALIGNMENT_EVIDENCE": "-",
        "UXD_DESCRIPTION": "na",
        "UXD_DESCRIPTION_EVIDENCE": "-",
        "CROSS_TEAM_DEPS_LANGUAGE": "fail",
        "CROSS_TEAM_DEPS_LANGUAGE_EVIDENCE": "-",
    }
    values.update(overrides)
    lines = ["FPDOR_DESCRIPTION_START", f"TICKET: {ticket}"]
    for key in (
        "REQUIREMENTS_CLARITY",
        "ACCEPTANCE_CRITERIA",
        "RISKS_ASSUMPTIONS",
        "ARCHITECTURAL_ALIGNMENT",
        "UXD_DESCRIPTION",
        "CROSS_TEAM_DEPS_LANGUAGE",
    ):
        lines.append(f"{key}: {values[key]}")
        lines.append(f"{key}_EVIDENCE: {values[key + '_EVIDENCE']}")
    lines.append("FPDOR_DESCRIPTION_END")
    return "\n".join(lines)


class TestParseDescriptionOutput:
    def test_valid_output(self):
        output = "Preamble...\n\n" + _valid_block() + "\n\nTrailing..."
        evaluation = parse_description_output(output)
        assert evaluation is not None
        assert evaluation.ticket == "RHAISTRAT-1745"
        assert set(evaluation.criteria.keys()) == set(CRITERION_KEYS)
        assert evaluation.verdict_for("requirements_clarity") == "pass"
        assert evaluation.verdict_for("acceptance_criteria") == "fail"
        assert evaluation.verdict_for("architectural_alignment") == "na"
        assert "Requirements section" in (
            evaluation.criteria["requirements_clarity"].evidence
        )
        assert evaluation.criteria["acceptance_criteria"].evidence == ""

    def test_aipcc_ticket(self):
        evaluation = parse_description_output(_valid_block(ticket="AIPCC-99"))
        assert evaluation.ticket == "AIPCC-99"

    def test_no_block(self):
        assert parse_description_output("no structured output") is None

    def test_incomplete_criteria(self):
        output = """
FPDOR_DESCRIPTION_START
TICKET: RHAISTRAT-1
REQUIREMENTS_CLARITY: pass
REQUIREMENTS_CLARITY_EVIDENCE: x
FPDOR_DESCRIPTION_END
"""
        assert parse_description_output(output) is None

    def test_invalid_verdict(self):
        output = _valid_block(REQUIREMENTS_CLARITY="maybe")
        assert parse_description_output(output) is None

    def test_evidence_truncated_to_200(self):
        long_ev = "x" * 250
        evaluation = parse_description_output(
            _valid_block(REQUIREMENTS_CLARITY_EVIDENCE=long_ev)
        )
        assert len(evaluation.criteria["requirements_clarity"].evidence) == 200


class TestIsError:
    def test_error_line(self):
        assert "not found" in is_error(
            "FPDOR_DESCRIPTION_ERROR: RHAISTRAT-1 — issue not found"
        )

    def test_no_error(self):
        assert is_error(_valid_block()) is None


class TestInvokeDescriptionSkill:
    def test_missing_claude_binary_raises(self, monkeypatch):
        def boom(*args, **kwargs):
            raise FileNotFoundError("claude")

        monkeypatch.setattr(subprocess, "run", boom)
        with pytest.raises(DescriptionInvocationError) as exc:
            invoke_description_skill("RHAISTRAT-1")
        assert "not installed" in str(exc.value)

    def test_nonzero_exit_surfaces_stderr(self, monkeypatch):
        class FakeProc:
            returncode = 1
            stdout = ""
            stderr = "auth failed"

        monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeProc())
        with pytest.raises(DescriptionInvocationError) as exc:
            invoke_description_skill("RHAISTRAT-1")
        assert "auth failed" in str(exc.value)


class TestEvaluateDescriptions:
    def test_parses_success(self, monkeypatch):
        monkeypatch.setattr(
            description_invoker,
            "invoke_description_skill",
            lambda key, timeout=300: _valid_block(ticket=key),
        )
        result = evaluate_descriptions(["RHAISTRAT-10"])
        assert len(result.succeeded) == 1
        assert result.succeeded[0].ticket == "RHAISTRAT-10"
        assert result.failed == []

    def test_error_block_counts_as_failed(self, monkeypatch):
        monkeypatch.setattr(
            description_invoker,
            "invoke_description_skill",
            lambda key, timeout=300: (
                f"FPDOR_DESCRIPTION_ERROR: {key} — boom"
            ),
        )
        result = evaluate_descriptions(["RHAISTRAT-10"])
        assert result.succeeded == []
        assert result.failed == ["RHAISTRAT-10"]

    def test_timeout(self, monkeypatch):
        def boom(key, timeout=300):
            raise subprocess.TimeoutExpired(cmd="claude", timeout=timeout)

        monkeypatch.setattr(
            description_invoker, "invoke_description_skill", boom
        )
        result = evaluate_descriptions(["RHAISTRAT-10"], timeout=1)
        assert result.timed_out == ["RHAISTRAT-10"]
