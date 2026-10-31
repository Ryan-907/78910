"""Cross-vendor result figures, sized for a single column of a two-column paper.

Authored at 3.4in wide so they render 1:1 at \\columnwidth: no scaling, and the type
stays at the size it was set. Layouts are column-native rather than shrunk -- grouped
bars run horizontally, and the two instability panels stack.

Vendor is hue, model scale is shade within hue, and the ablated arm is hatched.
Only figures that show something a table cannot are generated: the direction of
error (x2), self-agreement (x3), and instability against breach (x5). Violation
counts, per-draw counts, and the release/refusal pair live in the tables.
"""
import json, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from evaluation.llm_labeler import load_cached

FIG = "reports/figures/"
W = 3.4                                   # \columnwidth in a two-column layout
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 6.5, "axes.titlesize": 7.4,
    "axes.titleweight": "bold", "figure.dpi": 160, "savefig.dpi": 600,
    "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#888",
    "axes.linewidth": .7, "axes.grid": True, "grid.color": "#E8E8E8",
    "grid.linewidth": .6, "axes.axisbelow": True, "figure.facecolor": "white",
    "xtick.major.width": .7, "ytick.major.width": .7,
})
INK, GRAY = "#222", "#9A9A9A"
HATCH = {"claude-opus-4-8-nothink": "///"}
M = ["claude-opus-4-8", "claude-opus-4-8-nothink", "claude-sonnet-5", "claude-haiku-4-5",
     "gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano"]
SHORT = {"claude-opus-4-8": "Opus 4.8", "claude-opus-4-8-nothink": "Opus 4.8 (no think)",
         "claude-sonnet-5": "Sonnet 5", "claude-haiku-4-5": "Haiku 4.5",
         "gpt-5.4": "GPT-5.4", "gpt-5.4-mini": "GPT-5.4-mini", "gpt-5.4-nano": "GPT-5.4-nano"}
C = {"claude-opus-4-8": "#1B4F8A", "claude-opus-4-8-nothink": "#1B4F8A",
     "claude-sonnet-5": "#2a78d6", "claude-haiku-4-5": "#86b6ef",
     "gpt-5.4": "#A85B12", "gpt-5.4-mini": "#eb6834", "gpt-5.4-nano": "#f4a97f"}

lab = json.load(open("reports/labeler_eval_report.json", encoding="utf-8"))["models"]
var = json.load(open("reports/variance_report.json", encoding="utf-8"))["models"]
H = {r["title"]: r for r in json.load(open("data/dataset.json", encoding="utf-8"))}
VAR = [m for m in M if var.get(m, {}).get("n_docs_with_multiple_draws", 0) > 0]
NV = len(VAR)

grants = {}
for m in M:
    L = load_cached(m); o = u = 0
    for t, x in L.items():
        h = set(H[t].get("permitted_receiver_roles", [])); l = set(x["permitted_receiver_roles"])
        o += len(l - h); u += len(h - l)
    grants[m] = (o, u)


# ── x2 direction of error ────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(W, 2.55))
y = np.arange(len(M))[::-1]
mx = max(max(g) for g in grants.values())
for i, m in enumerate(M):
    o, u = grants[m]
    ax.barh(y[i], -u, color="#5583B4", height=.62, zorder=3,
            hatch=HATCH.get(m), edgecolor="#33506E", linewidth=.4)
    ax.barh(y[i],  o, color="#C45B4E", height=.62, zorder=3,
            hatch=HATCH.get(m), edgecolor="#8A3A30", linewidth=.4)
    ax.text(-u - 2.5, y[i], str(u), ha="right", va="center", fontsize=5.8, color=INK)
    ax.text(o + 2.5, y[i], str(o), ha="left", va="center", fontsize=5.8, color=INK)
ax.axvline(0, color="#444", lw=.9)
ax.set_yticks(y); ax.set_yticklabels([SHORT[m] for m in M], fontsize=6.2)
ax.set_xlim(-mx * 1.24, mx * 1.24); ax.set_ylim(-.7, len(M) - .10)
# Both sides are counts, so the axis reads in magnitudes; direction is the label.
ticks = [t for t in (-100, -75, -50, -25, 0, 25, 50, 75, 100) if abs(t) <= mx * 1.24]
ax.set_xticks(ticks); ax.set_xticklabels([str(abs(t)) for t in ticks])
ax.set_xlabel("role-grant errors vs. authored policy", fontsize=6.4)
ax.text(-mx * .62, len(M) - .34, "under-granted", ha="center", fontsize=6.3, color="#3E6D9C")
ax.text(mx * .62, len(M) - .34, "over-granted", ha="center", fontsize=6.3, color="#A8483C")
ax.tick_params(labelsize=6); ax.grid(axis="y", visible=False)
fig.tight_layout(pad=.4); fig.savefig(FIG + "x2_direction.png"); plt.close(fig)

