"""Freeze a raw-source sample without inspecting extracted claim outcomes."""
from pathlib import Path
import json,csv,hashlib
ROOT=Path(__file__).resolve().parents[4]
P=ROOT/'paper/kse2026/revision-support';OUT=Path(__file__).resolve().parent
SEED='makis-source-history-audit-v1-20260917'
ledger_path=ROOT/'paper/fast2026/checklist-merge-2026-09-06/merged/release-staging/reports/analysis/fast-translation-cleanup-v1-2026-09-06/correction-ledger.jsonl'
ledger=[json.loads(l) for l in ledger_path.read_text().splitlines()]
prior=json.loads((P/'explicit-prior-audit.json').read_text())
excluded={r['task_id'] for r in ledger if r['dataset']=='size6'}|{r['task'] for r in prior}
prov=json.loads((P/'strength-controls.json').read_text())['provenance']
run_dirs={ (ROOT/path).parent.parent for path in prov['raw_hashes'] };paths=sorted(str(p.relative_to(ROOT)) for d in run_dirs for p in d.glob('*/result.json'));raws=[(path,json.loads((ROOT/path).read_text())) for path in paths]
tasks=sorted({r['task_id'] for _,r in raws});eligible=sorted(set(tasks)-excluded)
ranked=sorted(eligible,key=lambda t:hashlib.sha256((SEED+'|'+t).encode()).hexdigest());selected=ranked[:2]
questions={r['id']:r for r in map(json.loads,(P/'control-inputs/questions.jsonl').read_text().splitlines())}
conditions=['weak-het','weak-hom','medium-het','medium-hom'];mapping=[]
for ti,task in enumerate(selected):
 for ci,cond in enumerate(conditions):
  matches=[(path,r) for path,r in raws if r['task_id']==task and (('weak-'+cond.split('-')[-1] in path) if cond.startswith('weak') else ('v2-'+cond+'-full' in path))];assert len(matches)==1
  path,r=matches[0];did=f'D{ti*4+ci+1:02d}';fields=[]
  for agent,v in sorted(r['initial_proposals'].items()):fields.append(dict(id=f'I.{agent}',agent=agent,stage_order=0,text=v['explanation']))
  for i,rnd in enumerate(r['rounds'],1):
   for agent,v in sorted(rnd['arguments'].items()):
    for name in ['agree_reasoning','disagree_reasoning']:
     fields.append(dict(id=f'R{i}.argument.{agent}.{name}',agent=agent,stage_order=100+i*10,text=v.get(name,'')))
   for agent,v in sorted(rnd['adjustments'].items()):fields.append(dict(id=f'R{i}.revision.{agent}',agent=agent,stage_order=101+i*10,text=v['explanation']))
  packet={'debate_id':did,'puzzle':{k:questions[task][k] for k in ['hint','players','size','statements']},'fields':fields}
  (OUT/f'{did}-source.json').write_text(json.dumps(packet,indent=2)+'\n')
  mapping.append(dict(debate_id=did,task_id=task,condition_id='broad-luna-low-'+cond,repetition=1,raw_path=path,raw_sha256=hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),packet_sha256=hashlib.sha256((OUT/f'{did}-source.json').read_bytes()).hexdigest(),field_count=len(fields),nonempty_fields=sum(bool(f['text']) for f in fields)))
manifest={'seed':SEED,'selection':'First two puzzle IDs ranked by SHA256(seed|task), each across all four size-six conditions; exclude puzzle IDs touched by recorded correction ledger or eight-example source audit. No result/claim counts used.','population_tasks':tasks,'excluded_previously_reviewed_tasks':sorted(excluded),'eligible_tasks':eligible,'selected_tasks':selected,'puzzle_inclusion_probability_in_eligible_frame':2/len(eligible),'limitations':'Model-assisted diagnostic audit; excludes known previously reviewed puzzles, only two puzzle clusters, not an independent human holdout or representative estimate for all20puzzles. Blinded packets omit condition/model/solution/pipeline outputs; puzzle IDs and metadata removed from source packets.','debates':mapping}
(OUT/'sample-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'selected':selected,'debates':[(r['debate_id'],r['nonempty_fields']) for r in mapping]},indent=2))
