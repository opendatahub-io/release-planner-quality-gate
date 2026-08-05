# release-planner-quality-gate

Quality Gate 1: Feature Definition of Ready for Planning. Validates that RHAISTRAT features have RICE scores and priority set before they are considered ready for release planning. Features that pass this gate have been scored, prioritized, and signed off by a human — the minimum bar for entering release planning.

## What This Does

Given a set of RHAISTRAT features (discovered via JQL or specified individually), the pipeline:

1. **Discovers** candidate features from Jira using configurable JQL filters
2. **Evaluates** each feature against a set of hard checks (RICE fields present, priority set, human sign-off label)
3. **Auto-fixes** missing RICE scores using a Claude Code skill that researches the ticket and generates calibrated recommendations
4. **Re-evaluates** auto-fixed features to see if they now pass
5. **Labels** each feature with `rp-qg1-pass` or `rp-qg1-fail`
6. **Reports** results to `artifacts/run-data.json` and `artifacts/run-report.yaml`

The `strat-creator-human-sign-off` label (from the [strat-creator](../strat-creator) pipeline) is a prerequisite — only features that have been through strategy creation and human review are in scope.

## Architecture

**"Agents analyze, scripts decide."**

The Python orchestrator (`quality_gate.py`) handles all deterministic logic: JQL queries, field validation, verdict computation, label management, and Jira writes. The Claude Code skill (`/rice-score`) handles RICE score generation — it reads strategy documents, attachments, linked RFEs, and calibration data to produce scored recommendations.

The skill is **read-only by design**. It outputs structured text that the orchestrator parses and decides whether to write to Jira.

```
quality_gate.py          →  JQL discovery, check evaluation, label management
  ├── checks/            →  Pluggable check framework (field_present, label_present)
  ├── rice_invoker.py    →  Spawns Claude headlessly, parses structured output
  └── report.py          →  Generates JSON + YAML artifacts

/rice-score skill        →  Fetches ticket, reads attachments, applies RICE rubric
  ├── rice-rubric.md     →  Scoring scales, principles, bias guidance
  ├── calibration-examples.md  →  25 scored features for anchoring
  └── jira-fields.md     →  API reference and field IDs
```

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) for dependency management
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) (for RICE auto-generation)
- Jira API credentials:

```bash
export JIRA_SERVER=https://redhat.atlassian.net
export JIRA_USER=your-email@redhat.com
export JIRA_TOKEN=your-api-token
```

### Install

```bash
make install
```

### Run

```bash
# Single issue (testing)
make run-issue-dry ISSUE=RHAISTRAT-1745    # dry-run: generate RICE, no Jira writes
make run-issue ISSUE=RHAISTRAT-1745        # full run: write RICE + apply gate labels

# Batch (pipeline)
make run-dry                                # dry-run: evaluate all candidates
make run                                    # full run: evaluate, fix, label
```

`--dry-run` generates RICE recommendations locally but writes **nothing** to Jira — no fields, no comments, no labels.

## Checks

