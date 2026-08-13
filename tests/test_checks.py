"""Tests for the check framework and hard check implementations."""
import pytest

from scripts.checks import (
    CheckResult,
    instantiate_checks,
    compute_verdict,
    CHECK_REGISTRY,
)
# Importing hard_checks registers the check types
import scripts.checks.hard_checks  # noqa: F401


# --- CheckResult ---

class TestCheckResult:
    def test_passing_result(self):
        r = CheckResult(name="test", passed=True, details="ok")
        assert r.passed
        assert r.auto_fixable is False
        assert r.auto_fix_action is None

    def test_failing_result_with_auto_fix(self):
        r = CheckResult(
            name="test", passed=False, details="missing",
            auto_fixable=True, auto_fix_action="rice_scorer",
        )
        assert not r.passed
        assert r.auto_fixable
        assert r.auto_fix_action == "rice_scorer"


# --- Registry ---

class TestRegistry:
    def test_field_present_registered(self):
        assert "field_present" in CHECK_REGISTRY

    def test_label_present_registered(self):
        assert "label_present" in CHECK_REGISTRY

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unknown check type"):
            instantiate_checks([{"name": "bad", "type": "nonexistent"}])


# --- compute_verdict ---

class TestComputeVerdict:
    def test_all_pass(self):
        results = [
            CheckResult(name="a", passed=True, details="ok"),
            CheckResult(name="b", passed=True, details="ok"),
            CheckResult(name="c", passed=True, details="ok"),
        ]
        assert compute_verdict(results) == "pass"

    def test_one_fail(self):
        results = [
            CheckResult(name="a", passed=True, details="ok"),
            CheckResult(name="b", passed=False, details="missing"),
            CheckResult(name="c", passed=True, details="ok"),
        ]
        assert compute_verdict(results) == "fail"

    def test_all_fail(self):
        results = [
            CheckResult(name="a", passed=False, details="missing"),
            CheckResult(name="b", passed=False, details="missing"),
        ]
        assert compute_verdict(results) == "fail"

    def test_empty_results_pass(self):
        assert compute_verdict([]) == "pass"

    def test_infra_error_is_error_not_fail(self):
        results = [
            CheckResult(name="a", passed=True, details="ok"),
            CheckResult(
                name="has_child_epics", passed=False, details="not loaded",
                infra_error=True,
            ),
        ]
        assert compute_verdict(results) == "error"


# --- FieldPresentCheck ---

