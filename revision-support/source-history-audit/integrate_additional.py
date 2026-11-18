"""Retain post-unblinding candidate adjudications separately from frozen passes."""
from pathlib import Path
import json
P=Path(__file__).resolve().parent
extra=json.loads((P/'additional-candidate-adjudication.json').read_text())
for did,v in extra.items():
 p=P/f'{did}-audit-adjudicated.json';source=p if p.exists() else P/f'{did}-audit-firstpass.json';d=json.loads(source.read_text())
 if did=='D04':expr='SAME_ROLE(A,B)';v=v['candidates'][expr]
 else:expr=v['candidate']
 initial={}
 for a,r in v['agents'].items():initial[a]={'status':'absent' if (r['status'].startswith('absent') or r.get('polarity')=='negative') else r['status'],'evidence':r['evidence'],'note':r['rationale']}
 assert not any(r['status']=='present' for r in initial.values())
 target={'expression':expr,'initial':initial,'later':{a:{'status':'ambiguous','evidence':[],'note':'No unambiguous initial supply established for this candidate; later status not separately adjudicated and does not enter source-derived eligible counts.'} for a in initial},'adjudication_origin':'Candidate identified after pipeline comparison; independently source-reviewed; not part of blinded discovery.'}
 d['targets']=[t for t in d['targets'] if t['expression']!=expr]+[target]
 p.write_text(json.dumps(d,indent=2)+'\n')
