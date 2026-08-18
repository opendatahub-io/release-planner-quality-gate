"""Optional FPDoR description criteria via Claude Code skill invocation.

Not used by ``quality_gate.py`` — the gate uses ``description_signals.py``.
Kept for manual / ad-hoc runs of the ``/fpdor-description`` skill.

Invokes the fpdor-description skill headlessly, parses structured
pass/fail/na verdicts for description-based FPDoR criteria. Read-only —
the orchestrator applies results; this module does not write to Jira.
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field


CRITERION_KEYS = (
    "requirements_clarity",
    "acceptance_criteria",
    "risks_assumptions",
    "architectural_alignment",
    "uxd_description",
    "cross_team_deps_language",
)

VALID_VERDICTS = frozenset({"pass", "fail", "na"})

# Block field name → dataclass / dict key
_FIELD_TO_KEY = {
    "REQUIREMENTS_CLARITY": "requirements_clarity",
    "ACCEPTANCE_CRITERIA": "acceptance_criteria",
    "RISKS_ASSUMPTIONS": "risks_assumptions",
    "ARCHITECTURAL_ALIGNMENT": "architectural_alignment",
    "UXD_DESCRIPTION": "uxd_description",
    "CROSS_TEAM_DEPS_LANGUAGE": "cross_team_deps_language",
}


class DescriptionInvocationError(RuntimeError):
    """Raised when the Claude CLI cannot produce description verdicts."""


@dataclass
class CriterionVerdict:
    """One description criterion result."""
    key: str
    verdict: str  # pass | fail | na
    evidence: str = ""


@dataclass
class DescriptionEvaluation:
    """Parsed FPDoR description evaluation from the skill output."""
    ticket: str
    criteria: dict[str, CriterionVerdict] = field(default_factory=dict)

    def verdict_for(self, key: str) -> str | None:
        item = self.criteria.get(key)
        return item.verdict if item else None


@dataclass
class DescriptionResult:
    """Aggregate result of description-skill invocations."""
    succeeded: list[DescriptionEvaluation] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    timed_out: list[str] = field(default_factory=list)


_BLOCK_RE = re.compile(
    r"FPDOR_DESCRIPTION_START\s*\n(.*?)\nFPDOR_DESCRIPTION_END",
    re.DOTALL,
)


def parse_description_output(output: str) -> DescriptionEvaluation | None:
    """Parse the structured description evaluation from skill output."""
    match = _BLOCK_RE.search(output or "")
    if not match:
        return None

    body = match.group(1)
    ticket = None
    verdicts: dict[str, str] = {}
    evidence: dict[str, str] = {}

    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        name, value = line.split(":", 1)
        name = name.strip().upper()
        value = value.strip()
        if name == "TICKET":
            ticket = value
            continue
        if name.endswith("_EVIDENCE"):
            base = name[: -len("_EVIDENCE")]
            key = _FIELD_TO_KEY.get(base)
            if key:
                evidence[key] = "" if value == "-" else value[:200]
            continue
        key = _FIELD_TO_KEY.get(name)
        if key:
            verdict = value.lower()
            if verdict not in VALID_VERDICTS:
                return None
            verdicts[key] = verdict

    if not ticket:
        return None
    if set(verdicts.keys()) != set(CRITERION_KEYS):
        return None

    criteria = {
        key: CriterionVerdict(
            key=key,
            verdict=verdicts[key],
            evidence=evidence.get(key, ""),
        )
        for key in CRITERION_KEYS
    }
    return DescriptionEvaluation(ticket=ticket, criteria=criteria)


def is_error(output: str) -> str | None:
    """Check if the output indicates an error."""
    match = re.search(r"FPDOR_DESCRIPTION_ERROR:\s*(.+)", output or "")
    return match.group(1).strip() if match else None


def _build_invocation_error(issue_key: str, reason: str,
                            stderr: str = "", stdout: str = "") -> str:
    details = [
        f"Claude CLI failed while evaluating FPDoR description for "
        f"{issue_key}: {reason}."
    ]
    stderr = stderr.strip()
    stdout = stdout.strip()
    if stderr:
        details.append(f"stderr: {stderr}")
    elif stdout:
        details.append(f"stdout: {stdout}")
    return " ".join(details)


def invoke_description_skill(issue_key: str, timeout: int = 300) -> str:
    """Invoke the fpdor-description Claude skill headlessly."""
    repo_root = os.path.join(os.path.dirname(__file__), "..")
    try:
        proc = subprocess.run(
            [
                "claude", "-p", f"/fpdor-description {issue_key}",
                "--dangerously-skip-permissions",
                "--model", "claude-opus-4-6",
                "--verbose",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.path.abspath(repo_root),
        )
    except FileNotFoundError as exc:
        raise DescriptionInvocationError(
            _build_invocation_error(
                issue_key,
                "the `claude` executable is not installed or not on PATH",
            )
        ) from exc

    if proc.returncode != 0:
        raise DescriptionInvocationError(
            _build_invocation_error(
                issue_key,
                f"process exited with code {proc.returncode}",
                stderr=proc.stderr,
                stdout=proc.stdout,
            )
        )

    if not proc.stdout.strip():
        raise DescriptionInvocationError(
            _build_invocation_error(
                issue_key,
                "process returned no structured output",
                stderr=proc.stderr,
            )
        )

    return proc.stdout


def evaluate_descriptions(issue_keys: list[str],
                          timeout: int = 300) -> DescriptionResult:
    """Evaluate description criteria for a list of issues via Claude skill."""
    result = DescriptionResult()

    for key in issue_keys:
        print(f"  Evaluating FPDoR description for {key}...")
        try:
            output = invoke_description_skill(key, timeout=timeout)

            error = is_error(output)
            if error:
                result.failed.append(key)
                print(f"    {key}: error — {error}")
                continue

            evaluation = parse_description_output(output)
            if evaluation:
                result.succeeded.append(evaluation)
                summary = " ".join(
                    f"{k}={evaluation.verdict_for(k)}"
                    for k in CRITERION_KEYS
                )
                print(f"    {key}: {summary}")
            else:
                result.failed.append(key)
                print(f"    {key}: failed to parse description output")

        except DescriptionInvocationError as exc:
            result.failed.append(key)
            print(f"    {key}: {exc}")
        except subprocess.TimeoutExpired:
            result.timed_out.append(key)
            print(f"    {key}: timed out after {timeout}s")

    return result