class TestFieldPresentCheck:
    def _make_config(self, fields, auto_fix=None):
        cfg = {"name": "has_rice", "type": "field_present", "fields": fields}
        if auto_fix:
            cfg["auto_fix"] = auto_fix
        return cfg

    def test_all_fields_present(self):
        checks = instantiate_checks([
            self._make_config(["customfield_10862", "customfield_10836"]),
        ])
        issue = {"fields": {
            "customfield_10862": 8,
            "customfield_10836": 5,
        }}
        result = checks[0].evaluate(issue)
        assert result.passed
        assert "2 fields present" in result.details

    def test_some_fields_missing(self):
        checks = instantiate_checks([
            self._make_config(
                ["customfield_10862", "customfield_10836"],
                auto_fix="rice_scorer",
            ),
        ])
        issue = {"fields": {"customfield_10862": 8}}
        result = checks[0].evaluate(issue)
        assert not result.passed
        assert "customfield_10836" in result.details
        assert result.auto_fixable
        assert result.auto_fix_action == "rice_scorer"

    def test_all_fields_missing(self):
        checks = instantiate_checks([
            self._make_config(["customfield_10862", "customfield_10836"]),
        ])
        issue = {"fields": {}}
        result = checks[0].evaluate(issue)
        assert not result.passed
        assert "customfield_10862" in result.details
        assert "customfield_10836" in result.details

    def test_null_field_counts_as_missing(self):
        checks = instantiate_checks([
            self._make_config(["priority"]),
        ])
        issue = {"fields": {"priority": None}}
        result = checks[0].evaluate(issue)
        assert not result.passed

    def test_empty_string_counts_as_missing(self):
        checks = instantiate_checks([
            self._make_config(["priority"]),
        ])
        issue = {"fields": {"priority": ""}}
        result = checks[0].evaluate(issue)
        assert not result.passed

    def test_empty_list_counts_as_missing(self):
        checks = instantiate_checks([
            self._make_config(["labels"]),
        ])
        issue = {"fields": {"labels": []}}
        result = checks[0].evaluate(issue)
        assert not result.passed

    def test_empty_dict_counts_as_missing(self):
        checks = instantiate_checks([
            self._make_config(["priority"]),
        ])
        issue = {"fields": {"priority": {}}}
        result = checks[0].evaluate(issue)
        assert not result.passed

    def test_user_picker_requires_account_id(self):
        """Assignee / Product Manager must have a non-empty accountId."""
        for field in ("assignee", "customfield_10469"):
            checks = instantiate_checks([self._make_config([field])])
            issue = {"fields": {field: {"displayName": "Someone"}}}
            result = checks[0].evaluate(issue)
            assert not result.passed, f"{field} without accountId should fail"

            issue = {"fields": {field: {
                "displayName": "Someone",
                "accountId": "",
            }}}
            result = checks[0].evaluate(issue)
            assert not result.passed, f"{field} with blank accountId should fail"

            issue = {"fields": {field: {
                "displayName": "Someone",
                "accountId": "abc123",
            }}}
            result = checks[0].evaluate(issue)
            assert result.passed, f"{field} with accountId should pass"

    def test_zero_is_present(self):
        """Zero is a valid value (e.g., a score of 0)."""
        checks = instantiate_checks([
            self._make_config(["customfield_10862"]),
        ])
        issue = {"fields": {"customfield_10862": 0}}
        result = checks[0].evaluate(issue)
        assert result.passed

    def test_no_auto_fix_by_default(self):
        checks = instantiate_checks([
            self._make_config(["priority"]),
        ])
        issue = {"fields": {}}
        result = checks[0].evaluate(issue)
        assert not result.auto_fixable
        assert result.auto_fix_action is None

    def test_undefined_priority_counts_as_missing(self):
        checks = instantiate_checks([
            self._make_config(["priority"]),
        ])
        issue = {"fields": {"priority": {"name": "Undefined", "id": "10005"}}}
        result = checks[0].evaluate(issue)
        assert not result.passed

    def test_valid_priority_passes(self):
        checks = instantiate_checks([
            self._make_config(["priority"]),
        ])
        issue = {"fields": {"priority": {"name": "Major", "id": "10002"}}}
        result = checks[0].evaluate(issue)
        assert result.passed

    def test_undefined_value_in_dropdown_counts_as_missing(self):
        checks = instantiate_checks([
            self._make_config(["customfield_10665"]),
        ])
        issue = {"fields": {"customfield_10665": {"value": "Undefined"}}}
        result = checks[0].evaluate(issue)
        assert not result.passed

    def test_rice_fields_all_present(self):
        """Full RICE check: all 4 custom fields populated."""
        rice_fields = [
            "customfield_10862", "customfield_10836",
            "customfield_10838", "customfield_10637",
        ]
        checks = instantiate_checks([
            self._make_config(rice_fields, auto_fix="rice_scorer"),
        ])
        issue = {"fields": {
            "customfield_10862": 8,
            "customfield_10836": 5,
            "customfield_10838": {"id": "16144"},
            "customfield_10637": 3,
        }}
        result = checks[0].evaluate(issue)
        assert result.passed

    def test_rice_fields_partial(self):
        """RICE check fails if any of the 4 fields is missing."""
        rice_fields = [
            "customfield_10862", "customfield_10836",
            "customfield_10838", "customfield_10637",
        ]
        checks = instantiate_checks([
            self._make_config(rice_fields, auto_fix="rice_scorer"),
        ])
        issue = {"fields": {
            "customfield_10862": 8,
            "customfield_10836": 5,
            # confidence and effort missing
        }}
        result = checks[0].evaluate(issue)
        assert not result.passed
        assert result.auto_fixable


# --- LabelPresentCheck ---

