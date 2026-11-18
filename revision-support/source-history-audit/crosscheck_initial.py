"""Source-inventory agreement between independent annotation passes."""
from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from claim_logic import assignments,evaluate_expr,parse_compact_expression
P=Path(__file__).resolve().parent
ind=json.loads((P/'initial-independent-firstpass.json').read_text())
if isinstance(ind,dict) and 'debates' in ind:ind=ind['debates']
if isinstance(ind,list):ind={d['debate_id']:d for d in ind}
rows=[]
for path in sorted(P.glob('D??-audit-firstpass.json')):
 d=json.loads(path.read_text());did=d['debate_id'];packet=json.loads((P/f'{did}-source.json').read_text());fields={f['id']:f for f in packet['fields']};statements=[r['ast'] for r in packet['puzzle']['statements']]
 def sig(expr):return sum(1<<i for i,w in enumerate(assignments(6)) if evaluate_expr(parse_compact_expression(expr),w,statements))
 a={};b={}
 for t in d['targets']:
  for agent,v in t['initial'].items():
   if v['status']=='present' and sig(t['expression']) not in [0,(1<<192)-1]:a[(sig(t['expression']),agent)]=t
 for t in ind[did]['initial_targets']:
  f=fields[t['field_id']];assert f['stage_order']==0 and f['agent']==t['agent'] and t['span'].strip() and t['span'] in f['text'],t
  if sig(t['expression']) not in [0,(1<<192)-1]:b[(sig(t['expression']),t['agent'])]=t
 for key in sorted(set(a)|set(b)):
  rows.append({'debate_id':did,'agent':key[1],'signature_hex':f'{key[0]:x}','full_history_expression':a[key]['expression'] if key in a else None,'initial_only_expression':b[key]['expression'] if key in b else None,'agreement':key in a and key in b,'full_history_evidence':a[key]['initial'][key[1]] if key in a else None,'initial_only_evidence':b.get(key)})
(P/'initial-crosscheck.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps({'initial_presence_union':len(rows),'agreement':sum(r['agreement'] for r in rows),'disagreements':[r for r in rows if not r['agreement']]},indent=2))
