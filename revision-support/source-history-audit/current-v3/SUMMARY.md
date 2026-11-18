# Current-v3 source-history reconciliation

Eight debates, two puzzle clusters; diagnostic sample, not corpus error-rate estimate. Model-assisted source judgments with unresolved alternatives, not certified ground truth.

The independent current-claim reconstruction exactly matches all 63 semantic opportunities and their later-expression indicators in the sampled debates (80 exact-expression opportunities). The union of source-inventoried and pipeline-eligible propositions contains 43 propositions and 129 candidate recipient records; all three recipients are retained, including ineligible records and non-recurrences.

A versioned reference overlay retains 8 initial judgments as ambiguous (including already-ambiguous D08 polarity and unresolved D07 scope), and repairs three later reference omissions using explicit semantically equivalent B-knave assertions. No historical annotation, corpus claim, or historical comparison is modified. Alternative assignments are marginal possibilities, not independent rows for statistical inference.

| Stage | Clear agreements | Clear disagreements | Unresolved |
|---|---:|---:|---:|
| peer_supply | 103 | 0 | 26 |
| recipient_initial_presence | 106 | 0 | 23 |
| explicit_opposition | 79 | 0 | 50 |
| eligibility | 99 | 0 | 30 |
| later_recurrence | 112 | 1 | 16 |

Disagreements are conditional on these reviewed reference judgments, not certified extraction errors. Explicit opposition uses informative non-role initial commitments for both target and opposite, matching the main control; all-role semantic presence remains the recurrence eligibility rule. Explicit opposition is unresolved when the frozen target inventory does not establish the opposite proposition; absence from that inventory is not imputed as absence from source. Later recurrence is assessed on every candidate recipient; eligible-only outcomes are separated below.

| Tier / truth | Clear eligible with known outcome | Later recurrence | Ambiguous later among clear eligible |
|---|---:|---:|---:|
| strong_true | 9 | 9 | 0 |
| strong_false | 2 | 0 | 0 |
| weak_true | 13 | 7 | 0 |
| weak_false | 20 | 10 | 1 |

Of 44 unambiguously eligible records with a determinate later outcome, 44 agree with the current pipeline and 0 disagree, including non-recurrences. A further 1 unambiguously eligible records have unresolved later scope. The single later-expression disagreement in the full candidate universe is D01 agent-1, A-false: the source credits Agent-3 as correctly identifying falsity, while the pipeline lacks a committed later match. That recipient already expressed A-false initially, so this is not an eligible uptake event. These statements describe only the reviewed subset; unresolved records must not be counted as successes or failures.

Non-role explicit-opposition reconstruction matches all 80 archived exact-expression opportunity flags for these debates; opposition-reconstruction.csv records every comparison.

`stage-summary.csv` separates stage, tier and truth. `stage-decisions.csv` and `event-comparison.csv` retain every candidate decision. `alternative-assignments.csv` preserves unresolved eligibility/outcome possibilities; `reference-overlay.json` preserves the changed judgments and complete source fields. `summary.json` records input hashes. The source packets and frozen adjudications in the parent directory contain evidence spans and full histories.

Reproduce: `python source-history-audit/reconcile_current.py` from revision-support. No model calls or retranslations. Numerical reconstruction is checked separately from source fidelity.
