# Semantic matching and persistence sensitivity

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
| strong | 157/199 (78.9%) | 142/161 (88.2%) | 13/88 (14.8%) | 16/80 (20.0%) | 287 | 241 |
| weak | 132/241 (54.8%) | 130/208 (62.5%) | 96/200 (48.0%) | 96/173 (55.5%) | 441 | 381 |

The exact-expression strong-minus-weak gap contrast is 57.3 percentage points. Semantic matching gives 61.2 points, with a joint 20-puzzle percentile bootstrap 95% interval of 39.8 to 83.6. The bootstrap resamples the same 20 puzzle IDs jointly across tiers and pools recipient-pair counts within each replicate; it is descriptive uncertainty, not a causal estimate.

## Opposition and shared propositions

The common shared set has 64 exact proposition strata: 49 true and 15 false, each observed among eligible primary pairs in both tiers. The primary opposition flag means the recipient itself had an initial committed proposition semantically complementary to the supplied proposition, with no same-signature initial proposition. Within the 64 shared strata, opposition is represented in both tiers for 2 of 49 true strata and 3 of 15 false strata. The item-pooled opposition counts include every eligible pair in any shared stratum with opposition in that tier, including strata supported by only one tier. Equal-stratum rates use only propositions with opposition pairs in both tiers within a truth class, then weight each proposition stratum equally: 2 true strata from 1 puzzle(s), and 3 false strata from 2 puzzles. The false-proposition overlap is sparse, so its rate contrast is unstable and should remain descriptive.

## Recorded persistence

Across 622 initially absent semantic recipient-proposition pairs, 384 (61.7%) ever expressed the supplied proposition later; 212 expressed its finite-world complement; 77 expressed both at some point. Among the 384 ever-target pairs, latest-mention status was {"mixed": 11, "opposite_only": 32, "target_only": 341}; status at the latest recorded non-final stage was {"mixed": 11, "opposite_only": 32, "silent": 59, "target_only": 282}. Across all pairs, that endpoint had statuses {"mixed": 11, "opposite_only": 145, "silent": 184, "target_only": 282}. Silence means no matching proposition was recorded at that stage; it is not treated as retraction. Repeated or opposite expression is not evidence that one agent caused another's reasoning.

## Limits and provenance

This changes the counting unit from an exact formula string to one proposition signature per debate and recipient, so denominators need not equal the primary. The finite world set treats propositions as equivalent only under the disclosed exactly-one-spy constraint; it does not establish equivalence outside that puzzle domain. Claim records show expression, not private belief or causal uptake. The output JSON records SHA-256 hashes of the corrected claim corpus, canonical questions/labels, exact primary pair table and results, shared-stratum table, and evaluator.
