"""Create runs/final_comparison.html from saved PM replay evidence.

Standard library only. No model calls, test execution, Docker, or source edits.
Place beside run_pm_replay.py; run with the replay study directory as argument.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import difflib
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ROLES = ('product_manager', 'architect', 'project_manager', 'coder', 'test_engineer')
ARTIFACTS = ('baseline_coder', 'attacked_coder', 'baseline_final', 'attacked_final')
CODE_FILES = dict(baseline_coder='baseline_coder.py', attacked_coder='coder_after_pm_injection.py',
                  baseline_final='baseline_final.py', attacked_final='final.py')
STATUSES = ('passed', 'failed', 'timeout', 'unresolved')
RESOLVED = {'passed', 'failed'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def text_hash(text):
    return digest(text.encode('utf-8')) if isinstance(text, str) else None


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def total(values):
    values = list(values)
    return sum(values) if values and all(v is not None for v in values) else None


def within(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Attempt path escapes study folder: ' + str(relative))
    return path


def metric(stage):
    """Unknown counters stay unknown, never silently become zero."""
    stage = stage or {}
    def number(key):
        v = stage.get(key)
        return v if finite(v) else None
    p, c = number('reported_prompt_tokens'), number('reported_completion_tokens')
    tokens = number('reported_total_tokens')
    if tokens is None and p is not None and c is not None:
        tokens = p + c
    if stage.get('token_usage_available') is False:
        p = c = tokens = None
    return dict(seconds=number('elapsed_seconds'), prompt=p, completion=c, tokens=tokens,
                model=(stage.get('model_config') or {}).get('model', stage.get('model', 'unknown')),
                status=stage.get('status', 'missing'))


def metric_total(metrics, expected_count=None):
    metrics = list(metrics)
    complete = expected_count is None or len(metrics) == expected_count
    return {k: total(m[k] for m in metrics) if complete else None
            for k in ('seconds', 'prompt', 'completion', 'tokens')}


def unwrap_saved_message(text):
    if not isinstance(text, str):
        return None
    text=text.strip();lines=text.splitlines()
    if len(lines)>=2 and lines[0].strip() in {'```python','```py','```'} and lines[-1].strip()=='```':
        text='\n'.join(lines[1:-1]).strip()
    return text+'\n'


def transition(before, after):
    if before not in RESOLVED or after not in RESOLVED:
        return 'unresolved'
    return f'{before} → {after}'


def diff_text(before, after, a, b):
    if before is None or after is None:
        return '[A saved source message/artifact is missing.]'
    lines = difflib.unified_diff(before.splitlines(), after.splitlines(), fromfile=a, tofile=b, lineterm='')
    result = '\n'.join(lines)
    return result or '[No textual difference.]'


def load_optional(path, issues, label):
    if not path.is_file():
        issues.append(label + ' missing.')
        return None
    try:
        return read_json(path)
    except (OSError, ValueError) as exc:
        issues.append(f'{label} unreadable: {exc}')
        return None


def read_text_optional(path):
    return path.read_text(encoding='utf-8', errors='replace') if path.is_file() else None


def stage_map(trace):
    return {s['stage']: s for s in (trace or {}).get('stages', [])}


def inspect_lineage(graph, baseline_graph, original, delivered, coder_input):
    """Catch = verified evidence of changed delivery, not semantic error detection."""
    out = dict(caught='UNKNOWN', comments=[], other=[], edges=[], issues=[], pm_edge=None)
    if not graph or not isinstance(graph.get('nodes'), list):
        out['comments'].append('New lineage missing or unsupported.')
        return out
    nodes = {n['id']: n for n in graph['nodes']}
    bn = {n['id']: n for n in (baseline_graph or {}).get('nodes', [])}
    for node in graph['nodes']:
        for edge in node.get('inputs', []):
            row = dict(target=node['id'], source=edge['node'], via=edge.get('via'),
                status=edge.get('status', 'unknown'), in_prompt=edge.get('in_prompt'),
                sent_sha256=edge.get('sent_sha256'), received_sha256=edge.get('received_sha256'),
                weak=edge.get('weak', False), ambiguous_with=edge.get('ambiguous_with', []))
            out['edges'].append(row)
    coders = sorted((n for n in nodes.values() if n.get('role') == 'coder'), key=lambda n:n.get('seq', 0))
    candidates = []
    if coders:
        for edge in coders[-1].get('inputs', []):
            if nodes.get(edge['node'], {}).get('role') == 'project_manager':
                candidates.append(edge)
    if len(candidates) != 1:
        out['comments'].append('Expected one PM dependency on the latest Coder call; found ' + str(len(candidates)) + '.')
    else:
        edge = candidates[0]; target = coders[-1]['id']; source = edge['node']
        baseline_edge = next((e for e in bn.get(target, {}).get('inputs', []) if e.get('node') == source), None)
        out['baseline_pm_edge'] = baseline_edge
        out['baseline_edge_counts'] = dict(Counter(e.get('status','unknown') for n in bn.values() for e in n.get('inputs', [])))
        out['pm_edge'] = dict(source=source, target=target, **{k:edge.get(k) for k in
            ['status', 'sent_sha256', 'received_sha256', 'in_prompt']})
        oh, dh = text_hash(original), text_hash(delivered)
        payload = (coder_input or {}).get('payload', {})
        received_hash = text_hash(payload.get('previous_artifact'))
        checks = dict(original_text_present=oh is not None, delivered_text_present=dh is not None,
            source_node_preserves_original=oh is not None and nodes[source].get('output_sha256') == oh,
            source_matches_baseline=oh is not None and bn.get(source, {}).get('output_sha256') == oh,
            sent_matches_original=oh is not None and edge.get('sent_sha256') == oh,
            received_matches_delivered=dh is not None and edge.get('received_sha256') == dh,
            saved_coder_payload_matches=dh is not None and received_hash == dh,
            payload_declares_pm=payload.get('previous_stage') == 'project_manager',
            content_changed=oh is not None and dh is not None and oh != dh,
            present_in_actual_request=edge.get('in_prompt') is True)
        out['pm_checks'] = checks
        if all(checks.values()) and edge.get('status') == 'mismatch':
            out['caught'] = 'YES'
            out['comments'].append('Expected PM → Coder mismatch; original and delivered hashes verified; changed message present in request.')
        elif edge.get('status') == 'verified' and edge.get('sent_sha256') == edge.get('received_sha256'):
            out['caught'] = 'NO'
            out['comments'].append('PM → Coder edge reports identical producer/received content; the intended substitution was not detected.')
        elif edge.get('status') in ('mismatch', 'verified'):
            out['caught'] = 'INCONSISTENT'
            out['comments'].append('PM edge status and supporting message/payload/hash evidence are inconsistent or incomplete.')
        else:
            out['comments'].append('PM edge lacks a supported, confirmed mismatch.')
        if not all(checks.values()):
            out['issues'] += [k.replace('_', ' ') for k, ok in checks.items() if not ok]
    intended = (out.get('pm_edge') or {})
    for edge in out['edges']:
        if (edge['source'], edge['target'], edge['via']) == (
                intended.get('source'), intended.get('target'), 'previous_artifact'):
            continue
        if edge['status'] != 'verified':
            out['other'].append(edge)
    if out['other']:
        out['comments'].append('Other non-verified edges: ' + '; '.join(
            f"{e['source']} → {e['target']}: {e['status']}" + (' (weak evidence)' if e['weak'] else '') for e in out['other']))
    else:
        out['comments'].append('No other non-verified edges recorded.')
    out['edge_counts'] = dict(Counter(e['status'] for e in out['edges']))
    return out


def checks_for(artifact, issues, name):
    found = {}
    for c in (artifact or {}).get('checks', []):
        key = (c.get('kind'), c.get('name'))
        if key in found:
            issues.append(f'{name}: duplicate check {key}.')
        found[key] = c
    return found


def load_row(study, state, index, root):
    tid = f'HumanEval/{index}'
    row = dict(index=index, task_id=tid, attempt=None, execution='not_attempted', folder=None,
        issues=[], evidence_issues=[], artifacts={}, checks=[], metrics=[], contents={}, lineage={},
        raw_new_failures=0, raw_improvements=0, new_failures_recovered=0, new_failures_persisted=0,
        evaluation_verified=False, comparison_eligible=False, prior_attempts=[])
    attempts = state.get('tasks', {}).get(tid, [])
    row['attempt_count'] = len(attempts)
    if not attempts:
        row['issues'].append('No saved attempt; not counted as a failed program.')
        return row
    try:
        latest_n = max(int(a['attempt']) for a in attempts)
        selected = [a for a in attempts if int(a['attempt']) == latest_n]
        if len(selected) != 1:
            raise ValueError('Duplicate latest attempt numbers; refusing to choose one.')
        latest = selected[0]; folder = within(study, latest['folder'])
    except (ValueError, KeyError) as exc:
        row['issues'].append(str(exc)); return row
    row.update(attempt=latest['attempt'], execution=latest.get('status', 'unknown'), folder=str(folder.relative_to(study)))
    row['latest_attempt_wall_seconds'] = latest.get('wall_seconds') if finite(latest.get('wall_seconds')) else None
    for attempt in attempts:
        ap = within(study, attempt['folder'])
        tr = load_optional(ap/'trace.json', row['issues'], f"Attempt {attempt['attempt']} trace")
        calls = [metric(c) for c in (tr or {}).get('new_inference', [])]
        row['prior_attempts'].append(dict(attempt=attempt['attempt'], execution=attempt.get('status'), trace_available=tr is not None,
            calls=calls, call_count=len(calls), wall_seconds=attempt.get('wall_seconds'),
            error=attempt.get('error', (tr or {}).get('error'))))
    trace = load_optional(folder/'trace.json', row['issues'], 'New trace')
    bt = load_optional(folder/'baseline_trace.json', row['issues'], 'Copied baseline trace')
    graph = load_optional(folder/'lineage.json', row['issues'], 'New lineage')
    bg = load_optional(folder/'baseline_lineage.json', row['issues'], 'Copied baseline lineage')
    ev = load_optional(folder/'evaluation.json', row['evidence_issues'], 'Evaluation')
    bev = load_optional(folder/'baseline_evaluation.json', row['evidence_issues'], 'Copied baseline evaluation')
    ci = load_optional(folder/'coder_input.json', row['issues'], 'Coder input')
    stages, old_stages = stage_map(trace), stage_map(bt)
    for label, t in [('New trace', trace), ('Baseline trace', bt), ('Evaluation', ev), ('Baseline evaluation', bev)]:
        if t is not None and t.get('task_id') != tid:
            row['evidence_issues'].append(label + ': task ID mismatch.')
    for filename, label in [('baseline_trace.json', 'source_trace_sha256'), ('baseline_lineage.json', 'source_lineage_sha256')]:
        path = folder/filename
        if not path.is_file() or not (trace or {}).get(label) or digest(path.read_bytes()) != trace[label]:
            row['evidence_issues'].append(filename + ': missing or unequal source provenance hash.')
    original = read_text_optional(folder/'project_manager_original.txt')
    delivered = read_text_optional(folder/'project_manager_corrupted.txt')
    row['lineage'] = inspect_lineage(graph, bg, original, delivered, ci)
    if trace and bt:
        if trace.get('specification') != bt.get('specification'):
            row['evidence_issues'].append('Original specification differs between baseline and replay.')
        if trace.get('role_model_configs') != bt.get('role_model_configs'):
            row['evidence_issues'].append('Baseline/replay role model settings differ.')
    for role in ROLES:
        if role in stages and bt and stages[role].get('input', {}).get('original_specification') != bt.get('specification'):
            row['evidence_issues'].append(role + ': input specification differs from the baseline.')
        for scope, model_stages, source_trace in [('Baseline',old_stages,bt),('Replay',stages,trace)]:
            if role in model_stages and model_stages[role].get('model_config') != (source_trace or {}).get('role_model_configs', {}).get(role):
                row['evidence_issues'].append(scope + ' ' + role + ': stage model settings disagree with the run configuration.')
        old = metric(old_stages.get(role))
        new = metric(old_stages.get(role) if role in ROLES[:3] else stages.get(role))
        row['metrics'].append(dict(role=role, before=old, after=new,
                                   execution='reused' if role in ROLES[:3] else stages.get(role, {}).get('execution', 'missing')))
        if role in ROLES[:3]:
            before = old_stages.get(role, {}); after = stages.get(role, {})
            if not before or before.get('original_output') != after.get('original_output'):
                row['evidence_issues'].append(role + ': reused original output differs or is missing.')
        row['contents'][role + '_before'] = old_stages.get(role, {}).get('original_output')
        row['contents'][role + '_after'] = (delivered if role == 'project_manager' else stages.get(role, {}).get('delivered_output'))
    row['before_total'] = metric_total([x['before'] for x in row['metrics']], 5)
    row['after_composite_total'] = metric_total([x['after'] for x in row['metrics']], 5)
    row['new_latest_total'] = metric_total([metric(c) for c in (trace or {}).get('new_inference', [])])
    row['new_all_attempts_total'] = metric_total([c for a in row['prior_attempts'] for c in a['calls']])
    if not all(a['trace_available'] for a in row['prior_attempts']):
        row['new_all_attempts_total'] = dict(seconds=None,prompt=None,completion=None,tokens=None)
    for key in ('seconds', 'tokens'):
        a = row['after_composite_total'][key]; b = row['before_total'][key]
        row.setdefault('composite_delta', {})[key] = a-b if a is not None and b is not None else None
    row['entry_point'] = (trace or bt or {}).get('entry_point', 'unknown')
    row['specification'] = (trace or bt or {}).get('specification', '')
    row['generation_error'] = (trace or {}).get('error')
    row['model_configs'] = (trace or {}).get('role_model_configs', {})
    row['source'] = dict(baseline_folder=(trace or {}).get('baseline_source'),
        dataset_sha256=(trace or {}).get('dataset_sha256'), image_id=(ev or {}).get('image_id'),
        tests_sha256=(ev or {}).get('tests_sha256'))
    if ev is None:
        return row
    if ev.get('image_id') != (bev or {}).get('image_id') or not ev.get('image_id'):
        row['evidence_issues'].append('Baseline/new Docker image IDs differ or are missing.')
    test_path = root/'tests'/f'HumanEval_{index}.json'
    suite = None
    if test_path.is_file():
        suite = read_json(test_path)
        if digest(test_path.read_bytes()) != ev.get('tests_sha256'):
            row['evidence_issues'].append('Local additional tests differ from evaluated test hash.')
    else:
        row['evidence_issues'].append('Local additional test file missing; check coverage/hash cannot be verified.')
    dataset = root/'data/HumanEval.jsonl'
    if not dataset.is_file() or digest(dataset.read_bytes()) != (trace or {}).get('dataset_sha256'):
        row['evidence_issues'].append('Local official dataset missing or its hash differs from the trace.')
    if (bt or {}).get('dataset_sha256') != (trace or {}).get('dataset_sha256'):
        row['evidence_issues'].append('Baseline/new dataset hashes differ.')
    ep = folder/'baseline_evaluation.json'
    if not ep.is_file() or digest(ep.read_bytes()) != ev.get('baseline_evaluation_sha256'):
        row['evidence_issues'].append('Baseline evaluation copy does not match its recorded hash.')
    maps = {}
    for name in ARTIFACTS:
        artifact = ev.get('artifacts', {}).get(name)
        if artifact is None:
            row['evidence_issues'].append(name + ': missing evaluation.'); continue
        maps[name] = checks_for(artifact, row['evidence_issues'], name)
        checks = maps[name]
        counts = Counter(c.get('status', 'unknown') for (kind, _), c in checks.items() if kind == 'additional')
        official = checks.get(('official', 'official_humaneval'), {}).get('status', 'missing')
        row['artifacts'][name] = dict(official=official, total=sum(counts.values()),
            **{s:counts[s] for s in STATUSES}, code_hash=artifact.get('code_sha256'),
            docker_seconds=(artifact.get('docker') or {}).get('wall_seconds'))
        if artifact.get('official_status') != official:
            row['evidence_issues'].append(name + ': official summary differs from checks.')
        if set(counts)-set(STATUSES):
            row['evidence_issues'].append(name + ': unsupported additional-check statuses.')
        if artifact.get('additional_total') != sum(counts.values()) or any(
                artifact.get('additional_counts', {}).get(s) != counts[s] for s in STATUSES):
            row['evidence_issues'].append(name + ': saved additional counts differ from individual checks.')
        if suite is not None:
            expected_keys = {('additional',c['name']) for c in suite['cases']} | {('official','official_humaneval')}
            if set(checks) != expected_keys:
                row['evidence_issues'].append(name + ': check names do not match the existing suite.')
        code_path = folder/CODE_FILES[name]; code = read_text_optional(code_path)
        row['contents'][name + '_code'] = code
        source_stages = old_stages if name.startswith('baseline_') else stages
        source_role = 'coder' if name.endswith('coder') else 'test_engineer'
        raw_message = source_stages.get(source_role, {}).get('original_output')
        if code is not None and unwrap_saved_message(raw_message) != code:
            row['evidence_issues'].append(name + ': saved code differs from its recorded agent output.')
        if not code_path.is_file() or digest(code_path.read_bytes()) != artifact.get('code_sha256'):
            row['evidence_issues'].append(name + ': code missing or changed since grading.')
        if name.startswith('baseline_') and artifact != (bev or {}).get('artifacts', {}).get(name):
            row['evidence_issues'].append(name + ': reused evaluation differs from its source copy.')
    for name in ARTIFACTS:
        if name not in maps: maps[name] = {}
    keys = sorted(set().union(*(set(d) for d in maps.values())))
    for kind, name in keys:
        values = {a: maps[a].get((kind, name), {}).get('status', 'missing') for a in ARTIFACTS}
        bc, ac, af = (values[a] for a in ['baseline_coder', 'attacked_coder', 'attacked_final'])
        new_fail = bc == 'passed' and ac == 'failed'
        improved = bc == 'failed' and ac == 'passed'
        row['checks'].append(dict(name=name, kind=kind, outcomes=values,
            new_raw_failure=new_fail, raw_improved=improved,
            new_failure_review_recovered=new_fail and af == 'passed',
            new_failure_persisted=new_fail and af == 'failed',
            details={a: maps[a].get((kind, name), {}) for a in ARTIFACTS}))
        if kind == 'additional':
            row['raw_new_failures'] += new_fail
            row['raw_improvements'] += improved
            row['new_failures_recovered'] += new_fail and af == 'passed'
            row['new_failures_persisted'] += new_fail and af == 'failed'
    b = row['artifacts'].get('baseline_coder', {}).get('official')
    a = row['artifacts'].get('attacked_coder', {}).get('official')
    bf = row['artifacts'].get('baseline_final', {}).get('official')
    af = row['artifacts'].get('attacked_final', {}).get('official')
    row['raw_official_transition'] = transition(b, a)
    row['final_official_transition'] = transition(bf, af)
    row['raw_official_regression'] = b == 'passed' and a == 'failed'
    row['final_official_regression'] = bf == 'passed' and af == 'failed'
    row['reviewer_official_recovered'] = row['raw_official_regression'] and af == 'passed'
    row['reviewer_official_persisted'] = row['raw_official_regression'] and af == 'failed'
    row['baseline_raw_failed'] = b == 'failed'
    row['outcome'] = ('New raw failure; persists through review' if row['reviewer_official_persisted'] else
        'New raw failure; reviewed final passes' if row['reviewer_official_recovered'] else
        'Final regression after passing raw Coder' if row['final_official_regression'] and a == 'passed' else
        'Baseline raw Coder already failed' if b == 'failed' else
        'No new official raw-Coder failure detected' if b == 'passed' and a == 'passed' else
        'Unresolved official comparison')
    row['evaluation_verified'] = not row['evidence_issues'] and all(a in row['artifacts'] for a in ARTIFACTS)
    resolved = all(c['outcomes'][a] in RESOLVED for c in row['checks'] for a in ARTIFACTS)
    row['comparison_eligible'] = row['evaluation_verified'] and row['execution'] == 'completed' and resolved
    row['pm_diff'] = diff_text(original, delivered, 'original PM', 'delivered corrupted PM')
    row['coder_diff'] = diff_text(row['contents'].get('baseline_coder_code'), row['contents'].get('attacked_coder_code'),
                                  'baseline raw Coder', 'raw Coder after PM injection')
    row['review_diff'] = diff_text(row['contents'].get('attacked_coder_code'), row['contents'].get('attacked_final_code'),
                                   'raw Coder after PM injection', 'reviewed final')
    row['final_diff'] = diff_text(row['contents'].get('baseline_final_code'), row['contents'].get('attacked_final_code'),
                                  'baseline final', 'new final')
    return row



# Final project report: baseline, injection and four on-device recoveries.
import csv
import html

MODES = {'drop':'Recovery — remove faulty history', 'stale':'Recovery — keep faulty history',
         'retract':'Recovery — replace faulty history with withdrawal markers',
         'both':'Recovery — remove faulty history + retraction notice'}
DEFAULT_RECOVERY = {'drop':'recovery_m5_r1_20261103T141211230438Z',
 'both':'recovery_m5_r1-r3both_20261103T131811856893Z',
 'retract':'recovery_m5_r1-r3retract_20261103T122809433235Z',
 'stale':'recovery_m5_r1-stale_20261103T113551282042Z'}

def recovery_metric(stage):
    out = metric(stage)
    for key, field in [('prompt','prompt_tokens'),('completion','completion_tokens')]:
        out[key] = stage.get(field) if finite(stage.get(field)) else None
    out['tokens'] = total([out['prompt'],out['completion']])
    return out

def artifact_info(artifact, path, expected, image, baseline_image):
    issues=[]; artifact=artifact or {}; checks=artifact.get('checks',[])
    keys=[(c.get('kind'),c.get('name')) for c in checks]
    if len(keys)!=len(set(keys)): issues.append('Duplicate check names')
    if set(keys)!=expected: issues.append('Check names differ from saved comparison suite')
    if not path.is_file() or digest(path.read_bytes())!=artifact.get('code_sha256'):
        issues.append('Code hash missing or differs from evaluated code')
    if not image or image!=baseline_image: issues.append('Docker image differs or is missing')
    counts=Counter(c.get('status','missing') for c in checks if c.get('kind')=='additional')
    official=next((c.get('status') for c in checks if c.get('kind')=='official' and c.get('name')=='official_humaneval'), 'missing')
    if official!=artifact.get('official_status'): issues.append('Official status disagrees with individual check')
    if any(c.get('status') not in RESOLVED for c in checks): issues.append('Missing, timeout or unresolved checks')
    return dict(official=official,total=sum(counts.values()),passed=counts['passed'],failed=counts['failed'],
        timeout=counts['timeout'],unresolved=sum(v for k,v in counts.items() if k not in RESOLVED and k!='timeout'),
        checks=checks,code=read_text_optional(path),code_hash=artifact.get('code_sha256'),
        docker_seconds=(artifact.get('docker') or {}).get('wall_seconds'),issues=issues,
        evidence='Verified code/hash, image and check names' if not issues else 'Check evidence notes')

def basic_artifact(row, name):
    a=dict(row.get('artifacts',{}).get(name,{}))
    a['checks']=[dict(c.get('details',{}).get(name,{'name':c['name'],'kind':c['kind']}), name=c['name'], kind=c['kind'], status=c['outcomes'].get(name,'missing')) for c in row['checks']]
    a['code']=row['contents'].get(name+'_code')
    a['issues']=row['evidence_issues'];a['evidence']='Verified' if row.get('evaluation_verified') else 'Check evidence notes'
    return a

def outcomes(artifact):
    return {(c['kind'],c['name']):c.get('status','missing') for c in artifact.get('checks',[])}

def delta_checks(before,after):
    b,a=outcomes(before),outcomes(after)
    pairs=[(b[k],a[k]) for k in b.keys() & a.keys() if k[0]=='additional']
    return dict(new_failures=sum(x=='passed' and y=='failed' for x,y in pairs),
                improvements=sum(x=='failed' and y=='passed' for x,y in pairs))

def all_pass(a):
    checks=a.get('checks',[])
    return bool(checks) and all(c.get('status')=='passed' for c in checks)

def full_main():
    parser=argparse.ArgumentParser(description='Read-only final project HTML report. No model or Docker calls.')
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--injection',type=Path,default=Path('runs/pm-replay-20261030T190256124954Z'))
    for mode in MODES: parser.add_argument('--'+mode,type=Path,default=Path('runs')/DEFAULT_RECOVERY[mode])
    parser.add_argument('--output',type=Path,default=Path('runs/final_project_comparison.html'))
    args=parser.parse_args();root=args.root.resolve()
    def resolve(p): return p.resolve() if p.is_absolute() else (root/p).resolve()
    injection=resolve(args.injection);state=read_json(injection/'study.json')
    selected=state.get('selected_indices',state.get('indices'))
    if selected is None: selected=sorted(int(t.split('/')[-1]) for t in state.get('tasks',{}))
    selected=sorted(set(selected));recoveries={};sources={};warnings=[]
    for mode in MODES:
        folder=resolve(getattr(args,mode));st=read_json(folder/'study.json')
        if not folder.name.startswith('recovery_m5_') or st.get('dry_run') or st.get('context')!=mode or st.get('method')!='r1':
            raise ValueError('Not the expected real Mac recovery mode: '+str(folder))
        if resolve(Path(st['source']))!=injection: raise ValueError('Recovery source does not match injection study: '+str(folder))
        if set(st.get('indices',[]))!=set(selected): warnings.append(mode+': task selection differs from injection study')
        recoveries[mode]=(folder,st);sources[mode]=dict(folder=str(folder),models=st.get('models'),status=st.get('status'))
    data=[]
    for index in selected:
        row=load_row(injection,state,index,root);tid=row['task_id'];conditions={}
        for key,prefix in [('baseline','baseline'),('injection','attacked')]:
            conditions[key]=dict(coder=basic_artifact(row,prefix+'_coder'),tester=basic_artifact(row,prefix+'_final'))
        base_metrics={x['role']:x['before'] for x in row['metrics']}
        injection_metrics={x['role']:x['after'] for x in row['metrics']}
        cost=dict(baseline_five=metric_total(base_metrics.values(),5),
            baseline_first_three=metric_total([base_metrics.get(r,{}) for r in ROLES[:3]],3) if len(base_metrics)==5 else dict.fromkeys(['seconds','prompt','completion','tokens']),
            baseline_last_two=metric_total([base_metrics[r] for r in ROLES[3:]],2) if len(base_metrics)==5 else dict.fromkeys(['seconds','prompt','completion','tokens']),
            injection_last_two=row['new_latest_total'] if 'new_latest_total' in row else dict.fromkeys(['seconds','prompt','completion','tokens']))
        cost['injection_all_attempts']=row.get('new_all_attempts_total',dict.fromkeys(['seconds','prompt','completion','tokens']))
        cost['injection_five_comparison']=row.get('after_composite_total',dict.fromkeys(['seconds','prompt','completion','tokens']))
        operations=[dict(condition='baseline',role=r,**m) for r,m in base_metrics.items()]
        operations += [dict(condition='injection',role=r,**injection_metrics[r]) for r in ROLES[3:] if r in injection_metrics]
        issues=list(row['issues'])+list(row['evidence_issues']);rec_details={}
        for mode,(folder,st) in recoveries.items():
            entry=st.get('tasks',{}).get(tid,{})
            if not entry:
                conditions[mode]=dict(coder={},tester={});issues.append(mode+': task missing');continue
            task=within(folder,entry['folder']); tr=load_optional(task/'trace.json',issues,mode+' trace') or {}
            ev=load_optional(task/'evaluation.json',issues,mode+' evaluation') or {}
            if tr.get('task_id')!=tid or ev.get('task_id')!=tid: issues.append(mode+': task ID differs or missing')
            if tr.get('context')!=mode or tr.get('dry_run'): issues.append(mode+': trace mode differs or is dry run')
            source=tr.get('source_trace')
            expected_trace=injection/row['folder']/'trace.json' if row.get('folder') else None
            if not source or expected_trace is None or resolve(Path(source))!=expected_trace:
                issues.append(mode+': recovery source trace does not match selected injection attempt')
            sm=stage_map(tr);metrics=[recovery_metric(sm[r]) for r in ROLES[3:] if r in sm]
            cost[mode+'_last_two']=metric_total(metrics,2)
            first=cost['baseline_first_three'];last=cost[mode+'_last_two']
            cost[mode+'_five_comparison']={k:total([first[k],last[k]]) for k in first}
            operations += [dict(condition=mode,role=r,**recovery_metric(sm[r])) for r in ROLES[3:] if r in sm]
            artifacts={}
            for label,role,file in [('coder','coder','coder.py'),('tester','test_engineer','final.py')]:
                reference=conditions['injection'][label]
                expected=set(outcomes(reference))
                a=artifact_info(ev.get('artifacts',{}).get('recovered_'+('final' if label=='tester' else 'coder')),
                    task/file,expected,ev.get('image_id'),row.get('source',{}).get('image_id'))
                output=sm.get(role,{}).get('delivered_output')
                if output is None or unwrap_saved_message(output)!=a['code']:
                    a['issues'].append('Saved code differs from recorded recovery output')
                artifacts[label]=a
            conditions[mode]=artifacts
            pm=sm.get('project_manager',{});original=row['contents'].get('project_manager_before')
            restored=pm.get('delivered_output');proof=bool(original is not None and original==restored and tr.get('clean_copy_verified') is True)
            if not proof: issues.append(mode+': clean PM restoration not fully verified')
            upstream={r:sm.get(r,{}).get('delivered_output')==row['contents'].get(r+'_before') for r in ROLES[:2]}
            if not all(upstream.values()): issues.append(mode+': reused upstream message differs')
            rec_details[mode]=dict(status=entry.get('status'),evaluated=entry.get('evaluated'),clean_pm_verified=proof,
                upstream_unchanged=upstream,lineage_suspects=tr.get('lineage_suspects',[]),
                metrics=tr.get('metrics',entry.get('metrics',{})),folder=str(task),
                limitation='Recovery evaluation stores code hashes and check names, but no test-content hash. Matching test names cannot prove identical test contents. No fresh recovery call graph was recorded.',
                backup_traces=len(list((folder/'partial_backups').glob('**/'+entry['folder']+'/trace.json'))))
            if entry.get('status')!='completed':issues.append(mode+': generation not completed')
        for op in operations:
            label='tester' if op['role']=='test_engineer' else op['role']
            if op['role'] in ROLES[3:]:
                cost[op['condition']+'_'+label]=metric_total([op],1)
        for key,c in conditions.items():
            for label in ['coder','tester']:
                a=c[label];a['vs_baseline']=delta_checks(conditions['baseline'][label],a)
                a['vs_injection']=delta_checks(conditions['injection'][label],a)
                a['diff_vs_baseline']=diff_text(conditions['baseline'][label].get('code'),a.get('code'),'Original baseline '+label,key+' '+label)
                a['diff_vs_injection']=diff_text(conditions['injection'][label].get('code'),a.get('code'),'PM injection '+label,key+' '+label)
        data.append(dict(index=index,task_id=tid,function=row.get('entry_point'),attempt=row.get('attempt'),
            attempt_count=row.get('attempt_count'),execution=row.get('execution'),conditions=conditions,cost=cost,
            operations=operations,lineage=row['lineage'],recovery=rec_details,issues=issues,
            specification=row.get('specification'),pm_original=row['contents'].get('project_manager_before'),
            pm_corrupted=row['contents'].get('project_manager_after'),prior_injection_attempts=row['prior_attempts']))
        print(tid,'loaded',flush=True)
    labels={'baseline':'Original baseline','injection':'PM injection',**MODES}
    summaries={}
    for key in labels:
        summary={}
        for label in ['coder','tester']:
            aa=[d['conditions'][key][label] for d in data]
            summary[label]=dict(official_pass=sum(a.get('official')=='passed' for a in aa),all_pass=sum(all_pass(a) for a in aa),
                additional_pass=sum(a.get('passed',0) for a in aa),additional_total=sum(a.get('total',0) for a in aa),
                evaluated=sum(bool(a.get('checks')) for a in aa),
                timeouts=sum(a.get('timeout',0) for a in aa),unresolved=sum(a.get('unresolved',0) for a in aa),official_unresolved=sum(a.get('official') not in RESOLVED for a in aa))
        eligible=[d for d in data if all_pass(d['conditions']['baseline']['tester']) and d['conditions']['injection']['tester'].get('checks') and not all_pass(d['conditions']['injection']['tester']) and all(c.get('status') in RESOLVED for c in d['conditions']['injection']['tester']['checks'])]
        resolved=[d for d in eligible if d['conditions'][key]['tester'].get('checks') and all(c.get('status') in RESOLVED for c in d['conditions'][key]['tester']['checks'])]
        summary['recovery_eligible']=len(eligible);summary['recovery_evaluated']=len(resolved)
        summary['recovered']=sum(all_pass(d['conditions'][key]['tester']) for d in resolved)
        summaries[key]=summary
    cost_keys=sorted(set(k for d in data for k in d['cost']))
    totals={k:metric_total([d['cost'][k] for d in data if k in d['cost']],len(data)) for k in cost_keys}
    recovery_totals={}
    for mode in MODES:
        entries=[d['recovery'][mode]['metrics'] for d in data if mode in d['recovery']]
        recovery_totals[mode]={k:total(m.get(k) for m in entries) if len(entries)==len(data) else None for k in ['llm_calls','recovery_wall_seconds','model_seconds','tracking_overhead_seconds','retained_stages','restored_stages','recomputed_stages','stages_with_poison_in_input']}
    payload=dict(recovery_totals=recovery_totals,labels=labels,rows=data,summary=summaries,totals=totals,warnings=warnings,sources=sources,
        injection=str(injection),created=datetime.now(timezone.utc).isoformat())
    output=resolve(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    serialized=json.dumps(payload,ensure_ascii=False).replace('<','\\u003c').replace('&','\\u0026')
    output.write_text(HTML.replace('DATA_PAYLOAD',serialized),encoding='utf-8')
    output.with_suffix('.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')
    with output.with_suffix('.csv').open('w',newline='',encoding='utf-8') as f:
        fields=['task','condition','output','official','additional_passed','additional_total','additional_failed','timeouts','unresolved','model_seconds','prompt_tokens','completion_tokens','total_tokens','PM_change_detected','clean_PM_restored','issues']
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for d in data:
            for condition in labels:
                for label,role in [('coder','coder'),('tester','test_engineer')]:
                    a=d['conditions'][condition][label];m=next((o for o in d['operations'] if o['condition']==condition and o['role']==role),{})
                    writer.writerow(dict(task=d['task_id'],condition=labels[condition],output=label,official=a.get('official','missing'),additional_passed=a.get('passed'),additional_total=a.get('total'),additional_failed=a.get('failed'),timeouts=a.get('timeout'),unresolved=a.get('unresolved'),model_seconds=m.get('seconds'),prompt_tokens=m.get('prompt'),completion_tokens=m.get('completion'),total_tokens=m.get('tokens'),PM_change_detected=d['lineage'].get('caught'),clean_PM_restored=d['recovery'].get(condition,{}).get('clean_pm_verified'),issues='; '.join(d['issues']+a.get('issues',[]))))
    print('Saved:',output,'and matching .csv / .json files')

HTML=r'''<!doctype html><html><head><meta charset="utf-8"><title>Final multi-agent project comparison</title><style>
body{font:15px system-ui;background:#f4f7fb;color:#18324a;margin:24px}h1,h2{color:#123a60}table{border-collapse:collapse;background:white;width:100%;margin:16px 0}td,th{border:1px solid #d3deeb;padding:9px;text-align:left;vertical-align:top}th{background:#e5eff8;position:sticky;top:0}tr:nth-child(even){background:#f7faff}.scroll{overflow:auto;max-height:650px}.ok{color:#187348}.bad{color:#ae2635}.warn{color:#986100}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eaf0f5;padding:14px}details{background:white;padding:12px;margin:10px 0}button,input,select{padding:9px;margin:5px}small{color:#52687b}.add{color:#af2632}.del{color:#147146}
</style></head><body><h1>Multi-agent error propagation and recovery</h1>
<p>This report compares original baseline, PM injection, and four recovery modes on the same task IDs. It reads saved evidence; it does not run models or tests.</p>
<h2>Names and how to read the report</h2><ul>
<li><b>Original baseline Coder / Tester:</b> original clean pipeline outputs. Tester means the Test Engineer's reviewed final code, not the Docker evaluator.</li>
<li><b>PM injection Coder / Tester:</b> newly generated code and reviewed code after the Project Manager message was corrupted.</li>
<li><b>Recovery — remove faulty history (drop):</b> restore the original PM and omit old faulty history.</li>
<li><b>Recovery — keep faulty history (stale):</b> restore the PM but retain old faulty history.</li>
<li><b>Recovery — replace faulty history with withdrawal markers (retract):</b> restore the PM and replace faulty history entries with withdrawal markers.</li>
<li><b>Recovery — remove faulty history + retraction notice (both):</b> restore the PM, remove faulty history and add a withdrawal notice.</li></ul>
<p><b>Time:</b> model seconds are summed recorded model-call durations, not whole-study elapsed wall time. Baseline first three = Product Manager + Architect + Project Manager. Baseline last two = Coder + Tester. These two parts sum to the baseline five-stage total. PM injection and recovery incur only two new model calls per task. Five-stage comparison totals add the reused baseline first-three cost for context; these are not additional spending. Manual PM editing has no recorded model-call cost.</p>
<p><b>Tokens:</b> input, output and total tokens are shown separately. These are usage counts, not monetary charges. Missing measurements appear as “unknown”. Docker grading time is separate and only shown where recorded. Recovery wall time is generation/recovery time and excludes subsequent Docker evaluation.</p>
<p><b>Tests:</b> official is the entire official suite's result, not an individual-test count. Additional shows individual passed / total checks. Failed, timeout and unresolved are separate. Passing all recorded tests does not establish correctness on every possible input.</p>
<p><b>Lineage:</b> “PM change detected” verifies changed delivery on the source PM → Coder edge; it does not prove semantic error detection. Recovery restoration is verified separately by comparing restored PM text to baseline. The recovery runner did not save a fresh recovery call graph or test-content hashes; this report cannot reconstruct that missing evidence.</p>
<div id="notes"></div><h2>Overall test results</h2><div id="summary"></div><h2>Recorded time and tokens — whole selected study</h2><div id="costs"></div>
<h2>Recovery work and overhead — whole selected study</h2><div id="overheads"></div><h2>Task comparisons</h2><input id="search" placeholder="Search task or function"><select id="filter"><option value="all">All tasks</option><option value="broken">Baseline passes all; PM injection fails</option><option value="issues">Tasks with evidence notes</option></select><span id="count"></span><div class="scroll" id="overview"></div><h2>Task evidence, operations, tests and code</h2><div id="details"></div>
<script id="data" type="application/json">DATA_PAYLOAD</script><script>
const D=JSON.parse(document.getElementById('data').textContent),keys=Object.keys(D.labels);
const e=x=>String(x??'unknown').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const n=x=>x==null?'unknown':Number(x).toLocaleString(undefined,{maximumFractionDigits:3});
const table=(heads,rows)=>'<table><thead><tr>'+heads.map(x=>'<th>'+e(x)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+r.map(x=>'<td>'+x+'</td>').join('')+'</tr>').join('')+'</tbody></table>';
const badge=x=>'<b class="'+(x==='passed'?'ok':x==='failed'?'bad':'warn')+'">'+e(x??'missing')+'</b>';
const ap=a=>a.checks?.length&&a.checks.every(c=>c.status==='passed');
const fmt=a=>badge(a.official)+'<br>Additional '+n(a.passed)+' / '+n(a.total)+'<br>Failed '+n(a.failed)+'; timeout '+n(a.timeout)+'; unresolved '+n(a.unresolved);
const costnames={baseline_five:'Original baseline — all five agents',baseline_first_three:'Original baseline — first three agents',baseline_last_two:'Original baseline — Coder + Tester',injection_last_two:'PM injection — new Coder + Tester (latest attempts)',injection_all_attempts:'PM injection — new calls across all saved attempts',injection_five_comparison:'PM injection — five-stage comparison (includes reused work)'};
for(const k of keys)for(const role of ['coder','tester'])costnames[k+'_'+role]=D.labels[k]+' — '+(role==='coder'?'Coder':'Tester (reviewed code)');
for(const k of keys.slice(2)){costnames[k+'_last_two']=D.labels[k]+' — new Coder + Tester';costnames[k+'_five_comparison']=D.labels[k]+' — five-stage comparison (includes reused work)'}
const order=[...keys.flatMap(k=>[k+'_coder',k+'_tester']),'baseline_five','baseline_first_three','baseline_last_two','injection_last_two','injection_all_attempts',...keys.slice(2).map(k=>k+'_last_two'),'injection_five_comparison',...keys.slice(2).map(k=>k+'_five_comparison')];
function costTable(cost){return table(['Work measured','Model seconds','Input tokens','Output tokens','Total tokens'],order.filter(k=>cost[k]).map(k=>[e(costnames[k]),...['seconds','prompt','completion','tokens'].map(f=>n(cost[k][f]))]))}
document.getElementById('costs').innerHTML=costTable(D.totals);
document.getElementById('overheads').innerHTML=table(['Recovery mode','Recorded model calls','Recovery wall seconds (excludes Docker)','Model seconds','Dependency tracking seconds','Retained / restored / recomputed stages','Stages receiving old faulty content'],keys.slice(2).map(k=>{let r=D.recovery_totals[k];return [e(D.labels[k]),n(r.llm_calls),n(r.recovery_wall_seconds),n(r.model_seconds),n(r.tracking_overhead_seconds),[r.retained_stages,r.restored_stages,r.recomputed_stages].map(n).join(' / '),n(r.stages_with_poison_in_input)]}));
document.getElementById('summary').innerHTML=table(['Condition','Output','Official passed / selected','Official + every additional check passed / selected','Additional checks passed / total','Timeout / unresolved','Recovered injection-broken tasks (final code only)'],keys.flatMap(k=>['coder','tester'].map(role=>{let s=D.summary[k],a=s[role];return [e(D.labels[k]),role==='coder'?'Coder':'Tester (reviewed code)',a.official_pass+' / '+D.rows.length,a.all_pass+' / '+D.rows.length,a.additional_pass+' / '+a.additional_total,n(a.timeouts)+' / '+n(a.unresolved)+'; official unresolved '+n(a.official_unresolved),role==='tester'&& !['baseline','injection'].includes(k)?s.recovered+' / '+s.recovery_eligible+' eligible ('+s.recovery_evaluated+' evaluated)':'—']})));
document.getElementById('notes').innerHTML='<details><summary>Sources, completeness and accounting limits</summary><pre>'+e(JSON.stringify({injection:D.injection,recovery_sources:D.sources,warnings:D.warnings},null,2))+'</pre><p>Recovery costs cover successfully recorded current trace calls. Partial or failed calls may have consumed unrecorded time/tokens; these cannot be reconstructed. Baseline totals use the baseline attempts paired with the injection study; historical baseline retries are not included. Injection all-attempt totals cover saved trace calls, not unrecorded failed requests. Totals remain for the full study when filtering tasks.</p></details>';
function detail(d){let alltests=new Map();for(let k of keys)for(let role of ['coder','tester'])for(let c of d.conditions[k][role].checks||[])alltests.set(c.kind+': '+c.name,[c.kind,c.name]);
let cases=table(['Check',...keys.flatMap(k=>[D.labels[k]+' Coder',D.labels[k]+' Tester'])],[...alltests].map(([name,[kind,test]])=>[e(name),...keys.flatMap(k=>['coder','tester'].map(role=>{let c=(d.conditions[k][role].checks||[]).find(c=>c.kind===kind&&c.name===test);return badge(c?.status)+(c?'<details><summary>Recorded check details</summary><pre>'+e(JSON.stringify(c,null,2))+'</pre></details>':'')}))]));
let ops=table(['Condition','Agent','Model','Model seconds','Input tokens','Output tokens','Total tokens'],d.operations.map(o=>[e(D.labels[o.condition]),e(o.role==='test_engineer'?'Tester (reviewed code)':o.role),e(o.model),n(o.seconds),n(o.prompt),n(o.completion),n(o.tokens)]));
let testsummary=table(['Condition / output','Results','New additional failures / improvements vs baseline','New additional failures / improvements vs PM injection','Docker grading seconds','Evidence'],keys.flatMap(k=>['coder','tester'].map(role=>{let a=d.conditions[k][role];return[e(D.labels[k]+' '+role),fmt(a),n(a.vs_baseline?.new_failures)+' / '+n(a.vs_baseline?.improvements),n(a.vs_injection?.new_failures)+' / '+n(a.vs_injection?.improvements),n(a.docker_seconds),e(a.evidence)+'<br>'+e((a.issues||[]).join('; '))]})));
const diffHTML=s=>'<pre>'+String(s??'Missing').split('\n').map(line=>'<span class="'+(line.startsWith('-')?'del':line.startsWith('+')?'add':'')+'">'+e(line)+'</span>').join('\n')+'</pre>';
let code=keys.map(k=>'<details><summary>'+e(D.labels[k])+' — saved Coder / Tester code</summary>'+['coder','tester'].map(role=>'<h4>'+e(role)+'</h4><pre>'+e(d.conditions[k][role].code??'Missing')+'</pre><details><summary>Changes vs baseline (original green, changed red)</summary>'+diffHTML(d.conditions[k][role].diff_vs_baseline)+'</details><details><summary>Changes vs PM injection</summary>'+diffHTML(d.conditions[k][role].diff_vs_injection)+'</details>').join('')+'</details>').join('');
return '<details id="task-'+d.index+'"><summary>'+e(d.task_id+' — '+d.function)+' · PM change detected: '+e(d.lineage.caught)+'</summary><p>Injection attempt '+e(d.attempt)+' / '+e(d.attempt_count)+' saved attempts; execution '+e(d.execution)+'</p>'+testsummary+costTable(d.cost)+'<h3>Per-agent model-call metrics</h3>'+ops+'<h3>Lineage, restoration, recovery wall time and tracking overhead</h3><pre>'+e(JSON.stringify({source_lineage:d.lineage,recovery:d.recovery,evidence_notes:d.issues},null,2))+'</pre><h3>Every saved test outcome</h3><div class="scroll">'+cases+'</div><details><summary>Specification and original / corrupted PM messages</summary><h4>Specification</h4><pre>'+e(d.specification)+'</pre><h4 class="del">Original PM</h4><pre class="del">'+e(d.pm_original)+'</pre><h4 class="add">Corrupted PM</h4><pre class="add">'+e(d.pm_corrupted)+'</pre></details>'+code+'</details>'}
function render(){let query=document.getElementById('search').value.toLowerCase(),filter=document.getElementById('filter').value;let rr=D.rows.filter(d=>(d.task_id+' '+d.function).toLowerCase().includes(query)&&(filter!=='broken'||(ap(d.conditions.baseline.tester)&&!ap(d.conditions.injection.tester)))&&(filter!=='issues'||d.issues.length||keys.some(k=>['coder','tester'].some(r=>d.conditions[k][r].issues?.length))));document.getElementById('count').textContent=rr.length+' / '+D.rows.length+' tasks';document.getElementById('overview').innerHTML=table(['Task / function','PM change detected','Lineage comments',...keys.flatMap(k=>[D.labels[k]+' Coder',D.labels[k]+' Tester'])],rr.map(d=>['<a href="#task-'+d.index+'" onclick="document.getElementById(\'task-'+d.index+'\').open=true">'+e(d.task_id)+'<br>'+e(d.function)+'</a>',e(d.lineage.caught),e((d.lineage.comments||[]).join(' ')),...keys.flatMap(k=>['coder','tester'].map(r=>fmt(d.conditions[k][r])))]));document.getElementById('details').innerHTML=rr.map(detail).join('')}
document.getElementById('search').oninput=render;document.getElementById('filter').onchange=render;render();
</script></body></html>'''

if __name__=='__main__':
    full_main()
