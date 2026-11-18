"""Semantic matching sensitivity and descriptive persistence audit.

Recomputes the primary exact-expression exposure rates at proposition level,
then audits their overlap with the existing shared-stratum/opposition controls
and summarizes later recorded commitments. This is descriptive; no model calls.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
import hashlib
import json
import re

import numpy as np
import pandas as pd

from claim_logic import assignments, evaluate_expr, parse_compact_expression, contains_role_predicate


P = Path(__file__).resolve().parent
INPUT = P / "control-inputs"
CLAIMS_PATH = P / "corrections/source-audit-v3/claims.csv"
EXACT_PAIRS_PATH = P / "controlled-exposure-pairs.csv"
PRIMARY_RESULT_PATH = P / "strength-controls.json"
SHARED_PATH = P / "shared-claim-strata.csv"
PRIMARY_SCRIPT_PATH = P / "strength_controls.py"
OUT_JSON = P / "matching_persistence.json"
OUT_PAIRS = P / "matching_persistence_pairs.csv"
OUT_OVERLAP = P / "matching_persistence_overlap.csv"
OUT_REPORT = P / "matching_persistence_findings.md"

COMMITMENTS = {"assert", "endorse"}
INFORMATIVE = {"truth_aligned", "misleading"}
FINAL_STAGE = 10010
PLAYER_COUNT = 6
BOOTSTRAP_SEED = 20260919
BOOTSTRAP_DRAWS = 10000


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def norm_expr(row: pd.Series) -> str:
    effective = str(row.get("effective_expression", "") or "").strip()
    return effective or str(row.get("expression", "") or "").strip()


questions = {
    row["id"]: row
    for row in map(json.loads, (INPUT / "questions.jsonl").read_text().splitlines())
}
labels = {
    row["id"]: row
    for row in map(json.loads, (INPUT / "labels.jsonl").read_text().splitlines())
}
worlds = list(assignments(PLAYER_COUNT))
full_mask = (1 << len(worlds)) - 1
world_index = {world: index for index, world in enumerate(worlds)}
statements = {
    task: [item["ast"] for item in row["statements"]]
    for task, row in questions.items()
}
gold_world = {
    task: tuple(labels[task]["roles"][player] for player in questions[task]["players"])
    for task in questions
}
assert all(world in world_index for world in gold_world.values())


@lru_cache(maxsize=None)
def signature(task: str, expression: str) -> int | None:
    ast = parse_compact_expression(expression)
    if ast is None:
        return None
    bits = 0
    for index, world in enumerate(worlds):
        if evaluate_expr(ast, world, statements[task]):
            bits |= 1 << index
    return bits


@lru_cache(maxsize=None)
def truth_at_gold(task: str, expression: str) -> bool | None:
    sig = signature(task, expression)
    if sig is None:
        return None
    return bool(sig & (1 << world_index[gold_world[task]]))


def truth_label(is_true: bool) -> str:
    return "truth_aligned" if is_true else "misleading"


def proposition_truth(task: str, sig: int) -> bool:
    return bool(sig & (1 << world_index[gold_world[task]]))


def is_non_role(expression: str) -> bool:
    # Matches the primary's exclusion intent while tolerating harmless spacing/case.
    return not contains_role_predicate(parse_compact_expression(expression))


claims = pd.read_csv(CLAIMS_PATH).fillna("")
claims["expr"] = claims.apply(norm_expr, axis=1)
claims["commitment_norm"] = claims["commitment"].astype(str).str.lower()
commitments = claims[claims.commitment_norm.isin(COMMITMENTS)].copy()
claims["signature"] = None
commitments["signature"] = [signature(task, expr) for task, expr in zip(commitments.task_id, commitments.expr)]
claims.loc[commitments.index, "signature"] = commitments["signature"]
parse_failures = int(commitments.signature.isna().sum())
commitments = commitments[commitments.signature.notna()].copy()
commitments["stage_order_num"] = pd.to_numeric(commitments.stage_order)
commitments["truth"] = [
    proposition_truth(task, sig)
    for task, sig in zip(commitments.task_id, commitments.signature)
]

initial = commitments[commitments.stage_order_num.eq(0)]
initial_props: dict[tuple[str, str, str, str], set[int]] = defaultdict(set)
for row in initial.itertuples():
    initial_props[(row.condition_id, row.task_id, str(row.repetition), row.agent_id)].add(row.signature)

supplies: dict[tuple[str, str, str, int], list] = defaultdict(list)
for row in initial.itertuples():
    if row.information_type not in INFORMATIVE or not is_non_role(row.expr):
        continue
    supplies[(row.condition_id, row.task_id, str(row.repetition), row.signature)].append(row)

history_max_stage = (
    commitments[commitments.stage_order_num.lt(FINAL_STAGE)]
    .groupby(["condition_id", "task_id", "repetition"])
    .stage_order_num.max()
    .to_dict()
)
later = commitments[
    commitments.stage_order_num.gt(0) & commitments.stage_order_num.lt(FINAL_STAGE)
].copy()
later_by_recipient: dict[tuple[str, str, str, str], list] = defaultdict(list)
for row in later.itertuples():
    later_by_recipient[(row.condition_id, row.task_id, str(row.repetition), row.agent_id)].append(row)

semantic_rows: list[dict] = []
for (condition, task, repetition, sig), source_rows in supplies.items():
    truth = proposition_truth(task, sig)
    # Informative type is inherited from the corrected primary annotation, while
    # correctness is independently evaluated on the canonical gold world.
    source_types = sorted({str(row.information_type) for row in source_rows})
    assert all(item == truth_label(truth) for item in source_types), (
        condition, task, repetition, sig, truth, source_types
    )
    initial_source_agents = sorted({str(row.agent_id) for row in source_rows})
    for recipient in ("agent-1", "agent-2", "agent-3"):
        if sig in initial_props[(condition, task, repetition, recipient)]:
            continue
        recipient_rows = later_by_recipient[(condition, task, repetition, recipient)]
        target_rows = [row for row in recipient_rows if row.signature == sig]
        opposite_rows = [row for row in recipient_rows if row.signature == (full_mask ^ sig)]
        max_stage = history_max_stage[(condition, task, int(repetition))]
        last_stage_target = [row for row in recipient_rows if row.stage_order_num == max_stage and row.signature == sig]
        last_stage_opposite = [
            row for row in recipient_rows
            if row.stage_order_num == max_stage and row.signature == (full_mask ^ sig)
        ]
        if last_stage_target and last_stage_opposite:
            last_stage_status = "mixed"
        elif last_stage_target:
            last_stage_status = "target_only"
        elif last_stage_opposite:
            last_stage_status = "opposite_only"
        else:
            last_stage_status = "silent"

        mention_rows = target_rows + opposite_rows
        if not mention_rows:
            last_mention_order = None
            last_mention_status = "never"
        else:
            last_mention_order = max(int(row.stage_order_num) for row in mention_rows)
            mention_target = [row for row in target_rows if int(row.stage_order_num) == last_mention_order]
            mention_opposite = [row for row in opposite_rows if int(row.stage_order_num) == last_mention_order]
            if mention_target and mention_opposite:
                last_mention_status = "mixed"
            elif mention_target:
                last_mention_status = "target_only"
            else:
                last_mention_status = "opposite_only"

        semantic_rows.append({
            "condition_id": condition,
            "task_id": task,
            "repetition": int(repetition),
            "composition": "het" if "-het" in condition else "hom",
            "tier": "strong" if "medium" in condition else "weak",
            "recipient": recipient,
            "signature_hex": format(sig, "x"),
            "source_expressions": "|".join(sorted({str(row.expr) for row in source_rows})),
            "source_agents": "|".join(initial_source_agents),
            "source_claim_count": len(source_rows),
            "truth_class": truth_label(truth),
            "adopted_ever": int(bool(target_rows)),
            "target_claim_count_later": len(target_rows),
            "opposite_claim_count_later": len(opposite_rows),
            "ever_opposite": int(bool(opposite_rows)),
            "mixed_history": int(bool(target_rows) and bool(opposite_rows)),
            "latest_recorded_debate_stage": int(max_stage),
            "latest_stage_status": last_stage_status,
            "last_mention_stage": last_mention_order if last_mention_order is not None else "",
            "last_mention_status": last_mention_status,
        })

semantic = pd.DataFrame(semantic_rows)
assert not semantic.empty
semantic.to_csv(OUT_PAIRS, index=False)


def rate_summary(frame: pd.DataFrame) -> dict:
    out = {}
    for tier in ("strong", "weak"):
        part = frame[frame.tier.eq(tier)]
        classes = {}
        for klass in ("truth_aligned", "misleading"):
            rows = part[part.truth_class.eq(klass)]
            classes[klass] = {
                "adopted": int(rows.adopted_ever.sum()),
                "eligible": int(len(rows)),
                "rate": float(rows.adopted_ever.mean()) if len(rows) else None,
                "n_puzzles": int(rows.task_id.nunique()),
            }
        true_rate = classes["truth_aligned"]["rate"]
        false_rate = classes["misleading"]["rate"]
        out[tier] = {
            "pairs": int(len(part)),
            "n_puzzles": int(part.task_id.nunique()),
            "classes": classes,
            "gap_pp": 100 * (true_rate - false_rate) if true_rate is not None and false_rate is not None else None,
        }
    if all(out[tier]["gap_pp"] is not None for tier in ("strong", "weak")):
        out["strong_minus_weak_gap_pp"] = out["strong"]["gap_pp"] - out["weak"]["gap_pp"]
    else:
        out["strong_minus_weak_gap_pp"] = None
    return out


exact_pairs = pd.read_csv(EXACT_PAIRS_PATH).fillna("")
primary_result = json.loads(PRIMARY_RESULT_PATH.read_text())
exact_primary = exact_pairs.copy()
exact_primary["adopted"] = pd.to_numeric(exact_primary.adopted).astype(int)
exact_primary["tier"] = exact_primary["tier"].astype(str)
exact_primary["truth_class"] = exact_primary["information_type"].map({
    "truth_aligned": "truth_aligned", "misleading": "misleading"
})
assert exact_primary.truth_class.notna().all()
exact_primary = exact_primary.rename(columns={"adopted": "adopted_ever"})
exact_summary = rate_summary(exact_primary)
assert len(exact_primary) == primary_result["provenance"]["all_eligible_pairs_reproduced"]
for tier in ("strong", "weak"):
    for klass, index in (("truth_aligned", 0), ("misleading", 2)):
        base = exact_summary[tier]["classes"][klass]
        expected = primary_result["all"][tier]["counts"][index:index + 2]
        assert [base["adopted"], base["eligible"]] == expected


def joint_puzzle_bootstrap(frame: pd.DataFrame) -> dict:
    puzzle_ids = sorted(set(exact_primary.task_id))
    assert len(puzzle_ids) == 20, len(puzzle_ids)
    index = {puzzle: i for i, puzzle in enumerate(puzzle_ids)}
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    weights = rng.multinomial(len(puzzle_ids), np.ones(len(puzzle_ids)) / len(puzzle_ids), size=BOOTSTRAP_DRAWS)
    point = {}
    counts = {}
    for tier in ("strong", "weak"):
        arr = np.zeros((len(puzzle_ids), 4), dtype=float)
        subset = frame[frame.tier.eq(tier)]
        for row in subset.itertuples():
            j = 0 if row.truth_class == "truth_aligned" else 2
            arr[index[row.task_id], j] += int(row.adopted_ever)
            arr[index[row.task_id], j + 1] += 1
        counts[tier] = arr
        sums = arr.sum(axis=0)
        point[tier] = 100 * (sums[0] / sums[1] - sums[2] / sums[3])
    boot = {}
    for tier in ("strong", "weak"):
        sampled = weights @ counts[tier]
        with np.errstate(divide="ignore", invalid="ignore"):
            boot[tier] = 100 * (sampled[:, 0] / sampled[:, 1] - sampled[:, 2] / sampled[:, 3])
    diff = boot["strong"] - boot["weak"]
    diff = diff[np.isfinite(diff)]
    return {
        "estimand": "pooled (truth-aligned adoption rate - misleading adoption rate), strong tier minus weak tier; same resampled task IDs for both tiers",
        "cluster_unit": "20 size-6 task IDs; bootstrap resamples 20 IDs with replacement",
        "seed": BOOTSTRAP_SEED,
        "draws": BOOTSTRAP_DRAWS,
        "gap_pp": {tier: point[tier] for tier in ("strong", "weak")},
        "strong_minus_weak_gap_pp": point["strong"] - point["weak"],
        "ci_95_percentile_pp": np.quantile(diff, [0.025, 0.975]).tolist(),
        "defined_draws": int(len(diff)),
    }


primary_boot = primary_result["all"]["difference"]
semantic_boot = joint_puzzle_bootstrap(semantic)


# Audit the joint support of initial opposition and the exact shared-proposition
# strata used by shared-claim-strata.csv. Common strata are exact key tuples
# present in at least one eligible exposure in each tier.
shared_key = ["task_id", "composition", "expression", "information_type"]
shared_file = pd.read_csv(SHARED_PATH)
present = {
    tier: set(map(tuple, exact_primary.loc[exact_primary.tier.eq(tier), shared_key].itertuples(index=False, name=None)))
    for tier in ("strong", "weak")
}
common_keys = present["strong"] & present["weak"]
assert len(common_keys) == len(shared_file)
assert common_keys == set(map(tuple, shared_file[shared_key].itertuples(index=False, name=None)))
exact_primary["is_shared_stratum"] = [
    tuple(row) in common_keys
    for row in exact_primary[shared_key].itertuples(index=False, name=None)
]
exact_primary["explicit_opposite"] = pd.to_numeric(exact_primary.explicit_opposite).astype(int)
overlap_parts: list[dict] = []
overlap_summary: dict = {
    "shared_definition": "exact (task_id, composition, expression text, information_type) tuple represented among eligible primary exposure pairs in both tiers",
    "opposition_definition": "existing corrected primary flag: the recipient had at least one committed initial non-role proposition semantically complementary to the supplied proposition on the finite exactly-one-spy worlds, and no same-signature initial proposition",
    "weighting": "item-pooled results count eligible recipient pairs; matched-stratum results first compute adopted/eligible within each stratum and tier, then give each common stratum equal weight within truth class",
    "common_shared_strata": int(len(common_keys)),
    "common_shared_strata_by_truth": {
        klass: int(sum(key[3] == klass for key in common_keys))
        for klass in ("truth_aligned", "misleading")
    },
    "eligible_pairs_with_opposition_in_any_common_shared_stratum_by_tier_and_truth": {},
    "eligible_pairs_with_opposition_in_mutually_supported_strata_by_tier_and_truth": {},
    "matched_opposition_strata_by_truth": {},
    "equal_stratum_rates": {},
}
for tier in ("strong", "weak"):
    overlap_summary["eligible_pairs_with_opposition_in_any_common_shared_stratum_by_tier_and_truth"][tier] = {}
    part = exact_primary[exact_primary.tier.eq(tier) & exact_primary.is_shared_stratum & exact_primary.explicit_opposite.eq(1)]
    for klass in ("truth_aligned", "misleading"):
        sub = part[part.truth_class.eq(klass)]
        overlap_summary["eligible_pairs_with_opposition_in_any_common_shared_stratum_by_tier_and_truth"][tier][klass] = {
            "adopted": int(sub.adopted_ever.sum()),
            "eligible": int(len(sub)),
            "rate": float(sub.adopted_ever.mean()) if len(sub) else None,
            "n_puzzles": int(sub.task_id.nunique()),
        }

matched_keys_by_truth: dict[str, set[tuple]] = {}
for klass in ("truth_aligned", "misleading"):
    candidates = {key for key in common_keys if key[3] == klass}
    by_tier_key: dict[str, dict[tuple, tuple[int, int]]] = {"strong": {}, "weak": {}}
    for tier in ("strong", "weak"):
        part = exact_primary[
            exact_primary.tier.eq(tier)
            & exact_primary.is_shared_stratum
            & exact_primary.explicit_opposite.eq(1)
            & exact_primary.truth_class.eq(klass)
        ]
        grouped = part.groupby(shared_key).adopted_ever.agg(["sum", "count"])
        for key, row in grouped.iterrows():
            by_tier_key[tier][tuple(key)] = (int(row["sum"]), int(row["count"]))
    matched = candidates & set(by_tier_key["strong"]) & set(by_tier_key["weak"])
    matched_keys_by_truth[klass] = matched
    overlap_summary["matched_opposition_strata_by_truth"][klass] = {
        "n_candidate_shared_strata": int(len(candidates)),
        "strong_supported": int(len(set(by_tier_key["strong"]) & candidates)),
        "weak_supported": int(len(set(by_tier_key["weak"]) & candidates)),
        "both_tiers_supported": int(len(matched)),
        "matched_task_ids": int(len({key[0] for key in matched})),
    }
    rates = {}
    for tier in ("strong", "weak"):
        cell_rates = [by_tier_key[tier][key][0] / by_tier_key[tier][key][1] for key in matched]
        rates[tier] = float(np.mean(cell_rates)) if cell_rates else None
    overlap_summary["equal_stratum_rates"][klass] = rates
    for key in sorted(candidates):
        row = {name: value for name, value in zip(shared_key, key)}
        row.update({"truth_class": klass})
        for tier in ("strong", "weak"):
            counts = by_tier_key[tier].get(key, (0, 0))
            row[f"{tier}_adopted"] = counts[0]
            row[f"{tier}_eligible"] = counts[1]
            row[f"{tier}_rate"] = counts[0] / counts[1] if counts[1] else ""
        row["matched_opposition_stratum"] = int(key in matched)
        overlap_parts.append(row)

true_rates = overlap_summary["equal_stratum_rates"]["truth_aligned"]
false_rates = overlap_summary["equal_stratum_rates"]["misleading"]
if all(true_rates[tier] is not None and false_rates[tier] is not None for tier in ("strong", "weak")):
    overlap_summary["equal_stratum_gap_pp"] = {
        tier: 100 * (true_rates[tier] - false_rates[tier]) for tier in ("strong", "weak")
    }
    overlap_summary["equal_stratum_strong_minus_weak_gap_pp"] = (
        overlap_summary["equal_stratum_gap_pp"]["strong"] - overlap_summary["equal_stratum_gap_pp"]["weak"]
    )
else:
    overlap_summary["equal_stratum_gap_pp"] = None
    overlap_summary["equal_stratum_strong_minus_weak_gap_pp"] = None
pd.DataFrame(overlap_parts).to_csv(OUT_OVERLAP, index=False)

for tier in ("strong", "weak"):
    overlap_summary["eligible_pairs_with_opposition_in_mutually_supported_strata_by_tier_and_truth"][tier] = {}
    for klass in ("truth_aligned", "misleading"):
        keys = matched_keys_by_truth[klass]
        rows = exact_primary[
            exact_primary.tier.eq(tier)
            & exact_primary.explicit_opposite.eq(1)
            & exact_primary.truth_class.eq(klass)
            & exact_primary[shared_key].apply(tuple, axis=1).isin(keys)
        ]
        overlap_summary["eligible_pairs_with_opposition_in_mutually_supported_strata_by_tier_and_truth"][tier][klass] = {
            "adopted": int(rows.adopted_ever.sum()),
            "eligible": int(len(rows)),
            "rate": float(rows.adopted_ever.mean()) if len(rows) else None,
            "n_puzzles": int(rows.task_id.nunique()),
        }

def pooled_gap_summary(block: dict) -> dict:
    gaps = {}
    for tier in ("strong", "weak"):
        true_rate = block[tier]["truth_aligned"]["rate"]
        false_rate = block[tier]["misleading"]["rate"]
        gaps[tier] = 100 * (true_rate - false_rate) if true_rate is not None and false_rate is not None else None
    return {
        "gap_pp": gaps,
        "strong_minus_weak_gap_pp": gaps["strong"] - gaps["weak"]
        if gaps["strong"] is not None and gaps["weak"] is not None else None,
    }

overlap_summary["item_pooled_gap_for_any_common_shared_opposition_rows"] = pooled_gap_summary(
    overlap_summary["eligible_pairs_with_opposition_in_any_common_shared_stratum_by_tier_and_truth"]
)
overlap_summary["item_pooled_gap_for_mutually_supported_opposition_rows"] = pooled_gap_summary(
    overlap_summary["eligible_pairs_with_opposition_in_mutually_supported_strata_by_tier_and_truth"]
)


latest_stage_distribution = Counter(
    semantic.latest_recorded_debate_stage.astype(int).astype(str).tolist()
)
latest_status_counts = Counter(semantic.latest_stage_status.astype(str))
last_mention_counts = Counter(semantic.last_mention_status.astype(str))
ever_target_pairs = semantic[semantic.adopted_ever.eq(1)]
persistence = {
    "eligible_semantic_pairs": int(len(semantic)),
    "n_puzzles": int(semantic.task_id.nunique()),
    "ever_target_expression": int(semantic.adopted_ever.sum()),
    "ever_target_rate": float(semantic.adopted_ever.mean()),
    "ever_opposite_expression": int(semantic.ever_opposite.sum()),
    "ever_opposite_rate": float(semantic.ever_opposite.mean()),
    "ever_both_target_and_opposite": int(semantic.mixed_history.sum()),
    "ever_both_rate": float(semantic.mixed_history.mean()),
    "latest_recorded_debate_stage_distribution": dict(sorted(latest_stage_distribution.items())),
    "latest_recorded_stage_status": dict(sorted(latest_status_counts.items())),
    "last_mention_status": dict(sorted(last_mention_counts.items())),
    "among_ever_target": {
        "latest_recorded_stage_status": dict(sorted(Counter(ever_target_pairs.latest_stage_status.astype(str)).items())),
        "last_mention_status": dict(sorted(Counter(ever_target_pairs.last_mention_status.astype(str)).items())),
    },
    "definition": {
        "ever_target": "any later ASSERT/ENDORSE expression with the supplied proposition signature at stage_order > 0 and < 10010",
        "ever_opposite": "any such expression with the bitwise-complement signature over the same 192 exactly-one-spy worlds",
        "latest_recorded_stage_status": "whether target, opposite, both, or neither was expressed at the maximum non-final stage_order present anywhere in that condition/task/repetition; neither is recorded silence at that stage",
        "last_mention_status": "target/opposite/mixed at the latest stage when either proposition was expressed; never means neither was expressed in the recorded debate history",
        "interpretation": "these are claim-recording states; silence is not retraction, and an expressed claim does not establish uptake caused by another agent",
    },
}

input_paths = [
    CLAIMS_PATH,
    INPUT / "questions.jsonl",
    INPUT / "labels.jsonl",
    INPUT / "initial-positions.json",
    EXACT_PAIRS_PATH,
    PRIMARY_RESULT_PATH,
    SHARED_PATH,
    PRIMARY_SCRIPT_PATH,
    P / "claim_logic.py",
]
result = {
    "definitions": {
        "semantic_universe": "all 192 six-player role assignments with exactly one spy, matching claim_logic.assignments(6)",
        "supply": "a stage-0 ASSERT/ENDORSE claim with corrected information_type truth_aligned or misleading and no ROLE predicate; each semantic proposition signature is counted once per condition, task, repetition",
        "initial_absence": "recipient has no stage-0 ASSERT/ENDORSE claim with the same semantic signature; checks all committed formulas, including role-bearing formulas, against the same finite-world signature",
        "later_recurrence": "any recipient ASSERT/ENDORSE claim semantically equivalent on that same universe at stage_order > 0 and < 10010",
        "truth_class": "direct truth evaluation of the supplied proposition on canonical labels.jsonl gold roles; informative source annotations are checked against this classification",
        "rate_estimand": "eligible recipient-pair pooled adoption rates for truth-aligned and misleading propositions; per-tier gap is true rate minus false rate",
        "pair_unit": "one condition x task x repetition x semantic supply proposition x initially absent recipient",
        "final_stage": "all claims with stage_order >= 10010 excluded from later recurrence and persistence summaries",
    },
    "primary_exact_expression": {
        "source": "controlled-exposure-pairs.csv and strength-controls.json all condition",
        "pairs": int(len(exact_primary)),
        "summary": exact_summary,
        "reported_primary_joint_puzzle_bootstrap": {
            "estimand": "as stored by strength_controls.py",
            "seed": primary_result["provenance"]["seed"],
            "draws": primary_result["provenance"]["draws"],
            "strong_minus_weak_gap_pp": primary_boot["gap_pp"],
            "ci_95_percentile_pp": primary_boot["ci"],
            "defined_draws": primary_boot["defined_draws"],
        },
    },
    "semantic_sensitivity": {
        "pairs": int(len(semantic)),
        "summary": rate_summary(semantic),
        "joint_puzzle_bootstrap": semantic_boot,
        "denominator_change_vs_exact_by_tier_truth": {
            tier: {
                klass: semantic_summary["eligible"] - exact_summary[tier]["classes"][klass]["eligible"]
                for klass, semantic_summary in rate_summary(semantic)[tier]["classes"].items()
            }
            for tier in ("strong", "weak")
        },
    },
    "joint_shared_and_opposition": overlap_summary,
    "persistence": persistence,
    "audit": {
        "claim_rows": int(len(claims)),
        "assert_or_endorse_rows": int(claims.commitment_norm.isin(COMMITMENTS).sum()),
        "unparsed_assert_or_endorse_rows_excluded": parse_failures,
        "final_stage_rows_excluded": int((pd.to_numeric(claims.stage_order) >= FINAL_STAGE).sum()),
        "semantic_supply_proposition_count": int(semantic.groupby(["condition_id", "task_id", "repetition", "signature_hex"]).ngroups),
        "source_label_gold_world_mismatches": 0,
        "all_20_puzzle_primary_exact_pairs_reproduced": int(exact_primary.task_id.nunique()),
        "model_calls": 0,
    },
    "provenance": {
        "sha256": {path.relative_to(P).as_posix(): sha256(path) for path in input_paths},
        "script_sha256": sha256(Path(__file__)),
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_draws": BOOTSTRAP_DRAWS,
    },
}
OUT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


def pct(rate: float | None) -> str:
    return "n/a" if rate is None else f"{100 * rate:.1f}%"


def fmt_cell(block: dict) -> str:
    return f"{block['adopted']}/{block['eligible']} ({pct(block['rate'])})"


semantic_summary = result["semantic_sensitivity"]["summary"]
comparison_lines = []
for tier in ("strong", "weak"):
    exact = exact_summary[tier]
    sem = semantic_summary[tier]
    comparison_lines.append(
        f"| {tier} | {fmt_cell(exact['classes']['truth_aligned'])} | "
        f"{fmt_cell(sem['classes']['truth_aligned'])} | {fmt_cell(exact['classes']['misleading'])} | "
        f"{fmt_cell(sem['classes']['misleading'])} | {exact['pairs']} | {sem['pairs']} |"
    )

joint_ci = semantic_boot["ci_95_percentile_pp"]
opp_true = overlap_summary["matched_opposition_strata_by_truth"]["truth_aligned"]
opp_false = overlap_summary["matched_opposition_strata_by_truth"]["misleading"]
report = f"""# Semantic matching and persistence sensitivity

