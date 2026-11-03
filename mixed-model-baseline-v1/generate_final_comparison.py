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


def summarize(rows):
    valid = [r for r in rows if r['comparison_eligible']]
    summary = dict(selected=len(rows), eligible=len(valid), excluded=len(rows)-len(valid),
        completed=sum(r['execution']=='completed' for r in rows),
        pm_detected=sum(r.get('lineage',{}).get('caught')=='YES' for r in rows),
        lineage_other_tasks=sum(bool(r.get('lineage',{}).get('other')) for r in rows),
        raw_official_regressions=sum(r.get('raw_official_regression',False) for r in valid),
        final_official_regressions=sum(r.get('final_official_regression',False) for r in valid),
        official_recovered=sum(r.get('reviewer_official_recovered',False) for r in valid),
        official_persisted=sum(r.get('reviewer_official_persisted',False) for r in valid),
        baseline_raw_already_failed=sum(r.get('baseline_raw_failed',False) for r in valid),
        raw_additional_regressions=sum(r['raw_new_failures'] for r in valid),
        raw_additional_improvements=sum(r['raw_improvements'] for r in valid), artifacts={})
    for a in ARTIFACTS:
        summary['artifacts'][a] = dict(official_passed=sum(r['artifacts'][a]['official']=='passed' for r in valid),
            additional_passed=sum(r['artifacts'][a]['passed'] for r in valid),
            additional_total=sum(r['artifacts'][a]['total'] for r in valid))
    summary['before_five_stage'] = metric_total([metric_total_row(r, 'before_total') for r in valid])
    summary['after_composite_five_stage'] = metric_total([metric_total_row(r, 'after_composite_total') for r in valid])
    calls = [c for r in rows for a in r['prior_attempts'] for c in a['calls']]
    summary['missing_attempt_traces'] = sum(not a.get('trace_available', False) for r in rows for a in r['prior_attempts'])
    summary['actual_all_attempts'] = metric_total(calls)
    if summary['missing_attempt_traces']:
        summary['actual_all_attempts'] = dict(seconds=None,prompt=None,completion=None,tokens=None)
    summary['actual_new_call_count'] = len(calls)
    summary['new_calls_missing_tokens'] = sum(c['tokens'] is None for c in calls)
    summary['known_reported_tokens'] = sum(c['tokens'] for c in calls if c['tokens'] is not None)
    summary['known_recorded_seconds'] = sum(c['seconds'] for c in calls if c['seconds'] is not None)
    walls=[a.get('wall_seconds') if finite(a.get('wall_seconds')) else None for r in rows for a in r['prior_attempts']]
    summary['summed_attempt_wall_seconds'] = total(walls)
    return summary


def metric_total_row(row, key):
    return row.get(key) or dict(seconds=None, prompt=None, completion=None, tokens=None)


HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Final comparison — PM injection and error propagation</title>
<style>
:root{font-family:system-ui,sans-serif;color:#203247;background:#f3f6fa}body{margin:0}main{padding:25px;max-width:1900px;margin:auto}h1{margin:0;font-size:27px}h2{font-size:20px}h3{font-size:16px}.panel,details.task{background:#fff;border:1px solid #d9e3ed;border-radius:9px;padding:18px;margin:16px 0}.muted{color:#53677d;font-size:13px}.notice{border-left:4px solid #d8941e;background:#fff5df;padding:12px}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}.card{background:white;padding:15px;border:1px solid #d9e3ed;border-radius:8px}.big{font-size:28px;font-weight:750}.scroll{overflow:auto;max-height:75vh}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid #d9e3ed;padding:9px;text-align:left;vertical-align:top}thead th{background:#e6eff7;position:sticky;top:0;z-index:1}tbody tr:nth-child(even){background:#f8fafc}.main-table{min-width:2350px}a{color:#145d95}.badge{display:inline-block;font-size:12px;border-radius:4px;padding:3px 6px;font-weight:650;white-space:nowrap}.good{color:#166436;background:#e4f5e9}.bad{color:#9c2832;background:#ffe5e8}.warn{color:#80580e;background:#fff0c9}.neutral{color:#44596f;background:#eaf0f5}.toolbar{display:flex;gap:10px;flex-wrap:wrap;align-items:center}input,select,button{font:inherit;font-size:14px;border:1px solid #bacbdc;border-radius:5px;padding:8px;background:white}button{cursor:pointer}input{min-width:230px}pre{font:12px/1.5 ui-monospace,monospace;white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f7fa;padding:12px;max-height:450px;overflow:auto}code{font:12px ui-monospace,monospace;overflow-wrap:anywhere}.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}summary{cursor:pointer;font-weight:650}.task>summary{font-size:16px}.removed{color:#166436;background:#e4f5e9}.added{color:#9c2832;background:#ffe5e8}.stage-flow{padding:12px;background:#eef4fa;border-radius:6px;font-size:14px}.metric-cell{white-space:nowrap}.hash{max-width:220px;word-break:break-all}.comments{max-width:360px;min-width:220px}.help{max-width:1150px;line-height:1.6}.foot{font-size:12px;color:#53677d}details details{margin:12px 0;border-top:1px solid #e3eaf1;padding-top:12px}tr.hidden,details.hidden{display:none}.metric-table{min-width:1200px}@media(max-width:800px){main{padding:12px}.grid2{grid-template-columns:1fr}}@media print{.toolbar{display:none}.scroll{max-height:none;overflow:visible}body{background:white}.panel{break-inside:avoid}}
</style></head><body><main>
<h1>Final comparison: PM injection and error propagation</h1>
<p id="subtitle" class="muted"></p>
<div class="panel help"><div class="stage-flow">Reused Product Manager → Reused Architect → <strong>Substituted PM delivery</strong> → New Coder → New Test Engineer</div>
<p>The main table compares <strong>raw Coder outputs before review</strong>. Expand a task for reviewed final outcomes, all five agents' metrics, PM/code differences, individual tests and lineage evidence.</p>
<p class="notice"><strong>“PM detected” means a changed message was recorded on the PM → Coder edge.</strong> It does not mean lineage diagnosed a semantic error or prevented propagation. Passing available tests does not prove full correctness.</p>
<p><strong>Before:</strong> saved baseline latency/tokens for all five stages. <strong>After composite:</strong> baseline metrics for the three reused stages + the latest new Coder/Test Engineer metrics. <strong>Actual new replay:</strong> new calls only; no token or time charge is assigned again to reused stages. Model-call/stage latency sums are not elapsed wall-clock duration. Prompt and completion tokens are shown separately in each task.</p>
<p>Diff colors: original removed lines are green; replacement lines are red. These colors identify versions, not correctness.</p><p>Official suite outcomes and individual additional-case counts remain separate. Missing metrics are “—”, not zero. Latest attempts are selected; earlier successful attempts never replace a newer failed/incomplete attempt. Retries appear separately in actual replay cost. “Token cost” means token usage; no dollar or energy cost is estimated.</p></div>
<div id="cards" class="cards"></div>
<div class="panel"><h2>Aggregate test outcomes</h2><div id="aggregate"></div><p id="eligibility" class="muted"></p></div>
<div class="panel"><h2>Aggregate latency and tokens</h2><div id="costs"></div><p class="muted">Five-stage totals use reliable completed comparisons only. Actual new replay cost covers saved calls across all selected tasks and attempts, including failures. Attempt wall-time sums include Docker/orchestration and exclude pauses between attempts; they are not calendar duration.</p></div>
<div class="panel"><div class="toolbar"><input id="search" placeholder="Search task, function, outcome, comments"><select id="filter"><option value="all">All tasks</option><option value="regression">New raw-Coder official failures</option><option value="final">Final official regressions</option><option value="persistent">New official failures persisting</option><option value="recovered">New official failures reviewed to pass</option><option value="additional">New additional-case failures</option><option value="baseline">Baseline raw Coder already failed</option><option value="lineage">PM mismatch not confirmed / other lineage flags</option><option value="evidence">Missing/unverified evaluation evidence</option><option value="incomplete">Incomplete execution</option></select><button id="csv">Download visible rows as CSV</button><button id="expand">Expand visible task details</button><button id="collapse">Collapse task details</button></div><p id="shown" class="muted"></p>
<div class="scroll"><table class="main-table"><thead><tr><th>Task / function</th><th>Attempt / execution</th><th>Original raw Coder<br>additional passed / total</th><th>Failed</th><th>T / U</th><th>After PM injection<br>additional passed / total</th><th>Failed</th><th>T / U</th><th>Official<br>original / new</th><th>New additional<br>failures / improvements</th><th>Reviewed final<br>official original / new</th><th>Evidence</th><th>PM change detected<br>by lineage?</th><th>Lineage comments</th><th>Before 5-stage<br>seconds / tokens</th><th>After composite 5-stage<br>seconds / tokens</th><th>Actual new calls<br>latest seconds / tokens</th><th>Actual new calls<br>all attempts seconds / tokens</th></tr></thead><tbody id="main-rows"></tbody></table></div></div>
<h2>Per-task evidence and operation metrics</h2><div id="task-details"></div>
<div class="panel help"><h2>Definitions and limitations</h2><ul><li>A new test failure is baseline <code>passed</code> → attacked <code>failed</code>. Timeouts/unresolved checks are not silently counted as program failures.</li><li>Reviewer recovery here means a newly failed raw-Coder check passed on the reviewed final artifact. This is an observed test transition, not proof of a specific reasoning repair.</li><li>Lineage flags include mismatch, undeclared, captured and unverified edges. “Captured” is first-observed configuration evidence, not necessarily a fault.</li><li>Original messages can already contain defects; the baseline is a comparison condition, not an infallible oracle. Code differences and test transitions do not alone establish adoption of the intended injected rule.</li><li>HTML embeds all displayed messages/code/evidence, has no external assets, and never executes the candidate Python. Review before sharing: original prompts, code and local paths are included.</li><li>Some partial/interrupted requests may have consumed tokens or compute not recorded in saved files.</li></ul><details><summary>Study provenance / report inputs</summary><pre id="provenance"></pre></details></div>
<noscript>This offline report requires JavaScript enabled to display its embedded data.</noscript>
</main><script id="report-data" type="application/json">__REPORT_DATA__</script>
<script>
'use strict';
const D=JSON.parse(document.getElementById('report-data').textContent),rows=D.rows,S=D.summary;
const $=id=>document.getElementById(id),esc=x=>String(x??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=x=>x==null?'—':Number(x).toLocaleString('en-US',{maximumFractionDigits:0}),sec=x=>x==null?'—':Number(x).toLocaleString('en-US',{minimumFractionDigits:3,maximumFractionDigits:3});
const badge=x=>`<span class="badge ${['passed','verified','YES'].includes(x)?'good':['failed','NO','INCONSISTENT'].includes(x)?'bad':'warn'}">${esc(x||'missing')}</span>`;
const art=(r,a)=>r.artifacts[a]||{},metricCell=m=>`${sec(m?.seconds)} s<br>${num(m?.tokens)} tokens`;
const count=a=>a.total==null?'—':`<strong>${num(a.passed)} / ${num(a.total)}</strong>`;
const artNames={baseline_coder:'Original raw Coder',attacked_coder:'Raw Coder after PM injection',baseline_final:'Original reviewed final',attacked_final:'New reviewed final'};
const roleNames={product_manager:'Product Manager',architect:'Architect',project_manager:'Project Manager',coder:'Coder',test_engineer:'Test Engineer'};
$('subtitle').textContent=`Study: ${D.study_name} · Status: ${D.study_status} · Generated: ${D.generated_utc} · Offline report, no inference or tests rerun`;
const cards=[['Tasks completed',`${S.completed} / ${S.selected}`],['Reliable comparisons',`${S.eligible} / ${S.selected}`],['PM delivery mismatches confirmed',`${S.pm_detected} / ${S.selected}`],['New raw-Coder official failures',S.raw_official_regressions],['Final official regressions',S.final_official_regressions],['New official failures reviewed to pass',S.official_recovered],['New official failures persisting',S.official_persisted],['Tasks with other lineage flags',S.lineage_other_tasks]];
$('cards').innerHTML=cards.map(([a,b])=>`<div class="card"><div class="muted">${esc(a)}</div><div class="big">${esc(b)}</div></div>`).join('');
$('aggregate').innerHTML='<table><thead><tr><th>Artifact</th><th>Official passes / reliable tasks</th><th>Additional passed / total cases</th></tr></thead><tbody>'+Object.entries(S.artifacts).map(([a,v])=>`<tr><td>${artNames[a]}</td><td>${v.official_passed} / ${S.eligible}</td><td>${v.additional_passed} / ${v.additional_total}</td></tr>`).join('')+'</tbody></table>';
$('eligibility').textContent=`${S.excluded} selected tasks excluded from aggregate test comparisons because execution, checks, or evidence are incomplete/unverified. Individual rows remain visible. Additional-case raw regressions: ${S.raw_additional_regressions}; improvements: ${S.raw_additional_improvements}.`;
function costrow(label,m){return `<tr><td>${esc(label)}</td><td>${sec(m?.seconds)}</td><td>${num(m?.prompt)}</td><td>${num(m?.completion)}</td><td>${num(m?.tokens)}</td></tr>`}
$('costs').innerHTML='<table><thead><tr><th>Scope</th><th>Stage/call seconds</th><th>Prompt tokens</th><th>Completion tokens</th><th>Total tokens</th></tr></thead><tbody>'+costrow('Before: all five stages, reliable comparisons',S.before_five_stage)+costrow('After composite: reused three + new two, reliable comparisons',S.after_composite_five_stage)+costrow('Actual new replay: all saved tasks/attempts',S.actual_all_attempts)+'</tbody></table>'+`<p class="muted">Recorded new calls: ${S.actual_new_call_count}. Calls missing token counters: ${S.new_calls_missing_tokens}. Missing attempt trace files: ${S.missing_attempt_traces}. Known reported token subtotal: ${num(S.known_reported_tokens)}; known recorded call seconds: ${sec(S.known_recorded_seconds)}. Summed saved attempt wall time: ${sec(S.summed_attempt_wall_seconds)} s.</p>`;
function rowhtml(r){const b=art(r,'baseline_coder'),a=art(r,'attacked_coder'),bf=art(r,'baseline_final'),af=art(r,'attacked_final'),l=r.lineage||{};return `<tr data-index="${r.index}"><td><a href="#task-${r.index}" class="tasklink" data-index="${r.index}">${esc(r.task_id)}</a><br>${esc(r.entry_point)}</td><td>${esc(r.attempt)} / ${esc(r.attempt_count)} attempts<br>${esc(r.execution)}</td><td>${count(b)}</td><td>${num(b.failed)}</td><td>${num(b.timeout)} / ${num(b.unresolved)}</td><td>${count(a)}</td><td>${num(a.failed)}</td><td>${num(a.timeout)} / ${num(a.unresolved)}</td><td>${badge(b.official)}<br>${badge(a.official)}</td><td>${r.raw_new_failures} / ${r.raw_improvements}</td><td>${badge(bf.official)}<br>${badge(af.official)}</td><td>${badge(r.evaluation_verified?'YES':'UNKNOWN')}<br><span class="muted">${r.evaluation_verified?'Hash/check evidence verified':esc((r.evidence_issues||[]).join(' '))}</span></td><td>${badge(l.caught)}<br><span class="muted">Changed delivery</span></td><td class="comments">${esc((l.comments||[]).join(' '))}</td><td class="metric-cell">${metricCell(r.before_total)}</td><td class="metric-cell">${metricCell(r.after_composite_total)}</td><td class="metric-cell">${metricCell(r.new_latest_total)}</td><td class="metric-cell">${metricCell(r.new_all_attempts_total)}</td></tr>`}
$('main-rows').innerHTML=rows.map(rowhtml).join('');
function diffhtml(text){return String(text||'No data').split('\n').map(l=>`<span class="${l.startsWith('-')&&!l.startsWith('---')?'removed':l.startsWith('+')&&!l.startsWith('+++')?'added':''}">${esc(l)}</span>`).join('\n')}
function metricTable(r){return '<div class="scroll"><table class="metric-table"><thead><tr><th rowspan="2">Operation / model</th><th rowspan="2">After execution</th><th colspan="4">Before — saved baseline</th><th colspan="4">After — reused or newly executed</th></tr><tr>'+['Seconds','Prompt tokens','Completion tokens','Total tokens','Seconds','Prompt tokens','Completion tokens','Total tokens'].map(x=>`<th>${x}</th>`).join('')+'</tr></thead><tbody>'+r.metrics.map(m=>`<tr><td>${roleNames[m.role]}<br><span class="muted">${esc(m.before.model)} → ${esc(m.after.model)}</span></td><td>${esc(m.execution)}${m.execution==='reused'?'<br><span class="muted">No new call charged</span>':''}</td><td>${sec(m.before.seconds)}</td><td>${num(m.before.prompt)}</td><td>${num(m.before.completion)}</td><td>${num(m.before.tokens)}</td><td>${sec(m.after.seconds)}</td><td>${num(m.after.prompt)}</td><td>${num(m.after.completion)}</td><td>${num(m.after.tokens)}</td></tr>`).join('')+'</tbody></table></div><table><thead><tr><th>Complete-example scope</th><th>Seconds</th><th>Prompt tokens</th><th>Completion tokens</th><th>Total tokens</th></tr></thead><tbody>'+costrow('Before: all five stages',r.before_total)+costrow('After composite: reused three + new two',r.after_composite_total)+costrow('Actual new roles: latest attempt',r.new_latest_total)+costrow('Actual recorded calls: all attempts',r.new_all_attempts_total)+'</tbody></table>'+`<p class="muted">Composite change: ${sec(r.composite_delta?.seconds)} s / ${num(r.composite_delta?.tokens)} tokens. Latest attempt elapsed wall time (including Docker/orchestration): ${sec(r.latest_attempt_wall_seconds)} s.</p>`}
function detailhtml(r){const l=r.lineage||{};return `<details class="task" id="task-${r.index}" data-index="${r.index}"><summary>${esc(r.task_id)} · ${esc(r.entry_point)} · ${esc(r.outcome||r.execution)} · PM detected: ${esc(l.caught||'UNKNOWN')}</summary><p class="muted">Selected ${esc(r.folder)}. Source baseline: ${esc(r.source?.baseline_folder)}. ${esc(r.generation_error||'')}</p>${[...(r.issues||[]),...(r.evidence_issues||[])].length?'<div class="notice">'+esc([...(r.issues||[]),...(r.evidence_issues||[])].join(' '))+'</div>':''}<h3>Five-agent latency and token accounting</h3>${metricTable(r)}<h3>All artifact outcomes</h3><table><thead><tr><th>Artifact</th><th>Official suite</th><th>Additional passed / total</th><th>Failed</th><th>Timeout / unresolved</th><th>Saved Docker seconds</th></tr></thead><tbody>${Object.entries(artNames).map(([a,name])=>{const v=art(r,a);return `<tr><td>${name}</td><td>${badge(v.official)}</td><td>${count(v)}</td><td>${num(v.failed)}</td><td>${num(v.timeout)} / ${num(v.unresolved)}</td><td>${sec(v.docker_seconds)}${a.startsWith('baseline')?' (historical)':''}</td></tr>`}).join('')}</tbody></table><p class="muted">New additional raw-Coder failures: ${r.raw_new_failures}; subsequently passing final checks: ${r.new_failures_recovered}; still failing final checks: ${r.new_failures_persisted}. Remaining cases may be unresolved.</p><details><summary>PM change detection and full lineage edges</summary><p>${esc((l.comments||[]).join(' '))}</p><pre>${esc(JSON.stringify({baseline_pm_edge:l.baseline_pm_edge,new_pm_edge:l.pm_edge,baseline_edge_counts:l.baseline_edge_counts,new_edge_counts:l.edge_counts,checks:l.pm_checks,issues:l.issues},null,2))}</pre><div class="scroll"><table><thead><tr><th>Producer → consumer</th><th>Field</th><th>Status</th><th>In prompt?</th><th>Original hash</th><th>Received hash</th><th>Other evidence</th></tr></thead><tbody>${(l.edges||[]).map(e=>`<tr><td>${esc(e.source)} → ${esc(e.target)}</td><td>${esc(e.via)}</td><td>${badge(e.status)}</td><td>${esc(e.in_prompt)}</td><td class="hash"><code>${esc(e.sent_sha256)}</code></td><td class="hash"><code>${esc(e.received_sha256)}</code></td><td>${esc(e.weak?'weak':'')} ${esc(e.ambiguous_with?.join(', '))}</td></tr>`).join('')}</tbody></table></div></details><details><summary>Original specification</summary><pre>${esc(r.specification)}</pre></details><details><summary>Original / corrupted PM messages and diff</summary><div class="grid2"><div><h3>Original PM output</h3><pre>${esc(r.contents.project_manager_before)}</pre></div><div><h3>Delivered corrupted PM output</h3><pre>${esc(r.contents.project_manager_after)}</pre></div></div><pre>${diffhtml(r.pm_diff)}</pre></details><details><summary>Original / new raw Coder code and diff</summary><div class="grid2"><div><h3>Original raw Coder</h3><pre>${esc(r.contents.baseline_coder_code)}</pre></div><div><h3>Raw Coder after PM injection</h3><pre>${esc(r.contents.attacked_coder_code)}</pre></div></div><pre>${diffhtml(r.coder_diff)}</pre></details><details><summary>Reviewer changes and baseline/new final comparison</summary><div class="grid2"><div><h3>Original reviewed final</h3><pre>${esc(r.contents.baseline_final_code)}</pre></div><div><h3>New reviewed final</h3><pre>${esc(r.contents.attacked_final_code)}</pre></div></div><h3>New Coder → new reviewed final</h3><pre>${diffhtml(r.review_diff)}</pre><h3>Baseline final → new final</h3><pre>${diffhtml(r.final_diff)}</pre></details><details><summary>Individual official/additional checks, errors and actual results</summary><div class="scroll"><table><thead><tr><th>Check</th>${Object.values(artNames).map(x=>`<th>${x}</th>`).join('')}<th>Raw transition</th><th>After review</th></tr></thead><tbody>${r.checks.map(c=>`<tr><td>${esc(c.kind)}: ${esc(c.name)}</td>${Object.keys(artNames).map(a=>{const e=c.details[a]||{};return `<td>${badge(c.outcomes[a])}<br><span class="muted">${esc(e.error||e.reason||'')}${e.actual_repr!=null?'<br>Actual: '+esc(e.actual_repr):''}${e.expected_literal!=null?'<br>Expected: '+esc(e.expected_literal):''}</span></td>`}).join('')}<td>${c.new_raw_failure?'New failure':c.raw_improved?'Improved':'—'}</td><td>${c.new_failure_review_recovered?'New failure now passes':c.new_failure_persisted?'New failure persists':'—'}</td></tr>`).join('')}</tbody></table></div></details><details><summary>All five saved agent messages</summary>${Object.entries(roleNames).map(([role,name])=>`<details><summary>${name} (${role==='project_manager'?'substituted delivery':role==='coder'||role==='test_engineer'?'rerun':'reused'})</summary><div class="grid2"><pre>${esc(r.contents[role+'_before'])}</pre><pre>${esc(r.contents[role+'_after'])}</pre></div></details>`).join('')}</details><details><summary>Attempt history / new call cost / model settings</summary><pre>${esc(JSON.stringify({attempts:r.prior_attempts,role_model_configs:r.model_configs,source:r.source},null,2))}</pre></details></details>`}
$('task-details').innerHTML=rows.map(detailhtml).join('');
$('provenance').textContent=JSON.stringify(D.provenance,null,2);
let visible=rows;
function apply(){const q=$('search').value.toLowerCase(),f=$('filter').value;visible=rows.filter(r=>{const text=[r.task_id,r.entry_point,r.execution,r.outcome,...(r.lineage?.comments||[])].join(' ').toLowerCase();if(!text.includes(q))return false;switch(f){case'regression':return r.raw_official_regression;case'final':return r.final_official_regression;case'persistent':return r.reviewer_official_persisted;case'recovered':return r.reviewer_official_recovered;case'additional':return r.raw_new_failures>0;case'baseline':return r.baseline_raw_failed;case'lineage':return r.lineage?.caught!=='YES'||r.lineage?.other?.length>0;case'evidence':return !r.evaluation_verified;case'incomplete':return r.execution!=='completed';default:return true}});const ids=new Set(visible.map(r=>String(r.index)));document.querySelectorAll('tr[data-index],details.task').forEach(e=>e.classList.toggle('hidden',!ids.has(e.dataset.index)));$('shown').textContent=`Showing ${visible.length} / ${rows.length} tasks. Dashboard totals remain for the whole study.`}
$('search').addEventListener('input',apply);$('filter').addEventListener('change',apply);apply();
document.addEventListener('click',e=>{const a=e.target.closest('.tasklink');if(a){const d=$('task-'+a.dataset.index);d.open=true}});
$('expand').onclick=()=>visible.forEach(r=>$('task-'+r.index).open=true);$('collapse').onclick=()=>document.querySelectorAll('details.task').forEach(e=>e.open=false);
$('csv').onclick=()=>{const headers=['task','attempt','execution','original_raw_official','new_raw_official','original_final_official','new_final_official','new_additional_failures','additional_improvements','pm_change_detected','lineage_comments','before_five_stage_seconds','before_five_stage_tokens','after_composite_seconds','after_composite_tokens','actual_new_latest_seconds','actual_new_latest_tokens','actual_new_all_attempts_seconds','actual_new_all_attempts_tokens','evaluation_verified'];const quote=x=>{let t=String(x??'');if(typeof x==='string'&&/^[=+@\-\t\r]/.test(t))t="'"+t;return '"'+t.replace(/"/g,'""')+'"'};const cells=visible.map(r=>[r.task_id,r.attempt,r.execution,art(r,'baseline_coder').official,art(r,'attacked_coder').official,art(r,'baseline_final').official,art(r,'attacked_final').official,r.raw_new_failures,r.raw_improvements,r.lineage?.caught,r.lineage?.comments?.join(' '),r.before_total?.seconds,r.before_total?.tokens,r.after_composite_total?.seconds,r.after_composite_total?.tokens,r.new_latest_total?.seconds,r.new_latest_total?.tokens,r.new_all_attempts_total?.seconds,r.new_all_attempts_total?.tokens,r.evaluation_verified]);const blob=new Blob(['\ufeff'+[headers,...cells].map(row=>row.map(quote).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'});const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='final_comparison.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
</script></body></html>'''


def build_report(study, root, output):
    state = read_json(study/'study.json')
    if state.get('schema_version') != 'mixed-pm-replay-study/v1':
        raise ValueError('Expected a run_pm_replay.py study (mixed-pm-replay-study/v1).')
    indices = state['indices']
    if not all(isinstance(i,int) and not isinstance(i,bool) and i>=0 for i in indices) or len(set(indices)) != len(indices):
        raise ValueError('Invalid/duplicate task indices in checkpoint.')
    rows=[]
    for i in indices:
        try:
            rows.append(load_row(study, state, i, root))
        except (ValueError, OSError, KeyError, TypeError) as exc:
            rows.append(dict(index=i,task_id=f'HumanEval/{i}',entry_point='unknown',attempt=None,
                attempt_count=len(state.get('tasks',{}).get(f'HumanEval/{i}',[])),execution='report_evidence_error',
                folder=None,issues=[f'{type(exc).__name__}: {exc}'],evidence_issues=['Evidence could not be parsed.'],
                artifacts={},checks=[],metrics=[],contents={},lineage={},prior_attempts=[],evaluation_verified=False,
                comparison_eligible=False,raw_new_failures=0,raw_improvements=0,new_failures_recovered=0,new_failures_persisted=0))
    inputs = {str((study/'study.json').resolve()):digest((study/'study.json').read_bytes())}
    for row in rows:
        if row.get('folder'):
            for name in ['trace.json','baseline_trace.json','evaluation.json','baseline_evaluation.json',
                         'lineage.json','baseline_lineage.json','coder_input.json']:
                p=study/row['folder']/name
                if p.is_file():inputs[str(p.relative_to(study))]=digest(p.read_bytes())
    data=dict(study_name=study.name,study_status=state.get('status'),generated_utc=datetime.now(timezone.utc).isoformat(),
              rows=rows,summary=summarize(rows),provenance=dict(study=str(study.resolve()),root=str(root.resolve()),
                baseline=state.get('baseline'),injections=state.get('injections'),generator_sha256=digest(Path(__file__).read_bytes()),
                source_input_hashes=inputs,selection='Latest attempt only for outcomes; all saved attempts for actual replay cost.',
                model_calls_performed=0,tests_executed=False,baseline_metrics_reused=True))
    payload=json.dumps(data,ensure_ascii=False,allow_nan=False).replace('&','\\u0026').replace('<','\\u003c').replace('>','\\u003e').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    output.parent.mkdir(parents=True,exist_ok=True)
    temporary=output.with_suffix(output.suffix+'.tmp')
    temporary.write_text(HTML.replace('__REPORT_DATA__',payload),encoding='utf-8')
    temporary.replace(output)
    return data


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('study',type=Path,help='Completed or partial runs/pm-replay-TIMESTAMP folder')
    parser.add_argument('--root',type=Path,default=ROOT,help='Project folder containing existing tests/ and data/')
    parser.add_argument('--output',type=Path,help='Default: PROJECT/runs/final_comparison.html')
    args=parser.parse_args();output=(args.output or args.root/'runs/final_comparison.html').resolve()
    if output.suffix.lower()!='.html':parser.error('--output must end with .html')
    data=build_report(args.study.resolve(),args.root.resolve(),output)
    s=data['summary']
    print('Report:',output)
    print(f"Tasks: {s['selected']} | reliable comparisons: {s['eligible']} | PM delivery mismatches confirmed: {s['pm_detected']}")
    print('No models or Docker checks were run. Unknown/missing evidence is flagged in the report.')


if __name__=='__main__':
    main()
