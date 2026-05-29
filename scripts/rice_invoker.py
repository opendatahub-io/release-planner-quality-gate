"""RICE score generation via Claude Code skill invocation.

Invokes the rice-score skill headlessly, parses the structured output,
and optionally writes results to Jira.
"""
import os
import re
import subprocess
from dataclasses import dataclass, field


@dataclass
class RiceRecommendation:
    """Parsed RICE recommendation from the skill output."""
    ticket: str
    reach: int
    impact: int
    confidence: int  # 50, 75, or 100
    effort: int
    expected_rice: float
    justification: str


@dataclass
class RiceResult:
    """Aggregate result of RICE invocations."""
    succeeded: list[RiceRecommendation] = field(default_factory=list)
    already_scored: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    timed_out: list[str] = field(default_factory=list)


# Confidence percentage → Jira dropdown option ID
CONFIDENCE_OPTIONS = {
    100: "16144",
    75: "16145",
    50: "16146",
}

# RICE custom field IDs
RICE_FIELDS = {
    "reach": "customfield_10862",
    "impact": "customfield_10836",
    "confidence": "customfield_10838",
    "effort": "customfield_10637",
}


def parse_rice_output(output: str) -> RiceRecommendation | None:
    """Parse the structured RICE recommendation from skill output."""
    match = re.search(
        r"RICE_RECOMMENDATION_START\s*\n"
        r"TICKET:\s*(\S+)\s*\n"
        r"REACH:\s*(\d+)\s*\n"
        r"IMPACT:\s*(\d+)\s*\n"
        r"CONFIDENCE:\s*(\d+)\s*\n"
        r"EFFORT:\s*(\d+)\s*\n"
        r"EXPECTED_RICE:\s*([\d.]+)\s*\n"
        r"JUSTIFICATION:\s*\n(.*?)"
        r"RICE_RECOMMENDATION_END",
        output,
        re.DOTALL,
    )
    if not match:
        return None

    return RiceRecommendation(
        ticket=match.group(1),
        reach=int(match.group(2)),
        impact=int(match.group(3)),
        confidence=int(match.group(4)),
        effort=int(match.group(5)),
        expected_rice=float(match.group(6)),
        justification=match.group(7).strip(),
    )


def is_already_scored(output: str) -> str | None:
    """Check if the output indicates the ticket is already scored."""
    match = re.search(r"RICE_ALREADY_SCORED:\s*(\S+)", output)
    return match.group(1) if match else None


def is_error(output: str) -> str | None:
    """Check if the output indicates an error."""
    match = re.search(r"RICE_ERROR:\s*(.+)", output)
    return match.group(1).strip() if match else None


def invoke_rice_skill(issue_key: str, timeout: int = 300) -> str:
    """Invoke the rice-score Claude skill headlessly."""
    repo_root = os.path.join(os.path.dirname(__file__), "..")
    proc = subprocess.run(
        [
            "claude", "-p", f"/rice-score {issue_key}",
            "--dangerously-skip-permissions",
            "--model", "claude-opus-4-6",
            "--verbose",
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=os.path.abspath(repo_root),
    )
    return proc.stdout


def generate_rice_scores(issue_keys: list[str],
                         timeout: int = 300) -> RiceResult:
    """Generate RICE scores for a list of issues via Claude skill."""
    result = RiceResult()

    for key in issue_keys:
        print(f"  Generating RICE for {key}...")
        try:
            output = invoke_rice_skill(key, timeout=timeout)

            already = is_already_scored(output)
            if already:
                result.already_scored.append(already)
                print(f"    {key}: already scored")
                continue

            error = is_error(output)
            if error:
                result.failed.append(key)
                print(f"    {key}: error — {error}")
                continue

            rec = parse_rice_output(output)
            if rec:
                result.succeeded.append(rec)
                print(f"    {key}: R={rec.reach} I={rec.impact} "
                      f"C={rec.confidence}% E={rec.effort} "
                      f"→ RICE={rec.expected_rice}")
            else:
                result.failed.append(key)
                print(f"    {key}: failed to parse RICE output")

        except subprocess.TimeoutExpired:
            result.timed_out.append(key)
            print(f"    {key}: timed out after {timeout}s")

    return result


def write_rice_to_jira(rec: RiceRecommendation, server: str, user: str,
                       token: str):
    """Write RICE fields + justification comment to Jira."""
    from scripts.jira_utils import (
        api_call_with_retry, add_labels, add_comment, markdown_to_adf,
    )

    # Set the 4 RICE fields
    confidence_option = CONFIDENCE_OPTIONS.get(rec.confidence)
    if not confidence_option:
        raise ValueError(f"Invalid confidence: {rec.confidence}")

    body = {
        "fields": {
            RICE_FIELDS["reach"]: rec.reach,
            RICE_FIELDS["impact"]: rec.impact,
            RICE_FIELDS["confidence"]: {"id": confidence_option},
            RICE_FIELDS["effort"]: rec.effort,
        }
    }
    api_call_with_retry(server, f"/issue/{rec.ticket}", user, token,
                        body=body, method="PUT")

    # Post justification comment (ADF format required by Jira API v3)
    comment_md = (
        f"**RICE SCORE JUSTIFICATION (auto-generated):**\n\n"
        f"| Dimension | Score | Scale |\n"
        f"|-----------|-------|-------|\n"
        f"| Reach | {rec.reach} | 1-3-5-8-13 |\n"
        f"| Impact | {rec.impact} | 1-3-5-8-13 |\n"
        f"| Confidence | {rec.confidence}% | 50-75-100 |\n"
        f"| Effort | {rec.effort} | 1-2-3-5-8-13 |\n"
        f"| **RICE Score** | **{rec.expected_rice}** | (RxIxC)/E |\n\n"
        f"{rec.justification}"
    )
    comment_adf = markdown_to_adf(comment_md)
    add_comment(server, user, token, rec.ticket, comment_adf)

    # Add auto-rice label
    add_labels(server, user, token, rec.ticket, ["rp-qg1-auto-rice"])
