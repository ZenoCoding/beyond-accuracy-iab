"""Expose source anchors for disputed extracted events after unblinding."""
from pathlib import Path
import json,csv,sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from claim_logic import assignments,evaluate_expr,parse_compact_expression
P=Path(__file__).resolve().parent;SUP=P.parent
maps=json.loads((P/'sample-manifest.json').read_text())['debates'];ids={(r['condition_id'],r['task_id']):r['debate_id'] for r in maps}
packets={r['debate_id']:json.loads((P/(r['debate_id']+'-source.json')).read_text()) for r in maps}
comparisons=list(csv.DictReader((P/'event-comparison.csv').open()));disputed={(r['debate_id'],int(r['signature_hex'],16),r['recipient']) for r in comparisons if r['comparison']!='agreement'}
rows=[]
for r in csv.DictReader((SUP/'control-inputs/claims.csv').open()):
 key=(r['condition_id'],r['task_id'])
 if key not in ids or r['commitment'] not in ['assert','endorse'] or int(r['stage_order'])>=10010:continue
 did=ids[key];expr=r['effective_expression'] or r['expression'];ast=parse_compact_expression(expr)
 if ast is None:continue
 stmts=[v['ast'] for v in packets[did]['puzzle']['statements']];bits=sum(1<<i for i,w in enumerate(assignments(6)) if evaluate_expr(ast,w,stmts))
 if not any(d==did and b==bits for d,b,a in disputed):continue
 n=int(float(r['round_index'])) if r['round_index'] else 0;agent=r['agent_id']
 fid=f'I.{agent}' if r['stage']=='initial_proposal' else (f'R{n}.revision.{agent}' if r['stage']=='self_adjustment' else f'R{n}.argument.{agent}.{r["field"]}')
 f=next(f for f in packets[did]['fields'] if f['id']==fid)
 rows.append(dict(debate_id=did,signature_hex=f'{bits:x}',agent=agent,stage_order=int(r['stage_order']),field_id=fid,expression=expr,span=r['source_span'],verbatim=r['source_span'] in f['text'],source_text=f['text'],claim_uid=r['claim_uid']))
(P/'pipeline-disputed-evidence.json').write_text(json.dumps(rows,indent=2)+'\n')
print(f'{len(rows)} extracted occurrences for disputed targets; {sum(not r["verbatim"] for r in rows)} non-verbatim spans')
