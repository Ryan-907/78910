"""
Paper III — Stage 2a: Role Permission Authoring Scaffold

Produces the file the researcher fills in to author the six role permission sets,
plus the per-type impact preview that makes each decision informed without making
any of them for them.

Why this module authors nothing
-------------------------------
The role permission sets are the normative artifact of Paper III. Paper II's
central finding is that language models cannot author normative policy — ACL
conformance as low as 23%, self-agreement as low as 26%. A model-authored
permission set would refute the paper it appears in.

So: every cell is blank. There is no recommended column, no default, no ordering
that implies a preference, and no per-(role, type) statistic. A prefilled sheet
collects confirmation rather than authorship, and the provenance of these sets is
the point of the exercise.

What IS supplied, per information type
--------------------------------------
Enough context to decide, none of it role-specific:

* the v1.2.0 definition verbatim, including the boundary rulings settled after the
  Stage 1c human pass (staffing headcount, Type 1 vs Type 2 NPI, emergency
  contact as a subject attribute);
* how many documents carry it as a SUBJECT-LINKED type — third-party and
  organisational occurrences are excluded, because those are what the fifth check
  filters out before the subset test;
* the sensitivity tiers those documents sit in;
* one or two example values from the corpus;
* how many currently-permitted flows carry it.

The last is deliberately per-type and never per (role, type). A per-cell count
would be the outcome of that cell's decision, which would steer the authoring
rather than inform it. A type in 2 documents and a type in 95 are different
decisions and the author should know which is which; which ROLE loses what is the
author's call to make, not a number to read off.

Usage
-----
    python -m stage2.build_template

Outputs (stage2/artifacts/)
    permission_template_v1.2.0.csv    THE FILE TO FILL IN — 16 rows, 6 blank cells each
    permission_reference_v1.2.0.html  readable reference alongside the template
    impact_preview_v1.2.0.json        per-type impact, machine-readable
    impact_preview_v1.2.0.csv         per-type impact, one row per type
    template_record_v1.2.0.json       construction record
"""

from __future__ import annotations

import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from core.ci_policy import evaluate_document_flow
from evaluation.eval_flows import load_dataset, reconstruct_document
from world.agents_pool import EXTENDED_ALL_AGENTS
from core.ci_policy import get_active_role

from stage1.build_inventory import doc_id, load_corpus
from stage1.subject_linkage import OUT_JSON as LINKAGE_PATH, LINKAGE_VERSION
from stage1.vocabulary import INFORMATION_TYPES, VOCAB, VOCAB_VERSION

ARTIFACT_DIR = Path("stage2/artifacts")

TEMPLATE_PATH  = ARTIFACT_DIR / f"permission_template_v{VOCAB_VERSION}.csv"
REFERENCE_PATH = ARTIFACT_DIR / f"permission_reference_v{VOCAB_VERSION}.html"
IMPACT_JSON    = ARTIFACT_DIR / f"impact_preview_v{VOCAB_VERSION}.json"
IMPACT_CSV     = ARTIFACT_DIR / f"impact_preview_v{VOCAB_VERSION}.csv"
RECORD_PATH    = ARTIFACT_DIR / f"template_record_v{VOCAB_VERSION}.json"

# The six roles actually held by the 24-agent pool. `Facilities Contractor` is
# defined in ROLE_CONTEXTS but held by no agent, so it is not authored here;
# adding it later would be additive and would not disturb these six.
ROLES = ("Doctor", "Nurse", "Billing Specialist", "HR Manager",
         "IT Contractor", "Patient")

DECISION_VALUES = ("permit", "deny")

TYPE_NAMES = [t.name for t in INFORMATION_TYPES]


# ---------------------------------------------------------------------------
# Gather
# ---------------------------------------------------------------------------

def subject_linked_by_doc() -> dict[str, set[str]]:
    """{doc_id: {information types carried as SUBJECT-linked}} from linkage v1.2.0."""
    link = json.loads(LINKAGE_PATH.read_text(encoding="utf-8"))
    corpus_hash = load_corpus()[1]
    if link["corpus_sha256"] != corpus_hash:
        raise SystemExit("Corpus changed since linkage was built — re-run "
                         "stage1.subject_linkage.")
    if link["vocab_version"] != VOCAB_VERSION:
        raise SystemExit(
            f"Linkage was built against vocabulary v{link['vocab_version']} but the "
            f"vocabulary is now v{VOCAB_VERSION}. The vocabulary is frozen for "
            f"Stage 2; re-run stage1.subject_linkage or restore the frozen version.")
    out: dict[str, set[str]] = defaultdict(set)
    for d in link["detections"]:
        if d["classification"] == "subject":
            out[d["doc_id"]].add(d["information_type"])
    return out, link


