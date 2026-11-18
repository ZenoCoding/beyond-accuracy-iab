"""Structural checks only; verbatim anchoring does not establish semantic fidelity."""
from pathlib import Path
import json,sys,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from claim_logic import parse_compact_expression,contains_role_predicate
P=Path(__file__).resolve().parent

def check(path):
 d=json.loads(path.read_text());s=json.loads((P/(d['debate_id']+'-source.json')).read_text());fields={f['id']:f for f in s['fields']}
 assert len(fields)==len(s['fields'])
 assert len(d['reviewed_field_ids'])==len(set(d['reviewed_field_ids']))
 assert set(d['reviewed_field_ids'])=={f['id'] for f in s['fields'] if f['text']}, (path,'field coverage mismatch')
 for t in d['targets']:
  ast=parse_compact_expression(t['expression']);assert ast is not None and not contains_role_predicate(ast),(path,t['expression'])
  for phase in ['initial','later']:
   assert set(t[phase])=={'agent-1','agent-2','agent-3'}
   for agent,v in t[phase].items():
    assert v['status'] in {'present','absent','ambiguous'}
    if v['status']=='present':assert v['evidence'],(path,t['expression'],phase,agent)
    for e in v.get('evidence',[]):
     f=fields[e['field_id']];assert f['agent']==agent and ((f['stage_order']==0)==(phase=='initial'))
     assert e['span'].strip() and e['span'] in f['text'],(path,e)
 for e in d.get('exclusions',[]):
  assert e['span'].strip() and e['span'] in fields[e['field_id']]['text'],(path,e)
 return {'file':path.name,'targets':len(d['targets']),'reviewed_fields':len(d['reviewed_field_ids']),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
if __name__=='__main__':
 paths=[Path(x) for x in sys.argv[1:]] or sorted(P.glob('D??-audit-firstpass.json'))
 print(json.dumps([check(p) for p in paths],indent=2))
