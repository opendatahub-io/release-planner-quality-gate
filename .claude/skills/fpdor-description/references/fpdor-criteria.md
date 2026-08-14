# FPDoR Description Criteria (QG1)

Aligned to Org Pulse Features List FPDoR (`fpdor.js` + `description-scanner.js`)
and Confluence Planning Phase DoR. This skill evaluates **description /
attachment evidence only**. Label and field shortcuts are applied by the
orchestrator, not this skill.

Verdicts: `pass` | `fail` | `na`

- **`pass`** — clear evidence in description or strategy attachment
- **`fail`** — content was expected and is missing or too vague
- **`na`** — not checked (Org Pulse uses null / not-checked); does **not** block gate pass

Be conservative on `pass`. Prefer `na` over `fail` only where Org Pulse does.

---

## requirements_clarity

**Pass** when the description or strategy attachment has substantive content for
at least one of:

- Problem statement / goals / high-level requirements
- Scope (in/out of scope, non-goals)
- Use cases / user stories

Vague one-liners without problem, scope, or requirements do **not** pass.

**Fail** when description/attachments are empty or lack those signals.

**na** — not used (always pass or fail).

---

## acceptance_criteria

**Pass** when there are testable acceptance or success criteria, for example:

- An “Acceptance criteria” / “Success criteria” / “Definition of done” section
- Given/When/Then (or equivalent) criteria
- Measurable success conditions (“measured by…”)

Capability slogans (“users can easily…”, “works correctly”) without verification
do **not** pass (same spirit as strat-creator testability review).

**Fail** when no AC/success criteria are present.

**na** — not used.

---

## risks_assumptions

**Pass** when risks, assumptions, constraints, dependencies, or blockers are
documented (dedicated section or clear prose).

**Fail** when none are present.

**na** — not used.

---

## architectural_alignment

**Pass** when:

- There is architecture / technical design / system design / ADR / RFC content, **or**
- The text explicitly says architecture is **not required** (e.g. “architecture not required”, “no architecture review required”)

**na** when there is content but no architecture signal and no “not required”
note (Org Pulse: not-checked, not a hard fail).

**Fail** — avoid unless the ticket claims architecture work is mandatory and
provides nothing; default to `na` when unsure.

---

## uxd_description

Only the **description N/A note**. UXD **component** assignment is checked
elsewhere by the orchestrator.

**Pass** when the description explicitly states UX/UI is not needed, e.g.:

- `N/A – no UX` / `N/A – no UI`
- `no UX required` / `no UXD required` / `no UI required`

**na** when there is no such note (component may still pass the field check).

**Fail** — not used for description-only evaluation (missing note → `na`).

---

## cross_team_deps_language

Only **language** in description/attachments. Multi-component counts and
`epic-creator-auto-decomposed` are orchestrator concerns.

**Pass** when dependency / cross-team language is present, e.g.:

- “depends on”, “cross-team”, “cross-functional”, “multi-team”, “multi-component”

**Fail** when no such language is present (orchestrator may still pass via
≥2 eng components or epic-creator label).

**na** — not used.

---

## Empty description + no useful attachments

| Criterion | Verdict |
|-----------|---------|
| requirements_clarity | fail |
| acceptance_criteria | fail |
| risks_assumptions | fail |
| architectural_alignment | na |
| uxd_description | na |
| cross_team_deps_language | fail |
