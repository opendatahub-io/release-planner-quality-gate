"""Hard check implementations: field_present, label_present, docs_impact,
has_child_epics, description_criterion.
"""
from scripts.checks import BaseCheck, CheckResult, register_check
from scripts.description_invoker import CRITERION_KEYS

INVALID_VALUES = {"Undefined", "None", "N/A"}
# Jira user-picker fields used by FPDoR Phase 1 checks.
USER_PICKER_FIELDS = {"assignee", "customfield_10469"}

# Orchestrator attaches DescriptionEvaluation (or None on infra failure).
FPDOR_DESCRIPTION_ATTR = "_fpdor_description"

NON_ENG_COMPONENTS = {"Documentation", "Docs", "UXD"}


def _labels(issue: dict) -> list:
    return list(issue.get("fields", {}).get("labels") or [])


def _has_label(issue: dict, exact: str) -> bool:
    return exact in _labels(issue)


def _has_label_prefix(issue: dict, prefix: str) -> bool:
    for label in _labels(issue):
        if isinstance(label, str) and label.startswith(prefix):
            return True
    return False


def _label_shortcuts_hit(issue: dict, config: dict) -> str | None:
    """Return a matching shortcut label/prefix, or None."""
    for label in config.get("label_shortcuts") or []:
        if _has_label(issue, label):
            return label
    for prefix in config.get("label_prefixes") or []:
        if _has_label_prefix(issue, prefix):
            return prefix + "*"
    return None


def _component_names(issue: dict) -> list[str]:
    comps = issue.get("fields", {}).get("components") or []
    names = []
    for c in comps:
        if isinstance(c, dict):
            name = (c.get("name") or "").strip()
        else:
            name = str(c).strip()
        if name:
            names.append(name)
    return names


def _eng_component_count(issue: dict) -> int:
    seen = set()
    count = 0
    for name in _component_names(issue):
        if name in NON_ENG_COMPONENTS or name in seen:
            continue
        seen.add(name)
        count += 1
    return count


def _has_uxd_component(issue: dict) -> bool:
    return any(n == "UXD" for n in _component_names(issue))


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


@register_check("description_criterion")
class DescriptionCriterionCheck(BaseCheck):
    """FPDoR description criterion via label shortcuts or skill enrichment.

    Config:
      criterion: one of CRITERION_KEYS
      label_shortcuts: exact labels that pass without the skill
      label_prefixes: label prefixes that pass without the skill
      accept_uxd_component: if true, UXD component passes (uxd_description)
      accept_multi_eng_components: if true, ≥2 eng components pass
      accept_epic_creator_label: if true, epic-creator-auto-decomposed passes

    Expects orchestrator to set ``issue["_fpdor_description"]`` to a
    DescriptionEvaluation when the skill ran, or ``None`` on infra failure.
    When shortcuts apply, enrichment may be omitted.
    """

    def shortcut_result(self, issue: dict) -> CheckResult | None:
        """Return a CheckResult when a non-skill shortcut applies."""
        hit = _label_shortcuts_hit(issue, self.config)
        if hit:
            return CheckResult(
                name=self.name,
                passed=True,
                details=f"Passed via label shortcut ({hit})",
            )
        if self.config.get("accept_uxd_component") and _has_uxd_component(issue):
            return CheckResult(
                name=self.name,
                passed=True,
                details="Passed via UXD component",
            )
        if self.config.get("accept_epic_creator_label") and _has_label(
            issue, "epic-creator-auto-decomposed"
        ):
            return CheckResult(
                name=self.name,
                passed=True,
                details="Passed via epic-creator-auto-decomposed",
            )
        if self.config.get("accept_multi_eng_components"):
            eng = _eng_component_count(issue)
            if eng >= 2:
                return CheckResult(
                    name=self.name,
                    passed=True,
                    details=f"Passed via {eng} engineering components",
                )
        return None

    def evaluate(self, issue: dict) -> CheckResult:
        criterion = self.config.get("criterion")
        if criterion not in CRITERION_KEYS:
            return CheckResult(
                name=self.name,
                passed=False,
                details=f"Invalid description criterion: {criterion!r}",
            )

        shortcut = self.shortcut_result(issue)
        if shortcut is not None:
            return shortcut

        enrichment = issue.get(FPDOR_DESCRIPTION_ATTR, _MISSING)
        if enrichment is _MISSING:
            return CheckResult(
                name=self.name,
                passed=False,
                infra_error=True,
                details=(
                    "Description skill was not run for this issue; "
                    "cannot verify criterion"
                ),
            )
        if enrichment is None:
            return CheckResult(
                name=self.name,
                passed=False,
                infra_error=True,
                details=(
                    "Description skill lookup failed; "
                    "cannot verify criterion — Jira labels left unchanged"
                ),
            )

        item = enrichment.criteria.get(criterion)
        if item is None:
            return CheckResult(
                name=self.name,
                passed=False,
                infra_error=True,
                details=f"Description skill omitted criterion {criterion}",
            )

        evidence = (item.evidence or "").strip()
        evidence_note = f": {evidence}" if evidence else ""

        if item.verdict == "pass":
            return CheckResult(
                name=self.name,
                passed=True,
                details=f"Passed via description skill{evidence_note}",
            )
        if item.verdict == "na":
            return CheckResult(
                name=self.name,
                passed=True,
                not_applicable=True,
                details=f"N/A via description skill{evidence_note}",
            )
        return CheckResult(
            name=self.name,
            passed=False,
            details=f"Failed description criterion{evidence_note}",
        )


# Sentinel: attribute missing vs explicitly None (infra failure).
_MISSING = object()


def issue_needs_description_skill(issue: dict, check_configs: list[dict]) -> bool:
    """True when at least one description_criterion lacks a field/label shortcut."""
    for cfg in check_configs or []:
        if cfg.get("type") != "description_criterion":
            continue
        check = DescriptionCriterionCheck(name=cfg["name"], config=cfg)
        if check.shortcut_result(issue) is None:
            return True
    return False
