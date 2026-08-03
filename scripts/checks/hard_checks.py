"""Hard check implementations: field_present, label_present, docs_impact."""
from scripts.checks import BaseCheck, CheckResult, register_check

INVALID_VALUES = {"Undefined", "None", "N/A"}


def _field_missing(val) -> bool:
    """True when a Jira field value should be treated as unset."""
    if val is None or val == "" or val == []:
        return True
    if isinstance(val, dict):
        if val.get("name") in INVALID_VALUES or val.get("value") in INVALID_VALUES:
            return True
        # User-picker fields (assignee, Product Manager) need an accountId.
        if "accountId" in val and not val.get("accountId"):
            return True
    return False


@register_check("field_present")
class FieldPresentCheck(BaseCheck):
    """Verifies one or more Jira fields have non-null, non-empty values."""

    def evaluate(self, issue: dict) -> CheckResult:
        fields = self.config.get("fields", [])
        issue_fields = issue.get("fields", {})
        missing = [f for f in fields if _field_missing(issue_fields.get(f))]

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
