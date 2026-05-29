"""Tests for report generation."""
import json
import os

import yaml
import pytest

from scripts.report import generate_run_report, write_reports


SAMPLE_RUN_DATA = {
    "generated_at": "2026-05-29T14:00:00+00:00",
    "dry_run": False,
    "mode": "batch",
    "summary": {"total": 3, "pass": 2, "fail": 1},
    "issues": [
        {
            "key": "RHAISTRAT-100",
            "verdict": "pass",
            "checks": {
                "has_rice": {"passed": True, "details": "All 4 fields present",
                             "auto_fixable": False},
                "has_priority": {"passed": True, "details": "All 1 fields present",
                                 "auto_fixable": False},
                "has_sign_off": {"passed": True, "details": "All required labels present",
                                 "auto_fixable": False},
            },
        },
        {
            "key": "RHAISTRAT-101",
            "verdict": "pass",
            "checks": {
                "has_rice": {"passed": True, "details": "All 4 fields present",
                             "auto_fixable": False},
                "has_priority": {"passed": True, "details": "All 1 fields present",
                                 "auto_fixable": False},
                "has_sign_off": {"passed": True, "details": "All required labels present",
                                 "auto_fixable": False},
            },
        },
        {
            "key": "RHAISTRAT-102",
            "verdict": "fail",
            "checks": {
                "has_rice": {"passed": False, "details": "Missing fields: customfield_10862",
                             "auto_fixable": True},
                "has_priority": {"passed": True, "details": "All 1 fields present",
                                 "auto_fixable": False},
                "has_sign_off": {"passed": True, "details": "All required labels present",
                                 "auto_fixable": False},
            },
        },
    ],
}


class TestGenerateRunReport:
    def test_basic_structure(self):
        report = generate_run_report(SAMPLE_RUN_DATA)
        assert report["title"] == "Release Quality Gate 1: Feature Definition of Ready for Planning"
        assert report["dry_run"] is False
        assert report["mode"] == "batch"
        assert report["summary"]["total"] == 3
        assert report["summary"]["pass"] == 2
        assert report["summary"]["fail"] == 1

    def test_separates_passed_and_failed(self):
        report = generate_run_report(SAMPLE_RUN_DATA)
        assert len(report["passed_issues"]) == 2
        assert len(report["failed_issues"]) == 1
        assert report["failed_issues"][0]["key"] == "RHAISTRAT-102"

    def test_all_pass_no_failed_key(self):
        data = {
            **SAMPLE_RUN_DATA,
            "issues": [i for i in SAMPLE_RUN_DATA["issues"]
                       if i["verdict"] == "pass"],
        }
        report = generate_run_report(data)
        assert "failed_issues" not in report
        assert len(report["passed_issues"]) == 2

    def test_all_fail_no_passed_key(self):
        data = {
            **SAMPLE_RUN_DATA,
            "issues": [i for i in SAMPLE_RUN_DATA["issues"]
                       if i["verdict"] == "fail"],
        }
        report = generate_run_report(data)
        assert "passed_issues" not in report
        assert len(report["failed_issues"]) == 1

    def test_empty_issues(self):
        data = {**SAMPLE_RUN_DATA, "issues": []}
        report = generate_run_report(data)
        assert "passed_issues" not in report
        assert "failed_issues" not in report

    def test_single_mode_includes_key(self):
        data = {
            **SAMPLE_RUN_DATA,
            "mode": "single",
            "issue_key": "RHAISTRAT-100",
        }
        report = generate_run_report(data)
        assert report["issue_key"] == "RHAISTRAT-100"
        assert report["mode"] == "single"

    def test_dry_run_flag(self):
        data = {**SAMPLE_RUN_DATA, "dry_run": True}
        report = generate_run_report(data)
        assert report["dry_run"] is True


class TestWriteReports:
    def test_writes_both_files(self, tmp_path):
        json_path, yaml_path = write_reports(SAMPLE_RUN_DATA, str(tmp_path))
        assert os.path.exists(json_path)
        assert os.path.exists(yaml_path)

    def test_json_is_valid(self, tmp_path):
        json_path, _ = write_reports(SAMPLE_RUN_DATA, str(tmp_path))
        with open(json_path) as f:
            data = json.load(f)
        assert data["summary"]["total"] == 3

    def test_yaml_is_valid(self, tmp_path):
        _, yaml_path = write_reports(SAMPLE_RUN_DATA, str(tmp_path))
        with open(yaml_path) as f:
            report = yaml.safe_load(f)
        assert report["title"].startswith("Release Quality Gate 1")
        assert len(report["failed_issues"]) == 1

    def test_creates_output_dir(self, tmp_path):
        out = str(tmp_path / "nested" / "dir")
        json_path, yaml_path = write_reports(SAMPLE_RUN_DATA, out)
        assert os.path.exists(json_path)
        assert os.path.exists(yaml_path)
