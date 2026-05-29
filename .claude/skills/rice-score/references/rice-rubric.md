# RICE Scoring Rubric for RHAI

**Formula**: RICE Score = (Reach x Impact x Confidence) / Effort

Jira auto-calculates the RICE Score when all four fields are entered. The "Prioritization" tab appears on a Feature once any RICE field has an entry.

RICE scores are **relative**, not absolute. They are meaningful only when compared to other scores in the same backlog. A score of 40 is not inherently "good" or "bad" — it only matters relative to the other features being scored in the same cycle.

---

## Reach (Market)

How many users or customers will be affected within a given time period (default: per quarter).

Reach measures **breadth** — who encounters this feature, not how much it helps them (that is Impact). Use real data when available: telemetry, user counts, segment sizes. Avoid pulling numbers from intuition when analytics exist.

| Score | Meaning | Guidance |
|---|---|---|
| 1 | Very few users (niche request) | Single customer or a handful of power users. No broader applicability. |
| 3 | Small user group (<10% of users) | A specific persona or deployment pattern. Named customers can be listed. |
| 5 | Moderate user group (10-30% of users) | A meaningful segment — e.g., all GPU users, all model-serving users. |
| 8 | Large group (30-70% of users) | Most users in the product's core workflows are touched. |
| 13 | Nearly all users (>70%) | Foundational change affecting virtually every user of the platform. |

### Reach Pitfalls
- **Inflating via total user count**: Do not use "all registered users" when only a segment is affected. Define who is "reached" — a user who *encounters* the feature, not one who merely exists in the system.
- **Platform/infrastructure features**: For features users benefit from indirectly (e.g., cost optimization, platform reliability), Reach is the full population that benefits from the outcome, even if they never interact with the feature directly.
- **Confusing Reach with Impact**: A login-flow fix reaches 100% of users (R=13) but may have low per-user Impact. A niche ML pipeline feature reaches 5% (R=3) but may be high Impact for them. Score them independently.

---

## Impact (Customer/System)

How much this will benefit **each individual** user who is reached. Impact is depth per person, not total business value.

| Score | Meaning | Guidance |
|---|---|---|
| 1 | Minimal | Small quality-of-life polish. Users barely notice. |
| 3 | Low | Slight workflow improvement or minor feature addition. Saves minutes, not hours. |
| 5 | Medium | Noticeable productivity or capability gain. Users would mention it in a review. |
| 8 | High | Major pain point solved or significant new capability. Changes how users work. |
| 13 | Massive / Non-negotiable | Strategic differentiator, or legal/compliance/security requirement with hard deadlines. |

### Impact Assessment Checklist
Score Impact by asking these questions (answer yes to move up the scale):
- **Pain severity**: How painful is the status quo? Workarounds exist (lower) vs. blocked entirely (higher).
- **Frequency**: How often do affected users hit this? Daily (higher) vs. once per release (lower).
- **Alternatives**: Can users achieve this with existing features or workarounds? Easy workaround (lower) vs. impossible without this (higher).
- **Blocking other work**: Does this unblock other teams, features, or customer deployments?
- **Market positioning**: Does this open new markets, close competitive gaps, or defend existing ones?

### Impact Pitfalls
- **"Everything is high impact"**: If more than ~20% of features in a scoring cycle get I=8 or I=13, the scale is inflated. Force-rank: would you trade Feature A's impact for Feature B's? If yes, one of them is scored too high.
- **Confusing business value with per-user impact**: A feature that saves the company $1M but affects 3 users has high *business value* but the per-user impact might only be I=5. Score per-user impact here; business value is captured by the R x I product.
- **AI/ML-specific**: Model accuracy improvements, training pipeline features, and inference optimizations should be scored on the user-perceived outcome (faster results, better predictions, lower cost), not on the technical sophistication.

---

## Confidence

How certain you are of your Reach and Impact estimates. Confidence applies only to Reach and Impact — the Effort score accounts for uncertainty independently.

Confidence is the **bias brake** in the formula. It penalizes optimism that lacks evidence. Be honest — defaulting to 100% defeats the purpose of this factor.

| Score | Meaning | Evidence Required |
|---|---|---|
| 50% | Hypothesis or guesswork | No direct customer data. Internal assumption or competitive guess. Strategy review flagged concerns. Unresolved upstream dependencies. |
| 75% | Some evidence, still assumptions | Approved RFE with some customer evidence. Named customer demand. Competitive analysis. Strategy review passed (7-8/8). Anecdotal evidence from support tickets or sales calls. |
| 100% | Strong evidence, high certainty | Multiple validated customer requests. Telemetry data confirming reach/impact. Approved RFE with field validation. Legal/compliance requirement with documented mandate. |

### Confidence Calibration Rules
1. **No user data = 50%, period.** If you cannot point to a specific data source (telemetry, customer interviews, support tickets, RFE votes), your confidence is 50%.
2. **Anecdotal evidence caps at 75%.** Support tickets and sales anecdotes are evidence, but not validated. They get you to 75%, not 100%.
3. **100% requires measurable evidence.** Analytics, survey results with statistical significance, multiple independent customer confirmations, or legal mandates.
4. **Strategy review as signal**: A strategy review that recommended REVISE should push Confidence toward 50%. A review that passed with high marks (7-8/8) supports 75%.
5. **Confidence covers Reach AND Impact uncertainty.** If you are confident about Reach but uncertain about Impact (or vice versa), use the lower confidence level.