This is a corrected-corpus, descriptive sensitivity analysis. It uses no new model calls. The reproducible script is matching_persistence.py; machine-readable outputs are matching_persistence.json, matching_persistence_pairs.csv, and matching_persistence_overlap.csv.

## Definitions

- Proposition equivalence is evaluated over the same 192 six-player assignments with exactly one spy, using canonical puzzle statements and the finite-world evaluator in claim_logic.py.
- An initial supply is a stage-0 ASSERT/ENDORSE claim annotated truth_aligned or misleading that contains no ROLE predicate. Equivalent initial supplies are deduplicated once per condition, puzzle, repetition, and semantic signature.
- Initial absence means the recipient has no stage-0 ASSERT/ENDORSE claim with that same signature, including a role-bearing expression. Later recurrence means any semantically equivalent recipient ASSERT/ENDORSE claim at stage_order greater than 0 and less than 10010. Final decision claims are excluded.
- Truth class is evaluated directly on the canonical gold role assignment. Source information labels agree with that direct evaluation for all included supplies.
- Rates pool eligible recipient-proposition pairs. The gap is the true-claim adoption rate minus the misleading-claim adoption rate. The contrast is the strong-tier gap minus the weak-tier gap.

## Primary versus semantic matching

The exact primary uses raw expression equality for initial absence and later recurrence. The sensitivity uses semantic signatures for both. Cells show adopted/eligible pairs and rate.

