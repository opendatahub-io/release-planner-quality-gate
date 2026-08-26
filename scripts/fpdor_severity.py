"""FPDoR item importance for gate-comment display order.

Aligned with Org Pulse ``fpdor-severity.js`` (ranked list 2026-08-07).
Display/triage only — does not affect pass/fail verdict or fingerprints.
"""
from scripts.checks import CheckResult

SEVERITY_RANK = {
    "soft": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

SEVERITY_LABEL = {
    "critical": "Critical",
    "high": "High",
    "medium": "Medium",
    "soft": "Soft",
}

# QG1 check name → (severity tier, stable order within tier).
# Maps to Org Pulse Confluence item names; has_rubric_pass ≈ Source RFE tier.
FPDOR_CHECK_SEVERITY = {
    "has_components": ("critical", 1),
    "has_child_epics": ("critical", 2),
    "has_target_version": ("critical", 3),
    "has_delivery_owner": ("critical", 4),
    "has_release_type": ("high", 5),
    "has_priority": ("high", 6),
    "has_rice": ("high", 7),
    "has_docs_impact": ("high", 8),
    "has_cross_team_deps": ("medium", 9),
    "has_pm": ("medium", 10),
    "has_sign_off": ("medium", 11),
    "has_requirements_clarity": ("medium", 12),
    "has_acceptance_criteria": ("medium", 13),
    "has_risks_assumptions": ("medium", 14),
    "has_architectural_alignment": ("medium", 15),
    "has_rubric_pass": ("soft", 16),
    "has_uxd_description": ("soft", 17),
}


def check_severity(check_name: str) -> str:
    """Return severity tier for a QG1 check name."""
    tier, _ = FPDOR_CHECK_SEVERITY.get(check_name, ("medium", 99))
    return tier


def check_severity_label(check_name: str) -> str:
    """Human-readable importance label for gate comments."""
    return SEVERITY_LABEL[check_severity(check_name)]


def _display_outcome_rank(result: CheckResult) -> int:
    """Lower rank sorts earlier: fail, error, N/A, pass."""
    if not result.passed and not result.not_applicable and not result.infra_error:
        return 0
    if result.infra_error:
        return 1
    if result.not_applicable:
        return 2
    return 3


def sort_checks_for_display(check_results: list[CheckResult]) -> list[CheckResult]:
    """Sort checks by descending FPDoR importance (critical first).

  Within the same tier, failures sort before errors, N/A, and passes.
    """
    def sort_key(result: CheckResult):
        tier, order = FPDOR_CHECK_SEVERITY.get(result.name, ("medium", 99))
        return (
            -SEVERITY_RANK[tier],
            _display_outcome_rank(result),
            order,
            result.name,
        )

    return sorted(check_results, key=sort_key)