class TestLabelPresentCheck:
    def _make_config(self, labels):
        return {"name": "has_sign_off", "type": "label_present",
                "labels": labels}

    def test_label_present(self):
        checks = instantiate_checks([
            self._make_config(["strat-creator-human-sign-off"]),
        ])
        issue = {"fields": {
            "labels": ["strat-creator-human-sign-off", "other-label"],
        }}
        result = checks[0].evaluate(issue)
        assert result.passed

    def test_label_missing(self):
        checks = instantiate_checks([
            self._make_config(["strat-creator-human-sign-off"]),
        ])
        issue = {"fields": {"labels": ["other-label"]}}
        result = checks[0].evaluate(issue)
        assert not result.passed
        assert "strat-creator-human-sign-off" in result.details

    def test_no_labels_at_all(self):
        checks = instantiate_checks([
            self._make_config(["strat-creator-human-sign-off"]),
        ])
        issue = {"fields": {"labels": []}}
        result = checks[0].evaluate(issue)
        assert not result.passed

    def test_multiple_required_labels_all_present(self):
        checks = instantiate_checks([
            self._make_config(["label-a", "label-b"]),
        ])
        issue = {"fields": {"labels": ["label-a", "label-b", "label-c"]}}
        result = checks[0].evaluate(issue)
        assert result.passed

    def test_multiple_required_labels_one_missing(self):
        checks = instantiate_checks([
            self._make_config(["label-a", "label-b"]),
        ])
        issue = {"fields": {"labels": ["label-a"]}}
        result = checks[0].evaluate(issue)
        assert not result.passed
        assert "label-b" in result.details


# --- New hard checks: components, release type, docs required, target version ---

