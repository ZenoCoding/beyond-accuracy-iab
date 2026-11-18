"""Render both current AUC tables from the same numerical result file."""
from pathlib import Path
import csv
P=Path(__file__).resolve().parent
rows={r['feature']:r for r in csv.DictReader((P/'puzzle-cluster-auc.csv').open())}
labels={'any_initial_correct':'At least one correct initial solution','initial_net_bits':'Net initial information','false_resistance':'False-claim resistance','initial_precision':'Initial claim precision','initial_true_bits':'Truth-aligned initial bits','initial_correct_propositions':'Correct distinct initial propositions','selectivity':'True uptake minus false uptake','uptake_true':'True-claim uptake','initial_distinct':'Distinct initial propositions','post_initial_distinct':'Distinct later propositions, including final decisions','post_initial_distinct_before_final':'Distinct later propositions, excluding final decisions'}
for name,keys in [('auc_table_full',list(labels)),('auc_table',['any_initial_correct','initial_net_bits','false_resistance','selectivity','initial_distinct'])]:
 f=P.parent/'figures'/f'{name}.tex';text=f.read_text();before,body=text.split('\\midrule\n',1);_,after=body.split('\\bottomrule',1);lines=[]
 for k in keys:
  r=rows[k];ci=f"{float(r['within_auc']):.3f} [{float(r['within_low']):.3f}, {float(r['within_high']):.3f}]"
  cells=[labels[k],r['n'],f"{float(r['pooled_auc']):.3f}",ci] if name=='auc_table_full' else [labels[k],f"{r['n']} / {r['within_contributing']}",ci]
  lines.append(' & '.join(cells)+r' \\')
 f.write_text(before+'\\midrule\n'+'\n'.join(lines)+'\n\\bottomrule'+after)
print('Rendered both AUC tables from puzzle-cluster-auc.csv.')
