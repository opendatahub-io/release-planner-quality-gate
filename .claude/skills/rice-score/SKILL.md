---
name: rice-score
description: >-
  Research a RHAISTRAT Feature ticket and recommend RICE scores (Reach, Impact,
  Confidence, Effort). Read-only — outputs structured recommendations for the
  Python orchestrator to write to Jira. Used headlessly by quality_gate.py.
---

# RICE Scoring for Release Quality Gate

Research a single RHAISTRAT Feature ticket and recommend RICE scores. This skill
is **read-only** — it does NOT write to Jira. The Python orchestrator handles
all Jira writes.

## Reference Files

Read these before scoring:
- `references/rice-rubric.md` — Full RICE rubric with scoring scales
- `references/jira-fields.md` — Jira custom field IDs and API reference
- `references/calibration-examples.md` — Scored examples from our batch for anchoring

## Input

A single Jira key passed as the skill argument: `/rice-score RHAISTRAT-1745`

## Workflow

### Step 1: Fetch the Target Ticket

Fetch the full ticket with all relevant fields:
```bash
curl -s -u "$JIRA_USER:$JIRA_TOKEN" \
  "$JIRA_SERVER/rest/api/3/issue/{{TICKET_KEY}}?fields=summary,description,status,comment,issuelinks,attachment,issuetype,parent,priority,labels,customfield_10862,customfield_10836,customfield_10838,customfield_10637,customfield_10864"
```

### Step 2: Build Calibration Data

Fetch existing RICE-scored issues for relative positioning:
```bash
curl -s -u "$JIRA_USER:$JIRA_TOKEN" "$JIRA_SERVER/rest/api/3/search/jql" \
  -H "Content-Type: application/json" \
  -d '{"jql": "project = RHAISTRAT AND labels = \"strat-creator-human-sign-off\" AND cf[10862] IS NOT EMPTY ORDER BY key ASC", "fields": ["summary","customfield_10862","customfield_10836","customfield_10838","customfield_10637","customfield_10864"], "maxResults": 20}'
```

Format as calibration anchors:
```
- RHAISTRAT-XXXX (Summary): R=X, I=X, C=XX%, E=X, RICE=X.X
```

Also read the examples in `references/calibration-examples.md` for additional context.

### Step 3: Research the Ticket

Gather all available evidence:
1. Read the description thoroughly
2. Download and read strategy attachments (review docs, refined strategies)
3. Follow issuelinks to read linked RFE tickets for customer context and approval status
4. Read all comments for reviewer feedback, strategy review scores, sizing disagreements

### Step 4: Apply the RICE Rubric

Score each dimension using `references/rice-rubric.md`. Key principles:
- **Calibrate, don't score in isolation** — justify relative to sibling tickets
- **Trust strategy reviews over original estimates** — reviews reflect multi-reviewer assessment
- **Confidence reflects evidence quality, not feature importance**
- **Effort captures coordination cost** — team count and dependency chains matter
- **Flag re-scoring triggers** — note what would change the score

### Step 5: Output Structured Recommendation

Output the recommendation in this exact format so the Python orchestrator can parse it:

```
RICE_RECOMMENDATION_START
TICKET: {{TICKET_KEY}}
REACH: <value>
IMPACT: <value>
CONFIDENCE: <value as percentage: 50, 75, or 100>
EFFORT: <value>
EXPECTED_RICE: <calculated score>
JUSTIFICATION:
<Multi-line justification text explaining each dimension's score,
calibration context vs siblings, key evidence, and re-scoring triggers.>
RICE_RECOMMENDATION_END
```

Valid values:
- Reach: 1, 3, 5, 8, 13
- Impact: 1, 3, 5, 8, 13
- Confidence: 50, 75, 100
- Effort: 1, 2, 3, 5, 8, 13

## Error Handling

- **Ticket not found**: Output `RICE_ERROR: Ticket {{KEY}} not found`
- **RICE fields already set**: Output `RICE_ALREADY_SCORED: {{KEY}} R=X I=X C=X% E=X RICE=X.X`
- **No attachments**: Score from description, links, and comments. Note reduced confidence.
- **Effort = 13**: Flag in justification that the feature must be broken down.