class TestNewHardChecks:
    def test_components_present(self):
        checks = instantiate_checks([
            {"name": "has_components", "type": "field_present",
             "fields": ["components"]},
        ])
        issue = {"fields": {"components": [{"name": "Dashboard"}]}}
        assert checks[0].evaluate(issue).passed

    def test_components_empty_list_fails(self):
        checks = instantiate_checks([
            {"name": "has_components", "type": "field_present",
             "fields": ["components"]},
        ])
        issue = {"fields": {"components": []}}
        assert not checks[0].evaluate(issue).passed

    def test_release_type_present(self):
        checks = instantiate_checks([
            {"name": "has_release_type", "type": "field_present",
             "fields": ["customfield_10851"]},
        ])
        issue = {"fields": {"customfield_10851": {"value": "Tech Preview"}}}
        assert checks[0].evaluate(issue).passed

    def test_release_type_missing(self):
        checks = instantiate_checks([
            {"name": "has_release_type", "type": "field_present",
             "fields": ["customfield_10851"]},
        ])
        issue = {"fields": {}}
        assert not checks[0].evaluate(issue).passed

    def test_docs_impact_yes_with_documentation_component(self):
        checks = instantiate_checks([
            {"name": "has_docs_impact", "type": "docs_impact",
             "docs_required_field": "customfield_10665",
             "documentation_component": "Documentation"},
        ])
        issue = {"fields": {
            "customfield_10665": {"value": "Yes"},
            "components": [{"name": "Documentation"}, {"name": "Dashboard"}],
        }}
        assert checks[0].evaluate(issue).passed

    def test_docs_impact_yes_without_documentation_component_fails(self):
        checks = instantiate_checks([
            {"name": "has_docs_impact", "type": "docs_impact",
             "docs_required_field": "customfield_10665",
             "documentation_component": "Documentation"},
        ])
        issue = {"fields": {
            "customfield_10665": {"value": "Yes"},
            "components": [{"name": "Dashboard"}],
        }}
        result = checks[0].evaluate(issue)
        assert not result.passed
        assert "Documentation" in result.details

    def test_docs_impact_no_passes_without_documentation_component(self):
        checks = instantiate_checks([
            {"name": "has_docs_impact", "type": "docs_impact",
             "docs_required_field": "customfield_10665",
             "documentation_component": "Documentation"},
        ])
        issue = {"fields": {
            "customfield_10665": {"value": "No"},
            "components": [{"name": "Dashboard"}],
        }}
        assert checks[0].evaluate(issue).passed

    def test_docs_impact_missing_field_fails(self):
        checks = instantiate_checks([
            {"name": "has_docs_impact", "type": "docs_impact",
             "docs_required_field": "customfield_10665",
             "documentation_component": "Documentation"},
        ])
        issue = {"fields": {"components": [{"name": "Documentation"}]}}
        assert not checks[0].evaluate(issue).passed

    def test_target_version_present(self):
        checks = instantiate_checks([
            {"name": "has_target_version", "type": "field_present",
             "fields": ["customfield_10855"]},
        ])
        issue = {"fields": {"customfield_10855": [{"name": "rhoai-3.5"}]}}
        assert checks[0].evaluate(issue).passed

    def test_target_version_empty_fails(self):
        checks = instantiate_checks([
            {"name": "has_target_version", "type": "field_present",
             "fields": ["customfield_10855"]},
        ])
        issue = {"fields": {"customfield_10855": []}}
        assert not checks[0].evaluate(issue).passed

    def test_child_epics_present_passes(self):
        checks = instantiate_checks([
            {"name": "has_child_epics", "type": "has_child_epics",
             "engineering_projects": ["RHOAIENG", "RHAIENG"]},
        ])
        issue = {
            "key": "RHAISTRAT-100",
            "fields": {},
            "_child_epics": [
                {"key": "RHOAIENG-1", "project": "RHOAIENG"},
                {"key": "RHAIENG-2", "project": "RHAIENG"},
            ],
        }
        result = checks[0].evaluate(issue)
        assert result.passed
        assert "2 child epic" in result.details
        assert "RHOAIENG-1" in result.details

    def test_child_epics_preview_truncates(self):
        from scripts.checks.hard_checks import preview_child_keys

        children = [{"key": f"RHOAIENG-{i}"} for i in range(1, 8)]
        preview = preview_child_keys(children)
        assert preview == (
            "RHOAIENG-1, RHOAIENG-2, RHOAIENG-3, RHOAIENG-4, RHOAIENG-5, "
            "… (+2 more)"
        )
        checks = instantiate_checks([
            {"name": "has_child_epics", "type": "has_child_epics"},
        ])
        result = checks[0].evaluate({
            "key": "RHAISTRAT-100",
            "fields": {},
            "_child_epics": children,
        })
        assert result.passed
        assert "7 child epic" in result.details
        assert "… (+2 more)" in result.details

    def test_child_epics_empty_fails(self):
        checks = instantiate_checks([
            {"name": "has_child_epics", "type": "has_child_epics",
             "engineering_projects": ["RHOAIENG", "RHAIENG", "AIPCC", "INFERENG", "RHAI"]},
        ])
        issue = {"key": "RHAISTRAT-100", "fields": {}, "_child_epics": []}
        result = checks[0].evaluate(issue)
        assert not result.passed
        assert "No child Epics found" in result.details
        assert "RHOAIENG" in result.details

    def test_rhai_child_epic_passes(self):
        checks = instantiate_checks([
            {"name": "has_child_epics", "type": "has_child_epics",
             "engineering_projects": ["RHAI"]},
        ])
        issue = {
            "key": "RHAISTRAT-100",
            "fields": {},
            "_child_epics": [{"key": "RHAI-1", "project": "RHAI"}],
        }
        assert checks[0].evaluate(issue).passed

    def test_child_epics_missing_enrichment_fails(self):
        checks = instantiate_checks([
            {"name": "has_child_epics", "type": "has_child_epics"},
        ])
        issue = {"key": "RHAISTRAT-100", "fields": {}}
        result = checks[0].evaluate(issue)
        assert not result.passed
        assert result.infra_error is True
        assert "not loaded" in result.details
        assert "labels left unchanged" in result.details
        assert compute_verdict([result]) == "error"

    def test_child_epics_label_alone_does_not_pass(self):
        """epic-creator-auto-decomposed is not a substitute for real children."""
        checks = instantiate_checks([
            {"name": "has_child_epics", "type": "has_child_epics"},
        ])
        issue = {
            "key": "RHAISTRAT-100",
            "fields": {"labels": ["epic-creator-auto-decomposed"]},
            "_child_epics": [],
        }
        assert not checks[0].evaluate(issue).passed


