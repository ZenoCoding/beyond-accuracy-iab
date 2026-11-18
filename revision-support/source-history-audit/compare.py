"""Compare blinded source reannotation with frozen extraction; no corpus edits."""
from pathlib import Path
import sys,json,csv,hashlib
from collections import defaultdict
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from claim_logic import assignments,evaluate_expr,parse_compact_expression
P=Path(__file__).resolve().parent;SUP=P.parent
manifest=json.loads((P/'sample-manifest.json').read_text());maps={r['debate_id']:r for r in manifest['debates']}
ids={(r['condition_id'],r['task_id']):did for did,r in maps.items()}
worlds=list(assignments(6));full=(1<<len(worlds))-1
labels={r['id']:r for r in map(json.loads,(SUP/'control-inputs/labels.jsonl').read_text().splitlines())}
packets={did:json.loads((P/f'{did}-source.json').read_text()) for did in maps}
def sig(did,expr):
 ast=parse_compact_expression(expr);statements=[s['ast'] for s in packets[did]['puzzle']['statements']]
 return sum(1<<i for i,w in enumerate(worlds) if evaluate_expr(ast,w,statements))
def truth(did,bits):
 roles=labels[maps[did]['task_id']]['roles'];gold=tuple(roles[p] for p in packets[did]['puzzle']['players']);return 'true' if bits&(1<<worlds.index(gold)) else 'false'
def tier(did):return 'weak' if 'weak' in maps[did]['condition_id'] else 'strong'
def csvload(p):return list(csv.DictReader(p.open()))
def csvwrite(path,rows):
 if not rows:path.write_text('');return
 with path.open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def merge(values):
 return 'present' if 'present' in values else ('ambiguous' if 'ambiguous' in values else 'absent')
