# Output Contract — `/fpdor-description`

The skill must emit **exactly one** of the following blocks so
`scripts/description_invoker.py` can parse it reliably.

Evidence values: single line, ≤200 characters, no newlines. Use `-` if none.

Verdict values: lowercase `pass`, `fail`, or `na` only.

---

## Success block

```
FPDOR_DESCRIPTION_START
TICKET: RHAISTRAT-1745
REQUIREMENTS_CLARITY: pass
REQUIREMENTS_CLARITY_EVIDENCE: Section "Requirements" describes problem and in-scope work.
ACCEPTANCE_CRITERIA: fail
ACCEPTANCE_CRITERIA_EVIDENCE: -
RISKS_ASSUMPTIONS: pass
RISKS_ASSUMPTIONS_EVIDENCE: "Risks" lists dependency on Serving API freeze.
ARCHITECTURAL_ALIGNMENT: na
ARCHITECTURAL_ALIGNMENT_EVIDENCE: -
UXD_DESCRIPTION: na
UXD_DESCRIPTION_EVIDENCE: -
CROSS_TEAM_DEPS_LANGUAGE: fail
CROSS_TEAM_DEPS_LANGUAGE_EVIDENCE: -
FPDOR_DESCRIPTION_END
```

Field order is fixed. Do not omit fields. Do not add extra keys inside the block.

---

## Error block

When the issue cannot be fetched or evaluated:

```
FPDOR_DESCRIPTION_ERROR: RHAISTRAT-1745 — issue not found or inaccessible
```

---

## Notes for the orchestrator

- Fingerprint / skip logic should hash **verdicts only**, not evidence text.
- Label shortcuts (`strat-creator-rubric-pass`, human sign-off, etc.) are applied
  **before** invoking this skill; the skill must not assume those labels.
