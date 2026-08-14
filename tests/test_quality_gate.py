"""Tests for the quality gate orchestrator."""
import json
import os
import urllib.error
from unittest.mock import patch

import pytest

from scripts.quality_gate import (
    build_jql,
    collect_required_fields,
    load_config,
    build_run_data,
    evaluate_issue,
    enrich_issues_with_child_epics,
)
from scripts.jira_utils import fetch_child_epics_by_parent
from scripts.checks import CheckResult, compute_verdict, instantiate_checks
import scripts.checks.hard_checks  # noqa: F401


# --- JQL Builder ---

class TestBuildJql:
    def test_default_config(self):
        config = {
            "jql": {
                "project": "RHAISTRAT",
                "required_labels": ["strat-creator-human-sign-off"],
                "excluded_statuses": ["Closed", "Resolved"],
                "skip_labels": ["rp-qg1-pass"],
                "order_by": "key ASC",
            }
        }
        jql = build_jql(config)
        assert 'project = RHAISTRAT' in jql
        assert 'labels = "strat-creator-human-sign-off"' in jql
        assert "cf[10855]" not in jql
        assert 'status != "Closed"' in jql
        assert 'status != "Resolved"' in jql
        assert 'labels != "rp-qg1-pass"' in jql
        assert jql.endswith("ORDER BY key ASC")

    def test_minimal_config(self):
        config = {"jql": {"project": "RHAISTRAT"}}
        jql = build_jql(config)
        assert jql == "project = RHAISTRAT ORDER BY key ASC"

    def test_no_target_versions(self):
        config = {
            "jql": {
                "project": "RHAISTRAT",
                "required_labels": ["some-label"],
            }
        }
        jql = build_jql(config)
        assert "cf[10855]" not in jql

    def test_multiple_skip_labels(self):
        config = {
            "jql": {
                "project": "RHAISTRAT",
                "skip_labels": ["rp-qg1-pass", "rp-qg1-skip"],
            }
        }
        jql = build_jql(config)
        assert 'labels != "rp-qg1-pass"' in jql
        assert 'labels != "rp-qg1-skip"' in jql


# --- Config Loading ---

class TestLoadConfig:
    def test_load_pipeline_settings(self):
        config = load_config()
        assert config["jql"]["project"] == "RHAISTRAT"
        assert "rice_fields" in config
        assert "labels" in config
        assert "checks" in config

    def test_rice_field_ids(self):
        config = load_config()
        rice = config["rice_fields"]
        assert rice["reach"] == "customfield_10862"
        assert rice["impact"] == "customfield_10836"
        assert rice["confidence"] == "customfield_10838"
        assert rice["effort"] == "customfield_10637"
        assert rice["score"] == "customfield_10864"

    def test_label_names(self):
        config = load_config()
        labels = config["labels"]
        assert labels["gate_pass"] == "rp-qg1-pass"
        assert labels["gate_fail"] == "rp-qg1-fail"
        assert labels["auto_rice"] == "rp-qg1-auto-rice"

    def test_fpdor_phase1_checks_configured(self):
        config = load_config()
        names = {c["name"]: c["type"] for c in config["checks"]["hard_checks"]}
        assert names["has_pm"] == "field_present"
        assert names["has_delivery_owner"] == "field_present"
        assert names["has_rubric_pass"] == "label_present"
        assert names["has_docs_impact"] == "docs_impact"
        assert names["has_child_epics"] == "has_child_epics"
        assert "has_docs_required" not in names
        child_cfg = next(
            c for c in config["checks"]["hard_checks"]
            if c["name"] == "has_child_epics"
        )
        assert "RHOAIENG" in child_cfg["engineering_projects"]
        assert "INFERENG" in child_cfg["engineering_projects"]
        assert "RHAI" in child_cfg["engineering_projects"]
        assert "RHELAI" in child_cfg["engineering_projects"]

    def test_discovery_does_not_skip_prior_passes(self):
        """rp-qg1-pass must stay in scope so criteria changes revalidate."""
        config = load_config()
        skip = config["jql"].get("skip_labels") or []
        assert "rp-qg1-pass" not in skip
        jql = build_jql(config)
        assert 'labels != "rp-qg1-pass"' not in jql


