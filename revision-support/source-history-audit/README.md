# Raw-source history audit

This directory contains a model-assisted diagnostic audit of eight complete six-player debates: two puzzle IDs in all four team conditions. The sample and annotation protocol were frozen before reviewing extracted outcomes. `sample-manifest.json` records selection, source hashes and the condition mapping; `protocol-freeze.json` records the independent annotation assignments. Blinded source packets omit model identities, condition labels, verified answers and extracted claims.

`prior-review-overlap.json` records an older source audit discovered after freezing the sample. One selected puzzle had appeared there. The sample was retained rather than replaced. The annotators use Luna at xhigh effort, the same model family as the original low-effort translator, so shared interpretation errors remain possible. This is not an untouched holdout or independent human validation, and the two puzzle clusters cannot support a corpus-wide error-rate estimate.

Two annotators reconstruct initial supplies and recipient histories from all nonempty raw fields. A third independently inventories initial claims. `*-firstpass.json` files preserve those passes; later adjudication must be stored separately. `check_annotations.py` verifies field coverage, expression syntax and verbatim anchors, not semantic accuracy. `crosscheck_initial.py` compares the two initial inventories. `compare.py` compares source-derived events with the frozen pipeline, preserving the distinction between exact expression matching and semantic matching.

Run the structural and comparison checks with Python 3.11+ after annotation files are present:

```sh
python check_annotations.py
python crosscheck_initial.py
python compare.py
```

Preparation reads local raw archives at recorded repository paths. The source packets preserve the fields needed for this audit. Running `prepare.py` recreates the frozen packets from that archive; it is not necessary to review the included packets. Do not replace annotations or silently update the paper's full-corpus estimates from this small audit. The final findings and remaining uncertainties belong in `FINDINGS.md` once reconciliation is complete.
