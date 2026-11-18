"""Apply bounded source-grounded claim corrections without retranslating debates.

Preserves original inventories and full source records. Rebuilds claim recurrence
and initial-supply features; it does not recompute historical relation analyses.
"""
from pathlib import Path
from copy import deepcopy
import csv
import hashlib
import json
import math
import numpy as np
import pandas as pd
from claim_logic import assignments, evaluate_expr, parse_compact_expression, contains_role_predicate, unique_index
from rebuild_initial_features import rebuild_features

P = Path(__file__).resolve().parent
OUT = P / 'corrections/source-audit-v3'
BASE = P / 'corrections/role-predicate-v2'
INPUT = P / 'control-inputs/claims.csv'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apply():
    with INPUT.open() as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames
        original = list(reader)
    rows = deepcopy(original)
    unique_index(rows, ('claim_uid',), 'original claims')
    frozen = json.loads((OUT / 'frozen-fields.json').read_text())
    questions = {r['id']: r for r in map(json.loads, (P / 'control-inputs/questions.jsonl').read_text().splitlines())}
    labels = {r['id']: r for r in map(json.loads, (P / 'control-inputs/labels.jsonl').read_text().splitlines())}
    ledger = []
    corrected_fields = []
    worlds = list(assignments(6))

    def score(row, new=False, no_premises=False):
        question = questions[row['task_id']]
        attribution = set(row['attribution'].split('|')) if row['attribution'] else set()
        effective_commitment = row['commitment']
        if effective_commitment in {'report', 'endorse'} and f"agent:{row['agent_id']}" in attribution:
            effective_commitment = 'endorse'
        committed = effective_commitment in {'assert', 'endorse'}
        raw_expression = row['effective_expression'] or row['expression']
        ast = None if effective_commitment in {'report', 'reject'} or not raw_expression else parse_compact_expression(raw_expression)
        statements = [s['ast'] for s in question['statements']]
        target = tuple(labels[row['task_id']]['roles'][p] for p in question['players'])
        n = sum(evaluate_expr(ast, w, statements) for w in worlds) if ast is not None else None
        truth = evaluate_expr(ast, target, statements) if ast is not None else None
        kind = 'unscored' if not committed or n is None or truth is None else ('contradictory' if n == 0 else ('redundant' if n == 192 else ('truth_aligned' if truth else 'misleading')))
        if ast is None:
            row['effective_expression'] = ''
        row.update(committed=str(int(committed)), target_truth=str(truth) if committed and truth is not None else '',
                   expression_truth_at_target=str(truth) if truth is not None else '', role_world_count='192',
                   supporting_role_world_count=str(float(n)) if n is not None else '',
                   information_bits=str(math.log2(192/n)) if n else '',
                   information_type=kind, structurally_impossible=str(int(n == 0)))
        reset_premises = new or no_premises
        if not committed or reset_premises:
            row.update(premise_world_count='', conditional_supporting_world_count='', conditional_information_bits='',
                       conditional_information_type='unscored', premises_admit_target='')
        if reset_premises:
            row.update(stated_premise_claim_ids='', stated_premise_count='0', stated_premise_status='none_extracted')
            if committed:
                row.update(premise_world_count='192.0', conditional_supporting_world_count=str(float(n)),
                           conditional_information_bits=row['information_bits'], conditional_information_type=kind,
                           premises_admit_target='True')

    for item in frozen:
        record = deepcopy(item['record'])
        source = record['source']
        field_rows = [r for r in rows if r['condition_id'] == item['condition_id'] and r['task_id'] == source['task_id']
                      and r['agent_id'] == source['agent_id'] and r['stage_order'] == '0']
        assert len({r['field_uid'] for r in field_rows}) == 1
        by_id = {r['local_claim_id']: r for r in field_rows}
        formal = {c['id']: c for c in record['claims']}
        assert set(by_id) == set(formal), 'Frozen formal record and claim inventory disagree'
        for cid, row in by_id.items():
            assert row['source_span'] == formal[cid]['source_span']
            assert row['commitment'] == formal[cid]['commitment']
        changed = []

        def mutate(cid, rationale, no_premises=False, **updates):
            row = by_id[cid]
            before = deepcopy(row)
            row.update(updates)
            assert row['source_span'] and row['source_span'] in record['source_text']
            score(row, no_premises=no_premises)
            formal[cid].update(commitment=row['commitment'], case_id=row['case_id'] or None,
                               attributions=row['attribution'].split('|') if row['attribution'] else [], source_span=row['source_span'])
            changed.append(cid)
            ledger.append(dict(debate_id=item['debate_id'], field_uid=row['field_uid'], claim_uid=row['claim_uid'],
                               operation='update', rationale=rationale, before=before, after=deepcopy(row)))

        def mark_unresolved_premises(cid, premise_ids, rationale):
            row = by_id[cid]
            before = deepcopy(row)
            score(row)
            row.update(stated_premise_claim_ids=','.join(premise_ids),
                       stated_premise_count=str(len(premise_ids)),
                       stated_premise_status='unresolved_reference',
                       premise_world_count='', conditional_supporting_world_count='',
                       conditional_information_bits='', conditional_information_type='unscored',
                       premises_admit_target='')
            changed.append(cid)
            ledger.append(dict(debate_id=item['debate_id'], field_uid=row['field_uid'], claim_uid=row['claim_uid'],
                               operation='update', rationale=rationale, before=before, after=deepcopy(row)))

        def add(expr, span, rationale):
            cid = 'c' + str(max(int(c[1:]) for c in formal) + 1)
            row = {k: '' for k in columns}
            prototype = field_rows[0]
            for key in ['condition_id', 'condition_label', 'task_id', 'repetition', 'field_uid', 'stage', 'stage_order',
                        'round_index', 'agent_id', 'field', 'player', 'operational_final_correct', 'behavior_stratum']:
                row[key] = prototype[key]
            row.update(local_claim_id=cid, claim_uid=prototype['field_uid'] + ':' + cid, commitment='assert',
                       expression=expr, effective_expression=expr, source_span=span)
            assert span and span in record['source_text']
            score(row, new=True)
            claim = dict(id=cid, commitment='assert', case_id=None, attributions=[],
                         expression=parse_compact_expression(expr), source_span=span)
            record['claims'].append(claim)
            formal[cid] = claim
            rows.append(row)
            changed.append(cid)
            ledger.append(dict(debate_id=item['debate_id'], field_uid=row['field_uid'], claim_uid=row['claim_uid'],
                               operation='add', rationale=rationale, before=None, after=deepcopy(row)))

        did, agent = item['debate_id'], source['agent_id']
        if (did, agent) == ('D04', 'agent-2'):
            mutate('c6', 'Reformulation of the content attributed to A, not an assertion of equal roles.',
                   commitment='report', attribution='player:A')
            mark_unresolved_premises(
                'c7', ['c6'],
                'The cited content is a report; _resolve_premises retains its ID but cannot use a neutral report as a truth-bearing premise.'
            )
        elif (did, agent) == ('D06', 'agent-1'):
            for player in ['C', 'F']:
                add(f'STMT_TRUE({player})', 'This contradiction shows C and F are knights (truth-tellers)',
                    'Explicit truth-teller description adds a statement evaluation beyond the existing role claim.')
        elif (did, agent) == ('D02', 'agent-2'):
            add('STMT_TRUE(E)', 'E must be knight telling truth',
                'Explicit truth evaluation remains expressed even though this field also asserts its opposite.')
        elif (did, agent) == ('D02', 'agent-3'):
            assert not any(c['id'] == 'h2' for c in record['cases'])
            mutate('c14', 'The if-clause makes F truth a hypothetical consequence rather than an unconditional assertion.',
                   commitment='hypothetical', case_id='h2')
            mutate('c15', 'Antecedent of the same explicit conditional; not an independently asserted count.',
                   commitment='assume', case_id='h2', source_span='if at most two among C,D,E,F are knights')
            mutate('c18', 'The final role assignment independently asserts F as a knight; detach it from the conditional truth/count analysis.',
                   source_span='D,E,F knights', no_premises=True)
            removed = [rel for rel in record['relations'] if rel.get('to') == 'c18']
            assert len(removed) == 1 and removed[0].get('from') == ['c14', 'c15', 'c16', 'c17']
            record['relations'] = [rel for rel in record['relations'] if rel.get('to') != 'c18']
            ledger.append(dict(debate_id=did, field_uid=by_id['c18']['field_uid'], claim_uid=by_id['c18']['claim_uid'],
                               operation='remove_relation',
                               rationale='The relation derives the final role claim from premises now scoped to a conditional clause.',
                               before=removed[0], after=None))
            record['cases'].append(dict(id='h2', disposition='unresolved', explicit=True,
                                        source_span="F's statement is true if at most two among C,D,E,F are knights"))
        else:
            raise AssertionError('Unexpected frozen field')
        record['source_audit_correction'] = dict(version='source-audit-v3', modified_claim_ids=changed,
                                                 model_retranslation=False, relation_annotations_regenerated=False)
        corrected_fields.append(dict(debate_id=did, condition_id=item['condition_id'], record=record))

    unique_index(rows, ('claim_uid',), 'corrected claims')
    modified = {r['claim_uid'] for r in ledger}
    after_by_id = {r['claim_uid']: r for r in rows}
    assert all(r == after_by_id[r['claim_uid']] for r in original if r['claim_uid'] not in modified)
    with (OUT / 'claims.csv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    (OUT / 'correction-ledger.json').write_text(json.dumps(ledger, indent=2) + '\n')
    (OUT / 'corrected-fields.json').write_text(json.dumps(corrected_fields, indent=2) + '\n')
    d = pd.DataFrame(rows)
    c = d[d.commitment.isin(['assert', 'endorse'])].copy()
    c['expr'] = c.effective_expression.where(c.effective_expression.ne(''), c.expression)
    c['stage_order'] = pd.to_numeric(c.stage_order)
    exposure_rows = []
    keys = ['condition_id', 'task_id', 'repetition', 'expression', 'recipient']
    for key, group in c.groupby(keys[:3]):
        for expr, gg in group.groupby('expr'):
            if contains_role_predicate(parse_compact_expression(expr)) or gg.stage_order.min() != 0:
                continue
            origin = gg[gg.stage_order.eq(0)]
            kind = origin.information_type.iloc[0]
            assert origin.information_type.nunique() == 1
            if kind not in ['truth_aligned', 'misleading']:
                continue
            for agent in ['agent-1', 'agent-2', 'agent-3']:
                if agent in set(origin.agent_id):
                    continue
                row = dict(zip(keys, [*key, expr, agent]))
                row.update(dataset='size6', information_type=kind,
                           adopted=int(any(gg.agent_id.eq(agent) & gg.stage_order.gt(0) & gg.stage_order.lt(10010))))
                exposure_rows.append(row)
    old_exposure = pd.read_csv(BASE / 'exposure-pairs.csv')
    exposures = pd.concat([pd.DataFrame(exposure_rows)[old_exposure.columns], old_exposure[old_exposure.dataset.eq('size8')]], ignore_index=True)
    exposures['repetition'] = pd.to_numeric(exposures.repetition)
    exposures = exposures.sort_values(['dataset', *keys])
    unique_index(exposures.to_dict('records'), tuple(keys), 'corrected exposure pairs')
    exposures.to_csv(OUT / 'exposure-pairs.csv', index=False)

    base_features = pd.read_csv(BASE / 'debate-features.csv', float_precision='round_trip')
    # Verify original definitions before using the helper on the changed claims.
    baseline = pd.read_csv(INPUT).fillna('')
    reference = rebuild_features(base_features, baseline)
    initial_columns = ['initial_distinct','initial_true','initial_false','initial_precision',
                       'initial_true_bits','initial_false_bits','initial_net_bits','initial_correct_propositions']
    for name in initial_columns:
        assert np.allclose(reference[name], base_features[name], equal_nan=True, atol=1e-10, rtol=0), name
    features = rebuild_features(base_features, pd.read_csv(OUT / 'claims.csv').fillna(''))
    # Publish only the features used in these analyses, not stale relation summaries.
    keep = list(base_features.columns[:15]) + ['claim_count', 'committed_claim_count'] + initial_columns + [
        'dataset','stratum','post_initial_distinct','post_initial_distinct_before_final',
        'eligible_true_pairs','adopted_true_pairs','uptake_true','eligible_false_pairs','adopted_false_pairs','uptake_false','false_resistance','selectivity']
    features = features[keep].copy()
    for i, r in features.iterrows():
        sub = exposures[exposures.condition_id.eq(r.condition_id) & exposures.task_id.eq(r.task_id) & exposures.repetition.eq(r.repetition) & exposures.dataset.eq(r.dataset)]
        if r.dataset == 'size6':
            claims = d[d.condition_id.eq(r.condition_id) & d.task_id.eq(r.task_id) & d.repetition.eq(str(r.repetition))]
            features.at[i, 'claim_count'] = len(claims)
            features.at[i, 'committed_claim_count'] = pd.to_numeric(claims.committed, errors='raise').sum()
        for kind, label in [('truth_aligned', 'true'), ('misleading', 'false')]:
            a = sub[sub.information_type.eq(kind)]
            features.at[i, f'eligible_{label}_pairs'] = len(a)
            features.at[i, f'adopted_{label}_pairs'] = a.adopted.sum()
            features.at[i, f'uptake_{label}'] = a.adopted.mean() if len(a) else np.nan
        features.at[i, 'false_resistance'] = 1 - features.at[i, 'uptake_false']
        features.at[i, 'selectivity'] = features.at[i, 'uptake_true'] - features.at[i, 'uptake_false']
    features.to_csv(OUT / 'debate-features.csv', index=False)
    auc = pd.read_csv(BASE / 'paper-auc.csv')
    for i, r in auc.iterrows():
        sub = features[features[r.feature].notna()]
        success, failure = sub[sub.operational_final_correct.eq(1)], sub[sub.operational_final_correct.eq(0)]
        auc.at[i, 'n'] = len(sub)
        for mode in ['pooled', 'within_condition']:
            vals, contributors = [], set()
            for si, s in success.iterrows():
                for fi, f in failure.iterrows():
                    if mode == 'within_condition' and s.stratum != f.stratum:
                        continue
                    vals.append(float(s[r.feature] > f[r.feature]) + .5 * float(s[r.feature] == f[r.feature]))
                    contributors.update([si, fi])
            auc.at[i, 'auc_' + mode] = np.mean(vals)
            if mode == 'within_condition':
                auc.at[i, 'n_within_contributing'] = len(contributors)
                auc.at[i, 'within_comparison_pairs'] = len(vals)
        for col in ['pooled_ci_low','pooled_ci_high','within_ci_low','within_ci_high']:
            auc.at[i, col] = np.nan
    auc.to_csv(OUT / 'paper-auc.csv', index=False)
    manifest = dict(version='source-audit-v3', operations=len(ledger), modified_existing_claims=sum(r['operation']=='update' for r in ledger),
                    added_claims=sum(r['operation']=='add' for r in ledger), corrected_fields=len(frozen), claim_rows=len(rows),
                    committed_claims=int(pd.to_numeric(d.committed, errors='raise').sum()), corrected_exposure_pairs=exposures.groupby('dataset').size().to_dict(),
                    removed_stale_unused_feature_columns=sorted(set(base_features.columns)-set(keep)),
                    relation_annotations_regenerated=False, new_translation_calls=0,
                    input_sha256={str(p.relative_to(P)):digest(p) for p in [INPUT, OUT/'frozen-fields.json', BASE/'exposure-pairs.csv', BASE/'debate-features.csv', BASE/'paper-auc.csv']})
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    apply()