# --- collect_required_fields ---

class TestCollectRequiredFields:
    def test_returns_list(self):
        config = load_config()
        fields = collect_required_fields(config)
        assert isinstance(fields, list)

    def test_includes_rice_fields(self):
        config = load_config()
        fields = collect_required_fields(config)
        assert "customfield_10862" in fields
        assert "customfield_10836" in fields
        assert "customfield_10838" in fields
        assert "customfield_10637" in fields

    def test_includes_priority_and_labels(self):
        config = load_config()
        fields = collect_required_fields(config)
        assert "priority" in fields
        assert "labels" in fields

    def test_includes_fpdor_phase1_fields(self):
        config = load_config()
        fields = collect_required_fields(config)
        assert "customfield_10469" in fields  # Product Manager
        assert "assignee" in fields
        assert "customfield_10665" in fields  # docs required
        assert "components" in fields


# --- evaluate_issue ---

class TestEvaluateIssue:
    def _checks(self):
        return instantiate_checks([
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
        ])

    def test_full_pass(self):
        issue = {"key": "RHAISTRAT-100", "fields": {
            "customfield_10862": 8,
            "customfield_10836": 5,
            "customfield_10838": {"id": "16144"},
            "customfield_10637": 3,
            "priority": {"name": "Critical"},
            "labels": ["strat-creator-human-sign-off"],
        }}
        results = evaluate_issue(issue, self._checks())
        assert compute_verdict(results) == "pass"

    def test_missing_rice_fails(self):
        issue = {"key": "RHAISTRAT-100", "fields": {
            "priority": {"name": "Normal"},
            "labels": ["strat-creator-human-sign-off"],
        }}
        results = evaluate_issue(issue, self._checks())
        assert compute_verdict(results) == "fail"
        rice = [r for r in results if r.name == "has_rice"][0]
        assert rice.auto_fixable

    def test_missing_priority_fails(self):
        issue = {"key": "RHAISTRAT-100", "fields": {
            "customfield_10862": 8,
            "customfield_10836": 5,
            "customfield_10838": {"id": "16144"},
            "customfield_10637": 3,
            "labels": ["strat-creator-human-sign-off"],
        }}
        results = evaluate_issue(issue, self._checks())
        assert compute_verdict(results) == "fail"


# --- build_run_data ---

class TestBuildRunData:
    def test_structure(self):
        results = {
            "RHAISTRAT-100": [
                CheckResult("has_rice", True, "ok"),
                CheckResult("has_priority", True, "ok"),
            ],
            "RHAISTRAT-101": [
                CheckResult("has_rice", False, "missing", True, "rice_scorer"),
                CheckResult("has_priority", True, "ok"),
            ],
        }
        data = build_run_data(results, {}, dry_run=True, mode="batch")
        assert data["dry_run"] is True
        assert data["mode"] == "batch"
        assert data["summary"]["total"] == 2
        assert data["summary"]["pass"] == 1
        assert data["summary"]["fail"] == 1
        assert data["summary"]["error"] == 0
        assert len(data["issues"]) == 2
        assert "generated_at" in data

    def test_infra_error_excluded_from_fail_tally(self):
        results = {
            "RHAISTRAT-100": [
                CheckResult("has_rice", True, "ok"),
            ],
            "RHAISTRAT-101": [
                CheckResult(
                    "has_child_epics", False, "not loaded",
                    infra_error=True,
                ),
            ],
        }
        data = build_run_data(results, {}, dry_run=True, mode="batch")
        assert data["summary"]["pass"] == 1
        assert data["summary"]["fail"] == 0
        assert data["summary"]["error"] == 1
        assert data["issues"][1]["verdict"] == "error"

    def test_single_mode_includes_key(self):
        results = {
            "RHAISTRAT-100": [
                CheckResult("has_rice", True, "ok"),
            ],
        }
        data = build_run_data(
            results, {}, dry_run=False, mode="single",
            issue_key="RHAISTRAT-100")
        assert data["mode"] == "single"
        assert data["issue_key"] == "RHAISTRAT-100"

    def test_empty_results(self):
        data = build_run_data({}, {}, dry_run=True, mode="batch")
        assert data["summary"]["total"] == 0
        assert data["summary"]["pass"] == 0
        assert data["summary"]["fail"] == 0
        assert data["summary"]["error"] == 0
        assert data["issues"] == []


