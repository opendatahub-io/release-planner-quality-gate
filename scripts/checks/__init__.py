"""Check framework for release quality gates.

Registry pattern: each check type is a class implementing evaluate(issue) → CheckResult.
Config maps check names to types + params. Adding new checks = new type + config entries.
"""
from dataclasses import dataclass, field
from abc import ABC, abstractmethod


@dataclass
class CheckResult:
    """Result of a single quality check on a Jira issue."""
    name: str
    passed: bool
    details: str
    auto_fixable: bool = False
    auto_fix_action: str | None = None
    # True when the check could not run due to infrastructure failure
    # (not a Feature content gap). Orchestrator skips Jira writes; artifacts
    # use verdict "error" rather than "fail".
    infra_error: bool = False
    # True when the check does not apply (Org Pulse ``null``). Does not fail
    # the gate; fingerprint status is ``na``.
    not_applicable: bool = False


CHECK_REGISTRY: dict[str, type["BaseCheck"]] = {}


def register_check(type_name: str):
    """Decorator to register a check type in the global registry."""
    def decorator(cls):
        CHECK_REGISTRY[type_name] = cls
        return cls
    return decorator


class BaseCheck(ABC):
    """Base class for all quality checks."""

    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config

    @abstractmethod
    def evaluate(self, issue: dict) -> CheckResult:
        ...


def instantiate_checks(check_configs: list[dict]) -> list[BaseCheck]:
    """Create check instances from config definitions."""
    checks = []
    for cfg in check_configs:
        check_type = cfg["type"]
        if check_type not in CHECK_REGISTRY:
            raise ValueError(f"Unknown check type: {check_type}")
        cls = CHECK_REGISTRY[check_type]
        checks.append(cls(name=cfg["name"], config=cfg))
    return checks


FPDOR_TOTAL_COUNT = 17


def compute_fpdor_score(check_results: list[CheckResult]) -> dict:
    """Org Pulse–aligned FPDoR score for gate comments and artifacts.

    Always uses a fixed denominator of 17. Items marked ``not_applicable``
    have ``passed=True`` and count toward ``passed_count`` (same as Org Pulse
    ``state: 'not-applicable'``). Only real failures (``passed=False`` and
    not N/A, not infra error) increment ``fail_count``.
    """
    passed_count = sum(1 for r in check_results if r.passed)
    na_count = sum(1 for r in check_results if r.not_applicable)
    fail_count = sum(
        1 for r in check_results
        if not r.passed and not r.not_applicable and not r.infra_error
    )
    error_count = sum(1 for r in check_results if r.infra_error)
    return {
        "passed_count": passed_count,
        "total_count": FPDOR_TOTAL_COUNT,
        "na_count": na_count,
        "fail_count": fail_count,
        "error_count": error_count,
    }


def compute_verdict(check_results: list[CheckResult]) -> str:
    """Derive pass / fail / error from check results.

    ``error`` means at least one check hit an infrastructure failure and
    must not be tallied as a content fail. ``not_applicable`` checks do not
    block a pass.
    """
    if any(r.infra_error for r in check_results):
        return "error"
    applicable = [r for r in check_results if not r.not_applicable]
    if not applicable or all(r.passed for r in applicable):
        return "pass"
    return "fail"