| Tier | Exact true | Semantic true | Exact false | Semantic false | Exact pairs | Semantic pairs |
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(comparison_lines)}

The exact-expression strong-minus-weak gap contrast is {exact_summary['strong_minus_weak_gap_pp']:.1f} percentage points. Semantic matching gives {semantic_summary['strong_minus_weak_gap_pp']:.1f} points, with a joint 20-puzzle percentile bootstrap 95% interval of {joint_ci[0]:.1f} to {joint_ci[1]:.1f}. The bootstrap resamples the same 20 puzzle IDs jointly across tiers and pools recipient-pair counts within each replicate; it is descriptive uncertainty, not a causal estimate.

## Opposition and shared propositions

The common shared set has {overlap_summary['common_shared_strata']} exact proposition strata: {overlap_summary['common_shared_strata_by_truth']['truth_aligned']} true and {overlap_summary['common_shared_strata_by_truth']['misleading']} false, each observed among eligible primary pairs in both tiers. The primary opposition flag means the recipient itself had an initial committed proposition semantically complementary to the supplied proposition, with no same-signature initial proposition. Within these {overlap_summary['common_shared_strata']} shared strata, opposition is represented in both tiers for {opp_true['both_tiers_supported']} of {opp_true['n_candidate_shared_strata']} true strata and {opp_false['both_tiers_supported']} of {opp_false['n_candidate_shared_strata']} false strata. The item-pooled opposition counts include every eligible pair in any shared stratum with opposition in that tier, including strata supported by only one tier. Equal-stratum rates use only propositions with opposition pairs in both tiers within a truth class, then weight each proposition stratum equally: {opp_true['both_tiers_supported']} true strata from {opp_true['matched_task_ids']} puzzle(s), and {opp_false['both_tiers_supported']} false strata from {opp_false['matched_task_ids']} puzzles. The false-proposition overlap is sparse, so its rate contrast is unstable and should remain descriptive.