def example_values(link: dict) -> dict[str, list[str]]:
    """Up to two representative subject-linked values per type, deterministically."""
    seen: dict[str, Counter] = defaultdict(Counter)
    for d in link["detections"]:
        if d["classification"] == "subject":
            v = d["value"].strip()
            if v:
                seen[d["information_type"]][v] += 1
    out: dict[str, list[str]] = {}
    for t, counter in seen.items():
        # Most frequent first; ties broken alphabetically so the result is stable.
        ranked = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
        out[t] = [v for v, _ in ranked[:2]]
    return out


def baseline_permits(sl: dict[str, set[str]]) -> tuple[dict, dict]:
    """
    Run the EXISTING four-check gate over all 2,520 flows.

    Read-only: `evaluate_document_flow` is imported and called, never modified.
    """
    records = load_dataset()
    docs = [(doc_id(i), r, reconstruct_document(r)) for i, r in enumerate(records)]

    total = permitted = 0
    per_type_permitted = Counter()
    per_type_permitted_docs: dict[str, set[str]] = defaultdict(set)

    for agent in EXTENDED_ALL_AGENTS:
        for did, _rec, doc in docs:
            total += 1
            allowed, _reason = evaluate_document_flow(agent, doc)
            if allowed:
                permitted += 1
                for t in sl.get(did, ()):
                    per_type_permitted[t] += 1
                    per_type_permitted_docs[t].add(did)

    summary = {
        "flows_total": total,
        "flows_permitted": permitted,
        "flows_denied": total - permitted,
        "agents": len(EXTENDED_ALL_AGENTS),
        "documents": len(docs),
    }
    return summary, {
        "per_type_permitted_flows": dict(per_type_permitted),
        "per_type_permitted_docs": {k: sorted(v) for k, v in per_type_permitted_docs.items()},
    }


def build_rows(sl: dict[str, set[str]], link: dict) -> list[dict]:
    records = load_dataset()
    tier_of = {doc_id(i): r["sensitivity_tier"] for i, r in enumerate(records)}

    docs_with: dict[str, list[str]] = defaultdict(list)
    for did, types in sl.items():
        for t in types:
            docs_with[t].append(did)

    examples = example_values(link)
    _summary, impact = baseline_permits(sl)

    rows = []
    for t in INFORMATION_TYPES:
        dids = sorted(docs_with.get(t.name, []))
        tiers = Counter(tier_of[d] for d in dids)
        rows.append({
            "information_type": t.name,
            "family": t.family,
            "extra_sensitive": "yes" if t.extra_sensitive else "",
            "definition": " ".join(t.definition.split()),
            "subject_linked_documents": len(dids),
            "tiers": "; ".join(f"{k} {v}" for k, v in sorted(tiers.items(),
                                                             key=lambda kv: (-kv[1], kv[0]))),
            "permitted_flows_carrying_it":
                impact["per_type_permitted_flows"].get(t.name, 0),
            "example_1": examples.get(t.name, [""])[0] if examples.get(t.name) else "",
            "example_2": (examples[t.name][1]
                          if len(examples.get(t.name, [])) > 1 else ""),
            "_doc_ids": dids,
        })
    return rows, _summary, impact


# ---------------------------------------------------------------------------
# Emit
# ---------------------------------------------------------------------------

