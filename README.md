# Beyond Accuracy
**Formalization for Understanding Information Exchange in Multi-Agent Debate**  
Sarah Wu and Tycho Young · IAB 2026

This repository contains the corrected analysis and underlying records for 120 three-agent Knight–Knave–Spy debates. The main comparison uses 80 debates on 20 six-player puzzles. Stronger teams repeated 78.9% of previously unexpressed true peer claims and 12.8% of false ones. Weaker teams repeated 54.5% and 48.3%, respectively.

## Reproduce the paper
From the repository root with Python 3.12, run:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r revision-support/requirements-reproduction.txt
.venv/bin/python revision-support/reproduce_numerical_results.py
```

The replay uses frozen inputs and runs locally without model calls. Start with [uptake by tier](revision-support/tier-uptake.json), [outcome rankings](revision-support/puzzle-cluster-auc.csv), or the [source-audit reconciliation](revision-support/source-history-audit/current-v3/). The scripts rebuild tables in place.

## Follow a result back to its data
The [baseline inputs](revision-support/control-inputs/) precede two corrections. The [eligibility correction](revision-support/corrections/role-predicate-v2/) identifies role predicates in formal expressions. The [claim corrections](revision-support/corrections/source-audit-v3/) contain the final claims, eligible pairs, and correction ledger used in the paper. The [version map](revision-support/ARTIFACT_VERSIONS.json) records the baseline file hashes.

For original puzzle statements, transcripts, translations and historical scoring code, unpack the raw archive and verify it:

```sh
tar -xzf beyondaccuracysupplement.tar.gz
(cd release-staging && python3 scripts/verify_release.py)
```

The archive preserves an earlier analysis. Use the top-level replay above for the IAB estimates.

[Code license](LICENSE-CODE) · [Data license](LICENSE-DATA)
