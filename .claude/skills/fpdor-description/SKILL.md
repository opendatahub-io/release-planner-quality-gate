---
name: fpdor-description
description: >-
  Optional manual helper to evaluate Feature Planning Definition of Ready
  (FPDoR) description criteria for a RHAISTRAT or AIPCC Feature/Initiative.
  Read-only. Not used by CI quality_gate.py — the gate uses the deterministic
  Org Pulse description scanner instead.
argument-hint: "[Jira issue key]"
user-invocable: true
---

# FPDoR Description Criteria Evaluation (optional / manual)

Evaluate **description-based** FPDoR planning criteria for a single Feature or
Initiative. This skill is **read-only** — it does NOT write to Jira.

**Important:** `quality_gate.py` does **not** invoke this skill. CI evaluates
description criteria with `scripts/description_signals.py` (Org Pulse
`parseDescriptionSignals` port) plus label/field shortcuts. Use this skill only
for ad-hoc human review when you want Claude to inspect attachments as well.

Do **not** score Jira fields (RICE, PM, Target Version, components, etc.).
Those are deterministic checks outside this skill.

## Reference Files

Read before evaluating:
- `references/fpdor-criteria.md` — Pass / fail / na rules aligned to Org Pulse FPDoR
- `references/output-contract.md` — Exact structured output format

## Input

A single Jira key: `/fpdor-description RHAISTRAT-1745`

## Workflow

### Step 1: Fetch the ticket

```bash
curl -s -u "$JIRA_USER:$JIRA_TOKEN" \
  "$JIRA_SERVER/rest/api/3/issue/{{TICKET_KEY}}?fields=summary,description,status,labels,components,issuetype,issuelinks,attachment,project"
```

If the issue is missing or inaccessible, emit `FPDOR_DESCRIPTION_ERROR` (see
output contract) and stop.

### Step 2: Gather description evidence (priority order)

1. **Jira description** (ADF) — primary source for Legacy Features.
2. **Attachments** — especially `*-strategy.md` / strategy docs from AI SDLC;
   these often contain requirements, AC, risks, and architecture.
3. Do **not** treat comments as sufficient evidence for criteria pass (comments
   are noisy); attachments + description only.

Download useful attachments:
```bash
curl -s -u "$JIRA_USER:$JIRA_TOKEN" \
  "$JIRA_SERVER/rest/api/3/attachment/content/{attachmentId}" -L
```

### Step 3: Evaluate each description criterion

Use `references/fpdor-criteria.md`. For each criterion return exactly one of:
`pass`, `fail`, or `na`.

| Criterion key | What to look for |
|---------------|------------------|
| `requirements_clarity` | Problem/scope/requirements/use-case content |
| `acceptance_criteria` | Testable acceptance or success criteria |
| `risks_assumptions` | Risks, assumptions, constraints, or blockers |
| `architectural_alignment` | Architecture notes, design/ADR/RFC, or explicit “not required” |
| `uxd_description` | Explicit “N/A – no UX/UI” style note (component is checked elsewhere) |
| `cross_team_deps_language` | Cross-team / multi-component dependency language |

**Empty or near-empty description and no useful attachments:**
- `requirements_clarity`, `acceptance_criteria`, `risks_assumptions` → `fail`
- `architectural_alignment`, `uxd_description` → `na`
- `cross_team_deps_language` → `fail`

### Step 4: Emit structured output

Emit **exactly one** block in the format from `references/output-contract.md`.
Evidence lines must be short (≤200 chars) quotes or paraphrases.

## Constraints

- Read-only: no Jira writes, no label changes.
- Be conservative on `pass` — require clear evidence.
- Prefer `na` over `fail` when Org Pulse treats the item as not-checked
  (architecture without signals; UXD without N/A note).
- Do not invent RFE/link/label passes — the orchestrator handles those.
- Remember: production gate labeling uses the scanner, not this skill.
