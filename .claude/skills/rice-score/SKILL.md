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

**Strategy and review attachments are the richest source of evidence.** The Jira
description has limited formatting (ADF), but the attached strategy and review
documents contain the full analysis from the strat-creator pipeline.

#### 3a. Download and read attachments (highest priority)

List attachments from the ticket's `attachment` field. Look for:
- **Strategy document** (`*-strategy.md` or the main `.md` attachment): Contains the
  full refined strategy — HOW, dependencies, impacted teams/components, effort estimates,
  risks, acceptance criteria, non-functional requirements, and scope boundaries.
- **Review document** (`*-review.md`): Contains 4-dimension review scores (feasibility,
  testability, scope, architecture, each 0-2) with detailed prose feedback from
  independent reviewers. Total score out of 8.

Download each attachment:
```bash
curl -s -u "$JIRA_USER:$JIRA_TOKEN" \
  "$JIRA_SERVER/rest/api/3/attachment/content/{attachmentId}" -L
```

**How attachment content maps to RICE dimensions:**
- Strategy's **effort estimate and team count** → RICE Effort
- Strategy's **dependencies and risks** → RICE Effort and Confidence
- Strategy's **scope and acceptance criteria** → RICE Reach (who benefits)
- Review's **total score (X/8)** → RICE Confidence (7-8/8 = 75-100%, 3-6/8 = 50-75%)
- Review's **feasibility verdict** → RICE Effort (reject/revise = bump effort up)
- Review's **scope verdict** → RICE Reach and Effort (scope too large = higher effort)

#### 3b. Read the description

The Jira description may contain a summary of the strategy or the business need.
It complements but does not replace the attachment content.

#### 3c. Follow issuelinks to linked RFEs

Read linked RHAIRFE tickets for customer context, approval status, and priority labels.
RFE comments often contain customer evidence that informs Reach and Impact.

#### 3d. Read all comments

Check for reviewer feedback, strategy review scores, sizing disagreements,
and any RICE scoring discussions or prior justifications.

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
