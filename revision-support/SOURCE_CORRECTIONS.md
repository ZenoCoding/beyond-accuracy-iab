# Bounded source corrections

This note records the source-grounded changes in `corrections/source-audit-v3/`
and the candidates deliberately left unresolved. The correction repairs a few
specific measurements in four sampled translation fields from an eight-debate
source audit. It is not a corpus-wide translation revision or an estimate of
corpus-wide error.

## Applied changes

The corrections start from the preserved claim inventory and the four complete
formal records in `corrections/source-audit-v3/frozen-fields.json`. The package
contains source-only packets and annotations for all eight audited debates,
plus a frozen pre-correction comparison snapshot. The source spans are checked
against the original field text. Original inputs and the earlier
role-predicate overlay remain preserved.

| Audit field | Source-grounded change | Why |
|---|---|---|
| D04, agent 2 | Reclassify claim c6 (`SAME_ROLE(A,B)`) as a report attributed to A. Keep dependent claim c7's reference to c6, but mark that premise unresolved and clear its conditional score. | The text describes what A's statement reduces to; a report does not establish that A and B have the same role as a truth-bearing premise. |
| D02, agent 2 | Add `STMT_TRUE(E)` from “E must be knight telling truth”; retain the field's existing, contradictory claim. | The explicit truth evaluation is present in the text even though the same field also expresses its negation. |
| D02, agent 3 | Move the F-truth claim and its count antecedent into a new unresolved hypothetical case for “F's statement is true if at most two among C,D,E,F are knights.” Keep the separate earlier case intact. Reanchor the final F-role claim to the later final role list (“D,E,F knights”) and remove its unsupported premise links. | The conditional does not state F-truth unconditionally; the final role list is stated as the conclusion. The annotation should follow those scopes and source spans. |
| D06, agent 1 | Add `STMT_TRUE(C)` and `STMT_TRUE(F)` from the explicit description of C and F as “knights (truth-tellers).” | These truth evaluations are explicit content in addition to the already represented role claims. |

The correction therefore changes commitment and case metadata, adds three
explicit statement-truth claims, marks one dependent premise unresolved, and
repairs one final role claim's evidence and local premise link. It does not replace the translator or regenerate
relation annotations across the corpus. The analyses recompute the affected
claim recurrence, initial-supply features, and downstream summaries from the
corrected frozen records.

## Candidates left unresolved

The pilot's initial “omitted claim” labels were broader than the confirmed
correction set. On checking complete fields, several candidates already
appeared under explicit hypothetical assumptions. They remain hypothetical;
the correction does not promote them to unconditional claims.

| Audit candidate | Disposition |
|---|---|
| D03, agent 2: E-false claim under “assuming B knave works.” | Already represented as hypothetical; no scope promotion. |
| D05, agent 1: A-false and count/role claims under “If B knave.” | Already represented in the conditional case; no scope promotion. |
| D06, agent 2: A-false and the four-knave count under the explicit case. | Remains case-scoped. The count expression is also inconsistent with the surrounding arithmetic, so it is not used as an unconditional supply. |
| D08: positive `SAME_ROLE` reading of “same role as B false false.” | Polarity remains unclear; no correction is applied. |

Other candidates involving implication, assumed solutions, count universes,
or uncertain source-to-expression mapping also remain unchanged. The source
audit ledger preserves their excerpts and rationales. These unresolved cases
are not silently counted as confirmed translator errors.

## Reproduction and limits

Run `python revision-support/reproduce_numerical_results.py` from the
extracted `makis2026/` directory to regenerate the versioned overlays and
downstream analyses. The source correction reads frozen translation records;
it makes no translation or debate-generation calls. The pre-correction
source-audit comparison is preserved as a historical baseline.

The source reconstruction and adjudication were model-assisted, using the
same model family as the translator, followed by root-assistant review. No
human fidelity validation has been performed. The correction covers four
fields in a small diagnostic sample. It does not establish the completeness
or semantic accuracy of unreviewed claims, and it does not justify a
corpus-wide translation accuracy estimate. See
`source-history-audit/FINDINGS.md` for the audit design and limitations, and
`corrections/source-audit-v3/manifest.json` plus
`corrections/source-audit-v3/correction-ledger.json` for generated inputs,
hashes, and row-level changes.