# --- child epic enrichment ---

class TestFetchChildEpicsByParent:
    def test_groups_epics_by_parent(self):
        fake_issues = [
            {
                "key": "RHOAIENG-1",
                "fields": {
                    "parent": {"key": "RHAISTRAT-100"},
                    "project": {"key": "RHOAIENG"},
                    "summary": "Epic A",
                },
            },
            {
                "key": "RHAIENG-2",
                "fields": {
                    "parent": {"key": "RHAISTRAT-200"},
                    "project": {"key": "RHAIENG"},
                    "summary": "Epic B",
                },
            },
        ]
        with patch(
            "scripts.jira_utils.search_issues", return_value=fake_issues
        ) as mock_search:
            by_parent = fetch_child_epics_by_parent(
                "https://example.atlassian.net", "u", "t",
                ["RHAISTRAT-100", "RHAISTRAT-200", "RHAISTRAT-300"],
                projects=["RHOAIENG", "RHAIENG"],
            )
        assert mock_search.called
        jql = mock_search.call_args[0][3]
        assert "issuetype = Epic" in jql
        assert 'parent in ("RHAISTRAT-100", "RHAISTRAT-200", "RHAISTRAT-300")' in jql
        assert 'project in ("RHOAIENG", "RHAIENG")' in jql
        assert mock_search.call_args.kwargs.get("max_results") == 100
        assert [c["key"] for c in by_parent["RHAISTRAT-100"]] == ["RHOAIENG-1"]
        assert [c["key"] for c in by_parent["RHAISTRAT-200"]] == ["RHAIENG-2"]
        assert by_parent["RHAISTRAT-300"] == []

    def test_batches_parent_keys_and_passes_max_results(self):
        """Parent keys above batch_size must issue separate quoted JQL pages."""
        parents = [f"RHAISTRAT-{i}" for i in range(1, 6)]
        calls = []

        def fake_search(server, user, token, jql, fields=None, max_results=50):
            calls.append({"jql": jql, "max_results": max_results})
            # Return one epic for the first parent in each batch.
            if "RHAISTRAT-1" in jql:
                return [{
                    "key": "RHOAIENG-1",
                    "fields": {
                        "parent": {"key": "RHAISTRAT-1"},
                        "project": {"key": "RHOAIENG"},
                        "summary": "Epic 1",
                    },
                }]
            if "RHAISTRAT-4" in jql:
                return [{
                    "key": "RHOAIENG-4",
                    "fields": {
                        "parent": {"key": "RHAISTRAT-4"},
                        "project": {"key": "RHOAIENG"},
                        "summary": "Epic 4",
                    },
                }]
            return []

        with patch(
            "scripts.jira_utils.search_issues", side_effect=fake_search
        ):
            by_parent = fetch_child_epics_by_parent(
                "https://example.atlassian.net", "u", "t",
                parents,
                projects=["RHOAIENG"],
                batch_size=3,
            )

        assert len(calls) == 2
        assert all(c["max_results"] == 100 for c in calls)
        assert (
            'parent in ("RHAISTRAT-1", "RHAISTRAT-2", "RHAISTRAT-3")'
            in calls[0]["jql"]
        )
        assert (
            'parent in ("RHAISTRAT-4", "RHAISTRAT-5")' in calls[1]["jql"]
        )
        assert 'project in ("RHOAIENG")' in calls[0]["jql"]
        assert [c["key"] for c in by_parent["RHAISTRAT-1"]] == ["RHOAIENG-1"]
        assert [c["key"] for c in by_parent["RHAISTRAT-4"]] == ["RHOAIENG-4"]
        assert by_parent["RHAISTRAT-2"] == []
        assert by_parent["RHAISTRAT-5"] == []

    def test_empty_parents_returns_empty(self):
        assert fetch_child_epics_by_parent(
            "s", "u", "t", [], projects=["RHOAIENG"]) == {}


