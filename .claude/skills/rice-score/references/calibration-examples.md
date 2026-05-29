# Calibration Examples

These are real RHAISTRAT features from the rhoai-3.5 batch with human-sign-off
that already have RICE scores. Use them as anchoring reference points when scoring
new tickets — every score should be justified relative to these examples.

## How to Use

When scoring a new ticket, compare it against these calibrated examples:
- "R=8 because this affects a similar user population to RHAISTRAT-1742 (Agent Deployments, R=8)"
- "E=3 because the cross-team coordination is comparable to RHAISTRAT-1534 (Config Persistence, E=3)"

## Full Calibration Table (25 scored features, sorted by RICE descending)

- RHAISTRAT-1565 (EvalHub UI: Configurable Quality Thresholds): R=13, I=13, C=100%, E=1 → RICE=169.0
- RHAISTRAT-1566 (EvalHub UI: Evaluation Run Config Validation): R=13, I=13, C=100%, E=1 → RICE=169.0
- RHAISTRAT-1473 (Validated Defaults for Tool Calling Config): R=11, I=13, C=100%, E=2 → RICE=71.5
- RHAISTRAT-1579 (MaaS Endpoint Registration in MLflow): R=8, I=13, C=75%, E=3 → RICE=26.0
- RHAISTRAT-1267 (Perses Scalable Dashboard Patterns): R=13, I=8, C=100%, E=5 → RICE=20.8
- RHAISTRAT-1524 (Surface cold-start/vRAM metrics in Catalog): R=5, I=7, C=100%, E=2 → RICE=17.5
- RHAISTRAT-1547 (MaaS Self-Service Subscription Page): R=8, I=8, C=75%, E=3 → RICE=16.0
- RHAISTRAT-1742 (Deploy agent images from AI Hub): R=8, I=8, C=75%, E=3 → RICE=16.0
- RHAISTRAT-133 (Chat Metrics & Observability in Playground): R=8, I=6, C=75%, E=3 → RICE=12.0
- RHAISTRAT-1550 (MaaS Settings IA Redesign): R=3, I=5, C=75%, E=1 → RICE=11.25
- RHAISTRAT-1762 (MCP Registry – Operational Governance): R=7, I=8, C=75%, E=4 → RICE=10.5
- RHAISTRAT-1534 (Configuration Persistence for Gen AI Studio): R=8, I=5, C=75%, E=3 → RICE=10.0
- RHAISTRAT-1527 (Multimodal Support in Gen AI Studio): R=8, I=8, C=75%, E=5 → RICE=9.6
- RHAISTRAT-1758 (Agent Deployments View – Runtime Visibility): R=8, I=8, C=75%, E=5 → RICE=9.6
- RHAISTRAT-1523 (Model Catalog: Export model data as CSV): R=5, I=5, C=75%, E=2 → RICE=9.375
- RHAISTRAT-1536 (Granular Role Creation UI): R=5, I=5, C=75%, E=2 → RICE=9.375
- RHAISTRAT-1699 (Workbench env vars reference existing secrets): R=5, I=5, C=75%, E=2 → RICE=9.375
- RHAISTRAT-1748 (Model-prompt pairing in Playground): R=5, I=5, C=75%, E=2 → RICE=9.375
- RHAISTRAT-1749 (Model-prompt associations in prompt registry): R=5, I=5, C=75%, E=2 → RICE=9.375
- RHAISTRAT-1714 (Xeon Model Discoverability & Labeling): R=3, I=3, C=100%, E=1 → RICE=9.0
- RHAISTRAT-1115 (Feature Store & Workbenches Integration P2): R=5, I=7, C=100%, E=5 → RICE=7.0
- RHAISTRAT-1521 (KALE integration into RHOAI): R=8, I=5, C=50%, E=3 → RICE=6.667
- RHAISTRAT-1535 (YAML Editor GA – UI/YAML Toggle): R=5, I=5, C=75%, E=3 → RICE=6.25
- RHAISTRAT-1555 (MLFlow Prompt Template in Gen AI Studio): R=5, I=8, C=75%, E=5 → RICE=6.0
- RHAISTRAT-1492 (AutoML Advanced Experiment Settings): R=3, I=5, C=75%, E=3 → RICE=3.75

## Scoring Patterns Observed

- **High RICE (>50)**: Legal/compliance requirements or foundational features with near-universal reach (R≥11, I≥13) and low effort
- **Mid-high RICE (15-50)**: Major pain points (I≥8) with broad reach (R≥8), moderate effort
- **Mid RICE (9-15)**: Moderate reach (R=5-8) × moderate impact (I=5-8), typically C=75%, E=2-3
- **Low RICE (<9)**: Niche features (R=3-5), high effort relative to impact, or low confidence
- **Cluster at 9.375**: Many features land at R=5, I=5, C=75%, E=2 — the "standard moderate feature" baseline
- **C=50% is rare**: Only 1 of 25 features. Most approved strategies score 75% or 100% confidence