## Recorded persistence

Across {persistence['eligible_semantic_pairs']} initially absent semantic recipient-proposition pairs, {persistence['ever_target_expression']} ({pct(persistence['ever_target_rate'])}) ever expressed the supplied proposition later; {persistence['ever_opposite_expression']} expressed its finite-world complement; {persistence['ever_both_target_and_opposite']} expressed both at some point. Among the {persistence['ever_target_expression']} ever-target pairs, latest-mention status was {json.dumps(persistence['among_ever_target']['last_mention_status'], sort_keys=True)}; status at the latest recorded non-final stage was {json.dumps(persistence['among_ever_target']['latest_recorded_stage_status'], sort_keys=True)}. Across all pairs, that endpoint had statuses {json.dumps(persistence['latest_recorded_stage_status'], sort_keys=True)}. Silence means no matching proposition was recorded at that stage; it is not treated as retraction. Repeated or opposite expression is not evidence that one agent caused another's reasoning.

## Limits and provenance

This changes the counting unit from an exact formula string to one proposition signature per debate and recipient, so denominators need not equal the primary. The finite world set treats propositions as equivalent only under the disclosed exactly-one-spy constraint; it does not establish equivalence outside that puzzle domain. Claim records show expression, not private belief or causal uptake. The output JSON records SHA-256 hashes of the corrected claim corpus, canonical questions/labels, exact primary pair table and results, shared-stratum table, and evaluator.
"""
OUT_REPORT.write_text(report)

print(json.dumps({
    "exact_primary": exact_summary,
    "semantic_sensitivity": semantic_summary,
    "semantic_bootstrap": semantic_boot,
    "joint_shared_opposition": overlap_summary,
    "persistence": persistence,
    "outputs": [str(path.relative_to(P)) for path in (OUT_JSON, OUT_PAIRS, OUT_OVERLAP, OUT_REPORT)],
}, indent=2, sort_keys=True))
