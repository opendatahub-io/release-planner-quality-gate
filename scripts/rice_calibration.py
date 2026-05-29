"""RICE Calibration: Compare AI-generated scores vs human scores for rhoai-3.4.

Fetches 46 RHAISTRAT issues with existing human RICE scores, applies the rubric
independently, and generates comparison charts + statistics.

Usage:
    python scripts/rice_calibration.py
    # Outputs charts to artifacts/ and prints summary statistics.
"""

import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# ---------------------------------------------------------------------------
# AI Scores — applied from rubric + calibration examples after reading each
# issue's summary, description, priority, labels, and status.
#
# Rubric scales:
#   Reach:      1, 3, 5, 8, 13
#   Impact:     1, 3, 5, 8, 13
#   Confidence: 50, 75, 100
#   Effort:     1, 2, 3, 5, 8, 13
#
# Scoring rationale is inline. Human scores that use non-standard values
# (6, 7, 9, 10, 19) are noted — the AI always uses rubric-standard values.
# ---------------------------------------------------------------------------

AI_SCORES = {
    # RHAISTRAT-44: Build/Update runtime container image for KF Trainer v2
    # Training runtime image packaging. Reaches training users (~10-30%).
    # High impact: essential for Training Hub workflows. Multiple deps + communities = high effort.
    "RHAISTRAT-44":   {"R": 5,  "I": 8,  "C": 75,  "E": 5},

    # RHAISTRAT-150: Prompt Engineering & Management - Embed MLFlow UI
    # Broad reach across Gen AI Studio users. High impact: structured prompt mgmt.
    # Cross-team (MLflow + dashboard), moderate-high effort.
    "RHAISTRAT-150":  {"R": 8,  "I": 8,  "C": 75,  "E": 5},

    # RHAISTRAT-161: Llama Stack Multi-Arch [Power]
    # Niche: ppc64le (Power) is small user base. High impact for those users (blocked without it).
    # Build/QE coordination effort, some unknowns.
    "RHAISTRAT-161":  {"R": 3,  "I": 8,  "C": 75,  "E": 3},

    # RHAISTRAT-172: AI Asset Endpoints - Add Custom Endpoints Support
    # Very broad: nearly all Gen AI Studio users benefit from custom endpoints.
    # High impact: enables third-party models. Low effort: UI + config flags.
    "RHAISTRAT-172":  {"R": 13, "I": 8,  "C": 75,  "E": 2},

    # RHAISTRAT-193: Extend Training Dashboard to Support RayJobs
    # Moderate reach: Ray users in training. Medium impact: visibility improvement.
    # Cross-component integration, moderate effort.
    "RHAISTRAT-193":  {"R": 5,  "I": 5,  "C": 75,  "E": 5},

    # RHAISTRAT-297: Improve UX for Gateway discovery/creation in UI
    # Broad reach: all llm-d/model deployment users. High impact: solves UX blocker.
    # Scoped to UI discovery, low effort.
    "RHAISTRAT-297":  {"R": 8,  "I": 8,  "C": 100, "E": 2},

    # RHAISTRAT-309: Model Checkpointing for KF Trainer (GA)
    # Niche: GPU training users with preemptible environments. Low-medium impact.
    # Some complexity with distributed training + storage backends.
    "RHAISTRAT-309":  {"R": 3,  "I": 5,  "C": 75,  "E": 3},

    # RHAISTRAT-545: Surface Existing Vector Stores in Gen AI Studio Playground
    # Broad reach: RAG/playground users. High impact: enables governed RAG workflows.
    # Dev preview scope, UI-focused, low effort.
    "RHAISTRAT-545":  {"R": 8,  "I": 8,  "C": 75,  "E": 2},

    # RHAISTRAT-813: OCI Compliant Storage for Model Registry Phase 2
    # Nearly all users benefit from registry storage. High impact: foundational.
    # Multi-team, OCI compliance, moderate effort.
    "RHAISTRAT-813":  {"R": 13, "I": 8,  "C": 75,  "E": 5},

    # RHAISTRAT-965: MCP Server Distillation - Tool-Calling Training Data
    # Niche: AI engineers doing tool-calling fine-tuning. High impact for them.
    # Novel capability, moderate effort with MCP integration.
    "RHAISTRAT-965":  {"R": 3,  "I": 8,  "C": 75,  "E": 3},

    # RHAISTRAT-974: Quality-Hardened Multilingual Flow (SDG Hub)
    # Moderate reach: multilingual users. Medium impact: reference implementation.
    # Multi-language eval + quality bar definition, high effort.
    "RHAISTRAT-974":  {"R": 5,  "I": 5,  "C": 75,  "E": 5},

    # RHAISTRAT-983: OGX/Llama Stack Multi-Arch [ARM]
    # Moderate reach: ARM deployments are growing. High impact for ARM users.
    # Build/QE coordination, some unknowns.
    "RHAISTRAT-983":  {"R": 5,  "I": 8,  "C": 100, "E": 3},

    # RHAISTRAT-1051: [GA] Support NeMo Guardrails
    # Broad reach: model serving users need guardrails. High impact: enterprise safety.
    # Complex: productionize + Konflux integration + cross-team.
    "RHAISTRAT-1051": {"R": 8,  "I": 8,  "C": 100, "E": 5},

    # RHAISTRAT-1054: Tech-preview readiness for Responses API
    # Broad reach: API consumers. High impact: security + reliability hardening.
    # Multi-faceted: RBAC, error handling, scale testing.
    "RHAISTRAT-1054": {"R": 8,  "I": 8,  "C": 75,  "E": 5},

    # RHAISTRAT-1072: Refactor Llama-Stack Upstream Release Process
    # Internal tooling: reaches all LLS developers. Medium impact: fixes broken process.
    # Scoped refactor, moderate effort.
    "RHAISTRAT-1072": {"R": 5,  "I": 5,  "C": 75,  "E": 3},

    # RHAISTRAT-1074: Sign and verify AI Artifacts in Registry (Tech Preview)
    # Nearly all registry users benefit. High impact: security/provenance foundation.
    # API-level work, moderate effort.
    "RHAISTRAT-1074": {"R": 13, "I": 8,  "C": 100, "E": 3},

    # RHAISTRAT-1079: Agent Connector Framework in SDG Hub
    # Small reach: SDG Hub power users integrating external tools.
    # High impact: extensibility. Moderate effort: framework design.
    "RHAISTRAT-1079": {"R": 3,  "I": 8,  "C": 75,  "E": 3},

    # RHAISTRAT-1084: [DP] MCP Catalog - Enterprise Control
    # Moderate reach: MCP adopters. High impact: discovery + deployment.
    # Cross-component (catalog UI + runtime + gateway), high effort.
    "RHAISTRAT-1084": {"R": 5,  "I": 8,  "C": 75,  "E": 5},

    # RHAISTRAT-1112: Prompt Management integration in playground
    # Moderate reach: playground users. High impact: structured prompt consumption.
    # UI integration with existing prompt registry, moderate effort.
    "RHAISTRAT-1112": {"R": 5,  "I": 8,  "C": 75,  "E": 3},

    # RHAISTRAT-1117: [GA] MaaS Subscription Model Redesign
    # Very broad: all MaaS users. Massive impact: architectural redesign, GA blocker.
    # Complex entity model redesign, moderate effort (well-scoped).
    "RHAISTRAT-1117": {"R": 13, "I": 13, "C": 100, "E": 3},

    # RHAISTRAT-1129: Feast Feature Server Performance Optimization
    # Moderate reach: feature store users (State Farm etc.). Massive impact: 60ms SLA.
    # Performance optimization with compliance requirements, high effort.
    "RHAISTRAT-1129": {"R": 5,  "I": 13, "C": 100, "E": 5},

    # RHAISTRAT-1131: Feature Store OIDC Authentication Support
    # Moderate reach: feature store users. Medium impact: auth consistency.
    # Integration with platform OIDC, moderate effort.
    "RHAISTRAT-1131": {"R": 5,  "I": 5,  "C": 75,  "E": 3},

    # RHAISTRAT-1134: UI for Orchestration of Evaluations
    # Broad reach: all users wanting evaluations. Massive impact: democratizes evals.
    # Multi-release, complex UI + backend orchestration.
    "RHAISTRAT-1134": {"R": 8,  "I": 13, "C": 75,  "E": 5},

    # RHAISTRAT-1136: MVP Granular RBAC [Phase 2]
    # Broad reach: all project admins/users. Massive impact: fine-grained access control.
    # Building on Phase 1 infrastructure, moderate effort.
    "RHAISTRAT-1136": {"R": 8,  "I": 13, "C": 100, "E": 3},

    # RHAISTRAT-1148: Enhance Core Access Control Policy Engine for Llama Stack
    # Broad reach: all Llama Stack API users. High impact: endpoint-level RBAC.
    # Core engine changes, moderate effort.
    "RHAISTRAT-1148": {"R": 8,  "I": 8,  "C": 100, "E": 3},

    # RHAISTRAT-1157: Enable --max-model-len auto by default for vLLM
    # Nearly all model serving users. Massive impact: prevents OOM crashes.
    # Very simple: default flag change + UI checkbox.
    "RHAISTRAT-1157": {"R": 13, "I": 13, "C": 100, "E": 1},

    # RHAISTRAT-1158: Improve Maintenance of Llama Stack Demos
    # Moderate reach: field teams, partners, customers. Medium impact: perception fix.
    # Repo maintenance + ownership, moderate effort.
    "RHAISTRAT-1158": {"R": 5,  "I": 5,  "C": 75,  "E": 3},

    # RHAISTRAT-1161: MLFlow integration in RHOAI GA
    # Nearly all RHOAI users benefit. High impact: centralized ML lifecycle.
    # Multi-component integration, high effort.
    "RHAISTRAT-1161": {"R": 13, "I": 8,  "C": 100, "E": 5},

    # RHAISTRAT-1167: Enable vLLM Runtime Support in MaaS
    # Broad reach: model serving users. High impact: unifies runtime support.
    # UI + gateway integration, moderate effort.
    "RHAISTRAT-1167": {"R": 8,  "I": 8,  "C": 100, "E": 3},

    # RHAISTRAT-1178: Chatterbox Security Testing via Garak (Backend)
    # Moderate reach: security-focused users. High impact: productized security testing.
    # Complex: EvalHub + Garak + Chatterbox integration, high effort.
    "RHAISTRAT-1178": {"R": 5,  "I": 8,  "C": 75,  "E": 5},

    # RHAISTRAT-1179: Refactor AIMI/Chatterbox Logic into Garak
    # Small-moderate reach: internal/evaluation users. Medium-high impact: convergence.
    # Porting + compatibility work, high effort.
    "RHAISTRAT-1179": {"R": 5,  "I": 5,  "C": 75,  "E": 5},

    # RHAISTRAT-1180: Backend Report Artifact Generation for Security Testing
    # Moderate reach: security evaluation users. Medium-high impact: consumable reports.
    # Report generation + storage, high effort.
    "RHAISTRAT-1180": {"R": 5,  "I": 5,  "C": 75,  "E": 5},

    # RHAISTRAT-1181: SDG for Automated Model Safety Validation & Red Teaming
    # Moderate reach: security testing users. Low-medium impact: extends existing capability.
    # SDG workflow for custom policies, moderate effort.
    "RHAISTRAT-1181": {"R": 5,  "I": 3,  "C": 75,  "E": 3},

    # RHAISTRAT-1191: AutoML Backend - KFP orchestration
    # Broad reach: ML users wanting AutoML. Massive impact: end-to-end automation.
    # Complex: multiple components (AutoGluon + KServe + Registry + KFP).
    "RHAISTRAT-1191": {"R": 8,  "I": 13, "C": 75,  "E": 5},

    # RHAISTRAT-1204: AutoML UI MVP Experience
    # Nearly all RHOAI dashboard users could benefit. High impact: lowers ML barrier.
    # Complex UI + backend integration, very high effort.
    "RHAISTRAT-1204": {"R": 13, "I": 8,  "C": 75,  "E": 8},

    # RHAISTRAT-1213: [DP] AgentCard Support
    # Broad reach: agent deployers. Medium impact: discovery mechanism.
    # Spec + lightweight implementation, moderate effort.
    "RHAISTRAT-1213": {"R": 8,  "I": 5,  "C": 75,  "E": 3},

    # RHAISTRAT-1214: [DP] Agent MLflow Tracing Integration
    # Broad reach: agent deployers. Medium impact: observability convenience.
    # Config injection, low-moderate effort.
    "RHAISTRAT-1214": {"R": 8,  "I": 5,  "C": 75,  "E": 2},

    # RHAISTRAT-1216: [DP] Agent Deploy & Runtime Management
    # Nearly all agent users. High impact: standardized lifecycle management.
    # CR design + controller, low-moderate effort for MVP.
    "RHAISTRAT-1216": {"R": 13, "I": 8,  "C": 75,  "E": 3},

    # RHAISTRAT-1217: Improve Responses API OpenAI parity
    # Broad reach: API consumers. High impact: compatibility is critical.
    # Systematic gap-closing, high effort (many endpoints).
    "RHAISTRAT-1217": {"R": 8,  "I": 8,  "C": 75,  "E": 5},

    # RHAISTRAT-1233: Guardrails Integration with MCP Gateway
    # Moderate reach: MCP Gateway users. Medium-high impact: security integration.
    # Cross-component (TrustyAI + IBM plugin adapter + operator), moderate effort.
    "RHAISTRAT-1233": {"R": 5,  "I": 5,  "C": 75,  "E": 3},

    # RHAISTRAT-1259: Kagenti Codebase Cleanup & Dependency Reduction
    # Nearly all Kagenti/agent platform users benefit indirectly. High impact: tech debt.
    # Dependency removal + installer replacement, low-moderate effort.
    "RHAISTRAT-1259": {"R": 13, "I": 8,  "C": 100, "E": 2},

    # RHAISTRAT-1306: MCP Catalog Pre-Canned MCP Servers
    # Moderate reach: MCP adopters. Medium impact: reduces adoption friction.
    # Curating + containerizing, low effort.
    "RHAISTRAT-1306": {"R": 5,  "I": 5,  "C": 100, "E": 2},

    # RHAISTRAT-1316: Training Hub First-Class Model Family Support
    # Moderate reach: training users. Medium impact: tailored workflows.
    # Multiple model families + notebooks, moderate effort.
    "RHAISTRAT-1316": {"R": 5,  "I": 5,  "C": 100, "E": 3},

    # RHAISTRAT-1365: MLflow Experiment Tracking for Training Hub
    # Small reach: Training Hub users. Medium impact: experiment tracking.
    # Integration work, moderate effort.
    "RHAISTRAT-1365": {"R": 3,  "I": 5,  "C": 100, "E": 3},

    # RHAISTRAT-1393: Bring LangGraph agent from laptop to RH AI
    # Broad reach: agent developers. Medium impact: deployment convenience.
    # Reference implementation + docs, moderate effort.
    "RHAISTRAT-1393": {"R": 8,  "I": 5,  "C": 75,  "E": 3},

    # RHAISTRAT-1396: Update Garak dependency to midstream fork
    # Moderate reach: security testing users. Medium impact: enables Chatterbox.
    # Simple dependency swap + rebuild, low effort.
    "RHAISTRAT-1396": {"R": 5,  "I": 5,  "C": 75,  "E": 2},
}


