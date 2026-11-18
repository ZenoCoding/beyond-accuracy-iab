"""Reconcile frozen source judgments with v3. No model calls or historical writes."""
from pathlib import Path
import csv,json,hashlib,sys
from collections import defaultdict,Counter
from functools import lru_cache
P=Path(__file__).resolve().parent; S=P.parent; O=P/'current-v3'; O.mkdir(exist_ok=True)
sys.path.insert(0,str(S))
from claim_logic import assignments,evaluate_expr,parse_compact_expression,contains_role_predicate
inputs={'source-history-audit/reconcile_current.py':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
def read(p):
 inputs[str(p.relative_to(S))]=hashlib.sha256(p.read_bytes()).hexdigest()
 return json.loads(p.read_text())
def rows(p):
 inputs[str(p.relative_to(S))]=hashlib.sha256(p.read_bytes()).hexdigest()
 return list(csv.DictReader(p.open()))
def write(name,r):
 with (O/name).open('w') as f:
  if r:
   w=csv.DictWriter(f,fieldnames=list(r[0]));w.writeheader();w.writerows(r)
def dump(name,x):(O/name).write_text(json.dumps(x,indent=2)+'\n')
manifest=read(P/'sample-manifest.json'); maps={r['debate_id']:r for r in manifest['debates']}; ids={(r['condition_id'],r['task_id']):d for d,r in maps.items()}
packets={d:read(P/f'{d}-source.json') for d in maps}; annotations={d:read(P/f'{d}-audit-adjudicated.json') for d in maps}
for provenance in ['SOURCE_CORRECTIONS.md','claim_logic.py','strength_controls.py','corrections/source-audit-v3/correction-ledger.json','corrections/source-audit-v3/manifest.json']:
 inputs[provenance]=hashlib.sha256((S/provenance).read_bytes()).hexdigest()
labels={r['id']:r for r in map(json.loads,(S/'control-inputs/labels.jsonl').read_text().splitlines())};inputs['control-inputs/labels.jsonl']=hashlib.sha256((S/'control-inputs/labels.jsonl').read_bytes()).hexdigest()
worlds=list(assignments(6));full=(1<<len(worlds))-1; agents=['agent-1','agent-2','agent-3']
@lru_cache(None)
def sig(d,e):
 ast=parse_compact_expression(e); sts=[s['ast'] for s in packets[d]['puzzle']['statements']]
 return sum(1<<i for i,w in enumerate(worlds) if evaluate_expr(ast,w,sts))
def tier(d):return 'weak' if 'weak' in maps[d]['condition_id'] else 'strong'
def truth(d,b):
 gold=tuple(labels[maps[d]['task_id']]['roles'][p] for p in packets[d]['puzzle']['players'])
 return 'true' if b&(1<<worlds.index(gold)) else 'false'
# Versioned reference overlay; ambiguous means retain both unconditional and scoped readings.
changes=[('D03','NOT(STMT_TRUE(E))','agent-2'),('D05','NOT(STMT_TRUE(A))','agent-1'),('D05','COUNT(exactly,3,knave,A,B,C,D,E,F)','agent-1'),('D05','COUNT(exactly,2,knight,A,B,C,D,E,F)','agent-1'),('D06','NOT(STMT_TRUE(A))','agent-2'),('D06','COUNT(exactly,4,knave,A,B,C,E,F)','agent-2'),('D08','SAME_ROLE(A,B)','agent-1'),('D07','STMT_TRUE(E)','agent-1')]
overlay=[]
for d,e,a in changes:
 t=next(t for t in annotations[d]['targets'] if t['expression']==e);v=t['initial'][a]
 overlay.append(dict(debate_id=d,expression=e,agent=a,phase='initial',before=v.copy(),after_status='ambiguous',reason=('New reconciliation ambiguity: E-truth follows an explicit if-B-knave clause. The preceding independent B-knave assertion favors an unconditional reading, but the clause has no explicit case closure; retain both readings rather than certify either.' if d=='D07' else 'Previously documented unresolved scope/polarity candidate in SOURCE_CORRECTIONS.md; not a confirmed omission.'),origin=('new_scope_review' if d=='D07' else 'documented_deferral'),source_packet_sha256=inputs[f'source-history-audit/{d}-source.json'],annotation_sha256=inputs[f'source-history-audit/{d}-audit-adjudicated.json'],full_source=next(f['text'] for f in packets[d]['fields'] if f['id']=='I.'+a)))
 v['status']='ambiguous'
# Source-checked semantic correction to the reference: C says NOT ROLE(B,knave).
# A direct later assertion of B-knave is exactly C-false without KKS inference.
for a in agents:
 d='D06';e='NOT(STMT_TRUE(C))';t=next(t for t in annotations[d]['targets'] if t['expression']==e);v=t['later'][a]
 source=next(f['text'] for f in packets[d]['fields'] if f['id']=='R1.revision.'+a)
 assert sig(d,e)==sig(d,'ROLE(B,knave)')
 overlay.append(dict(debate_id=d,expression=e,agent=a,phase='later',before=v.copy(),after_status='present',origin='new_semantic_reference_repair',source_packet_sha256=inputs[f'source-history-audit/{d}-source.json'],annotation_sha256=inputs[f'source-history-audit/{d}-audit-adjudicated.json'],reason='Source explicitly asserts B is knave in R1 revision; this is semantically identical to NOT(STMT_TRUE(C)), not an inference from the speaker role.',full_source=source))
 v['status']='present'
dump('reference-overlay.json',overlay)
def options(status):return {1} if status=='present' else {0} if status=='absent' else {0,1}
def merge(v):return 'present' if 'present' in v else 'ambiguous' if 'ambiguous' in v else 'absent'
raw={}
for d,ann in annotations.items():
 for t in ann['targets']:
  b=sig(d,t['expression'])
  if b in (0,full):continue
  q=raw.setdefault((d,b),dict(expressions=[],initial=defaultdict(list),later=defaultdict(list),supply=defaultdict(list)))
  q['expressions'].append(t['expression'])
  for a in agents:
   for phase in ['initial','later']:q[phase][a].append(t[phase][a]['status'])
   q['supply'][a].append(t['initial'][a]['status'] if t['initial'][a].get('supply_eligible',True) else 'absent')
for q in raw.values():
 for phase in ['initial','later','supply']:q[phase]={a:merge(v) for a,v in q[phase].items()}
pc=defaultdict(lambda:dict(initial=set(),later=set(),supply=set(),expressions=set()))
for r in rows(S/'corrections/source-audit-v3/claims.csv'):
 k=(r['condition_id'],r['task_id'])
 if k not in ids or r['commitment'] not in ['assert','endorse']:continue
 d=ids[k];e=r['effective_expression'] or r['expression'];ast=parse_compact_expression(e)
 if ast is None:continue
 b=sig(d,e);q=pc[(d,b)];q['expressions'].add(e);a=r['agent_id'];stage=int(r['stage_order'])
 if stage==0:
  q['initial'].add(a)
  if not contains_role_predicate(ast) and b not in (0,full):q['supply'].add(a)
 elif stage<10010:q['later'].add(a)
pipe={}
for r in rows(S/'matching_persistence_pairs.csv'):
 if (r['condition_id'],r['task_id']) in ids:pipe[(ids[(r['condition_id'],r['task_id'])],int(r['signature_hex'],16),r['recipient'])]=int(r['adopted_ever'])
reconstructed={(d,b,a):int(a in q['later']) for (d,b),q in pc.items() if q['supply'] for a in agents if a not in q['initial']}
assert reconstructed==pipe, 'Current semantic pair reconstruction mismatch'
exact=[r for r in rows(S/'corrections/source-audit-v3/exposure-pairs.csv') if (r['condition_id'],r['task_id']) in ids]
controlled=[r for r in rows(S/'controlled-exposure-pairs.csv') if (r['condition_id'],r['task_id']) in ids]
opposition_checks=[]
for r in controlled:
 d=ids[(r['condition_id'],r['task_id'])];b=sig(d,r['expression']);a=r['recipient']
 actual=int(a in pc[(d,full^b)]['supply'] and a not in pc[(d,b)]['supply'])
 opposition_checks.append(dict(debate_id=d,signature_hex=f'{b:x}',recipient=a,expression=r['expression'],reconstructed=actual,archived=int(r['explicit_opposite'])))
assert all(r['reconstructed']==r['archived'] for r in opposition_checks), 'Current explicit opposition reconstruction mismatch'
write('opposition-reconstruction.csv',opposition_checks)
# Union candidate universe, including all three recipients whether eligible or not.
keys=set(raw)|{(d,b) for d,b,a in pipe}; events=[];decisions=[];alternatives=[]
for d,b in sorted(keys):
 q=raw.get((d,b)); p=pc[(d,b)];opp=raw.get((d,full^b));po=pc[(d,full^b)]
 for a in agents:
  ini=q['initial'][a] if q else 'unreviewed';late=q['later'][a] if q else 'unreviewed'
  peers=[q['supply'][v] for v in agents if v!=a] if q else ['unreviewed']
  peer=merge(peers) if q else 'unreviewed';op=opp['supply'][a] if opp else 'unreviewed'
  target_nonrole=q['supply'][a] if q else 'unreviewed'
  elig={int(s and not i) for s in options(peer) for i in options(ini)}
  strictopp={int(o and not i) for o in options(op) for i in options(target_nonrole)}
  status=lambda opts:'present' if opts=={1} else 'absent' if opts=={0} else 'ambiguous'
  base=dict(debate_id=d,tier=tier(d),truth=truth(d,b),signature_hex=f'{b:x}',expression='|'.join(q['expressions'] if q else sorted(p['expressions'])),recipient=a)
  vals={'peer_supply':(peer,int(bool(p['supply']-{a}))), 'recipient_initial_presence':(ini,int(a in p['initial'])),'explicit_opposition':(status(strictopp),int(a in po['supply'] and a not in p['supply'])),'eligibility':(status(elig),int((d,b,a) in pipe)),'later_recurrence':(late,int(a in p['later']))}
  ev=base|{k+'_reference':v[0] for k,v in vals.items()}|{k+'_pipeline':v[1] for k,v in vals.items()};events.append(ev)
  for stage,(ref,pv) in vals.items():
   decisions.append(base|dict(stage=stage,reference=ref,pipeline=pv,comparison='unresolved' if ref in ['ambiguous','unreviewed'] else 'agreement' if pv==int(ref=='present') else 'disagreement'))
  # Explicit pair-level possibilities, not jointly attainable corpus bounds.
  if len(elig)>1 or late in ['ambiguous','unreviewed'] or op in ['ambiguous','unreviewed']:
   for eligible in sorted(elig):
    for outcome in sorted(options(late)) if eligible else ['not_eligible']:
     alternatives.append(base|dict(possible_eligible=eligible,possible_later_outcome=outcome,initial_status=ini,peer_supply_status=peer,later_status=late,opposite_initial_status=op,note='Marginal possibilities; shared source judgments correlate rows.'))
write('event-comparison.csv',events);write('stage-decisions.csv',decisions);write('alternative-assignments.csv',alternatives)
agg=[]
for st in vals:
 for ti in ['strong','weak']:
  for tr in ['true','false']:
   sub=[r for r in decisions if r['stage']==st and r['tier']==ti and r['truth']==tr];c=Counter(r['comparison'] for r in sub)
   agg.append(dict(stage=st,tier=ti,truth=tr,decisions=len(sub),agreement=c['agreement'],disagreement=c['disagreement'],unresolved=c['unresolved']))
write('stage-summary.csv',agg)
rates={}
for ti in ['strong','weak']:
 for tr in ['true','false']:
  sub=[r for r in events if r['tier']==ti and r['truth']==tr and r['eligibility_reference']=='present'];clear=[r for r in sub if r['later_recurrence_reference'] in ['present','absent']]
  rates[ti+'_'+tr]=dict(unambiguous_eligible=len(sub),known_outcome_pairs=len(clear),recurrences=sum(r['later_recurrence_reference']=='present' for r in clear),ambiguous_later=len(sub)-len(clear))
clear_eligible=[r for r in events if r['eligibility_reference']=='present' and r['later_recurrence_reference'] in ['present','absent']]
clear_disagreements=sum(r['eligibility_pipeline']!=1 or r['later_recurrence_pipeline']!=int(r['later_recurrence_reference']=='present') for r in clear_eligible)
ambiguous_later=sum(r['eligibility_reference']=='present' and r['later_recurrence_reference'] not in ['present','absent'] for r in events)
result=dict(clear_eligible_known_outcomes=len(clear_eligible),clear_eligible_outcome_disagreements=clear_disagreements,opposition_reconstruction_rows=len(opposition_checks),opposition_reconstruction_match=True,scope='Eight debates, two puzzle clusters; diagnostic sample, not corpus error-rate estimate. Model-assisted source judgments with unresolved alternatives, not certified ground truth.',pipeline_semantic_pairs=len(pipe),pipeline_exact_pairs=len(exact),reconstruction_match=True,candidate_propositions=len(keys),candidate_recipient_records=len(events),reference_overlay_records=len(overlay),stage_summary=agg,source_clear_rates=rates,input_sha256=inputs)
dump('summary.json',result)
lines=['# Current-v3 source-history reconciliation','',result['scope'],'',f"The independent current-claim reconstruction exactly matches all {len(pipe)} semantic opportunities and their later-expression indicators in the sampled debates ({len(exact)} exact-expression opportunities). The union of source-inventoried and pipeline-eligible propositions contains {len(keys)} propositions and {len(events)} candidate recipient records; all three recipients are retained, including ineligible records and non-recurrences.",'',f"A versioned reference overlay retains {len(changes)} initial judgments as ambiguous (including already-ambiguous D08 polarity and unresolved D07 scope), and repairs three later reference omissions using explicit semantically equivalent B-knave assertions. No historical annotation, corpus claim, or historical comparison is modified. Alternative assignments are marginal possibilities, not independent rows for statistical inference.",'','| Stage | Clear agreements | Clear disagreements | Unresolved |','|---|---:|---:|---:|']
for st in vals:
 sub=[r for r in decisions if r['stage']==st];c=Counter(r['comparison'] for r in sub);lines.append(f"| {st} | {c['agreement']} | {c['disagreement']} | {c['unresolved']} |")
lines+=['','Disagreements are conditional on these reviewed reference judgments, not certified extraction errors. Explicit opposition uses informative non-role initial commitments for both target and opposite, matching the main control; all-role semantic presence remains the recurrence eligibility rule. Explicit opposition is unresolved when the frozen target inventory does not establish the opposite proposition; absence from that inventory is not imputed as absence from source. Later recurrence is assessed on every candidate recipient; eligible-only outcomes are separated below.','', '| Tier / truth | Clear eligible with known outcome | Later recurrence | Ambiguous later among clear eligible |','|---|---:|---:|---:|']
for k,v in rates.items():lines.append(f"| {k} | {v['known_outcome_pairs']} | {v['recurrences']} | {v['ambiguous_later']} |")
lines += ['', f'Of {len(clear_eligible)} unambiguously eligible records with a determinate later outcome, {len(clear_eligible)-clear_disagreements} agree with the current pipeline and {clear_disagreements} disagree, including non-recurrences. A further {ambiguous_later} unambiguously eligible records have unresolved later scope. The single later-expression disagreement in the full candidate universe is D01 agent-1, A-false: the source credits Agent-3 as correctly identifying falsity, while the pipeline lacks a committed later match. That recipient already expressed A-false initially, so this is not an eligible uptake event. These statements describe only the reviewed subset; unresolved records must not be counted as successes or failures.']
lines += ['', f'Non-role explicit-opposition reconstruction matches all {len(opposition_checks)} archived exact-expression opportunity flags for these debates; opposition-reconstruction.csv records every comparison.']
lines+=['','`stage-summary.csv` separates stage, tier and truth. `stage-decisions.csv` and `event-comparison.csv` retain every candidate decision. `alternative-assignments.csv` preserves unresolved eligibility/outcome possibilities; `reference-overlay.json` preserves the changed judgments and complete source fields. `summary.json` records input hashes. The source packets and frozen adjudications in the parent directory contain evidence spans and full histories.','', 'Reproduce: `python source-history-audit/reconcile_current.py` from revision-support. No model calls or retranslations. Numerical reconstruction is checked separately from source fidelity.']
(O/'SUMMARY.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines[:18]))