### Confidence Anti-Patterns
- **Defaulting to 100%**: The most common error. If everyone scores 100%, the Confidence factor becomes meaningless and the formula degrades to (R x I) / E.
- **Anchoring to the proposer's enthusiasm**: The person who proposed the feature will almost always overestimate confidence. Cross-reference with independent data.
- **Recency bias**: A loud recent customer complaint does not make something 100% confidence. Ask: is this representative, or is it one data point?

---

## Effort

High-level relative effort estimate. RHAI uses relative scoring (not person-months) to avoid false precision around complexity, dependencies, and unknowns.

Effort must include **all work**: design, engineering, QA, documentation, cross-team coordination, and deployment/rollout. Not just "dev time."

| Score | Meaning | Guidance |
|---|---|---|
| 1 | Low effort | Few unknowns, reasonable scope, one team, fits in a sprint. |
| 2 | Medium effort | Some unknowns, may involve a couple of teams, may exceed a sprint. |
| 3 | Medium+ | Some unknowns, cross-team effort, may require feature story mapping once prioritized. |
| 5 | High effort | Multiple unknowns, multiple teams, will likely require feature story mapping. |
| 8 | Massive effort | Multiple unknowns and dependencies, likely involves work outside our organization, absolutely requires story mapping and may need to be split into additional features. |
| 13 | Too large to estimate | Must be broken into smaller features before scoring. Flag to PM immediately. |

### Effort Assessment Guidance
- **Include hidden work**: Design, testing, documentation, migration paths, backward compatibility, and the coordination cost of cross-team work. Teams consistently underestimate by omitting these.
- **Dependencies increase effort**: If this feature is blocked by another ticket not yet started, or requires upstream work from outside the team, bump effort up by at least one tier.
- **AI/ML-specific effort**: Model training, data pipeline work, hyperparameter tuning, and inference optimization have unpredictable timelines. If the feature involves ML research or experimentation, add at least one tier to account for iteration cycles.
- **Trust strategy reviews**: If a strategy review disagreed with the original sizing, use the review's assessment.
- **E=13 is not a score, it is an action item**: It means "stop scoring and go break this down." Do not leave features at E=13 in the backlog.

### Effort Red Flags
- Strategy review disagreed with original sizing → trust the review
- Multiple teams + unresolved technical questions → bump effort up
- "We haven't done this before" → bump effort up (novelty risk)
- "Must be broken down" → E=13, flag to PM
- Requires changes to APIs or interfaces consumed by external teams → bump effort up

---

## Scoring Principles

### 1. Score Each Factor Independently
Do not let one factor influence another. A feature can be high Reach + low Impact, or low Reach + high Impact. The formula combines them; you should not.

### 2. RICE Informs Decisions, It Does Not Make Them
RICE produces a relative ranking, not a verdict. Valid reasons to override the ranking include:
- **Dependencies**: A lower-scoring feature may need to ship first to unblock a higher-scoring one. Document the trade-off.
- **Table stakes**: A feature may be required to sell to a market segment regardless of its score.
- **Strategic commitments**: Executive or customer commitments may override the ranking.
- **Regulatory deadlines**: Compliance work ships on the deadline's schedule, not the backlog's.

When overriding, document the reason in Jira so stakeholders can see the trade-off.

### 3. Guard Against Score Inflation
- Apply the "20% rule": no more than ~20% of features in a cycle should score at the top tier (8 or 13) for any single factor.
- Ask the **consider-the-opposite** question: "What evidence would make this score lower?" If you cannot answer, your score is too high.
- Score independently before comparing with others. Seeing someone else's scores first creates anchoring bias.

### 4. Dependencies Are Scored, Not Ignored
RICE does not natively model dependencies. Handle them as follows:
- **Blocking dependency on unstarted work**: Reduce Confidence (the unblocked value is uncertain until the blocker ships) or increase Effort (the total work includes the dependency).
- **Enabling/foundational features**: Score Reach and Impact based on the outcomes they unlock, not on the feature in isolation. Document which downstream features depend on this one.
- **Cross-team dependencies**: Factor coordination overhead into Effort.

### 5. Scores Are Living Numbers
Re-score when any of these triggers occur:
- **New data**: Customer research, telemetry, or market analysis that changes Reach or Impact estimates.
- **Scope change**: The feature's scope expanded or contracted significantly.
- **Strategy review**: A review recommended REVISE or changed the confidence/effort assessment.
- **Dependency resolved or introduced**: A blocker was completed (reducing effort/increasing confidence) or a new dependency was discovered.
- **Market shift**: Competitive landscape changed, regulatory requirement emerged or was dropped.
- **Quarterly cadence**: At minimum, re-examine scores at the start of each planning cycle. Reach estimates drift as markets shift, and Confidence should increase as discovery work completes.

### 6. Bias Awareness
Common cognitive biases that distort RICE scores:
- **Anchoring**: The first score suggested for a feature influences all subsequent discussion. Mitigate by having scorers write down their scores independently before sharing.
- **Recency**: A feature mentioned in last week's customer call feels more important than one from last quarter's research. Mitigate by referencing aggregate data, not individual anecdotes.
- **Optimism**: Teams inflate Reach and Impact for features they are excited about. Mitigate by using the Confidence factor honestly — excitement without evidence is 50%.
- **Sunk cost**: "We already started this" is not a reason to score it higher. Score the remaining value, not the invested effort.

---

## Comment Convention

Post a Jira comment starting with **"RICE SCORE JUSTIFICATION:"** documenting the rationale for each score. Include:
- The specific evidence or data source behind each score
- Any assumptions made (especially for Confidence < 100%)
- Dependencies that affected Effort or Confidence
- Whether any factor was an override of a previous score, and why