def load_human_scores():
    """Load human scores from the cached Jira data."""
    data_path = "/tmp/rice-calibration-issues.json"
    if not os.path.exists(data_path):
        print("ERROR: Run the Jira fetch first — /tmp/rice-calibration-issues.json not found.")
        sys.exit(1)

    with open(data_path) as f:
        issues = json.load(f)

    results = []
    for issue in issues:
        key = issue["key"]
        fields = issue["fields"]

        # Parse confidence dropdown
        conf_obj = fields.get("customfield_10838", {})
        conf_val = conf_obj.get("value", "") if isinstance(conf_obj, dict) else str(conf_obj)
        if "100" in str(conf_val):
            conf_pct = 100
        elif "75" in str(conf_val):
            conf_pct = 75
        elif "50" in str(conf_val):
            conf_pct = 50
        else:
            conf_pct = None

        results.append({
            "key": key,
            "summary": fields["summary"],
            "human_R": fields.get("customfield_10862", 0),
            "human_I": fields.get("customfield_10836", 0),
            "human_C": conf_pct,
            "human_E": fields.get("customfield_10637", 0),
            "human_RICE": fields.get("customfield_10864"),
        })
    return results


def calc_rice(r, i, c, e):
    """Calculate RICE score: (R * I * C_fraction) / E."""
    if e == 0:
        return 0
    return (r * i * (c / 100.0)) / e


