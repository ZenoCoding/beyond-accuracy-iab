"""Controls for initial answers, explicit opposing claims, and shared claim supply.
No model calls. Uses corrected archived claims and frozen exposure pairs.
"""
from pathlib import Path
from functools import lru_cache
import json, hashlib
import numpy as np
import pandas as pd
from claim_logic import parse_compact_expression, evaluate_expr, assignments, contains_role_predicate, unique_index, verify_pair_inventory
P=Path(__file__).resolve().parent
I=P/'control-inputs'
CORRECTED=P/'corrections/source-audit-v3'
C=CORRECTED/'claims.csv'
d=pd.read_csv(C).fillna('')
e=pd.read_csv(CORRECTED/'exposure-pairs.csv');e=e[e.dataset.eq('size6')].copy()
assert len(d)==json.loads((CORRECTED/'manifest.json').read_text())['claim_rows']
unique_index(d.to_dict('records'), ('claim_uid',), 'claims')
q={key[0]:r for key,r in unique_index(list(map(json.loads,(I/'questions.jsonl').read_text().splitlines())), ('id',), 'questions').items()}
gold={key[0]:r['roles'] for key,r in unique_index(list(map(json.loads,(I/'labels.jsonl').read_text().splitlines())), ('id',), 'labels').items()}
snapshot=json.loads((I/'initial-positions.json').read_text())
positions={key:tuple(r['roles']) for key,r in unique_index(snapshot['rows'], ('condition_id','task_id','repetition','agent_id'), 'initial positions').items()}
hashes=snapshot['raw_hashes']
worlds=list(assignments(6));full=(1<<len(worlds))-1
@lru_cache(None)
def parsed(expr):
 a=parse_compact_expression(expr);assert a is not None;return a
@lru_cache(None)
def sig(task,expr):
 a=parsed(expr);ss=[s['ast'] for s in q[task]['statements']]
 return sum((1<<i) for i,w in enumerate(worlds) if evaluate_expr(a,w,ss))
d['expr']=d.effective_expression.where(d.effective_expression.ne(''),d.expression)
c=d[d.commitment.isin(['assert','endorse'])]
initial={k:g for k,g in c[c.stage_order.eq(0)].groupby(['condition_id','task_id','repetition','agent_id'])}
# Independently rebuild original eligibility and uptake from corrected claims.
reconstructed={}
for key,g in c.groupby(['condition_id','task_id','repetition']):
 for expr,gg in g.groupby('expr'):
  if contains_role_predicate(parsed(expr)) or gg.stage_order.min()!=0:continue
  origin=gg[gg.stage_order.eq(0)];kind=origin.information_type.iloc[0]
  if kind not in ['truth_aligned','misleading']:continue
  for a in ['agent-1','agent-2','agent-3']:
   if a in set(origin.agent_id):continue
   adopted=int(any((gg.agent_id==a)&(gg.stage_order>0)&(gg.stage_order<10010)))
   reconstructed[(*key,expr,a)]=(kind,adopted)
verify_pair_inventory(e.to_dict('records'), reconstructed)
rows=[]
for r in e.to_dict('records'):
 key=(r['condition_id'],r['task_id'],r['repetition']);a=r['recipient'];expr=r['expression']
 assert reconstructed[(*key,expr,a)]==(r['information_type'],r['adopted'])
 task=r['task_id'];ss=[s['ast'] for s in q[task]['statements']]
 truth=evaluate_expr(parsed(expr),tuple(gold[task][k] for k in q[task]['players']),ss)
 assert truth==(r['information_type']=='truth_aligned')
 r['incompatible_answer']=int(not evaluate_expr(parsed(expr),positions[*key,a],ss))
 signature=sig(task,expr); init=initial.get((*key,a));against=[];same=[]
 if init is not None:
  for z in init.itertuples():
   if contains_role_predicate(parsed(z.expr)):continue
   s=sig(task,z.expr)
   if s==full^signature:against.append(z.claim_uid)
   if s==signature:same.append(z.claim_uid)
 r['explicit_opposite']=int(bool(against) and not same)
 r['prior_equivalent']=int(bool(same));r['opposing_claim_ids']='|'.join(against)
 r['tier']='strong' if 'medium' in r['condition_id'] else 'weak';r['composition']='het' if '-het' in r['condition_id'] else 'hom'
 rows.append(r)
