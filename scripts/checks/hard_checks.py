"""Hard check implementations: field_present, label_present."""
from scripts.checks import BaseCheck, CheckResult, register_check


@register_check("field_present")
class FieldPresentCheck(BaseCheck):
    """Verifies one or more Jira fields have non-null, non-empty values."""

    def evaluate(self, issue: dict) -> CheckResult:
        fields = self.config.get("fields", [])
        issue_fields = issue.get("fields", {})
        missing = []
        for f in fields:
            val = issue_fields.get(f)
            if val is None or val == "" or val == []:
                missing.append(f)

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