class TestEnrichIssuesWithChildEpics:
    def _child_config(self):
        return {
            "checks": {
                "hard_checks": [
                    {
                        "name": "has_child_epics",
                        "type": "has_child_epics",
                        "engineering_projects": ["RHOAIENG"],
                    }
                ]
            }
        }

    def test_attaches_child_epics(self):
        issues = [{"key": "RHAISTRAT-100", "fields": {}}]
        with patch(
            "scripts.quality_gate.fetch_child_epics_by_parent",
            return_value={
                "RHAISTRAT-100": [{"key": "RHOAIENG-9", "project": "RHOAIENG"}],
            },
        ):
            ok = enrich_issues_with_child_epics(
                issues, self._child_config(), "s", "u", "t")
        assert ok is True
        assert issues[0]["_child_epics"][0]["key"] == "RHOAIENG-9"

    def test_noop_when_check_not_configured(self):
        issues = [{"key": "RHAISTRAT-100", "fields": {}}]
        ok = enrich_issues_with_child_epics(
            issues, {"checks": {"hard_checks": []}}, "s", "u", "t")
        assert ok is True
        assert "_child_epics" not in issues[0]

    def test_lookup_failure_sets_none_and_returns_false(self):
        issues = [{"key": "RHAISTRAT-100", "fields": {}}]
        with patch(
            "scripts.quality_gate.fetch_child_epics_by_parent",
            side_effect=urllib.error.URLError("jira down"),
        ):
            ok = enrich_issues_with_child_epics(
                issues, self._child_config(), "s", "u", "t")
        assert ok is False
        assert issues[0]["_child_epics"] is None

    def test_lookup_http_5xx_sets_none_and_returns_false(self):
        issues = [{"key": "RHAISTRAT-100", "fields": {}}]
        err = urllib.error.HTTPError(
            "https://jira.example/rest", 503, "Unavailable",
            hdrs=None, fp=None)
        with patch(
            "scripts.quality_gate.fetch_child_epics_by_parent",
            side_effect=err,
        ):
            ok = enrich_issues_with_child_epics(
                issues, self._child_config(), "s", "u", "t")
        assert ok is False
        assert issues[0]["_child_epics"] is None

    def test_lookup_http_4xx_propagates(self):
        issues = [{"key": "RHAISTRAT-100", "fields": {}}]
        err = urllib.error.HTTPError(
            "https://jira.example/rest", 400, "Bad Request",
            hdrs=None, fp=None)
        with patch(
            "scripts.quality_gate.fetch_child_epics_by_parent",
            side_effect=err,
        ):
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                enrich_issues_with_child_epics(
                    issues, self._child_config(), "s", "u", "t")
        assert exc_info.value.code == 400
        assert "_child_epics" not in issues[0]

    def test_lookup_programming_error_propagates(self):
        issues = [{"key": "RHAISTRAT-100", "fields": {}}]
        with patch(
            "scripts.quality_gate.fetch_child_epics_by_parent",
            side_effect=RuntimeError("bug"),
        ):
            with pytest.raises(RuntimeError, match="bug"):
                enrich_issues_with_child_epics(
                    issues, self._child_config(), "s", "u", "t")

    def test_suppress_write_only_when_enrichment_missing(self):
        from scripts.quality_gate import should_suppress_gate_write
        cfg = self._child_config()
        assert should_suppress_gate_write(
            {"key": "X", "_child_epics": None}, cfg) is True
        assert should_suppress_gate_write(
            {"key": "X", "_child_epics": []}, cfg) is False
        assert should_suppress_gate_write(
            {"key": "X", "_child_epics": [{"key": "E-1"}]}, cfg) is False
        assert should_suppress_gate_write(
            {"key": "X"}, {"checks": {"hard_checks": []}}) is False
