"""Descriptive initial-correctness sensitivity; frozen inputs, no model calls."""
from pathlib import Path
import csv, json, hashlib
import numpy as np
P=Path(__file__).resolve().parent
INPUT=P/'corrections/source-audit-v3/debate-features.csv'
D=list(csv.DictReader(INPUT.open()))
D=[r for r in D if r['size']=='6']
ids=sorted({r['task_id'] for r in D}); idx={p:i for i,p in enumerate(ids)}
w=np.random.default_rng(20260917).multinomial(len(ids),np.ones(len(ids))/len(ids),size=10000)
keys=['adopted_true_pairs','eligible_true_pairs','adopted_false_pairs','eligible_false_pairs']
def groupkey(r):return (r['task_id'],'het' if '-het' in r['condition_id'] else 'hom')
no=[r for r in D if r['any_initial_correct']=='0']
matched={groupkey(r) for r in no if sum(groupkey(s)==groupkey(r) for s in no)==2}
output={}
for name,rows in [('all',D),('none_initial_correct',no),('matched_none_initial_correct',[r for r in no if groupkey(r) in matched])]:
 result={}; draws={}
 for tier,word in [('strong','medium'),('weak','weak')]:
  rr=[r for r in rows if word in r['condition_id']]
  a=np.zeros((len(ids),4))
  for r in rr:a[idx[r['task_id']]]+=np.array([float(r[k]) for k in keys])
  totals=a.sum(axis=0); boot=w@a
  with np.errstate(divide='ignore',invalid='ignore'):g=100*(boot[:,0]/boot[:,1]-boot[:,2]/boot[:,3])
  draws[tier]=g
  result[tier]=dict(n_debates=len(rr),n_puzzles=len({r['task_id'] for r in rr}),counts=totals.astype(int).tolist(),true_rate=totals[0]/totals[1],false_rate=totals[2]/totals[3],gap_pp=100*(totals[0]/totals[1]-totals[2]/totals[3]))
 diff=draws['strong']-draws['weak']; diff=diff[np.isfinite(diff)]
 result['difference']=dict(gap_pp=result['strong']['gap_pp']-result['weak']['gap_pp'],ci=np.quantile(diff,[.025,.975]).tolist(),defined_draws=len(diff))
 output[name]=result
output['provenance']=dict(input_sha256=hashlib.sha256(INPUT.read_bytes()).hexdigest(),seed=20260917,draws=10000,method='Joint puzzle bootstrap over original 20 six-player puzzles; fixed descriptive subsets; pooled claim-recipient counts.')
(P/'initial-correctness-sensitivity.json').write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps(output,indent=2))