f=pd.DataFrame(rows);f.to_csv(P/'controlled-exposure-pairs.csv',index=False)
ids=sorted(f.task_id.unique());ix={s:i for i,s in enumerate(ids)}
w=np.random.default_rng(20260918).multinomial(len(ids),np.ones(len(ids))/len(ids),size=10000)
result={}
for name,sub in [('all',f),('incompatible_answer',f[f.incompatible_answer.eq(1)]),('explicit_opposite',f[f.explicit_opposite.eq(1)]),('beyond_statement_truth',f[~f.expression.str.match(r'^(NOT\()?STMT_TRUE\([A-Z]\)\)?$')])]:
 out={};draws={}
 for tier in ['strong','weak']:
  a=np.zeros((len(ids),4));rr=sub[sub.tier.eq(tier)]
  for r in rr.itertuples():
   j=0 if r.information_type=='truth_aligned' else 2
   a[ix[r.task_id],j]+=r.adopted;a[ix[r.task_id],j+1]+=1
  total=a.sum(axis=0);boot=w@a
  with np.errstate(divide='ignore',invalid='ignore'):
   gap=100*(total[0]/total[1]-total[2]/total[3]);draws[tier]=100*(boot[:,0]/boot[:,1]-boot[:,2]/boot[:,3])
  out[tier]={'counts':total.astype(int).tolist(),'gap_pp':gap,'n_puzzles':rr.task_id.nunique()}
 diff=draws['strong']-draws['weak'];diff=diff[np.isfinite(diff)]
 out['difference']={'gap_pp':out['strong']['gap_pp']-out['weak']['gap_pp'],'ci':np.quantile(diff,[.025,.975]).tolist() if len(diff) else None,'defined_draws':len(diff)}
 result[name]=out
# Equal weights per shared puzzle/composition/expression stratum, averaging recipients.
g=f.groupby(['task_id','composition','expression','information_type','tier']).adopted.mean().unstack('tier').dropna()
assert set(g.columns)=={'strong','weak'}
g.to_csv(P/'shared-claim-strata.csv')
true=g.index.get_level_values('information_type')=='truth_aligned';point=100*((g.strong-g.weak)[true].mean()-(g.strong-g.weak)[~true].mean())
a=np.zeros((len(ids),4))
for k,r in g.iterrows():
 j=0 if k[3]=='truth_aligned' else 2;a[ix[k[0]],j]+=r.strong-r.weak;a[ix[k[0]],j+1]+=1
b=w@a
with np.errstate(divide='ignore',invalid='ignore'):diff=100*(b[:,0]/b[:,1]-b[:,2]/b[:,3])
diff=diff[np.isfinite(diff)]
result['shared_claims']={'n_strata':len(g),'true_strata':int(true.sum()),'false_strata':int((~true).sum()),'n_puzzles':len(set(g.index.get_level_values('task_id'))),'difference_pp':point,'ci':np.quantile(diff,[.025,.975]).tolist(),'defined_draws':len(diff),'rates':{tier:{'true':g[tier][true].mean(),'false':g[tier][~true].mean()} for tier in ['strong','weak']}}
result['provenance']={'claims_sha256':hashlib.sha256(C.read_bytes()).hexdigest(),'exposure_sha256':hashlib.sha256((CORRECTED/'exposure-pairs.csv').read_bytes()).hexdigest(),'raw_hashes':hashes,'all_eligible_pairs_reproduced':len(f),'claims_rows':len(d),'seed':20260918,'draws':10000,'new_model_calls':0,'claim_path':str(C.relative_to(P)), 'control_input_hashes':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(I.iterdir()) if f.is_file()}}
(P/'strength-controls.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='provenance'},indent=2))
