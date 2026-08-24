# Org Pulse ↔ QG1 FPDoR alignment

Shared rule (Planning Domain standup, Aug 24 2026): **every feature is scored against a fixed 17-item FPDoR checklist**. Items that do not apply count as **pass (N/A)** — they do not shrink the denominator. Only real failures block `rp-qg1-pass`.

Source of truth for UI scoring: Org Pulse `modules/releases/server/planning/fpdor.js` ([Confluence FPDoR](https://redhat.atlassian.net/wiki/spaces/RHAI/pages/442958832)).

## Scoring

| System | Denominator | N/A handling | Blocks pass |
|--------|-------------|--------------|-------------|
| Org Pulse | `totalCount = 17` always | `pass: true`, `state: 'not-applicable'` | `pass === false` only |
| QG1 | `FPDOR_TOTAL_COUNT = 17` | `passed=True`, `not_applicable=True` | `passed=False` (non-N/A, non-infra) |

Gate comments and `run-data.json` include: **`Score: X/17 (Y N/A, Z FAIL)`**.

## The 17 checks (QG1 `pipeline-settings.yaml`)

| # | Org Pulse item | QG1 check | Type |
|---|----------------|-----------|------|
| 1 | Target Version | `has_target_version` | field |
| 2 | Release Type | `has_release_type` | field |
| 3 | Components | `has_components` | field |
| 4 | PM | `has_pm` | field |
| 5 | Delivery Owner | `has_delivery_owner` | field |
| 6 | Priority | `has_priority` | field |
| 7 | RICE | `has_rice` | field (+ auto-fix) |
| 8 | Docs impact | `has_docs_impact` | docs_impact |
| 9 | Requirements clarity | `has_requirements_clarity` | description |
| 10 | Acceptance criteria | `has_acceptance_criteria` | description |
| 11 | Risks & assumptions | `has_risks_assumptions` | description |
| 12 | Architectural alignment | `has_architectural_alignment` | description |
| 13 | UXD | `has_uxd_description` | description |
| 14 | Cross-team deps | `has_cross_team_deps` | description |
| 15 | Feature human sign-off | `has_sign_off` | label (AI First only) |
| 16 | Child epics | `has_child_epics` | structural |
| 17 | *(QG1-specific)* | `has_rubric_pass` | label (AI First only) |

### Item mapping differences

| Topic | Org Pulse | QG1 |
|-------|-----------|-----|
| **Source RFE / AI SDLC** | Separate criteria item (`evalSourceRfe`) | **Not a separate check.** Partial overlap via `strat-creator-auto-created` on description shortcuts only. |
| **Strategy rubric pass** | Not a separate item; `strat-creator-rubric-pass` shortcuts description criteria | **Separate AI First check** `has_rubric_pass` |
| **Human sign-off** | `strat-creator-human*` prefix | Exact label `strat-creator-human-sign-off` |
| **Child epics** | Accepts `epic-creator-auto-decomposed` label | Structural only — real child Epics in eng projects |
| **Components** | ≥1 **engineering** component (excludes Docs/UXD) | Any non-empty `components` field |

## N/A by path

| Check | Legacy (no `strat-creator-*`) | AI First (`strat-creator-*` labels) |
|-------|------------------------------|-------------------------------------|
| `has_sign_off` | **N/A** — not an AI First feature | Required (`strat-creator-human-sign-off`) |
| `has_rubric_pass` | **N/A** — not an AI First feature | Required (`strat-creator-rubric-pass`) |
| `has_architectural_alignment` | N/A when description has no architecture signals and architecture is not marked “not required” | Same |
| `has_uxd_description` | N/A when no UXD component and no “N/A – no UX” in description | Same |

On **Legacy** features, Org Pulse still evaluates rubric-backed description criteria (requirements, acceptance, risks, architecture shortcuts via description). QG1 does the same — only the two **label** checks are N/A.

## Dry-run examples (fixture parity)

### Legacy — `AIPCC-LEGACY` fixture (`tests/test_checks.py`)

| Metric | Org Pulse (expected) | QG1 |
|--------|---------------------|-----|
| Score | 17/17 | 17/17 |
| N/A | 2 (sign-off, rubric) | 2 (`has_sign_off`, `has_rubric_pass`) |
| FAIL | 0 | 0 |
| Verdict | ready | `pass` |

### AI First — `RHAISTRAT-100` fixture (`FULL_PASSING_ISSUE`)

| Metric | Org Pulse (expected) | QG1 |
|--------|---------------------|-----|
| Score | 17/17 | 17/17 |
| N/A | 0 | 0 |
| FAIL | 0 | 0 |
| Verdict | ready | `pass` |

Run locally:

```bash
pytest tests/test_checks.py::TestInstantiateChecks::test_legacy_full_pass_matches_org_pulse_seventeen -v
pytest tests/test_checks.py::TestInstantiateChecks::test_full_pass_scenario -v
```

Live Jira dry-run (check evaluation only — no RICE auto-fix, no Jira writes):

```bash
# Legacy (no strat-creator-* labels) — example RHAISTRAT-96
# Score: 9/17 (4 N/A, 8 FAIL) — N/A: sign-off, rubric, architecture, UXD

# AI First (strat-creator-* labels) — example RHAISTRAT-2469
# Score: 12/17 (1 N/A, 5 FAIL) — N/A: UXD only; sign-off/rubric required
```

Full path with auto-RICE:

```bash
make run-issue-dry ISSUE=RHAISTRAT-96      # Legacy
make run-issue-dry ISSUE=RHAISTRAT-2469    # AI First
```

Compare QG1 gate-comment **Score** line with Org Pulse Component load **X/17** for the same key.
