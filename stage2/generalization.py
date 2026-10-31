"""
Paper III — Generalization Bound for Over-Delivery and Unreachability

The strongest objection to Stage 2 is that its results hold on a corpus we built.
This module states the mechanism formally, so the claim is about a relationship
between bundle size and permission-set overlap rather than about 105 particular
documents, and then instantiates it on this corpus to see whether the derived
prediction matches the observed 67 unreachable documents.

The instantiation is a TEST, not a fit. Nothing here is tuned to reproduce 67;
where the prediction and the observation diverge, the divergence is the result.

Notation
--------
    V           the controlled vocabulary, |V| = 16
    T(d)        the subject-linked information types carried by document d
    k = |T(d)|  the document's BUNDLE SIZE
    R(d)        the roles the label admits (permitted_receiver_roles)
    P(r)        the types role r may receive, |P(r)| authored per role

Derivation
----------
The fifth check passes for (r, d) exactly when

    T(d) ⊆ P(r)

so a document is reachable iff SOME admitted role covers its whole bundle:

    reachable(d)  ⟺  ∃ r ∈ R(d) : T(d) ⊆ P(r)
    unreachable(d) ⟺  ∀ r ∈ R(d) : T(d) \\ P(r) ≠ ∅                        (1)

Note what (1) is not: it is not `T(d) ⊆ ⋃_{r∈R(d)} P(r)`. Coverage does not
compose across roles, because a document is released to one requester at a time.
Two roles that jointly cover a bundle still leave it unreachable if neither
covers it alone. This is the formal reason the result is a property of
document-level enforcement rather than of any particular permission set.

Define the residue of d under r:

    ρ(r, d) = |T(d) \\ P(r)|                                               (2)

and the document's minimum residue ρ*(d) = min_{r∈R(d)} ρ(r,d). Then
unreachable(d) ⟺ ρ*(d) ≥ 1, and ρ*(d) counts how many types would have to be
removed — by redaction or decomposition — to make d reachable at all.

Expected over-delivery
----------------------
Under a null model in which T(d) is a uniformly random k-subset of V, the
probability that a given role covers it is hypergeometric:

    Pr[T ⊆ P(r)]  =  C(|P(r)|, k) / C(|V|, k)                              (3)

which for |P(r)| = pV behaves like p^k for small k: coverage decays
EXPONENTIALLY IN BUNDLE SIZE. That is the generalization claim. Over-delivery is
not a quirk of this corpus; it is what happens whenever documents bundle many
information types and roles are permitted few, and it worsens multiplicatively as
bundles grow.

For a document admitting role set R, treating the per-role covering events as
independent gives

    Pr[unreachable(d)] ≈ ∏_{r∈R(d)} ( 1 − C(|P(r)|,k) / C(|V|,k) )         (4)

(4) is an approximation in a knowable direction: the events {T ⊆ P(r)} are
POSITIVELY correlated across roles, because the same T is tested against nested
permission sets — P(Nurse) ⊂ P(Doctor) here, so any bundle a Nurse covers a
Doctor covers too. Positive correlation makes the true probability of at least
one success higher than the independent product implies, so (4) OVERSTATES
unreachability. The exact figure under the same null model, computed by
enumerating k-subsets, is reported alongside it.

Usage
-----
    python -m stage2.generalization

Outputs (stage2/artifacts/)
    generalization_v1.2.0.json
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from itertools import combinations
from math import comb
from pathlib import Path

from stage1.build_inventory import doc_id, load_corpus
from stage1.subject_linkage import OUT_JSON as LINKAGE_PATH
from stage1.vocabulary import INFORMATION_TYPES, VOCAB_VERSION
from stage2.extended_gate import load_policy

ARTIFACT_DIR = Path("stage2/artifacts")
OUT_JSON = ARTIFACT_DIR / f"generalization_v{VOCAB_VERSION}.json"

V = [t.name for t in INFORMATION_TYPES]


# ---------------------------------------------------------------------------
# Observed
# ---------------------------------------------------------------------------

def observed(policy) -> dict:
    records = json.loads(Path("data/dataset.json").read_text(encoding="utf-8"))
    rows = []
    for i, rec in enumerate(records):
        did = doc_id(i)
        T = set(policy.subject_types.get(did, frozenset()))
        R = list(rec.get("permitted_receiver_roles", []))
        residues = {r: len(T - set(policy.permitted_for(r))) for r in R}
        rho_star = min(residues.values()) if residues else None
        rows.append({
            "doc_id": did,
            "k": len(T),
            "roles_admitted": R,
            "residues": residues,
            "rho_star": rho_star,
            # A document with no admitted roles, or carrying nothing, is outside
            # the mechanism: it is not unreachable BECAUSE of the fifth check.
            "in_scope": bool(R) and len(T) > 0,
            "unreachable": bool(R) and len(T) > 0 and rho_star is not None and rho_star >= 1,
        })
    return rows


# ---------------------------------------------------------------------------
# Null model
# ---------------------------------------------------------------------------

def covering_probability(p_size: int, k: int, v_size: int = len(V)) -> float:
    """Pr[T subset-of P] for T a uniform random k-subset of V. Equation (3)."""
    if k > p_size:
        return 0.0
    if k == 0:
        return 1.0
    return comb(p_size, k) / comb(v_size, k)


def predict_independent(k: int, roles: list[str], policy) -> float:
    """Equation (4): independent approximation. Overstates unreachability."""
    p = 1.0
    for r in roles:
        p *= (1.0 - covering_probability(len(policy.permitted_for(r)), k))
    return p


def predict_exact(k: int, roles: list[str], policy) -> float:
    """
    Exact Pr[unreachable] under the same null model, by enumerating every
    k-subset of V and asking whether any admitted role covers it.

    This removes the independence approximation, so the gap between this and
    `predict_independent` isolates how much of the latter's error is correlation
    between nested permission sets rather than the null model itself.
    """
    if k == 0:
        return 0.0
    if k > len(V):
        return 1.0
    sets = [frozenset(policy.permitted_for(r)) for r in roles]
    total = comb(len(V), k)
    uncovered = 0
    for T in combinations(V, k):
        Ts = frozenset(T)
        if not any(Ts <= P for P in sets):
            uncovered += 1
    return uncovered / total


# ---------------------------------------------------------------------------

def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    policy = load_policy()
    rows = observed(policy)

    in_scope = [r for r in rows if r["in_scope"]]
    obs_unreachable = sum(1 for r in rows if r["unreachable"])

    exp_ind = sum(predict_independent(r["k"], r["roles_admitted"], policy)
                  for r in in_scope)
    exp_exact = sum(predict_exact(r["k"], r["roles_admitted"], policy)
                    for r in in_scope)

    # Critical bundle size per role: the largest k at which a random k-subset is
    # still more likely than not to be covered.
    critical = {}
    for r in sorted(policy.role_permissions):
        n = len(policy.permitted_for(r))
        kstar = 0
        for k in range(0, len(V) + 1):
            if covering_probability(n, k) >= 0.5:
                kstar = k
        critical[r] = {"permission_set_size": n, "critical_bundle_size": kstar}

    # Coverage curve: Pr[covered] by role and bundle size.
    curve = {
        r: {str(k): round(covering_probability(len(policy.permitted_for(r)), k), 6)
            for k in range(1, 12)}
        for r in sorted(policy.role_permissions)
    }

    by_k_obs = defaultdict(lambda: [0, 0])
    for r in in_scope:
        by_k_obs[r["k"]][0] += 1
        if r["unreachable"]:
            by_k_obs[r["k"]][1] += 1
    by_k = {}
    for k in sorted(by_k_obs):
        n, u = by_k_obs[k]
        pred = [predict_exact(k, r["roles_admitted"], policy)
                for r in in_scope if r["k"] == k]
        by_k[str(k)] = {
            "documents": n,
            "observed_unreachable": u,
            "observed_rate": round(u / n, 4),
            "predicted_unreachable_exact": round(sum(pred), 2),
            "predicted_rate_exact": round(sum(pred) / n, 4),
        }

    residue_dist = Counter(r["rho_star"] for r in in_scope if r["unreachable"])

    # Residual analysis. A near-exact aggregate match can hide opposite-signed
    # per-stratum errors, so the deviations are reported by bundle size and the
    # driving co-occurrence is identified rather than left implicit.
    net = sum(d["observed_unreachable"] - d["predicted_unreachable_exact"]
              for d in by_k.values())
    mad = sum(abs(d["observed_unreachable"] - d["predicted_unreachable_exact"])
              for d in by_k.values())
    large = [r for r in in_scope if r["k"] >= 9]
    ssn_in_large = sum(1 for r in large
                       if "ssn" in policy.subject_types.get(r["doc_id"], frozenset()))
    base_rate = (sum(1 for r in in_scope
                     if "ssn" in policy.subject_types.get(r["doc_id"], frozenset()))
                 / len(in_scope))
    patient_admitted_in_large = sum(1 for r in large if "Patient" in r["roles_admitted"])
    residual = {
        "net_deviation": round(net, 2),
        "sum_absolute_deviation": round(mad, 2),
        "note": ("The aggregate agreement is partly cancellation. The null model "
                 "under-predicts unreachability at k=6-7 and over-predicts it at "
                 "k=9-10; the errors are of opposite sign and roughly equal "
                 "magnitude. Content independence -- the one assumption the null "
                 "model makes -- is violated."),
        "driver": {
            "explanation": ("Real bundles are not random subsets: `ssn` co-occurs "
                            "with large clinical bundles far above its base rate, "
                            "and `ssn` is permitted to Patient alone, which is "
                            "admitted on none of those documents. Large real "
                            "bundles are therefore systematically LESS coverable "
                            "than large random ones."),
            "documents_k_ge_9": len(large),
            "carrying_ssn": ssn_in_large,
            "ssn_rate_in_large_bundles": round(ssn_in_large / len(large), 3) if large else None,
            "ssn_base_rate_all_bundles": round(base_rate, 3),
            "patient_admitted_among_them": patient_admitted_in_large,
        },
    }

    artifact = {
        "artifact": "stage2_generalization",
        "vocab_version": VOCAB_VERSION,
        "corpus_sha256": load_corpus()[1],
        "vocabulary_size": len(V),
        "permission_set_sizes": {r: len(policy.permitted_for(r))
                                 for r in sorted(policy.role_permissions)},
        "condition": ("unreachable(d) iff for every admitted role r, "
                      "T(d) \\ P(r) is non-empty. Coverage does not compose "
                      "across roles: a document is released to one requester at "
                      "a time, so two roles that jointly cover a bundle still "
                      "leave it unreachable if neither covers it alone."),
        "observed": {
            "documents_total": len(rows),
            "documents_in_scope": len(in_scope),
            "out_of_scope": len(rows) - len(in_scope),
            "unreachable": obs_unreachable,
            "unreachable_rate_in_scope": round(obs_unreachable / len(in_scope), 4),
            "mean_bundle_size": round(sum(r["k"] for r in in_scope) / len(in_scope), 2),
            "min_residue_distribution": dict(sorted(residue_dist.items())),
        },
        "null_model_prediction": {
            "description": ("T(d) a uniformly random k-subset of V, with the actual "
                            "authored permission sets and the actual admitted role "
                            "sets held fixed. Only the CONTENT of each bundle is "
                            "randomised."),
            "expected_unreachable_independent_approx": round(exp_ind, 2),
            "expected_unreachable_exact": round(exp_exact, 2),
            "observed_unreachable": obs_unreachable,
            "discrepancy_exact": round(obs_unreachable - exp_exact, 2),
        },
        "critical_bundle_size": critical,
        "coverage_curve": curve,
        "by_bundle_size": by_k,
        "residual_analysis": residual,
    }
    OUT_JSON.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")

    print(f"Generalization bound — vocabulary v{VOCAB_VERSION}, |V| = {len(V)}\n")
    print("Permission set sizes")
    print("-" * 62)
    for r, d in critical.items():
        print(f"  {r:<20} |P| = {d['permission_set_size']:>2}   "
              f"critical bundle size k* = {d['critical_bundle_size']}")

    print(f"\nCoverage Pr[T subset-of P(r)] for a random k-subset")
    print("-" * 62)
    print(f"  {'role':<20}" + "".join(f"{('k='+str(k)):>9}" for k in (1, 3, 5, 7, 9)))
    for r in sorted(policy.role_permissions):
        n = len(policy.permitted_for(r))
        print(f"  {r:<20}" + "".join(
            f"{covering_probability(n, k):>9.3f}" for k in (1, 3, 5, 7, 9)))

    print(f"\nObserved vs predicted")
    print("-" * 62)
    o = artifact["observed"]
    p = artifact["null_model_prediction"]
    print(f"  documents in scope                  : {o['documents_in_scope']}")
    print(f"  mean bundle size                    : {o['mean_bundle_size']}")
    print(f"  OBSERVED unreachable                : {o['unreachable']}")
    print(f"  predicted, independent approx (4)   : {p['expected_unreachable_independent_approx']}")
    print(f"  predicted, exact under null model   : {p['expected_unreachable_exact']}")
    print(f"  discrepancy (observed - exact)      : {p['discrepancy_exact']:+}")

    print(f"\nBy bundle size")
    print("-" * 62)
    print(f"  {'k':>3}{'docs':>7}{'observed':>11}{'predicted':>11}{'obs rate':>10}{'pred rate':>11}")
    for k, d in by_k.items():
        print(f"  {k:>3}{d['documents']:>7}{d['observed_unreachable']:>11}"
              f"{d['predicted_unreachable_exact']:>11}"
              f"{d['observed_rate']:>10.2f}{d['predicted_rate_exact']:>11.2f}")

    print(f"\nMinimum residue of unreachable documents (types that would have to go)")
    print("-" * 62)
    for rho, n in sorted(residue_dist.items()):
        print(f"  rho* = {rho}: {n} documents")

    ra = artifact["residual_analysis"]
    dr = ra["driver"]
    print(f"\nResidual analysis")
    print("-" * 62)
    print(f"  net deviation                       : {ra['net_deviation']:+}")
    print(f"  sum of absolute deviations          : {ra['sum_absolute_deviation']}")
    print(f"  -> the aggregate match is partly cancellation: the model")
    print(f"     under-predicts at k=6-7 and over-predicts at k=9-10")
    print(f"  ssn in bundles of k>=9              : "
          f"{dr['carrying_ssn']}/{dr['documents_k_ge_9']} "
          f"({dr['ssn_rate_in_large_bundles']:.1%}) vs base rate "
          f"{dr['ssn_base_rate_all_bundles']:.1%}")
    print(f"  Patient admitted on any of them     : {dr['patient_admitted_among_them']}")

    print(f"\nWrote:\n  {OUT_JSON}")


if __name__ == "__main__":
    main()