# --- instantiate_checks with full config ---

ALL_HARD_CHECKS = [
    {
        "name": "has_rice",
        "type": "field_present",
        "fields": [
            "customfield_10862", "customfield_10836",
            "customfield_10838", "customfield_10637",
        ],
        "auto_fix": "rice_scorer",
    },
    {"name": "has_priority", "type": "field_present", "fields": ["priority"]},
    {"name": "has_pm", "type": "field_present",
     "fields": ["customfield_10469"]},
    {"name": "has_delivery_owner", "type": "field_present",
     "fields": ["assignee"]},
    {"name": "has_sign_off", "type": "label_present",
     "labels": ["strat-creator-human-sign-off"]},
    {"name": "has_rubric_pass", "type": "label_present",
     "labels": ["strat-creator-rubric-pass"]},
    {"name": "has_components", "type": "field_present", "fields": ["components"]},
    {"name": "has_release_type", "type": "field_present",
     "fields": ["customfield_10851"]},
    {"name": "has_docs_impact", "type": "docs_impact",
     "docs_required_field": "customfield_10665",
     "documentation_component": "Documentation"},
    {"name": "has_target_version", "type": "field_present",
     "fields": ["customfield_10855"]},
    {"name": "has_child_epics", "type": "has_child_epics",
     "engineering_projects": [
         "RHOAIENG", "RHAIENG", "AIPCC", "INFERENG", "RHAI",
     ]},
]

FULL_PASSING_ISSUE = {
    "key": "RHAISTRAT-100",
    "fields": {
        "customfield_10862": 8,
        "customfield_10836": 5,
        "customfield_10838": {"id": "16144"},
        "customfield_10637": 3,
        "priority": {"name": "Critical"},
        "customfield_10469": {
            "accountId": "pm-1", "displayName": "Pat Product"},
        "assignee": {
            "accountId": "eng-1", "displayName": "Dev Owner"},
        "labels": [
            "strat-creator-human-sign-off",
            "strat-creator-rubric-pass",
        ],
        "components": [{"name": "Dashboard"}, {"name": "Documentation"}],
        "customfield_10851": {"value": "Tech Preview"},
        "customfield_10665": {"value": "Yes"},
        "customfield_10855": [{"name": "rhoai-3.5"}],
    },
    "_child_epics": [{"key": "RHOAIENG-999", "project": "RHOAIENG"}],
}