raw={};annotation_hashes={}
for did in maps:
 path=P/f'{did}-audit-adjudicated.json'
 if not path.exists():path=P/f'{did}-audit-firstpass.json'
 if not path.exists():raise SystemExit('Missing '+str(path))
 d=json.loads(path.read_text());annotation_hashes[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
 for t in d['targets']:
  bits=sig(did,t['expression'])
  if bits in [0,full]:continue
  key=(did,bits)
  if key not in raw:raw[key]={'expressions':[],'supply_agents':set(),'initial':defaultdict(list),'later':defaultdict(list)}
  raw[key]['expressions'].append(t['expression'])
  raw[key]['supply_agents'].update(a for a,v in t['initial'].items() if v['status']=='present' and v.get('supply_eligible',True))
  for phase in ['initial','later']:
   for a,v in t[phase].items():raw[key][phase][a].append(v['status'])
for t in raw.values():
 for phase in ['initial','later']:t[phase]={a:merge(v) for a,v in t[phase].items()}
pipe={};exact=[]
for r in csvload(SUP/'corrections/role-predicate-v2/statistics-snapshot/matching_persistence_pairs.csv'):
 if (r['condition_id'],r['task_id']) not in ids:continue
 did=ids[r['condition_id'],r['task_id']];bits=int(r['signature_hex'],16)
 pipe[(did,bits,r['recipient'])]=r
for r in csvload(SUP/'corrections/role-predicate-v2/exposure-pairs.csv'):
 if (r['condition_id'],r['task_id']) in ids:exact.append(r)
# All extracted commitments used to inspect supply/presence discrepancies.
pc=defaultdict(lambda: {'initial':set(),'later':set(),'supply':set(),'expressions':set()})
from claim_logic import contains_role_predicate
for r in csvload(SUP/'control-inputs/claims.csv'):
 k=(r['condition_id'],r['task_id'])
 if k not in ids or r['commitment'] not in ['assert','endorse']:continue
 did=ids[k];expr=r['effective_expression'] or r['expression'];ast=parse_compact_expression(expr)
 if ast is None:continue
 bits=sig(did,expr);t=pc[(did,bits)];t['expressions'].add(expr);stage=int(r['stage_order'])
 if stage==0:
  t['initial'].add(r['agent_id'])
  if not contains_role_predicate(ast) and bits not in [0,full]:t['supply'].add(r['agent_id'])
 elif stage<10010:t['later'].add(r['agent_id'])
rows=[];source_pairs=[]
keys=set(raw)|{(did,bits) for did,bits,_ in pipe}
for did,bits in sorted(keys):
 target=raw.get((did,bits));p=pc[(did,bits)]
 for a in ['agent-1','agent-2','agent-3']:
  initial=target['initial'][a] if target else 'unreviewed_target';later=target['later'][a] if target else 'unreviewed_target'
  supplied=bool(target and target['supply_agents'])
  audit_eligible=bool(supplied and initial=='absent');pk=(did,bits,a);pr=pipe.get(pk)
  if not audit_eligible and pr is None:continue
  reason='agreement'
  if target is None:reason='pipeline_target_absent_from_independent_inventory_requires_adjudication'
  elif initial=='ambiguous':reason='ambiguous_initial_presence'
  elif not supplied:reason='ambiguous_initial_supply' if any(v=='ambiguous' for v in target['initial'].values()) else 'pipeline_supply_not_asserted'
  elif pr is not None and initial=='present':reason='pipeline_false_novelty_or_expression_policy_difference'
  elif audit_eligible and pr is None:reason='pipeline_missing_pair_or_expression_policy_difference'
  elif audit_eligible and later=='ambiguous':reason='ambiguous_later_recurrence'
  elif audit_eligible and pr is not None and int(pr['adopted_ever'])!=int(later=='present'):reason='later_recurrence_disagreement'
  exprs=target['expressions'] if target else sorted(p['expressions'])
  rows.append(dict(debate_id=did,tier=tier(did),truth=truth(did,bits),expression='|'.join(exprs),signature_hex=f'{bits:x}',recipient=a,audit_initial=initial,audit_later=later,audit_eligible=int(audit_eligible),pipeline_semantic_eligible=int(pr is not None),pipeline_adopted=int(pr['adopted_ever']) if pr else '',pipeline_initial_expression=int(a in p['initial']),pipeline_later_expression=int(a in p['later']),comparison=reason))
  if audit_eligible:source_pairs.append(rows[-1])
def summary(items,kind):
 result={}
 for tiername in ['strong','weak']:
  group=[r for r in items if r['tier']==tiername];out={}
  for tr in ['true','false']:
   sub=[r for r in group if r['truth']==tr];known=[r for r in sub if r.get('audit_later')!='ambiguous'];hits=sum(int(r['audit_later']=='present') if kind=='source' else int(r['adopted']) for r in known)
   out[tr]={'hits':hits,'pairs':len(known),'ambiguous_pairs':len(sub)-len(known),'rate':hits/len(known) if known else None}
  out['gap_pp']=100*(out['true']['rate']-out['false']['rate']) if all(out[x]['rate'] is not None for x in ['true','false']) else None
  result[tiername]=out
 result['difference_pp']=result['strong']['gap_pp']-result['weak']['gap_pp'] if all(result[t]['gap_pp'] is not None for t in ['strong','weak']) else None
 return result
pipeitems=[dict(tier=tier(d),truth=truth(d,b),adopted=r['adopted_ever']) for (d,b,a),r in pipe.items()]
exactitems=[dict(tier='weak' if 'weak' in r['condition_id'] else 'strong',truth='true' if r['information_type']=='truth_aligned' else 'false',adopted=r['adopted']) for r in exact]
csvwrite(P/'event-comparison.csv',rows)
result={'scope':'Eight sampled wholedebates, two puzzles. Source-derived semantic identity, not exactexpression estimand; no corpus-wide correction/inference. Unreviewed pipeline-only targets require adjudication.','annotation_sha256':annotation_hashes,'source_derived_provisional':summary(source_pairs,'source'),'pipeline_semantic_same_debates':summary(pipeitems,'pipe'),'pipeline_exact_same_debates':summary(exactitems,'pipe'),'comparison_counts':{reason:sum(r['comparison']==reason for r in rows) for reason in sorted({r['comparison'] for r in rows})},'sample_pairs':len(source_pairs),'pipeline_semantic_pairs':len(pipe),'pipeline_exact_pairs':len(exact)}
(P/'comparison-summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
