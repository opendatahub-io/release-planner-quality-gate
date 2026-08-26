"""Tests for FPDoR display ordering in gate comments."""
from scripts.checks import CheckResult
from scripts.fpdor_severity import (
    check_severity_label,
    sort_checks_for_display,
)


def _result(name, passed=True, not_applicable=False, infra_error=False):
    return CheckResult(
        name=name,
        passed=passed,
        details="detail",
        not_applicable=not_applicable,
        infra_error=infra_error,
    )


def test_check_severity_label():
    assert check_severity_label("has_child_epics") == "Critical"
    assert check_severity_label("has_uxd_description") == "Soft"


def test_sort_checks_by_importance_descending():
    """Severity first; within a tier, fail before N/A before pass."""
    results = [
        _result("has_uxd_description", passed=False),
        _result("has_child_epics", passed=False),
        _result("has_sign_off", not_applicable=True),
        _result("has_priority", passed=True),
    ]
    names = [r.name for r in sort_checks_for_display(results)]
    assert names == [
        "has_child_epics",
        "has_priority",
        "has_sign_off",
        "has_uxd_description",
    ]


def test_sort_checks_importance_within_failed():
    results = [
        _result("has_uxd_description", passed=False),
        _result("has_child_epics", passed=False),
        _result("has_docs_impact", passed=False),
    ]
    names = [r.name for r in sort_checks_for_display(results)]
    assert names == [
        "has_child_epics",
        "has_docs_impact",
        "has_uxd_description",
    ]