def build_comparison(human_data, ai_scores):
    """Merge human and AI scores into a comparison table."""
    rows = []
    for h in human_data:
        key = h["key"]
        ai = ai_scores.get(key)
        if ai is None:
            print(f"WARNING: No AI score for {key}, skipping")
            continue
        ai_rice = calc_rice(ai["R"], ai["I"], ai["C"], ai["E"])
        human_rice = h["human_RICE"]
        if human_rice is None:
            human_rice = calc_rice(h["human_R"], h["human_I"], h["human_C"], h["human_E"])
        rows.append({
            "key": key,
            "summary": h["summary"],
            "h_R": h["human_R"], "h_I": h["human_I"],
            "h_C": h["human_C"], "h_E": h["human_E"],
            "h_RICE": human_rice,
            "a_R": ai["R"], "a_I": ai["I"],
            "a_C": ai["C"], "a_E": ai["E"],
            "a_RICE": ai_rice,
        })
    return rows


def generate_charts(rows, out_dir):
    """Generate all comparison charts."""
    os.makedirs(out_dir, exist_ok=True)
    n = len(rows)

    # Extract arrays
    dims = {
        "Reach": ([r["h_R"] for r in rows], [r["a_R"] for r in rows]),
        "Impact": ([r["h_I"] for r in rows], [r["a_I"] for r in rows]),
        "Confidence": ([r["h_C"] for r in rows], [r["a_C"] for r in rows]),
        "Effort": ([r["h_E"] for r in rows], [r["a_E"] for r in rows]),
        "RICE Score": ([r["h_RICE"] for r in rows], [r["a_RICE"] for r in rows]),
    }

    # ---- Chart 1: Scatter plots (human vs AI) ----
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    fig.suptitle(f"RICE Calibration: AI vs Human Scores (rhoai-3.4, N={n})",
                 fontsize=14, fontweight="bold")

    for idx, (dim_name, (h_vals, a_vals)) in enumerate(dims.items()):
        ax = axes[idx // 3][idx % 3]
        h = np.array(h_vals, dtype=float)
        a = np.array(a_vals, dtype=float)

        ax.scatter(h, a, alpha=0.5, s=40, edgecolors="black", linewidths=0.5)

        # Perfect agreement line
        lo = min(h.min(), a.min()) * 0.9
        hi = max(h.max(), a.max()) * 1.1
        ax.plot([lo, hi], [lo, hi], "r--", alpha=0.5, label="Perfect agreement")

        # Correlation
        if np.std(h) > 0 and np.std(a) > 0:
            corr = np.corrcoef(h, a)[0, 1]
            ax.set_title(f"{dim_name} (r={corr:.2f})", fontsize=11)
        else:
            ax.set_title(dim_name, fontsize=11)

        ax.set_xlabel("Human", fontsize=9)
        ax.set_ylabel("AI", fontsize=9)
        ax.legend(fontsize=7, loc="upper left")

    # Hide the 6th subplot
    axes[1][2].axis("off")
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    path = os.path.join(out_dir, "rice_calibration_scatter.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"Saved: {path}")

    # ---- Chart 2: Bar chart (average human vs AI per dimension) ----
    fig, ax = plt.subplots(figsize=(10, 6))
    dim_names = list(dims.keys())
    h_means = [np.mean(dims[d][0]) for d in dim_names]
    a_means = [np.mean(dims[d][1]) for d in dim_names]
    x = np.arange(len(dim_names))
    width = 0.35
    bars1 = ax.bar(x - width/2, h_means, width, label="Human", color="#4878A8",
                   edgecolor="black", linewidth=0.5)
    bars2 = ax.bar(x + width/2, a_means, width, label="AI", color="#E8734A",
                   edgecolor="black", linewidth=0.5)
    ax.set_ylabel("Average Score")
    ax.set_title(f"Average RICE Dimension Scores: Human vs AI (N={n})",
                 fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(dim_names)
    ax.legend()

    # Value labels on bars
    for bars in [bars1, bars2]:
        for bar in bars:
            h_val = bar.get_height()
            ax.annotate(f"{h_val:.1f}", xy=(bar.get_x() + bar.get_width()/2, h_val),
                        xytext=(0, 3), textcoords="offset points",
                        ha="center", fontsize=8)

    plt.tight_layout()
    path = os.path.join(out_dir, "rice_calibration_bars.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"Saved: {path}")

    # ---- Chart 3: Histograms of score differences (AI - Human) ----
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    fig.suptitle(f"Score Differences (AI - Human) Distribution (N={n})",
                 fontsize=14, fontweight="bold")

    for idx, (dim_name, (h_vals, a_vals)) in enumerate(dims.items()):
        ax = axes[idx // 3][idx % 3]
        diffs = np.array(a_vals, dtype=float) - np.array(h_vals, dtype=float)
        ax.hist(diffs, bins=15, color="#6BAB7A", edgecolor="black", alpha=0.8)
        ax.axvline(0, color="red", linestyle="--", alpha=0.7)
        ax.axvline(diffs.mean(), color="blue", linestyle="-", alpha=0.7,
                   label=f"Mean={diffs.mean():.2f}")
        ax.set_title(dim_name, fontsize=11)
        ax.set_xlabel("AI - Human")
        ax.set_ylabel("Count")
        ax.legend(fontsize=8)

    axes[1][2].axis("off")
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    path = os.path.join(out_dir, "rice_calibration_diffs.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"Saved: {path}")

    # ---- Chart 4: Summary statistics table as image ----
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.axis("off")
    ax.set_title(f"RICE Calibration Summary Statistics (N={n})",
                 fontweight="bold", fontsize=13, pad=20)

    col_labels = ["Dimension", "Human Mean", "AI Mean", "Mean Diff",
                  "Mean Abs Error", "Median Diff", "Std Dev", "Correlation",
                  "Bias Direction"]
    table_data = []

    for dim_name, (h_vals, a_vals) in dims.items():
        h = np.array(h_vals, dtype=float)
        a = np.array(a_vals, dtype=float)
        diffs = a - h
        mae = np.mean(np.abs(diffs))
        mean_diff = np.mean(diffs)
        median_diff = np.median(diffs)
        std_diff = np.std(diffs)
        if np.std(h) > 0 and np.std(a) > 0:
            corr = np.corrcoef(h, a)[0, 1]
        else:
            corr = float("nan")

        if mean_diff > 0.3:
            bias = "AI higher"
        elif mean_diff < -0.3:
            bias = "AI lower"
        else:
            bias = "~Neutral"

        table_data.append([
            dim_name,
            f"{h.mean():.2f}",
            f"{a.mean():.2f}",
            f"{mean_diff:+.2f}",
            f"{mae:.2f}",
            f"{median_diff:+.2f}",
            f"{std_diff:.2f}",
            f"{corr:.3f}",
            bias,
        ])

    table = ax.table(cellText=table_data, colLabels=col_labels,
                     loc="center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.0, 1.6)

    # Style header
    for j in range(len(col_labels)):
        table[0, j].set_facecolor("#4878A8")
        table[0, j].set_text_props(color="white", fontweight="bold")

    # Alternate row colors
    for i in range(1, len(table_data) + 1):
        color = "#F0F4F8" if i % 2 == 0 else "white"
        for j in range(len(col_labels)):
            table[i, j].set_facecolor(color)

    plt.tight_layout()
    path = os.path.join(out_dir, "rice_calibration_stats.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved: {path}")


def print_summary(rows):
    """Print text summary with key findings."""
    n = len(rows)
    print(f"\n{'='*80}")
    print(f"RICE CALIBRATION SUMMARY — rhoai-3.4 (N={n})")
    print(f"{'='*80}\n")

    dims = {
        "Reach": ("h_R", "a_R"),
        "Impact": ("h_I", "a_I"),
        "Confidence": ("h_C", "a_C"),
        "Effort": ("h_E", "a_E"),
        "RICE Score": ("h_RICE", "a_RICE"),
    }

    print("PER-DIMENSION ANALYSIS")
    print("-" * 80)
    print(f"{'Dimension':<15} {'MAE':>8} {'Corr':>8} {'Mean Diff':>10} {'Bias':>14}")
    print("-" * 80)

    for dim_name, (h_key, a_key) in dims.items():
        h = np.array([r[h_key] for r in rows], dtype=float)
        a = np.array([r[a_key] for r in rows], dtype=float)
        diffs = a - h
        mae = np.mean(np.abs(diffs))
        mean_diff = np.mean(diffs)
        if np.std(h) > 0 and np.std(a) > 0:
            corr = np.corrcoef(h, a)[0, 1]
        else:
            corr = float("nan")

        if mean_diff > 0.3:
            bias = "AI higher"
        elif mean_diff < -0.3:
            bias = "AI lower"
        else:
            bias = "~Neutral"

        print(f"{dim_name:<15} {mae:>8.2f} {corr:>8.3f} {mean_diff:>+10.2f} {bias:>14}")

    # Largest disagreements by total RICE
    print(f"\n{'='*80}")
    print("TOP 10 LARGEST RICE SCORE DISAGREEMENTS")
    print("-" * 80)
    sorted_rows = sorted(rows, key=lambda r: abs(r["a_RICE"] - r["h_RICE"]),
                         reverse=True)
    for r in sorted_rows[:10]:
        diff = r["a_RICE"] - r["h_RICE"]
        print(f"  {r['key']:<18} Human={r['h_RICE']:>7.2f}  AI={r['a_RICE']:>7.2f}"
              f"  Diff={diff:>+8.2f}")
        print(f"    {r['summary'][:70]}")
        print(f"    Human: R={r['h_R']}, I={r['h_I']}, C={r['h_C']}%, E={r['h_E']}")
        print(f"    AI:    R={r['a_R']}, I={r['a_I']}, C={r['a_C']}%, E={r['a_E']}")
        print()

    # Issues where AI and human perfectly agree
    perfect = [r for r in rows
               if r["h_R"] == r["a_R"] and r["h_I"] == r["a_I"]
               and r["h_C"] == r["a_C"] and r["h_E"] == r["a_E"]]
    print(f"PERFECT AGREEMENT: {len(perfect)}/{n} issues")
    for r in perfect:
        print(f"  {r['key']}: R={r['h_R']}, I={r['h_I']}, C={r['h_C']}%, E={r['h_E']}")

    # Non-standard human scores
    print(f"\n{'='*80}")
    print("NON-STANDARD HUMAN SCORES (values outside rubric scale)")
    print("-" * 80)
    standard_R = {1, 3, 5, 8, 13}
    standard_I = {1, 3, 5, 8, 13}
    standard_C = {50, 75, 100}
    standard_E = {1, 2, 3, 5, 8, 13}
    for r in rows:
        issues = []
        if r["h_R"] not in standard_R:
            issues.append(f"R={r['h_R']}")
        if r["h_I"] not in standard_I:
            issues.append(f"I={r['h_I']}")
        if r["h_C"] not in standard_C:
            issues.append(f"C={r['h_C']}")
        if r["h_E"] not in standard_E:
            issues.append(f"E={r['h_E']}")
        if issues:
            print(f"  {r['key']}: {', '.join(issues)}")

    # Patterns
    print(f"\n{'='*80}")
    print("DIVERGENCE PATTERNS")
    print("-" * 80)

    # Where AI scored lower reach
    lower_r = [r for r in rows if r["a_R"] < r["h_R"]]
    higher_r = [r for r in rows if r["a_R"] > r["h_R"]]
    same_r = [r for r in rows if r["a_R"] == r["h_R"]]
    print(f"  Reach:  AI lower={len(lower_r)}, same={len(same_r)}, AI higher={len(higher_r)}")

    lower_i = [r for r in rows if r["a_I"] < r["h_I"]]
    higher_i = [r for r in rows if r["a_I"] > r["h_I"]]
    same_i = [r for r in rows if r["a_I"] == r["h_I"]]
    print(f"  Impact: AI lower={len(lower_i)}, same={len(same_i)}, AI higher={len(higher_i)}")

    lower_c = [r for r in rows if r["a_C"] < r["h_C"]]
    higher_c = [r for r in rows if r["a_C"] > r["h_C"]]
    same_c = [r for r in rows if r["a_C"] == r["h_C"]]
    print(f"  Confidence: AI lower={len(lower_c)}, same={len(same_c)}, AI higher={len(higher_c)}")

    lower_e = [r for r in rows if r["a_E"] < r["h_E"]]
    higher_e = [r for r in rows if r["a_E"] > r["h_E"]]
    same_e = [r for r in rows if r["a_E"] == r["h_E"]]
    print(f"  Effort: AI lower={len(lower_e)}, same={len(same_e)}, AI higher={len(higher_e)}")


def main():
    out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                           "artifacts")
    human_data = load_human_scores()
    rows = build_comparison(human_data, AI_SCORES)
    generate_charts(rows, out_dir)
    print_summary(rows)


if __name__ == "__main__":
    main()
