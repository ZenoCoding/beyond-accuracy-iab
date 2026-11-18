"""Reconcile the corrected 120-debate cohort with puzzle-cluster intervals.

Keeps the corrected metric values and AUC estimator. Within each puzzle size,
resamples 20 puzzle IDs and carries all associated conditions together.
No model calls or changes to translations; the copied inputs are immutable.
"""
from pathlib import Path
import hashlib
import json
import shutil
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE
INPUT = HERE / "corrections/source-audit-v3"
for name in ['debate-features.csv', 'paper-auc.csv', 'exposure-pairs.csv']:
    assert (INPUT / name).is_file(), f'Missing frozen input: {name}'

d = pd.read_csv(INPUT / 'debate-features.csv', float_precision='round_trip')
old = pd.read_csv(INPUT / 'paper-auc.csv', float_precision='round_trip')
e = pd.read_csv(INPUT / 'exposure-pairs.csv')
assert len(d) == 120 and d.operational_final_correct.sum() == 73
puzzles = sorted(d.task_id.unique())
assert len(puzzles) == 40
index = {p: i for i, p in enumerate(puzzles)}
rng = np.random.default_rng(20260906)
weights = np.zeros((10000, 40), dtype=int)
for size in [6, 8]:
    ids = sorted(d.loc[d['size'].eq(size), 'task_id'].unique())
    assert len(ids) == 20
    weights[:, [index[p] for p in ids]] = rng.multinomial(20, np.full(20, 1/20), size=10000)

def ratio(a, b):
    return np.divide(a, b, out=np.full(np.shape(a), np.nan), where=b != 0)

def interval(x):
    finite = x[np.isfinite(x)]
    return [float(v) for v in np.quantile(finite, [.025, .975])], len(finite)

rows = []
for feature in old.feature:
    a = d[d[feature].notna()]
    ss = a[a.operational_final_correct.eq(1)]
    ff = a[a.operational_final_correct.eq(0)]
    row = dict(feature=feature, n=len(a))
    for mode in ['pooled', 'within']:
        num = np.zeros((40, 40))
        den = np.zeros((40, 40))
        contributors = set()
        for si, s in ss.iterrows():
            for fi, f in ff.iterrows():
                if mode == 'within' and s.stratum != f.stratum:
                    continue
                i, j = index[s.task_id], index[f.task_id]
                den[i, j] += 1
                num[i, j] += float(s[feature] > f[feature]) + .5 * float(s[feature] == f[feature])
                contributors.update([si, fi])
        point = num.sum() / den.sum()
        expected = old.loc[old.feature.eq(feature), 'auc_pooled' if mode == 'pooled' else 'auc_within_condition'].iloc[0]
        assert np.isclose(point, expected, atol=1e-12), (feature, mode, point, expected)
        calc = lambda m: np.einsum('bi,ij,bj->b', weights, m, weights, optimize=True)
        ci, valid = interval(ratio(calc(num), calc(den)))
        row.update({mode+'_auc': point, mode+'_low': ci[0], mode+'_high': ci[1], mode+'_defined_draws': valid,
                    mode+'_pairs': int(den.sum()), mode+'_contributing': len(contributors)})
    rows.append(row)
pd.DataFrame(rows).to_csv(OUT / 'puzzle-cluster-auc.csv', index=False)

gaps = {}
gap_draws = {}
for tier in ['weak', 'strong']:
    ee = e[e.dataset.eq('size6') & e.condition_id.str.contains('weak' if tier == 'weak' else 'medium')]
    vals = {}
    draws = {}
    for kind, label in [('truth_aligned', 'true'), ('misleading', 'false')]:
        sub = ee[ee.information_type.eq(kind)]
        hits = np.zeros(40)
        counts = np.zeros(40)
        for p, group in sub.groupby('task_id'):
            hits[index[p]] = group.adopted.sum()
            counts[index[p]] = len(group)
        vals[label+'_hits'] = int(hits.sum())
        vals[label+'_pairs'] = int(counts.sum())
        vals[label+'_uptake'] = hits.sum()/counts.sum()
        draws[label] = ratio(weights @ hits, weights @ counts)
    vals['resistance'] = 1 - vals['false_uptake']
    vals['resistance_count'] = vals['false_pairs']-vals['false_hits']
    vals['gap_pp'] = 100*(vals['true_uptake']-vals['false_uptake'])
    gap_draws[tier] = 100*(draws['true']-draws['false'])
    vals['gap_ci'], vals['defined_draws'] = interval(gap_draws[tier])
    gaps[tier] = vals
ci, valid = interval(gap_draws['strong']-gap_draws['weak'])
gaps['difference'] = dict(gap_pp=gaps['strong']['gap_pp']-gaps['weak']['gap_pp'], gap_ci=ci, defined_draws=valid)
(OUT / 'tier-uptake.json').write_text(json.dumps(gaps, indent=2)+'\n')
provenance = dict(seed=20260906, draws=10000, resampling='20 puzzles with replacement independently within each size; all configurations sharing a puzzle are retained together',
                  inputs={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [INPUT/'debate-features.csv',INPUT/'paper-auc.csv',INPUT/'exposure-pairs.csv']},
                  points_match_corrected_table=True, n_debates=120, n_puzzles=40)
(OUT / 'provenance.json').write_text(json.dumps(provenance, indent=2)+'\n')
print(pd.DataFrame(rows)[['feature','n','within_auc','within_low','within_high','within_defined_draws']].to_string(index=False))
print(json.dumps(gaps, indent=2))
