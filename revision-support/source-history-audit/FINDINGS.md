# Raw-source audit findings

The pilot found source-to-measurement discrepancies that numerical replay cannot detect. They concern commitment, scope, and omitted explicit claims. The result supports targeted correction and clearer annotation rules; it does not justify replacing the translator, nor does it validate the full-corpus 57.3-point estimate.

## What was reviewed

Eight complete six-player debates cover two puzzles in all four team conditions: 336 nonempty initial and later pre-final fields. The sample was deterministically frozen without consulting extraction outcomes. Two Luna-xhigh agents reconstructed supplies and histories from source-only packets; a third independently inventoried all initial explanations. Model identities, condition labels, verified solutions and pipeline outputs were withheld during first passes. The root assistant reconciled source disagreements and then inspected pipeline discrepancies. Original annotations and later decisions are retained separately.

The initial passes agreed on 34 of 51 informative proposition–speaker presences found by either pass after semantic grouping. The remaining 17 involved count omissions, scope, contradictory assertions and direct evaluations. This is disagreement between annotators, not a translator accuracy estimate. Reconciliation corrected audit errors as well as pipeline errors. Later review also recovered a directly expressed relation equivalent to a puzzle statement, and distinguished direct formula equivalence from inferring statement truth from the speaker's role.

This is model-assisted adjudication using the same model family as the translator, followed by root-assistant review; shared interpretation errors remain possible. The initial exclusion registry was incomplete: an older adopted-pair audit included one of the two sampled puzzles. That overlap was discovered after freezing and is disclosed in `prior-review-overlap.json`; the sample was retained. This is not independent human validation, an untouched holdout, or a representative error-rate study.

## Discrepancies

The reconciliation retains nine source-level discrepancy groups affecting 13 records in the sampled semantic-pair comparison. These are judgments under the written annotation policy, not independently certified ground truth. The complete excerpts and rationales are in `source-discrepancy-ledger.json`.

| Measurement issue | Affected semantic pair records | Example |
|---|---:|---|
| Report/reformulation counted as initial assertion | 2 | “A's statement reduces to A and B same role” was scored as asserting SAME_ROLE(A,B). |
| Recipient's initial commitment missed | 2 | “A's statement is false” was present before the supposed uptake. |
| Conditional counted as an initial assertion | 1 | “F's statement is true if…” was reduced to unconditional F-true, hiding a potentially eligible recipient. |
| Explicit initial supplies omitted | 8 | “A is knave (lying)” and numerical whole-puzzle role counts contain explicit content beyond a bare role label. |

One omitted-supply judgment involves a false-statement description following an assumed solution and remains sensitive to the commitment policy. Count universes and implication/presupposition scope also require care. The artifact retains unresolved cases rather than declaring all differences errors. Its comparison classification includes 11 ambiguous recipient-initial comparisons, six comparisons with ambiguous initial supply, and one existing-pair later-recurrence ambiguity. An additional source-derived pair has ambiguous later recurrence. A disputed count-universe candidate supplies no unambiguous eligible pair.

## Sample-only effect

The original pipeline has 80 exact-expression opportunities and 64 semantic opportunities in these eight debates. The source-derived comparison groups semantically equivalent propositions, so it should be compared with semantic matching, not directly with the paper's exact-expression headline.

| Source-derived clear cases | True recurrence | False recurrence |
|---|---:|---:|
| Stronger teams | 9/9 | 0/2 |
| Weaker teams | 9/17 | 10/22 |

These counts exclude ambiguous initial eligibility and two pairs with ambiguous later recurrence (one per tier). Among these clear cases, the difference in true-minus-false rates is 92.5 points; the pipeline's semantic difference on the same debates is 65.7 points. The direction survives this pilot, but the denominators change, only two puzzle clusters are represented, and only two clear stronger-team false opportunities remain. The increase is not evidence that the full-corpus effect is larger or validated. No bootstrap interval or corpus-wide corrected effect is claimed.

## Consequence for the paper

Keep the translator fixed while resolving the recorded cases and clarifying assertion/report boundaries, assumption scope, count universes and explicit truth descriptions. Then apply a versioned correction to affected source records and recompute all downstream results. If these patterns recur systematically, change the relevant translator rules and evaluate them on separate data before rerunning the corpus. A new model or broad translator redesign is not supported by this pilot.

A human reviewer can inspect the included source packets and disagreement ledger; that independent adjudication would add evidence beyond another model-assisted pass. When first written, these findings preceded the v3 corrections described below and the manuscript update.

## Verification and files

Every full-history annotation lists all nonempty fields. The structural checker validates expression syntax, phase/agent ownership and verbatim evidence. These checks do not validate interpretation. `firstpass-freeze.json` preserves initial hashes; `adjudication-freeze.json` records the final audit version. `event-comparison.csv`, `comparison-summary.json` and `pipeline-disputed-evidence.json` expose the numerical comparison and underlying extraction spans. No debate generations or full-corpus retranslations were run.

## Follow-up: bounded source correction

The earlier discrepancy table was a pilot classification, not a set of nine
confirmed translator errors. In particular, the label “explicit initial
supplies omitted” overstated several cases: later source inspection found
some candidate claims already represented inside explicit hypothetical cases.
Those claims were not promoted to unconditional facts. Scope- and
polarity-sensitive candidates remain unresolved, as detailed in the
versioned correction ledger.

The project applied a source-grounded correction to four complete fields in
`../corrections/source-audit-v3/`. It relabels one reported reformulation as
a report, puts two claims under the explicit conditional they express, adds
three directly stated statement-truth claims, and reanchors a final role
claim to the speaker's final role list while removing its unsupported
premise links. The original claim inventory and frozen field records remain
available. The translation model was not rerun. The numerical reproduction
entry point applies this overlay before recomputing the affected results.
The sample-only comparison above remains the historical comparison against
the frozen pre-source-correction pipeline; it is not the revised paper's
current estimate.

This follow-up does not turn the audit into independent validation. The four
fields were selected from the model-assisted pilot and followed by
root-assistant review; no human fidelity audit has been performed. The
correction supports targeted measurement repair, but it does not estimate
corpus-wide translation error or establish that unreviewed claims are
complete and correctly scoped. See
`../corrections/source-audit-v3/manifest.json` and
`../corrections/source-audit-v3/correction-ledger.json` for the applied
changes once the reproduction overlay has been generated.

## Current-version reconciliation

The current source-audit-v3 comparison is now in [current-v3/SUMMARY.md](current-v3/SUMMARY.md), regenerated by `reconcile_current.py`. It preserves the historical comparison above, distinguishes claim corrections from reference corrections, and reports unresolved alternatives. Its stage decisions cover all 129 candidate recipient records rather than adopted examples alone. It remains a post-hoc model-assisted diagnostic.
