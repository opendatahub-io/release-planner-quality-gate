# RICE Scoring Rubric for RHAI

**Formula**: RICE Score = (Reach x Impact x Confidence) / Effort

Jira auto-calculates the RICE Score when all four fields are entered. The "Prioritization" tab appears on a Feature once any RICE field has an entry.

## Reach (Market)

How many people will be affected in a given time period.

| Score | Meaning |
|---|---|
| 1 | Very few users (niche request) |
| 3 | Small user group (<10% of users) |
| 5 | Moderate user group (10-30% of users) |
| 8 | Large group (30-70% of users) |
| 13 | Nearly all users (>70%) — game changer for the industry |

## Impact (Customer/System)

How much this will benefit those affected or contribute to the goal.

| Score | Meaning |
|---|---|
| 1 | Minimal (small QoL improvement) |
| 3 | Low (slight improvement in workflow or minor feature) |
| 5 | Medium (noticeable productivity or revenue gain) |
| 8 | High (major pain point solved, new capability) |
| 13 | Massive (game-changer, strategic differentiator) or Non-negotiable (legal requirement) |

Impact should also capture:
- **Pain level** — are we solving a common pain?
- **Blocking other work** — is this blocking other initiatives?
- **Addressing new market** — does this open traction or new markets?

## Confidence

How certain you are of your Reach and Impact estimates. Confidence applies only to Reach and Impact — the Effort score accounts for uncertainty independently.

| Score | Meaning |
|---|---|
| 50% | Mostly hypothesis or guesswork about reach and impact |
| 75% | Some data but still assumptions (think 75-90%) |
| 100% | Strong evidence/data validated by analytics or customer feedback (think >90%) |

## Effort

High-level relative effort estimate. RHAI uses relative scoring (not person-months) to avoid obscuring complexity, dependencies, and unknowns.

| Score | Meaning |
|---|---|
| 1 | Low effort — few unknowns, reasonable scope, one team in a sprint |
| 2 | Medium effort — some unknowns, may involve a couple of teams, may be more than a sprint |
| 3 | Medium+ — some unknowns, cross-team effort, may require feature story mapping once prioritized |
| 5 | High effort — multiple unknowns, multiple teams, will likely require feature story mapping |
| 8 | Massive effort — multiple unknowns and dependencies, likely connected to work outside our organization, will absolutely require feature story mapping and likely broken into additional features |
| 13 | Too large to responsibly estimate — must be broken into smaller features |

## Scoring Guidance

### Reach vs Impact
- Reach is about breadth (how many users), Impact is about depth (how much it matters to those users).
- A niche feature (R=3) can still be high impact (I=8) if it solves a critical pain point for those few users.
- A broad feature (R=8) can be low impact (I=3) if it's a minor polish.

### Confidence Signals
- **100%**: Multiple customer requests, telemetry data, approved RFE with field validation, legal/compliance requirement
- **75%**: Approved RFE with some customer evidence, competitive analysis, strategy review passed (7-8/8), named customer demand
- **50%**: Strategy review recommended REVISE, unresolved upstream dependencies, unvalidated technical assumptions, no direct customer evidence

### Effort Red Flags
- Strategy review disagreed with original sizing → trust the review
- Multiple teams + unresolved technical questions → bump effort up
- Blocking dependency on another ticket not yet started → factor into effort or confidence
- "Must be broken down" → E=13, flag to PM

### Comment Convention
Post a Jira comment starting with "RICE SCORE JUSTIFICATION:" documenting the rationale for each score.
