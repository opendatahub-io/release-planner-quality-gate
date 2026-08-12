"""Hard check implementations: field_present, label_present, docs_impact,
has_child_epics.
"""
from scripts.checks import BaseCheck, CheckResult, register_check

INVALID_VALUES = {"Undefined", "None", "N/A"}
# Jira user-picker fields used by FPDoR Phase 1 checks.
USER_PICKER_FIELDS = {"assignee", "customfield_10469"}


def _field_missing(val, *, requires_account_id=False) -> bool:
    """True when a Jira field value should be treated as unset."""
    if val is None or val == "" or val == [] or val == {}:
        return True
    if isinstance(val, dict):
        if val.get("name") in INVALID_VALUES or val.get("value") in INVALID_VALUES:
            return True
        if requires_account_id:
            return not bool(val.get("accountId"))
        # Blank accountId on any user-shaped object is still missing.
        if "accountId" in val and not val.get("accountId"):
            return True
    return False


@register_check("field_present")
class FieldPresentCheck(BaseCheck):
    """Verifies one or more Jira fields have non-null, non-empty values."""

    def evaluate(self, issue: dict) -> CheckResult:
        fields = self.config.get("fields", [])
        issue_fields = issue.get("fields", {})
        missing = [
            f for f in fields
            if _field_missing(
                issue_fields.get(f),
                requires_account_id=f in USER_PICKER_FIELDS,
            )
        ]

        if not missing:
            return CheckResult(
                name=self.name,
                passed=True,
                details=f"All {len(fields)} fields present",
            )

        auto_fix = self.config.get("auto_fix")
        return CheckResult(
            name=self.name,
            passed=False,
            details=f"Missing fields: {', '.join(missing)}",
            auto_fixable=auto_fix is not None,
            auto_fix_action=auto_fix,
        )


@register_check("label_present")
class LabelPresentCheck(BaseCheck):
    """Verifies the issue has specific labels."""

    def evaluate(self, issue: dict) -> CheckResult:
        required = set(self.config.get("labels", []))
        issue_labels = set(issue.get("fields", {}).get("labels", []))
        missing = required - issue_labels

        if not missing:
            return CheckResult(
                name=self.name,
                passed=True,
                details=f"All required labels present",
            )
        return CheckResult(
            name=self.name,
            passed=False,
            details=f"Missing labels: {', '.join(sorted(missing))}",
        )


@register_check("docs_impact")
class DocsImpactCheck(BaseCheck):
    """FPDoR docs impact: Docs Required set; if Yes, Documentation component set."""

    def evaluate(self, issue: dict) -> CheckResult:
        docs_field = self.config.get(
            "docs_required_field", "customfield_10665")
        docs_component = self.config.get(
            "documentation_component", "Documentation")
        issue_fields = issue.get("fields", {})
        docs_val = issue_fields.get(docs_field)

        if _field_missing(docs_val):
            return CheckResult(
                name=self.name,
                passed=False,
                details=f"Missing fields: {docs_field}",
            )

        value = docs_val.get("value") if isinstance(docs_val, dict) else docs_val
        if value not in ("Yes", "No"):
            return CheckResult(
                name=self.name,
                passed=False,
                details=(
                    f"Product Documentation Required must be Yes or No "
                    f"(got {value!r})"
                ),
            )

        if value == "No":
            return CheckResult(
                name=self.name,
                passed=True,
                details="Product Documentation Required = No",
            )

        components = issue_fields.get("components") or []
        names = {
            c.get("name") for c in components
            if isinstance(c, dict) and c.get("name")
        }
        if docs_component in names:
            return CheckResult(
                name=self.name,
                passed=True,
                details=(
                    f"Product Documentation Required = Yes; "
                    f"{docs_component} component present"
                ),
            )
        return CheckResult(
            name=self.name,
            passed=False,
            details=(
                f"Product Documentation Required = Yes but "
                f"{docs_component} component is not assigned"
            ),
        )


# In-memory enrichment key set by quality_gate.enrich_issues_with_child_epics.
CHILD_EPICS_ATTR = "_child_epics"


def preview_child_keys(children, limit=5):
    """Format child epic keys for details, truncating after ``limit``."""
    keys = [
        (c.get("key") or "?") if isinstance(c, dict) else str(c)
        for c in children
    ]
    preview = ", ".join(keys[:limit])
    if len(keys) > limit:
        preview += f", … (+{len(keys) - limit} more)"
    return preview


@register_check("has_child_epics")
class HasChildEpicsCheck(BaseCheck):
    """Feature must have ≥1 child Epic (parent hierarchy in eng projects).

    Expects the orchestrator to attach child epic summaries on the issue
    under ``_child_epics`` before evaluate(). Structural detection only —
    the ``epic-creator-auto-decomposed`` label is not treated as a pass
    (unlike pure label_present checks); QG1 verifies real child Epics.
    """

    def evaluate(self, issue: dict) -> CheckResult:
        children = issue.get(CHILD_EPICS_ATTR)
        if children is None:
            # Infrastructure / enrichment failure — not a Feature content
            # gap. Orchestrator suppresses Jira label writes for this case.
            return CheckResult(
                name=self.name,
                passed=False,
                infra_error=True,
                details=(
                    "Child epic data was not loaded (lookup failed); "
                    "cannot verify child Epics — Jira labels left unchanged"
                ),
            )
        if not children:
            projects = self.config.get("engineering_projects") or []
            project_hint = (
                f" in {', '.join(projects)}" if projects else ""
            )
            return CheckResult(
                name=self.name,
                passed=False,
                details=(
                    f"No child Epics found{project_hint} "
                    f"(issuetype = Epic AND parent = this Feature)"
                ),
            )

        preview = preview_child_keys(children)
        return CheckResult(
            name=self.name,
            passed=True,
            details=f"{len(children)} child epic(s): {preview}",
        )
