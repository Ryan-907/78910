"""
Generate publication figures for both live experiment arms.

  fig1-3  LLM-as-labeler, 2,520-flow clinic corpus. The gate's enforcement
          fidelity is a verified invariant (gate_accuracy_report.json: 2,520
          flows, 0 FP, 0 FN), so the only variable is the SOURCE OF THE LABEL.
  fig4-5  LLM-as-judge, 214 real HIPAA court cases (PrivaCI-Bench / GoldCoin).
          External ground truth; judge-only — the gate does not appear.

Reads the saved reports (+ recomputes the uncapped role-over-grant breakdown from
the labeler caches) and writes PNGs to reports/figures/. Palette is Okabe-Ito
(colorblind-safe); each model keeps one fixed color across every figure.

Run:  python -m evaluation.make_figures
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from evaluation.eval_flows import load_dataset
from evaluation.llm_labeler import load_cached as load_labels
from evaluation.run_labeler_eval import decide
from world.agents_pool import EXTENDED_ALL_AGENTS

FIG = Path("reports/figures"); FIG.mkdir(parents=True, exist_ok=True)
MODELS = ["claude-opus-4-8", "claude-sonnet-5", "claude-haiku-4-5"]
SHORT = {"claude-opus-4-8": "Opus 4.8", "claude-sonnet-5": "Sonnet 5", "claude-haiku-4-5": "Haiku 4.5"}

# Okabe-Ito, fixed per entity
C = {"claude-opus-4-8": "#0072B2", "claude-sonnet-5": "#D55E00", "claude-haiku-4-5": "#009E73"}
GRAY = "#999999"; INK = "#222222"; ROLECOL = {
    "Patient": "#CC79A7", "Doctor": "#0072B2", "Nurse": "#56B4E9",
    "Billing Specialist": "#E69F00", "HR Manager": "#009E73", "IT Contractor": "#D55E00"}

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 11, "axes.titlesize": 13,
    "axes.titleweight": "bold", "figure.dpi": 140, "savefig.dpi": 200,
    "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#888",
    "axes.grid": True, "grid.color": "#E6E6E6", "grid.linewidth": 0.8,
    "axes.axisbelow": True, "figure.facecolor": "white", "axes.facecolor": "white",
})


def _load(p): return json.load(open(p, encoding="utf-8"))


def _load_optional(p):
    """
    Variance results are optional — figures still build before that run finishes,
    and a partially-complete run (some models resampled, others not) is fine: any
    model with fewer than 2 draws per document is dropped rather than charted as 0.
    """
    try:
        v = _load(p)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    v["models"] = {m: d for m, d in v.get("models", {}).items()
                   if d.get("n_docs_with_multiple_draws", 0) > 0}
    return v or None


def _var_models(var):
    """Models in MODELS order that actually have variance data."""
    return [m for m in MODELS if var and m in var["models"]]


def bar_labels(ax, bars, fmt="{:.0f}", dy=0):
    for b in bars:
        ax.text(b.get_x() + b.get_width()/2, b.get_height() + dy,
                fmt.format(b.get_height()), ha="center", va="bottom",
                fontsize=10, fontweight="bold", color=INK)


# ---------------------------------------------------------------------------
# Recompute uncapped violations from labeler caches (report caps list at 40)
# ---------------------------------------------------------------------------
def full_violations(records, labels):
    viol = []
    for rec in records:
        lab = labels.get(rec["title"])
        if not lab or not lab.get("ok", True):
            continue
        h_tier, h_roles, h_extra = rec["sensitivity_tier"], rec.get("permitted_receiver_roles", []), rec.get("extra_sensitive", False)
        l_tier, l_roles, l_extra = lab["sensitivity_tier"], lab["permitted_receiver_roles"], lab["extra_sensitive"]
        for ag in EXTENDED_ALL_AGENTS:
            base = decide(ag, rec, h_tier, h_roles, h_extra)
            llm  = decide(ag, rec, l_tier, l_roles, l_extra)
            if (not base) and llm:
                deny_roles = not decide(ag, rec, l_tier, h_roles, l_extra)
                deny_tier  = not decide(ag, rec, h_tier, l_roles, l_extra)
                cause = ("roles+tier" if deny_roles and deny_tier else
                         "roles too broad" if deny_roles else
                         "tier under-rated" if deny_tier else "other")
                viol.append({"added": set(l_roles) - set(h_roles), "cause": cause,
                             "doc_type": rec["document_type"]})
    return viol


def main():
    gate = _load("reports/gate_accuracy_report.json")
    lab = _load("reports/labeler_eval_report.json")
    judge = _load("reports/flow_judge_report.json")   # judge-only arm; no gate in it
    var = _load_optional("reports/variance_report.json")   # optional 4th experiment
    records = load_dataset()
    viol = {m: full_violations(records, load_labels(m)) for m in MODELS}

    # ── FIG 1 — headline: induced privacy violations by label source ───────
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    cats = ["Human\n(baseline)"] + [SHORT[m] for m in MODELS]
    vals = [0] + [lab["models"][m]["flows"]["induced_privacy_violations"] for m in MODELS]
    cols = [GRAY] + [C[m] for m in MODELS]
    bars = ax.bar(cats, vals, color=cols, width=0.6, zorder=3)
    bar_labels(ax, bars, "{:.0f}", dy=0.6)
    # Error bars = observed min/max across identical re-labelings (experiment 4).
    # The human bar has none: the gate is deterministic, so its 0 cannot move.
    vm = _var_models(var)
    if vm:
        lo, hi = [0.0], [0.0]
        for m in MODELS:
            v = lab["models"][m]["flows"]["induced_privacy_violations"]
            if m in vm:
                lp = var["models"][m]["leaks_per_draw"]
                lo.append(max(0, v - lp["min"])); hi.append(max(0, lp["max"] - v))
            else:
                lo.append(0.0); hi.append(0.0)   # not resampled — no interval to draw
        ax.errorbar(range(len(cats)), vals, yerr=[lo, hi], fmt="none",
                    ecolor=INK, elinewidth=1.4, capsize=6, capthick=1.4, zorder=4)
        ax.set_ylabel("Induced privacy violations\n(flows the gate now wrongly PERMITS)")
        n = var["samples"]
        ax.set_title("Swapping human labels for LLM labels breaks a perfect gate")
        note = f"whiskers: min–max over {n} identical re-labelings"
        if len(vm) < len(MODELS):
            note += f" ({', '.join(SHORT[m] for m in vm)} only)"
        ax.text(0.985, 0.03, note, transform=ax.transAxes, fontsize=8.5,
                color="#666", ha="right", style="italic")
        ax.set_ylim(0, max(v + h for v, h in zip(vals, hi)) * 1.20)
    else:
        ax.set_ylabel("Induced privacy violations\n(flows the gate now wrongly PERMITS)")
        ax.set_title("Swapping human labels for LLM labels breaks a perfect gate")
        ax.set_ylim(0, max(vals) * 1.18)
    ax.text(0.015, 0.87, "Baseline (gate + human labels):\n2,520 flows → 0 privacy violations",
            transform=ax.transAxes, fontsize=9.5, color="#555", ha="left", va="top",
            bbox=dict(boxstyle="round,pad=0.4", fc="#F2F2F2", ec="#CCC"))
    fig.tight_layout(); fig.savefig(FIG/"fig1_induced_violations.png"); plt.close(fig)

    # ── FIG 2 — attribution + over-granted roles ───────────────────────────
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(12, 4.8))
    # left: leaks by cause
    causes = ["roles too broad", "tier under-rated", "roles+tier", "other"]
    xx = np.arange(len(MODELS)); w = 0.6
    bottoms = [0]*len(MODELS)
    cause_col = {"roles too broad": "#D55E00", "tier under-rated": "#56B4E9", "roles+tier": "#CC79A7", "other": GRAY}
    for cse in causes:
        vals = [Counter(v["cause"] for v in viol[m]).get(cse, 0) for m in MODELS]
        if sum(vals) == 0: continue
        axL.bar(xx, vals, w, bottom=bottoms, label=cse, color=cause_col[cse], zorder=3)
        bottoms = [b+v for b, v in zip(bottoms, vals)]
    for i, m in enumerate(MODELS):
        axL.text(i, bottoms[i]+0.8, str(bottoms[i]), ha="center", fontweight="bold", color=INK)
    axL.set_xticks(xx); axL.set_xticklabels([SHORT[m] for m in MODELS])
    axL.set_ylabel("Induced privacy violations"); axL.legend(frameon=False, fontsize=9)
    axL.set_title("Every leak traces to over-broad recipient roles")
    axL.set_ylim(0, max(bottoms)*1.15)
    # right: which role was wrongly added
    roles_order = ["Patient", "Doctor", "Nurse", "Billing Specialist", "HR Manager", "IT Contractor"]
    xr = np.arange(len(MODELS)); w2 = 0.6; bottoms = [0]*len(MODELS)
    for role in roles_order:
        vals = [sum(1 for v in viol[m] if role in v["added"]) for m in MODELS]
        if sum(vals) == 0: continue
        axR.bar(xr, vals, w2, bottom=bottoms, label=role, color=ROLECOL[role], zorder=3)
        bottoms = [b+v for b, v in zip(bottoms, vals)]
    axR.set_xticks(xr); axR.set_xticklabels([SHORT[m] for m in MODELS])
    axR.set_ylabel("Leaks where this role was over-granted")
    axR.legend(frameon=False, fontsize=8.5, title="role wrongly permitted", title_fontsize=9)
    axR.set_title("Who gets over-trusted (one leak may add several roles)")
    fig.tight_layout(); fig.savefig(FIG/"fig2_attribution_roles.png"); plt.close(fig)

    # ── FIG 3 — decoupling: tier accuracy vs induced leaks ─────────────────
    fig, ax = plt.subplots(figsize=(6.8, 4.8))
    for m in MODELS:
        tacc = lab["models"][m]["label_agreement"]["tier_exact"]
        leaks = lab["models"][m]["flows"]["induced_privacy_violations"]
        ax.scatter(tacc, leaks, s=180, color=C[m], zorder=3, edgecolor="white", linewidth=1.5)
        ax.annotate(SHORT[m], (tacc, leaks), textcoords="offset points", xytext=(10, 4),
                    fontsize=10, fontweight="bold", color=C[m])
    ax.set_xlabel("Sensitivity-tier labeling accuracy")
    ax.set_ylabel("Induced privacy violations")
    ax.set_title("Getting the tier right does not make you safe")
    ax.set_xlim(0.7, 0.9); ax.set_ylim(0, 75)
    ax.text(0.72, 68, "higher tier accuracy →  fewer leaks?  No relationship.",
            fontsize=9, color="#666", style="italic")
    fig.tight_layout(); fig.savefig(FIG/"fig3_decoupling.png"); plt.close(fig)

    # ── FIG 4 — external-validity arm: LLM as judge on real HIPAA cases ────
    fig, ax = plt.subplots(figsize=(8, 4.8))
    metrics = ["Accuracy", "Leak rate\n(should-deny permitted)", "Over-block rate"]
    x = np.arange(len(metrics)); w = 0.25
    for i, m in enumerate(MODELS):
        mm = judge["models"][m]
        vals = [mm["accuracy"], mm["privacy"]["privacy_violation_rate"],
                mm["overblocking"]["overblock_rate"]]
        bars = ax.bar(x + (i-1)*w, vals, w, label=SHORT[m], color=C[m], zorder=3)
        for b, v in zip(bars, vals):
            ax.text(b.get_x()+b.get_width()/2, v+0.01, f"{v:.0%}", ha="center",
                    va="bottom", fontsize=8.5, fontweight="bold", color=INK)
    ax.set_xticks(x); ax.set_xticklabels(metrics); ax.set_ylim(0, 1.0)
    ax.set_ylabel("Rate")
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.12))
    ax.set_title("LLM as decision-maker on real HIPAA court cases "
                 f"(n={judge['n_flows']}; only 20 should-deny)", pad=26)
    fig.tight_layout(); fig.savefig(FIG/"fig4_llm_judge_metrics.png"); plt.close(fig)

    # ── FIG 5 — judge confusion matrices ──────────────────────────────────
    labels3 = ["permit", "prohibit", "not appl."]
    keys3 = ["permit", "prohibit", "not applicable"]
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.1))
    for ax, m in zip(axes, MODELS):
        conf = judge["models"][m]["confusion"]
        mat = [[conf[g].get(p, 0) for p in keys3] for g in keys3]
        hi = max(max(r) for r in mat)
        ax.imshow(mat, cmap="Blues", vmin=0, vmax=hi)
        ax.set_xticks(range(3)); ax.set_xticklabels(labels3, fontsize=9)
        ax.set_yticks(range(3)); ax.set_yticklabels(labels3, fontsize=9)
        ax.set_xlabel("model verdict")
        if m == MODELS[0]: ax.set_ylabel("HIPAA ground truth")
        ax.set_title(SHORT[m], color=C[m])
        for r in range(3):
            for c in range(3):
                val = mat[r][c]
                ax.text(c, r, str(val), ha="center", va="center", fontsize=11,
                        color="white" if val > hi*0.5 else INK,
                        fontweight="bold" if r != c else "normal")
        # outline the critical cell: truth=prohibit, pred=permit
        ax.add_patch(plt.Rectangle((-0.5, 0.5), 1, 1, fill=False, edgecolor="#D55E00", lw=2.5))
    fig.suptitle("Where the judge errs — orange box = releasing PHI that HIPAA prohibits",
                 fontsize=12, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95)); fig.savefig(FIG/"fig5_confusion_matrices.png"); plt.close(fig)

    # ── FIG 6 — determinism: stability across identical re-labelings ──────
    if vm:
        n = var["samples"]
        fig, (axL, axR) = plt.subplots(1, 2, figsize=(12, 4.8))

        # left: share of documents where every draw produced the same value
        fields = [("tier_all_draws_agree", "Sensitivity tier\n(descriptive)"),
                  ("roles_all_draws_agree", "Permitted roles\n(normative — the ACL)"),
                  ("every_field_agrees", "Every field")]
        x = np.arange(len(fields))
        w = 0.25 if len(vm) > 1 else 0.45
        off = (len(vm) - 1) / 2
        for i, m in enumerate(vm):
            ls = var["models"][m]["label_stability"]
            vals = [ls[k] for k, _ in fields]
            bars = axL.bar(x + (i-off)*w, vals, w, label=SHORT[m], color=C[m], zorder=3)
            for b, v in zip(bars, vals):
                axL.text(b.get_x()+b.get_width()/2, v+0.012, f"{v:.0%}", ha="center",
                         va="bottom", fontsize=8.5, fontweight="bold", color=INK)
        axL.axhline(1.0, color=GRAY, lw=1.6, ls="--", zorder=2)
        axL.text(len(fields)-0.55, 1.012, "deterministic gate = 100%", fontsize=8.5,
                 color="#555", ha="right", style="italic")
        axL.set_xticks(x); axL.set_xticklabels([lbl for _, lbl in fields], fontsize=9.5)
        axL.set_ylim(0, 1.14); axL.set_ylabel(f"Documents where all {n} draws agree")
        axL.legend(frameon=False, fontsize=9, loc="lower left")
        axL.set_title("The same model relabels the same document differently")

        # right: access decisions that flip when only the label is re-rolled
        cats = ["Human\n(baseline)"] + [SHORT[m] for m in vm]
        vals = [0.0] + [var["models"][m]["decision_stability"]["unstable_rate"] for m in vm]
        cols = [GRAY] + [C[m] for m in vm]
        bars = axR.bar(cats, vals, color=cols, width=0.6, zorder=3)
        for b, v, m in zip(bars, vals, [None, *vm]):
            n_flip = 0 if m is None else var["models"][m]["decision_stability"]["unstable_flows"]
            axR.text(b.get_x()+b.get_width()/2, v + max(vals)*0.02,
                     f"{v:.2%}\n({n_flip} flows)", ha="center", va="bottom",
                     fontsize=9, fontweight="bold", color=INK)
        axR.set_ylabel("Share of the 2,520 access decisions\nthat change across re-labelings")
        axR.set_ylim(0, max(max(vals) * 1.30, 0.01))
        axR.set_title("Same policy, same request — different answer")
        fig.tight_layout(); fig.savefig(FIG/"fig6_label_variance.png"); plt.close(fig)

    print("Wrote figures to", FIG)
    for p in sorted(FIG.glob("*.png")):
        print("  ", p, f"({p.stat().st_size//1024} KB)")
    print("\nUncapped induced-violation counts:", {SHORT[m]: len(viol[m]) for m in MODELS})


if __name__ == "__main__":
    main()
