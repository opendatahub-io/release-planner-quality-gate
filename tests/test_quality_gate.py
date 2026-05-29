"""Tests for the quality gate orchestrator."""
import json
import os
import pytest

from scripts.quality_gate import (
    build_jql,
    collect_required_fields,
    load_config,
    build_run_data,
    evaluate_issue,
)
from scripts.checks import CheckResult, compute_verdict, instantiate_checks
import scripts.checks.hard_checks  # noqa: F401


# --- JQL Builder ---

class TestBuildJql:
    def test_default_config(self):
        config = {
            "jql": {
                "project": "RHAISTRAT",
                "required_labels": ["strat-creator-human-sign-off"],
                "target_versions": ["rhoai-3.5", "rhoai-3.5.EA1", "rhoai-3.5.EA2"],
                "excluded_statuses": ["Closed", "Resolved"],
                "skip_labels": ["rp-qg1-pass"],
                "order_by": "key ASC",
            }
        }
        jql = build_jql(config)
        assert 'project = RHAISTRAT' in jql
        assert 'labels = "strat-creator-human-sign-off"' in jql
        assert 'cf[10855] IN ("rhoai-3.5", "rhoai-3.5.EA1", "rhoai-3.5.EA2")' in jql
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


# --- collect_required_fields ---

class TestCollectRequiredFields:
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
        assert len(data["issues"]) == 2
        assert "generated_at" in data

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
        assert data["issues"] == []