Gate 1 hard checks align to the [Planning FPDoR](https://redhat.atlassian.net/wiki/spaces/RHAI/pages/442958832/Planning+Phase+-+Definition+of+Ready+Definition+of+Done) mandatory fields (Phase 1):

| Check | Type | What It Validates | Auto-Fixable |
|-------|------|-------------------|--------------|
| `has_rice` | `field_present` | All 4 RICE fields are set (Reach, Impact, Confidence, Effort) | Yes — triggers Claude skill |
| `has_priority` | `field_present` | Priority field is set | No |
| `has_pm` | `field_present` | Product Manager (`customfield_10469`) is set | No |
| `has_delivery_owner` | `field_present` | Assignee (Delivery Owner) is set | No |
| `has_sign_off` | `label_present` | Has `strat-creator-human-sign-off` label | No |
| `has_rubric_pass` | `label_present` | Has `strat-creator-rubric-pass` label (not implied by sign-off) | No |
| `has_components` | `field_present` | At least one component assigned | No |
| `has_release_type` | `field_present` | Release Type (`customfield_10851`) is set | No |
| `has_docs_impact` | `docs_impact` | Product Documentation Required is set; if Yes, `Documentation` component assigned | No |
| `has_target_version` | `field_present` | Target Version (`customfield_10855`) is set | No |

**Verdict**: all checks must pass → `rp-qg1-pass`. Any failure → `rp-qg1-fail`.

Discovery JQL still requires `strat-creator-human-sign-off` so signed-off features missing rubric/PM/owner are evaluated and labeled `rp-qg1-fail` rather than silently skipped.

The check framework is extensible — new check types are registered via `@register_check("type_name")` in `scripts/checks/`.

## RICE Scoring

When a feature fails `has_rice`, the orchestrator invokes the `/rice-score` Claude skill headlessly. The skill:

1. Fetches the target ticket and all its fields
2. Downloads and reads strategy/review attachments (the richest evidence source)
3. Reads linked RFEs for customer context
4. Fetches 20 existing scored features as calibration anchors
5. Applies the RICE rubric and outputs a structured recommendation

### RICE Fields

| Dimension | Field ID | Valid Values | What It Measures |
|-----------|----------|--------------|------------------|
| Reach | `customfield_10862` | 1, 3, 5, 8, 13 | Market size — how many users/accounts benefit |
| Impact | `customfield_10836` | 1, 3, 5, 8, 13 | Per-user depth — how much it moves the needle |
| Confidence | `customfield_10838` | 50%, 75%, 100% | Evidence quality — how sure are we |
| Effort | `customfield_10637` | 1, 2, 3, 5, 8, 13 | Relative complexity — not person-months |
| RICE Score | `customfield_10864` | (auto-calculated) | (Reach × Impact × Confidence%) / Effort |

Effort is relative complexity, not calendar time. E=13 is a red flag that the feature should be split.

## Jira Labels

| Label | Meaning |
|-------|---------|
| `rp-qg1-pass` | Passed Gate 1 — FPDoR Phase 1 hard checks (RICE, priority, PM, delivery owner, rubric + human sign-off, components, release type, docs impact, target version) |
| `rp-qg1-fail` | Failed Gate 1 — missing one or more requirements |
| `rp-qg1-auto-rice` | RICE scores were auto-generated by the Claude skill |

Labels are applied atomically: adding `rp-qg1-pass` removes `rp-qg1-fail` (and vice versa). Existing unrelated labels are untouched.

Discovery does **not** exclude `rp-qg1-pass`. Prior passes stay in scope so tightened hard checks (for example FPDoR Phase 1 or Phase 2) revalidate existing labels. Optional opt-out labels may still be listed under `jql.skip_labels` (for example `rp-qg1-skip`).

On re-runs, the orchestrator evaluates every in-scope candidate, but **skips Jira comment/label writes** when the check result fingerprint (`QG1-FP`) on a **bot-authored** gate comment is unchanged and labels already match. The fingerprint includes a hash of the configured hard-check set, so adding or changing checks invalidates prior fingerprints and forces label/comment updates. Fingerprints from human/other-author comments are ignored for skip decisions. That prevents daily comment churn without freezing stale passes across criteria changes.

Batch runs write `artifacts/run-data.json` **before** applying labels/comments, isolate per-issue Jira write failures (one bad ticket cannot abort the rest), and fall back to posting a new gate comment when updating an existing one returns HTTP 400/403 (edit denied). Gate-comment updates only target comments authored by the authenticated bot — marker matches from humans/other bots are left alone and a new comment is added. Comment lists are fetched once per issue and filtered in memory.

## Testing

```bash
make test              # All tests (87 tests)
make test-unit         # Checks + report only (fast, no server)
make test-integration  # Quality gate + label management (uses jira-emulator)
```

Integration tests use [jira-emulator](https://github.com/ederign/jira-emulator) — an in-memory Jira server that starts per-session and resets state per-test. No real Jira credentials needed for tests.

## Project Structure

```
scripts/
  quality_gate.py       # Main orchestrator — discover, evaluate, fix, label
  rice_invoker.py       # Headless Claude skill invocation + output parsing
  report.py             # JSON + YAML artifact generation
  jira_utils.py         # Shared Jira API utilities (from strat-creator)
  checks/
    __init__.py          # Check framework — BaseCheck, registry, verdict logic
    hard_checks.py       # field_present + label_present check implementations

tests/
  conftest.py            # jira-emulator fixtures
  test_checks.py         # Check framework + all check types
  test_quality_gate.py   # JQL builder, config, evaluate, run-data
  test_label_management.py  # Atomic label swap logic
  test_rice_invoker.py   # Structured output parsing
  test_report.py         # Report generation

config/
  pipeline-settings.yaml # JQL filters, check definitions, field IDs, labels

.claude/skills/rice-score/
  SKILL.md               # Skill definition — workflow, output format
  references/
    rice-rubric.md       # Scoring scales and principles
    calibration-examples.md  # 25 scored features for anchoring
    jira-fields.md       # API reference and field IDs
```
