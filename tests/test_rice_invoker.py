"""Tests for RICE invoker — output parsing and result handling."""
import subprocess

import pytest

import scripts.rice_invoker as rice_invoker
from scripts.rice_invoker import (
    parse_rice_output,
    is_already_scored,
    is_error,
    RiceRecommendation,
    RiceInvocationError,
    CONFIDENCE_OPTIONS,
)


# --- parse_rice_output ---

class TestParseRiceOutput:
    def test_valid_output(self):
        output = """
Some preamble text from Claude...

RICE_RECOMMENDATION_START
TICKET: RHAISTRAT-1745
REACH: 8
IMPACT: 5
CONFIDENCE: 75
EFFORT: 3
EXPECTED_RICE: 10.0
JUSTIFICATION:
R=8: Affects 30-70% of users — similar reach to RHAISTRAT-1500 (Model Serving, R=8).

I=5: Noticeable productivity gain but not a game-changer.

C=75%: Approved RFE with customer evidence but some technical assumptions remain.

E=3: Cross-team effort (dashboard + backend), may need story mapping.

Re-scoring trigger: If the UX spike confirms the simplified approach, effort drops to 2.
RICE_RECOMMENDATION_END

Some trailing text...
"""
        rec = parse_rice_output(output)
        assert rec is not None
        assert rec.ticket == "RHAISTRAT-1745"
        assert rec.reach == 8
        assert rec.impact == 5
        assert rec.confidence == 75
        assert rec.effort == 3
        assert rec.expected_rice == 10.0
        assert "R=8" in rec.justification
        assert "Re-scoring trigger" in rec.justification

    def test_minimal_justification(self):
        output = """
RICE_RECOMMENDATION_START
TICKET: RHAISTRAT-100
REACH: 1
IMPACT: 3
CONFIDENCE: 50
EFFORT: 1
EXPECTED_RICE: 1.5
JUSTIFICATION:
Niche feature with limited evidence.
RICE_RECOMMENDATION_END
"""
        rec = parse_rice_output(output)
        assert rec is not None
        assert rec.reach == 1
        assert rec.confidence == 50
        assert rec.justification == "Niche feature with limited evidence."

    def test_no_recommendation_block(self):
        output = "Claude said some things but no structured output."
        rec = parse_rice_output(output)
        assert rec is None

    def test_incomplete_block(self):
        output = """
RICE_RECOMMENDATION_START
TICKET: RHAISTRAT-100
REACH: 8
"""
        rec = parse_rice_output(output)
        assert rec is None

    def test_high_rice_score(self):
        output = """
RICE_RECOMMENDATION_START
TICKET: RHAISTRAT-999
REACH: 13
IMPACT: 13
CONFIDENCE: 100
EFFORT: 1
EXPECTED_RICE: 169.0
JUSTIFICATION:
Legal requirement affecting all users. Must ship.
RICE_RECOMMENDATION_END
"""
        rec = parse_rice_output(output)
        assert rec.expected_rice == 169.0
        assert rec.reach == 13
        assert rec.effort == 1

    def test_decimal_rice_score(self):
        output = """
RICE_RECOMMENDATION_START
TICKET: RHAISTRAT-500
REACH: 5
IMPACT: 3
CONFIDENCE: 75
EFFORT: 8
EXPECTED_RICE: 1.41
JUSTIFICATION:
Low priority, high effort.
RICE_RECOMMENDATION_END
"""
        rec = parse_rice_output(output)
        assert rec.expected_rice == pytest.approx(1.41)


# --- is_already_scored ---

class TestIsAlreadyScored:
    def test_already_scored(self):
        output = "RICE_ALREADY_SCORED: RHAISTRAT-1745 R=8 I=5 C=75% E=3 RICE=10.0"
        key = is_already_scored(output)
        assert key == "RHAISTRAT-1745"

    def test_not_already_scored(self):
        output = "Some normal output"
        assert is_already_scored(output) is None


# --- is_error ---

class TestIsError:
    def test_error_ticket_not_found(self):
        output = "RICE_ERROR: Ticket RHAISTRAT-9999 not found"
        error = is_error(output)
        assert error == "Ticket RHAISTRAT-9999 not found"

    def test_no_error(self):
        output = "Some normal output"
        assert is_error(output) is None


# --- CONFIDENCE_OPTIONS ---

class TestConfidenceOptions:
    def test_all_values_mapped(self):
        assert CONFIDENCE_OPTIONS[100] == "16144"
        assert CONFIDENCE_OPTIONS[75] == "16145"
        assert CONFIDENCE_OPTIONS[50] == "16146"

    def test_no_other_values(self):
        assert len(CONFIDENCE_OPTIONS) == 3


# --- RiceRecommendation ---

class TestRiceRecommendation:
    def test_dataclass_fields(self):
        rec = RiceRecommendation(
            ticket="RHAISTRAT-100",
            reach=8, impact=5, confidence=75, effort=3,
            expected_rice=10.0,
            justification="test",
        )
        assert rec.ticket == "RHAISTRAT-100"
        assert rec.reach == 8
        assert rec.expected_rice == 10.0


# --- invoke_rice_skill ---

class TestInvokeRiceSkill:
    def test_missing_claude_binary_raises_actionable_error(self, monkeypatch):
        def fake_run(*args, **kwargs):
            raise FileNotFoundError("claude not found")

        monkeypatch.setattr(rice_invoker.subprocess, "run", fake_run)

        with pytest.raises(RiceInvocationError) as exc_info:
            rice_invoker.invoke_rice_skill("RHAISTRAT-1938")

        assert "not installed or not on PATH" in str(exc_info.value)
        assert "RHAISTRAT-1938" in str(exc_info.value)

    def test_nonzero_exit_surfaces_stderr(self, monkeypatch):
        def fake_run(*args, **kwargs):
            return subprocess.CompletedProcess(
                args[0],
                130,
                stdout="",
                stderr="authentication required",
            )

        monkeypatch.setattr(rice_invoker.subprocess, "run", fake_run)

        with pytest.raises(RiceInvocationError) as exc_info:
            rice_invoker.invoke_rice_skill("RHAISTRAT-1938")

        assert "process exited with code 130" in str(exc_info.value)
        assert "authentication required" in str(exc_info.value)
