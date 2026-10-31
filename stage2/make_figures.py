"""
Paper III — Figures

Generates the paper's results figure from the Stage 2 artifacts. Deterministic:
no randomness, no wall-clock, and every value read from
`generalization_v1.2.0.json` rather than recomputed, so the figure cannot drift
from the numbers in the text.

Fig. coverage: Pr[T subset-of P(r)] against bundle size k, one line per role,
with the corpus's observed bundle-size range shaded. This is the paper's answer
to the made-up-corpus objection made visual: coverage decays exponentially in
bundle size, and this corpus sits in the region where most roles have already
fallen off.

Usage
-----
    python -m stage2.make_figures

Outputs (paper/figures/)
    coverage-curve.pdf   vector, for LaTeX inclusion
    coverage-curve.png   raster, for previewing
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")           # headless; no display required
import matplotlib.pyplot as plt

ARTIFACT = Path("stage2/artifacts/generalization_v1.2.0.json")
OUT_DIR = Path("paper/figures")

# Distinguishable without colour, for print and for colour-vision deficiency.
STYLE = {
    "Doctor":             dict(marker="o", linestyle="-",  color="#1b4965"),
    "Nurse":              dict(marker="s", linestyle="-",  color="#5fa8d3"),
    "Patient":            dict(marker="^", linestyle="--", color="#62929e"),
    "Billing Specialist": dict(marker="D", linestyle="-.", color="#c1666b"),
    "HR Manager":         dict(marker="v", linestyle=":",  color="#8a6d3b"),
    "IT Contractor":      dict(marker="x", linestyle=":",  color="#4d4d4d"),
}
ORDER = ["Doctor", "Nurse", "Patient", "Billing Specialist",
         "HR Manager", "IT Contractor"]


def main() -> None:
    a = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    curve = a["coverage_curve"]
    sizes = a["permission_set_sizes"]
    observed_ks = sorted(int(k) for k in a["by_bundle_size"])
    mean_k = a["observed"]["mean_bundle_size"]
    vocab = a["vocabulary_size"]

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # IEEE single column is ~3.5in wide.
    fig, ax = plt.subplots(figsize=(3.5, 2.7))

    # Shade the bundle sizes this corpus actually exhibits.
    ax.axvspan(min(observed_ks), max(observed_ks), color="#000000", alpha=0.055,
               lw=0, zorder=0)
    ax.axvline(mean_k, color="#444444", lw=0.8, linestyle=(0, (4, 3)), zorder=1)

    for role in ORDER:
        ks = sorted(int(k) for k in curve[role])
        ys = [curve[role][str(k)] for k in ks]
        ax.plot(ks, ys, label=f"{role} ({sizes[role]})", markersize=3.2,
                linewidth=1.15, zorder=3, **STYLE[role])

    ax.set_xlabel("Bundle size (information types per document)", fontsize=7.5)
    ax.set_ylabel("Probability role covers bundle", fontsize=7.5)
    ax.set_xlim(1, 11)
    ax.set_ylim(-0.02, 1.02)
    ax.set_xticks(range(1, 12))
    ax.tick_params(labelsize=7)
    ax.grid(True, linewidth=0.3, alpha=0.4)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)

    # Legend upper-right: the band above y=0.6 beyond k=7 is clear of every
    # curve. The annotation sits low inside the shaded region, clear of the flat
    # HR and IT Contractor lines that a lower-left legend would overlap.
    ax.annotate(f"observed bundle sizes\n(mean {mean_k})",
                xy=(mean_k, 0.0), xytext=(4.25, 0.16),
                fontsize=6.2, color="#333333", ha="left", va="bottom")

    ax.legend(fontsize=6.0, loc="upper right", frameon=False,
              handlelength=2.1, labelspacing=0.3, borderpad=0.1,
              title="Role (permitted types)", title_fontsize=6.2,
              alignment="left")

    fig.tight_layout(pad=0.25)
    for ext in ("pdf", "png"):
        fig.savefig(OUT_DIR / f"coverage-curve.{ext}", dpi=400,
                    bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)

    print(f"Coverage curve — vocabulary size {vocab}, "
          f"observed bundle sizes {min(observed_ks)}--{max(observed_ks)} "
          f"(mean {mean_k})")
    print("  permission set sizes:",
          ", ".join(f"{r} {sizes[r]}" for r in ORDER))
    print(f"\nWrote:\n  {OUT_DIR / 'coverage-curve.pdf'}"
          f"\n  {OUT_DIR / 'coverage-curve.png'}")


if __name__ == "__main__":
    main()