def write_template(rows: list[dict]) -> None:
    cols = (["information_type"] + list(ROLES) +
            ["family", "extra_sensitive", "subject_linked_documents", "tiers",
             "permitted_flows_carrying_it", "example_1", "example_2", "definition"])
    with open(TEMPLATE_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow([r["information_type"]] + [""] * len(ROLES) +
                       [r["family"], r["extra_sensitive"], r["subject_linked_documents"],
                        r["tiers"], r["permitted_flows_carrying_it"],
                        r["example_1"], r["example_2"], r["definition"]])


def write_impact(rows: list[dict], summary: dict, impact: dict) -> None:
    artifact = {
        "artifact":        "stage2a_impact_preview",
        "vocab_version":   VOCAB_VERSION,
        "linkage_version": LINKAGE_VERSION,
        "baseline_gate":   "core.ci_policy.evaluate_document_flow (four checks, unmodified)",
        "baseline":        summary,
        "note": ("Per information type only. Deliberately NOT per (role, type): a "
                 "per-cell count would be the outcome of that cell's decision and "
                 "would steer the authoring rather than inform it."),
        "types": [
            {
                "information_type": r["information_type"],
                "family": r["family"],
                "extra_sensitive": bool(r["extra_sensitive"]),
                "subject_linked_documents": r["subject_linked_documents"],
                "tiers": r["tiers"],
                "permitted_flows_carrying_it": r["permitted_flows_carrying_it"],
                "share_of_permitted_flows": (
                    round(r["permitted_flows_carrying_it"] / summary["flows_permitted"], 4)
                    if summary["flows_permitted"] else None),
                "document_ids": r["_doc_ids"],
            } for r in rows
        ],
    }
    IMPACT_JSON.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    with open(IMPACT_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["information_type", "family", "extra_sensitive",
                    "subject_linked_documents", "tiers",
                    "permitted_flows_carrying_it", "share_of_permitted_flows"])
        for e in artifact["types"]:
            w.writerow([e["information_type"], e["family"],
                        "yes" if e["extra_sensitive"] else "",
                        e["subject_linked_documents"], e["tiers"],
                        e["permitted_flows_carrying_it"],
                        e["share_of_permitted_flows"]])


HTML_HEAD = """<meta charset="utf-8">
<title>Paper III Stage 2a - permission authoring reference</title><style>
:root{color-scheme:light dark}
body{font:15px/1.6 -apple-system,Segoe UI,sans-serif;max-width:62rem;margin:2rem auto;
     padding:0 1rem;color:#111;background:#fff}
h1{font-size:1.45rem;margin-bottom:.2rem}
.meta{color:#555;font-size:.85rem;margin-bottom:1.2rem}
.info{border-left:4px solid #48c;background:#f3f8ff;padding:.7rem 1rem;margin:1rem 0;font-size:.9rem}
.warn{border-left:4px solid #b34;background:#fff5f5;padding:.7rem 1rem;margin:1rem 0;font-size:.9rem}
.t{border:1px solid #ddd;border-radius:7px;padding:.9rem 1.1rem;margin-bottom:1rem}
.t h2{font-size:1.02rem;margin:0 0 .35rem;font-family:ui-monospace,Consolas,monospace}
.tag{display:inline-block;font-size:.72rem;background:#eee;border-radius:3px;
     padding:.05rem .4rem;margin-left:.4rem;color:#444;font-family:inherit}
.tag.xs{background:#f6dede;color:#833}
.def{font-size:.9rem;margin:.4rem 0 .6rem}
.facts{font-size:.82rem;color:#444;font-family:ui-monospace,Consolas,monospace}
.ex{font-size:.8rem;color:#333;background:#fafafa;border-left:3px solid #ddd;
    padding:.35rem .6rem;margin-top:.45rem;font-family:ui-monospace,Consolas,monospace}
code{background:#f0f0f0;padding:0 .25em;border-radius:3px}
@media (prefers-color-scheme:dark){
 body{background:#141414;color:#e8e8e8} .t{border-color:#333}
 .tag{background:#262626;color:#bbb} .tag.xs{background:#3a2020;color:#e79}
 .facts{color:#bbb} .ex{background:#1c1c1c;border-color:#333;color:#ccc}
 .info{background:#12202e;border-color:#469} .warn{background:#2a1618;border-color:#c55}
 code{background:#242424}
}
</style>
"""


def write_reference(rows: list[dict], summary: dict) -> None:
    esc = html.escape
    with open(REFERENCE_PATH, "w", encoding="utf-8") as f:
        f.write(HTML_HEAD)
        f.write("<h1>Stage 2a - permission authoring reference</h1>\n")
        f.write(f'<div class="meta">vocabulary v{VOCAB_VERSION} (frozen) &nbsp;|&nbsp; '
                f'linkage v{LINKAGE_VERSION} &nbsp;|&nbsp; {len(rows)} information types '
                f'&nbsp;|&nbsp; {len(ROLES)} roles &nbsp;|&nbsp; baseline '
                f'{summary["flows_permitted"]} of {summary["flows_total"]} flows '
                f'permitted</div>\n')
        f.write(
            '<div class="info">This page is reference only. Author the decisions in '
            f'<code>permission_template_v{VOCAB_VERSION}.csv</code>: one row per '
            'information type, one column per role, each cell <code>permit</code> or '
            '<code>deny</code>. Then run '
            '<code>python -m stage2.validate_permissions</code>.<br><br>'
            'The question each cell asks is: <b>may this role receive this information '
            'type about the document’s subject?</b> The check runs only after role, '
            'context, and assignment have already passed, so a <code>permit</code> here '
            'does not grant access on its own — it declines to withdraw it.</div>\n')
        f.write(
            '<div class="warn">Counts below are per information type and never per '
            '(role, type). A per-cell figure would be the outcome of that cell’s '
            'decision rather than input to it. <b>Nothing here is prefilled or '
            'recommended</b>; the provenance of these sets is the point.</div>\n')

        for r in rows:
            xs = ' <span class="tag xs">extra-sensitive</span>' if r["extra_sensitive"] else ""
            f.write('<div class="t">')
            f.write(f'<h2>{esc(r["information_type"])}'
                    f'<span class="tag">{esc(r["family"])}</span>{xs}</h2>')
            f.write(f'<div class="def">{esc(r["definition"])}</div>')
            f.write(f'<div class="facts">subject-linked in '
                    f'<b>{r["subject_linked_documents"]}</b> of 105 documents'
                    f' &nbsp;|&nbsp; carried by <b>{r["permitted_flows_carrying_it"]}</b> '
                    f'of {summary["flows_permitted"]} currently-permitted flows<br>'
                    f'tiers: {esc(r["tiers"]) or "-"}</div>')
            ex = [e for e in (r["example_1"], r["example_2"]) if e]
            if ex:
                f.write('<div class="ex">' +
                        "<br>".join(esc(e[:110]) for e in ex) + '</div>')
            f.write('</div>\n')


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    if TEMPLATE_PATH.exists():
        with open(TEMPLATE_PATH, encoding="utf-8-sig", newline="") as f:
            filled = sum(1 for row in csv.DictReader(f)
                         if any((row.get(r) or "").strip() for r in ROLES))
        if filled:
            raise SystemExit(
                f"{TEMPLATE_PATH} already carries {filled} authored row(s). Refusing to "
                f"overwrite authored policy - move or rename it first.")

    sl, link = subject_linked_by_doc()
    rows, summary, impact = build_rows(sl, link)

    write_template(rows)
    write_impact(rows, summary, impact)
    write_reference(rows, summary)

    record = {
        "artifact":        "stage2a_template_record",
        "vocab_version":   VOCAB_VERSION,
        "linkage_version": LINKAGE_VERSION,
        "corpus_sha256":   load_corpus()[1],
        "roles":           list(ROLES),
        "decision_values": list(DECISION_VALUES),
        "cells_to_author": len(rows) * len(ROLES),
        "baseline":        summary,
        "authored_by":     "researcher (NOT a model - see module docstring)",
        "randomness":      "none",
    }
    RECORD_PATH.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")

    print(f"Stage 2a authoring scaffold - vocabulary v{VOCAB_VERSION} (frozen), "
          f"linkage v{LINKAGE_VERSION}\n")
    print(f"  baseline gate: {summary['flows_permitted']} of {summary['flows_total']} "
          f"flows permitted ({summary['flows_denied']} denied)")
    print(f"  template     : {len(rows)} information types x {len(ROLES)} roles "
          f"= {len(rows) * len(ROLES)} cells, all blank\n")
    print(f"  {'information type':<22}{'docs':>6}{'permitted flows':>17}  tiers")
    print("  " + "-" * 76)
    for r in sorted(rows, key=lambda x: -x["permitted_flows_carrying_it"]):
        print(f"  {r['information_type']:<22}{r['subject_linked_documents']:>6}"
              f"{r['permitted_flows_carrying_it']:>17}  {r['tiers'][:34]}")
    print(f"\nWrote:\n  {TEMPLATE_PATH}   <-- author here (permit / deny)"
          f"\n  {REFERENCE_PATH}\n  {IMPACT_JSON}\n  {IMPACT_CSV}\n  {RECORD_PATH}")
    print("\nThen: python -m stage2.validate_permissions")


if __name__ == "__main__":
    main()