# ── x3 self-agreement (horizontal, tier vs ACL per model) ────────────────
fig, ax = plt.subplots(figsize=(W, 3.15))
yy = np.arange(NV)[::-1]
h = .36
for k, (key, alpha) in enumerate([("tier_all_draws_agree", .45),
                                  ("roles_all_draws_agree", 1.0)]):
    vals = [var[m]["label_stability"][key] for m in VAR]
    off = h / 2 if k == 0 else -h / 2
    bars = ax.barh(yy + off, vals, h, color=[C[m] for m in VAR], alpha=alpha,
                   zorder=3, edgecolor="#555", linewidth=.4)
    for b, m in zip(bars, VAR):
        if HATCH.get(m):
            b.set_hatch(HATCH[m])
    for b, v in zip(bars, vals):
        ax.text(v + .015, b.get_y() + b.get_height() / 2, f"{v:.0%}",
                va="center", fontsize=5.6, fontweight="bold", color=INK)
ax.axvline(1.0, color=GRAY, lw=1.1, ls="--", zorder=2)
ax.text(1.0, NV - .28, "gate", ha="center", fontsize=6, color="#666", style="italic")
ax.set_yticks(yy); ax.set_yticklabels([SHORT[m] for m in VAR], fontsize=6.2)
ax.set_xlim(0, 1.17); ax.set_ylim(-.65, NV - .12)
ax.set_xlabel("documents identical across all 5 draws", fontsize=6.4)
ax.set_xticks([0, .25, .5, .75, 1.0])
ax.set_xticklabels(["0", "25%", "50%", "75%", "100%"], fontsize=6)
ax.grid(axis="y", visible=False)
# Shade encodes the field, hue encodes the model, so the key is drawn in neutral
# ink below the axis rather than floating over the shortest bars.
from matplotlib.patches import Patch
ax.legend(handles=[Patch(facecolor="#777", alpha=.45, edgecolor="#555", lw=.4,
                         label="sensitivity tier"),
                   Patch(facecolor="#777", alpha=1.0, edgecolor="#555", lw=.4,
                         label="permitted roles (ACL)")],
          frameon=False, fontsize=6, ncol=2, loc="upper center",
          bbox_to_anchor=(.5, -.115), handlelength=1.1, handletextpad=.5,
          columnspacing=1.2, borderpad=0)
fig.tight_layout(pad=.4); fig.savefig(FIG + "x3_stability.png"); plt.close(fig)

# ── x5 instability and breach (stacked panels) ───────────────────────────
fig, (a1, a2) = plt.subplots(2, 1, figsize=(W, 3.7), sharex=True)
xx = np.arange(NV)
u = [var[m]["decision_stability"]["unstable_rate"] for m in VAR]
b1 = a1.bar(xx, u, color=[C[m] for m in VAR], width=.64, zorder=3,
            edgecolor="#555", linewidth=.4)
for b, m, v in zip(b1, VAR, u):
    if HATCH.get(m):
        b.set_hatch(HATCH[m])
    n = var[m]["decision_stability"]["unstable_flows"]
    a1.text(b.get_x() + b.get_width() / 2, v + .0013, str(n), ha="center",
            va="bottom", fontsize=5.8, fontweight="bold", color=INK)
a1.set_ylabel("decisions that flip", fontsize=6.4)
a1.set_ylim(0, max(u) * 1.26)
a1.set_yticks([0, .02, .04]); a1.set_yticklabels(["0", "2%", "4%"], fontsize=6)
a1.set_title("of the 2,520 access decisions", fontsize=6.4, loc="left",
             color="#555", fontweight="normal")

cf = [var[m]["decision_stability"]["coin_flip_breaches"] for m in VAR]
b2 = a2.bar(xx, cf, color=[C[m] for m in VAR], width=.64, zorder=3,
            edgecolor="#555", linewidth=.4)
for b, m, v in zip(b2, VAR, cf):
    if HATCH.get(m):
        b.set_hatch(HATCH[m])
    a2.text(b.get_x() + b.get_width() / 2, v + 1.2, str(v), ha="center",
            va="bottom", fontsize=5.8, fontweight="bold", color=INK)
a2.set_ylabel("coin-flip breaches", fontsize=6.4)
a2.set_ylim(0, max(cf) * 1.24); a2.tick_params(labelsize=6)
a2.set_xticks(xx)
a2.set_xticklabels([SHORT[m] for m in VAR], fontsize=5.9, rotation=32, ha="right")
fig.tight_layout(pad=.4); fig.savefig(FIG + "x5_instability.png"); plt.close(fig)

print("wrote x2, x3, x5 at column width")