class TestInstantiateChecks:
    def test_pipeline_settings_checks(self):
        """Instantiate the full hard_checks config from pipeline-settings."""
        configs = [
            {
                "name": "has_rice",
                "type": "field_present",
                "fields": [
                    "customfield_10862", "customfield_10836",
                    "customfield_10838", "customfield_10637",
                ],
                "auto_fix": "rice_scorer",
            },
            {
                "name": "has_priority",
                "type": "field_present",
                "fields": ["priority"],
            },
            {
                "name": "has_sign_off",
                "type": "label_present",
                "labels": ["strat-creator-human-sign-off"],
            },
        ]
        checks = instantiate_checks(configs)
        assert len(checks) == 3
        assert checks[0].name == "has_rice"
        assert checks[1].name == "has_priority"
        assert checks[2].name == "has_sign_off"

    def test_full_pass_scenario(self):
        """Issue with all required fields passes all hard checks."""
        checks = instantiate_checks(ALL_HARD_CHECKS)
        results = [c.evaluate(FULL_PASSING_ISSUE) for c in checks]
        assert len(results) == 11
        assert compute_verdict(results) == "pass"
        assert all(r.passed for r in results)

    def test_missing_child_epics_fails(self):
        checks = instantiate_checks(ALL_HARD_CHECKS)
        issue = {**FULL_PASSING_ISSUE, "_child_epics": []}
        results = [c.evaluate(issue) for c in checks]
        assert compute_verdict(results) == "fail"
        child = [r for r in results if r.name == "has_child_epics"][0]
        assert not child.passed

    def test_missing_rice_fails(self):
        checks = instantiate_checks(ALL_HARD_CHECKS)
        issue = {**FULL_PASSING_ISSUE, "fields": {
            **FULL_PASSING_ISSUE["fields"],
            "customfield_10862": None,
            "customfield_10836": None,
            "customfield_10838": None,
            "customfield_10637": None,
        }}
        results = [c.evaluate(issue) for c in checks]
        assert compute_verdict(results) == "fail"
        rice_result = [r for r in results if r.name == "has_rice"][0]
        assert not rice_result.passed
        assert rice_result.auto_fixable

    def test_missing_priority_fails(self):
        checks = instantiate_checks(ALL_HARD_CHECKS)
        issue = {**FULL_PASSING_ISSUE, "fields": {
            k: v for k, v in FULL_PASSING_ISSUE["fields"].items()
            if k != "priority"
        }}
        results = [c.evaluate(issue) for c in checks]
        assert compute_verdict(results) == "fail"

    def test_missing_components_fails(self):
        checks = instantiate_checks(ALL_HARD_CHECKS)
        issue = {**FULL_PASSING_ISSUE, "fields": {
            **FULL_PASSING_ISSUE["fields"],
            "components": [],
        }}
        results = [c.evaluate(issue) for c in checks]
        assert compute_verdict(results) == "fail"
        comp = [r for r in results if r.name == "has_components"][0]
        assert not comp.passed

    def test_missing_release_type_fails(self):
        checks = instantiate_checks(ALL_HARD_CHECKS)
        issue = {**FULL_PASSING_ISSUE, "fields": {
            k: v for k, v in FULL_PASSING_ISSUE["fields"].items()
            if k != "customfield_10851"
        }}
        results = [c.evaluate(issue) for c in checks]
        assert compute_verdict(results) == "fail"

    def test_missing_docs_impact_fails(self):
        checks = instantiate_checks(ALL_HARD_CHECKS)
        issue = {**FULL_PASSING_ISSUE, "fields": {
            k: v for k, v in FULL_PASSING_ISSUE["fields"].items()
            if k != "customfield_10665"
        }}
        results = [c.evaluate(issue) for c in checks]
        assert compute_verdict(results) == "fail"

    def test_missing_rubric_pass_fails(self):
        checks = instantiate_checks(ALL_HARD_CHECKS)
        issue = {**FULL_PASSING_ISSUE, "fields": {
            **FULL_PASSING_ISSUE["fields"],
            "labels": ["strat-creator-human-sign-off"],
        }}
        results = [c.evaluate(issue) for c in checks]
        assert compute_verdict(results) == "fail"
        rubric = [r for r in results if r.name == "has_rubric_pass"][0]
        assert not rubric.passed

    def test_missing_pm_fails(self):
        checks = instantiate_checks(ALL_HARD_CHECKS)
        issue = {**FULL_PASSING_ISSUE, "fields": {
            k: v for k, v in FULL_PASSING_ISSUE["fields"].items()
            if k != "customfield_10469"
        }}
        results = [c.evaluate(issue) for c in checks]
        assert compute_verdict(results) == "fail"
        pm = [r for r in results if r.name == "has_pm"][0]
        assert not pm.passed

    def test_missing_delivery_owner_fails(self):
        checks = instantiate_checks(ALL_HARD_CHECKS)
        issue = {**FULL_PASSING_ISSUE, "fields": {
            k: v for k, v in FULL_PASSING_ISSUE["fields"].items()
            if k != "assignee"
        }}
        results = [c.evaluate(issue) for c in checks]
        assert compute_verdict(results) == "fail"
        owner = [r for r in results if r.name == "has_delivery_owner"][0]
        assert not owner.passed

    def test_missing_target_version_fails(self):
        checks = instantiate_checks(ALL_HARD_CHECKS)
        issue = {**FULL_PASSING_ISSUE, "fields": {
            **FULL_PASSING_ISSUE["fields"],
            "customfield_10855": [],
        }}
        results = [c.evaluate(issue) for c in checks]
        assert compute_verdict(results) == "fail"
