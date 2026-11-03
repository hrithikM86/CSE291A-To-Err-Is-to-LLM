"""Replay saved PM message interventions: two new role calls per task.

Place beside run_baseline.py. Baseline files, prompts, lineage.py and tests
are never edited. Generated Python is evaluated only by the Docker checker.
"""
import argparse
import ast
import asyncio
import copy
from datetime import datetime, timezone
import difflib
import fcntl
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import shutil
import subprocess
import time
import traceback

import run_baseline as base
from lineage import CallRecorder, instructions_text, model_settings_text, payload_routes
from role_lineage import RoleModelGraph
from runtime_utils import close_model_clients, model_identity, save

ROOT = Path(__file__).resolve().parent
ROLES = base.ROLES
NEW_ROLES = ('coder', 'test_engineer')
SCHEMA = 'mixed-pm-replay-study/v1'


def text_sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def inside(root, relative):
    """Resolve input paths without allowing a manifest to escape its root."""
    root = root.resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f'Path escapes its root: {relative}')
    return path


def source_folder(baseline, entry):
    parts = Path(entry['source_folder']).parts
    if len(parts) != 3 or parts[0] != 'tasks':
        raise ValueError('Unsupported source_folder; expected tasks/task-NNN/attempt-N.')
    return inside(baseline, Path(*parts[1:]))


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def require_equal(actual, expected, description):
    if actual != expected:
        raise ValueError(f'{description} differs from the supplied baseline/intervention.')


def load_interventions(path):
    manifest = read_json(path / 'manifest.json')
    require_equal(manifest.get('schema_version'), 'pm-message-interventions/v1', 'Manifest schema')
    entries = {e['task_id']: e for e in manifest['tasks']}
    if len(entries) != len(manifest['tasks']):
        raise ValueError('Duplicate task IDs in the intervention manifest.')
    return manifest, entries


def validate_task(baseline, package, entry, item):
    """Read-only integrity checks; no model imports, inference, or code execution."""
    src = source_folder(baseline, entry)
    require_equal(entry['task_id'], item['task_id'], 'Task ID')
    require_equal(entry['entry_point'], item['entry_point'], 'Entry point')
    require_equal(base.sha(src / 'trace.json'), entry['source_trace_sha256'], 'Baseline trace hash')
    require_equal(base.sha(src / 'lineage.json'), entry['source_lineage_sha256'], 'Baseline lineage hash')
    trace = read_json(src / 'trace.json')
    require_equal(trace['task_id'], item['task_id'], 'Baseline trace task')
    require_equal(trace['specification'], item['prompt'], 'Original specification')
    require_equal(text_sha(item['prompt']), entry['specification_sha256'], 'Specification hash')
    require_equal(trace['status'], 'completed', 'Baseline generation status')
    require_equal([s['stage'] for s in trace['stages']], list(ROLES), 'Baseline role order')
    for j, stage in enumerate(trace['stages']):
        role = stage['stage']
        text = (src / f'{role}.txt').read_text(encoding='utf-8')
        require_equal(stage['status'], 'completed', f'{role} status')
        require_equal(stage['original_output'], text, f'{role} saved output')
        require_equal(stage['delivered_output'], text, f'{role} original delivery')
        require_equal(stage['input']['original_specification'], item['prompt'], f'{role} specification')
        if j:
            require_equal(stage['input']['previous_artifact'], trace['stages'][j-1]['delivered_output'],
                          f'{role} original handoff')
    for key in ('original_pm', 'corrupted_pm', 'coder_payload'):
        artifact = entry[key]
        require_equal(base.sha(inside(package, artifact['file'])), artifact['sha256'], f'{key} hash')
    for role, record in entry['upstream'].items():
        require_equal(base.sha(inside(package, record['file'])), record['sha256'], f'{role} package hash')
        require_equal((src / f'{role}.txt').read_bytes(), inside(package, record['file']).read_bytes(),
                      f'{role} unchanged upstream copy')
    original = inside(package, entry['original_pm']['file']).read_bytes()
    require_equal(original, (src / 'project_manager.txt').read_bytes(), 'Original PM bytes')
    changed = inside(package, entry['corrupted_pm']['file']).read_text(encoding='utf-8')
    if changed == original.decode('utf-8'):
        raise ValueError('PM replacement is unchanged.')
    baseline_input = read_json(src / 'coder_input.json')
    require_equal(base.sha(src / 'coder_input.json'), entry['source_coder_input_sha256'], 'Coder input hash')
    expected = copy.deepcopy(baseline_input['payload'])
    expected['previous_artifact'] = changed
    require_equal(read_json(inside(package, entry['coder_payload']['file'])), expected, 'Prepared Coder payload')
    tests = entry['existing_tests']
    require_equal(base.sha(ROOT / 'data/HumanEval.jsonl'), tests['official_dataset_sha256'], 'Dataset hash')
    require_equal(base.sha(inside(ROOT, tests['additional_file'])), tests['sha256'], 'Additional-test hash')
    evaluation = read_json(src / 'evaluation.json')
    require_equal(evaluation['task_id'], item['task_id'], 'Evaluation task')
    require_equal(evaluation['tests_sha256'], tests['sha256'], 'Baseline graded test version')
    suite = read_json(inside(ROOT, tests['additional_file']))
    required_checks = {(c['name'], 'additional') for c in suite['cases']} | {('official_humaneval', 'official')}
    for artifact, filename in [('baseline_coder', 'coder.py'), ('baseline_final', 'final.py')]:
        result = evaluation['artifacts'][artifact]
        require_equal(result['code_sha256'], base.sha(src / filename), f'{artifact} graded code hash')
        require_equal({(c['name'], c['kind']) for c in result['checks']}, required_checks,
                      f'{artifact} check coverage')
        if not all(c['status'] in ('passed', 'failed') for c in result['checks']):
            raise ValueError(f'Baseline {artifact} has unresolved checks; resolve baseline evaluation first.')
    return src, trace, changed


def fingerprint(baseline, package, entries, items, indices, config_path, configs=None, image=None):
    """Pin all experiment-affecting inputs across resume; no historical file edits."""
    baseline_state = read_json(baseline / 'study.json')
    current = {}
    for name in ['run_baseline.py', 'lineage.py', 'role_lineage.py', 'metagpt_clean.py',
                 'runtime_utils.py', 'check_suites.py', 'evaluate_humaneval.py', 'data/HumanEval.jsonl']:
        current[name] = base.sha(ROOT / name)
        require_equal(current[name], baseline_state['snapshot']['files'][name], f'Baseline dependency {name}')
    current[Path(__file__).name] = base.sha(Path(__file__))
    sources = {}
    for i in indices:
        entry = entries[items[i]['task_id']]
        src, trace, _ = validate_task(baseline, package, entry, items[i])
        for name in ['trace.json', 'lineage.json', 'evaluation.json', 'coder.py', 'final.py'] + [
                f'{r}{suffix}' for r in ROLES for suffix in ['.txt', '_input.json']]:
            sources[str((src / name).relative_to(baseline))] = base.sha(src / name)
        require_equal(trace['role_model_configs'], baseline_state['snapshot']['role_model_configs'],
                      'Source task role configurations')
        if image is not None:
            require_equal(read_json(src / 'evaluation.json')['image_id'], image, 'Baseline Docker image')
    snapshot = dict(files=current, source_files=sources,
                    baseline_study_sha256=base.sha(baseline / 'study.json'),
                    intervention_manifest_sha256=base.sha(package / 'manifest.json'),
                    config_sha256=base.sha(config_path), image_id=image)
    if configs is not None:
        role_settings = {r: base.settings(c) for r, c in configs.items()}
        require_equal(role_settings, baseline_state['snapshot']['role_model_configs'], 'Per-role settings')
        models = {c.llm.model: model_identity(base.settings(c)) for c in configs.values()}
        for name, identity in models.items():
            require_equal(identity['digest'], baseline_state['snapshot']['models'][name]['digest'],
                          f'Ollama model digest for {name}')
        packages = {p: version(p) for p in baseline_state['snapshot']['packages']}
        require_equal(packages, baseline_state['snapshot']['packages'], 'Python package versions')
        require_equal(image, baseline_state['snapshot']['image_id'], 'Docker image ID')
        snapshot.update(role_model_configs=role_settings, models=models, packages=packages)
    return snapshot


def restore_upstream_graph(source_trace, source_graph):
    """Keep actual upstream call evidence; altered delivery becomes a mismatch edge."""
    upstream = set(ROLES[:3])
    cutoff = max(n['seq'] for n in source_graph['nodes'] if n.get('role') in upstream)
    kept = copy.deepcopy([n for n in source_graph['nodes'] if n['seq'] <= cutoff])
    if any(n.get('role') in NEW_ROLES for n in kept):
        raise ValueError('Unexpected source call order before PM; refusing to invent upstream lineage.')
    for node in kept:
        node['execution'] = 'reused'
    graph = RoleModelGraph.from_json(dict(schema=source_graph['schema'], nodes=kept))
    texts = {'specification': source_trace['specification']}
    for role in ROLES:
        texts[f'model_config:{role}'] = model_settings_text(source_trace['role_model_configs'][role])
    for stage in source_trace['stages'][:3]:
        role = stage['stage']
        texts[f'instructions:{role}'] = instructions_text([stage['role_prefix'], stage['guidance']])
        texts[graph.resolve(role)] = stage['original_output']
    # from_json restores identities and routing; hydrate exact text for verification
    # and undeclared-input checks, without editing Khushi's recorder or graph code.
    for node_id, text in texts.items():
        if node_id in graph.nodes:
            require_equal(graph.nodes[node_id]['output_sha256'], text_sha(text), f'{node_id} lineage text')
            graph._store_output(node_id, text)
    return graph


def write_diff(path, before, after, left, right):
    text = '\n'.join(difflib.unified_diff(before.splitlines(), after.splitlines(),
                                         fromfile=left, tofile=right, lineterm=''))
    path.write_text(text + ('\n' if text else ''), encoding='utf-8')


async def generate_replay(configs, item, entry, baseline, package, out, runtime):
    src, original_trace, changed = validate_task(baseline, package, entry, item)
    graph = restore_upstream_graph(original_trace, read_json(src / 'lineage.json'))
    trace = dict(schema_version='mixed-pm-replay/v1', experiment='manual_pm_message_replay',
                 condition='pm_message_injection', task_id=item['task_id'], entry_point=item['entry_point'],
                 specification=item['prompt'], dataset_sha256=original_trace['dataset_sha256'],
                 model_config=copy.deepcopy(original_trace['model_config']),
                 role_model_configs={r: base.settings(c) for r, c in configs.items()},
                 status='running', stages=[], new_inference=[], evaluation_file='evaluation.json',
                 generated_code_executed_by_agents=False,
                 baseline_source=str(src), source_trace_sha256=base.sha(src / 'trace.json'),
                 source_lineage_sha256=base.sha(src / 'lineage.json'),
                 intervention=dict(target='project_manager', kind='message_substitution',
                    source='assistant_authored_pm_package', original_sha256=entry['original_pm']['sha256'],
                    delivered_sha256=entry['corrupted_pm']['sha256'], fault_adoption='not_evaluated'))
    for name in ['trace.json', 'lineage.json', 'evaluation.json']:
        shutil.copy2(src / name, out / ('baseline_' + name))
    for role in ROLES[:3]:
        shutil.copy2(src / f'{role}.txt', out / f'{role}.txt')
        shutil.copy2(src / f'{role}_input.json', out / f'{role}_input.json')
        stage = copy.deepcopy(next(s for s in original_trace['stages'] if s['stage'] == role))
        stage.update(execution='reused', generation_reused=True, source_folder=str(src))
        if role == 'project_manager':
            shutil.copy2(src / f'{role}.txt', out / 'project_manager_original.txt')
            (out / 'project_manager_corrupted.txt').write_text(changed, encoding='utf-8')
            (out / 'project_manager.txt').write_text(changed, encoding='utf-8')
            stage.update(execution='reused_with_message_substitution', delivered_output=changed)
        trace['stages'].append(stage)
    for role, name in [('baseline_coder', 'coder.py'), ('baseline_final', 'final.py')]:
        shutil.copy2(src / name, out / f'{role}.py')
    write_diff(out / 'pm_injection.diff', entry_text(package, entry, 'original_pm'), changed,
               'project_manager_original.txt', 'project_manager_corrupted.txt')
    payload = read_json(inside(package, entry['coder_payload']['file']))
    recorder = CallRecorder(graph)
    started = time.perf_counter()
    base.save_trace(out, trace, graph)
    try:
        with recorder.recording(**runtime.get('recording', {})):
            for name, title, guidance in runtime['specs']:
                if name not in NEW_ROLES:
                    continue
                config = configs[name]
                action = runtime['Action'](guidance=guidance, config=config)
                initial_provider = action.llm
                role = runtime['Role'](name=name, profile=title,
                    goal='Produce a correct solution to the supplied function specification.',
                    actions=[action], config=config)
                instructions = [role.actions[0].prefix, guidance]
                stage = dict(stage=name, depends_on=['specification', payload['previous_stage']],
                    guidance=guidance, role_prefix=role.actions[0].prefix, input=copy.deepcopy(payload),
                    model_config=base.settings(config), status='running', execution='rerun', generation_reused=False)
                trace['stages'].append(stage)
                stage_started = time.perf_counter()
                before = None
                first_node = len(graph.nodes)
                try:
                    require_equal(instructions, read_json(src / f'{name}_input.json')['system_messages'],
                                  f'{name} original system instructions')
                    graph.add_source(f'instructions:{name}', instructions_text(instructions), kind='configuration')
                    save(out / f'{name}_input.json', dict(payload=payload, system_messages=instructions,
                                                         model_config=base.settings(config)))
                    base.save_trace(out, trace, graph)
                    before = action.llm.get_costs()
                    first_node = len(graph.nodes)
                    print(f'Running {name}: {config.llm.model}', flush=True)
                    with graph.model_scope(name), recorder.routing(payload_routes(stage['depends_on'], payload)):
                        response = await role.run(json.dumps(payload))
                    if response is None or not response.content.strip():
                        raise RuntimeError('Role returned no usable output.')
                    text = response.content
                    stage.update(status='completed', original_output=text, delivered_output=text)
                    (out / f'{name}.txt').write_text(text, encoding='utf-8')
                    print(text, flush=True)
                    code = runtime['unwrap'](text)
                    filename = 'coder_after_pm_injection.py' if name == 'coder' else 'final.py'
                    (out / filename).write_text(code, encoding='utf-8')
                    try:
                        tree = ast.parse(code)
                        stage['syntax_check'] = 'passed'
                        stage['entry_point_found'] = any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                            and n.name == item['entry_point'] for n in tree.body)
                    except SyntaxError as exc:
                        stage.update(syntax_check='failed', syntax_error=str(exc))
                    payload = dict(original_specification=item['prompt'], previous_stage=name, previous_artifact=text)
                except BaseException as exc:
                    stage.update(status='error', error=f'{type(exc).__name__}: {exc}')
                    raise
                finally:
                    stage['elapsed_seconds'] = round(time.perf_counter() - stage_started, 3)
                    stage['token_usage_available'] = False
                    if before is not None:
                        after = action.llm.get_costs()
                        stage['reported_prompt_tokens'] = after.total_prompt_tokens - before.total_prompt_tokens
                        stage['reported_completion_tokens'] = after.total_completion_tokens - before.total_completion_tokens
                        stage['reported_total_tokens'] = stage['reported_prompt_tokens'] + stage['reported_completion_tokens']
                        stage['token_usage_available'] = stage['reported_total_tokens'] > 0
                    stage['model_call_recorded'] = any(n.get('kind') == 'model_call' and n.get('role') == name
                        for n in list(graph.nodes.values())[first_node:])
                    if stage['model_call_recorded']:
                        trace['new_inference'].append(dict(model=config.llm.model, **{k:stage.get(k) for k in [
                        'stage', 'status', 'elapsed_seconds', 'reported_prompt_tokens',
                        'reported_completion_tokens', 'reported_total_tokens', 'token_usage_available']}))
                    for node in list(graph.nodes.values())[first_node:]:
                        node['trace_stage'] = len(trace['stages']) - 1
                        node['execution'] = 'rerun'
                    try:
                        base.save_trace(out, trace, graph)
                    finally:
                        await close_model_clients([initial_provider, action.llm, role.llm])
        trace['status'] = 'completed'
    except BaseException as exc:
        trace.update(status='error', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        trace['new_generation_wall_seconds'] = round(time.perf_counter() - started, 3)
        base.save_trace(out, trace, graph)
    return trace


def entry_text(package, entry, key):
    return inside(package, entry[key]['file']).read_text(encoding='utf-8')


def transition(before, after):
    if before not in ('passed', 'failed') or after not in ('passed', 'failed'):
        return 'UNRESOLVED'
    if before != 'passed':
        return 'NOT_ELIGIBLE'
    return 'YES' if after == 'failed' else 'NO'


def reports(folder, state):
    # Reuse the baseline's reporting mechanics: only new_inference contributes
    # model-call time and tokens, so reused generations are not charged again.
    base.reports(folder, state)
    call_rows = []
    for task_id, attempts in state['tasks'].items():
        for attempt in attempts:
            path = folder / attempt['folder'] / 'trace.json'
            if path.is_file():
                call_rows.extend(dict(task_id=task_id, attempt=attempt['attempt'], **call)
                    for call in read_json(path).get('new_inference', []))
    base.write_csv(folder / 'calls.csv', call_rows, ['task_id', 'attempt', 'stage', 'model', 'status',
        'elapsed_seconds', 'reported_prompt_tokens', 'reported_completion_tokens',
        'reported_total_tokens', 'token_usage_available'])
    rows, paired_checks = [], []
    for task_id, attempts in state['tasks'].items():
        if not attempts:
            continue
        latest = attempts[-1]
        out = folder / latest['folder']
        path = out / 'evaluation.json'
        row = dict(task_id=task_id, attempt=latest['attempt'], execution=latest['status'])
        if path.is_file():
            ev = read_json(path)
            artifacts = ev.get('artifacts', {})
            for name, value in artifacts.items():
                row[name + '_official'] = value['official_status']
                row[name + '_additional_total'] = value['additional_total']
                for status, count in value['additional_counts'].items():
                    row[name + '_additional_' + status] = count
            pairs = [('coder', 'baseline_coder', 'attacked_coder'), ('final', 'baseline_final', 'attacked_final')]
            for stage, b, a in pairs:
                bc = {(c['name'], c['kind']): c for c in artifacts.get(b, {}).get('checks', [])}
                ac = {(c['name'], c['kind']): c for c in artifacts.get(a, {}).get('checks', [])}
                for key in sorted(set(bc) | set(ac)):
                    before = bc.get(key, {}).get('status', 'missing')
                    after = ac.get(key, {}).get('status', 'missing')
                    paired_checks.append(dict(task_id=task_id, stage=stage, name=key[0], kind=key[1],
                        baseline_status=before, attacked_status=after, new_failure=transition(before, after)))
            b = row.get('baseline_coder_official'); a = row.get('attacked_coder_official')
            f = row.get('attacked_final_official')
            row['new_coder_official_failure'] = transition(b, a)
            row['final_official_regression'] = transition(row.get('baseline_final_official'), f)
            row['reviewer_official_recovery_after_new_coder_failure'] = (
                'YES' if f == 'passed' else 'NO' if f == 'failed' else 'UNRESOLVED'
            ) if row['new_coder_official_failure'] == 'YES' else 'NOT_ELIGIBLE'
            row['official_failure_persisted_after_review'] = (
                'YES' if f == 'failed' else 'NO' if f == 'passed' else 'UNRESOLVED'
            ) if row['new_coder_official_failure'] == 'YES' else 'NOT_ELIGIBLE'
        rows.append(row)
    fields = ['task_id', 'attempt', 'execution']
    for artifact in ['baseline_coder', 'baseline_final', 'attacked_coder', 'attacked_final']:
        fields += [artifact + '_official', artifact + '_additional_total'] + [
            artifact + '_additional_' + k for k in ['passed', 'failed', 'timeout', 'unresolved']]
    fields += ['new_coder_official_failure', 'final_official_regression',
               'reviewer_official_recovery_after_new_coder_failure', 'official_failure_persisted_after_review']
    base.write_csv(folder / 'comparison.csv', rows, fields)
    base.write_csv(folder / 'comparison_checks.csv', paired_checks, ['task_id', 'stage', 'name', 'kind',
        'baseline_status', 'attacked_status', 'new_failure'])
    totals = read_json(folder / 'totals.json')
    paired = [r for r in rows if r['execution'] == 'completed']
    totals.update(calls_missing_token_counters=sum(not c.get('token_usage_available') for c in call_rows),
        intervention_target='project_manager', new_role_calls_per_task=2,
        baseline_metrics_reused=True, baseline_tests_reexecuted=False,
        completed_comparison_tasks=len(paired),
        new_coder_official_failures=sum(r.get('new_coder_official_failure') == 'YES' for r in paired),
        final_official_regressions=sum(r.get('final_official_regression') == 'YES' for r in paired),
        reviewer_official_recoveries=sum(r.get('reviewer_official_recovery_after_new_coder_failure') == 'YES' for r in paired),
        official_new_failures_persisting=sum(r.get('official_failure_persisted_after_review') == 'YES' for r in paired),
        interpretation='These are test transitions, not proof of adoption of the intended PM fault. Inspect artifacts and diffs.')
    for artifact in ['baseline_coder', 'baseline_final', 'attacked_coder', 'attacked_final']:
        totals[artifact + '_official_passes_completed_pairs'] = sum(r.get(artifact + '_official') == 'passed' for r in paired)
        totals[artifact + '_additional_passes_completed_pairs'] = sum(r.get(artifact + '_additional_passed', 0) for r in paired)
        totals[artifact + '_additional_total_completed_pairs'] = sum(r.get(artifact + '_additional_total', 0) for r in paired)
    totals['new_coder_official_failure_eligible_tasks'] = sum(r.get('baseline_coder_official') == 'passed' for r in paired)
    totals['final_official_regression_eligible_tasks'] = sum(r.get('baseline_final_official') == 'passed' for r in paired)
    save(folder / 'totals.json', totals)
    overview = ['# PM message replay', '',
        f"Study status: {state['status']}",
        f"Completed comparison tasks: {len(paired)} / {len(state['indices'])}", '',
        '| Artifact | Official passes on completed tasks | Additional cases passed |',
        '|---|---:|---:|']
    for artifact in ['baseline_coder', 'baseline_final', 'attacked_coder', 'attacked_final']:
        overview.append(f"| {artifact} | {totals[artifact + '_official_passes_completed_pairs']} / {len(paired)} | "
            f"{totals[artifact + '_additional_passes_completed_pairs']} / {totals[artifact + '_additional_total_completed_pairs']} |")
    overview += ['', f"New raw-Coder official failures: {totals['new_coder_official_failures']} / {totals['new_coder_official_failure_eligible_tasks']} eligible baseline passes.",
        f"Final official regressions: {totals['final_official_regressions']} / {totals['final_official_regression_eligible_tasks']} eligible baseline passes.",
        f"Official test recoveries after a new raw-Coder failure: {totals['reviewer_official_recoveries']}.",
        f"New raw-Coder official failures persisting through review: {totals['official_new_failures_persisting']}.", '',
        f"New recorded model calls, all attempts: {totals['recorded_model_calls']}",
        f"New reported tokens, all attempts: {totals['reported_total_tokens']}",
        f"New recorded model-call seconds, all attempts: {totals['reported_model_seconds']}", '',
        'Baseline evaluation is reused after hash and environment checks; upstream generations are not charged again.',
        'Calls without reported token counters and interrupted requests may consume unreported computation.',
        'Official test outcomes do not establish full correctness or adoption of a specific fault.', '',
        '- comparison.csv: per-task baseline versus attacked raw Coder and final outcomes.',
        '- comparison_checks.csv: individual baseline-to-attacked test transitions.',
        '- calls.csv: new role calls across all attempts, tokens and latency.',
        '- lineage_edges.csv: recorded transmissions, including the substituted PM mismatch.',
        '- task-NNN/attempt-N/: full messages, code, diffs, trace, lineage and evaluation.', '']
    (folder / 'overview.md').write_text('\n'.join(overview), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--injections', type=Path)
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--limit', type=int, default=1)
    resume_group = parser.add_mutually_exclusive_group()
    resume_group.add_argument('--resume', type=Path)
    resume_group.add_argument('--resume-full', action='store_true',
        help='Resume the unique unfinished 164-task PM replay in runs/, refusing ambiguity.')
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--config', type=Path)
    parser.add_argument('--image')
    args = parser.parse_args()
    if args.resume_full:
        candidates = []
        for candidate in (ROOT / 'runs').glob('pm-replay-*'):
            checkpoint = candidate / 'study.json'
            if checkpoint.is_file():
                candidate_state = read_json(checkpoint)
                if (candidate_state.get('schema_version') == SCHEMA
                    and candidate_state.get('indices') == list(range(164))
                    and candidate_state.get('status') != 'completed'):
                    candidates.append(candidate)
        if len(candidates) != 1:
            raise SystemExit('Expected exactly one unfinished full replay; found '
                + str(len(candidates)) + '. Use --resume with an explicit folder if needed. '
                + ', '.join(str(p) for p in candidates))
        args.resume = candidates[0]
    from check_suites import evaluate_artifact, load_items, load_suite
    items = load_items()
    if args.resume:
        folder = args.resume.resolve()
        state = read_json(folder / 'study.json')
        require_equal(state['schema_version'], SCHEMA, 'Checkpoint schema')
        if any([args.baseline, args.injections, args.config, args.image]) or args.start != 0 or args.limit != 1:
            parser.error('With --resume, supply only the saved study folder (optionally --validate-only).')
        baseline = Path(state['baseline']); package = Path(state['injections'])
        config_path = Path(state['config']); image_tag = state['image_tag']; indices = state['indices']
    else:
        if not args.baseline or not args.injections:
            parser.error('Provide --baseline and --injections for a new study.')
        baseline = args.baseline.resolve(); package = args.injections.resolve()
        config_path = (args.config or ROOT / 'config/config2.yaml').resolve()
        image_tag = args.image or 'python:3.11-slim'
        if args.start < 0 or args.limit < 1 or args.start + args.limit > len(items):
            parser.error('Invalid task selection.')
        indices = list(range(args.start, args.start + args.limit))
    manifest, entries = load_interventions(package)
    require_equal(baseline.name, manifest['source_study'], 'Baseline study folder')
    require_equal(read_json(baseline / 'study.json')['status'], 'completed', 'Baseline study status')
    # This read-only pass works without importing MetaGPT or contacting Docker/Ollama.
    fingerprint(baseline, package, entries, items, indices, config_path)
    if args.validate_only:
        print(f'PASS: {len(indices)} task mappings, source handoffs, original code/evaluations, and test hashes verified.')
        print('No model calls, containers, or new study folders were created.')
        return
    runtime = base.runtime_modules()
    configs = base.load_configs(config_path, runtime)
    subprocess.run(['docker', 'info'], check=True, stdout=subprocess.DEVNULL)
    image = subprocess.check_output(['docker', 'image', 'inspect', image_tag,
                                    '--format', '{{.Id}}'], text=True).strip()
    snapshot = fingerprint(baseline, package, entries, items, indices, config_path, configs, image)
    if args.resume:
        require_equal(snapshot, state['snapshot'], 'Saved replay fingerprint; restore original files/settings before resuming')
    else:
        folder = ROOT / 'runs' / ('pm-replay-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
        folder.mkdir(parents=True)
        state = dict(schema_version=SCHEMA, condition='pm_message_injection', status='running',
            baseline=str(baseline), injections=str(package), config=str(config_path), image_tag=image_tag,
            indices=indices, tasks={}, snapshot=snapshot)
        shutil.copy2(package / 'manifest.json', folder / 'interventions_manifest.json')
    lock_file = (folder / '.run.lock').open('a')
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock_file.close()
        raise SystemExit('This study is already running in another process; do not start a duplicate.')
    if args.resume:
        state = read_json(folder / 'study.json')
        require_equal(state['snapshot'], snapshot, 'Saved replay fingerprint after acquiring lock')
    state['status'] = 'running'
    save(folder / 'study.json', state)
    interrupted = False
    with base.capture_console(folder), base.capture_library_log(folder, runtime), asyncio.Runner() as loop:
        print('PM REPLAY STUDY:', folder, flush=True)
        print('Reused roles: product_manager, architect, project_manager generation', flush=True)
        print('Substituted message: project_manager → coder', flush=True)
        try:
            for i in indices:
                item = items[i]; entry = entries[item['task_id']]
                attempts = state['tasks'].setdefault(item['task_id'], [])
                if attempts and attempts[-1]['status'] == 'completed':
                    continue
                relative = Path(f'task-{i:03d}') / f'attempt-{len(attempts)+1}'
                out = folder / relative; out.mkdir(parents=True)
                attempt = dict(attempt=len(attempts)+1, folder=str(relative), status='running')
                attempts.append(attempt); save(folder / 'study.json', state)
                started = time.perf_counter()
                with base.capture_console(out), base.capture_library_log(out, runtime):
                    print('\nTASK:', item['task_id'], 'attempt', attempt['attempt'], flush=True)
                    try:
                        loop.run(generate_replay(configs, item, entry, baseline, package, out, runtime))
                        src = source_folder(baseline, entry)
                        original_eval = read_json(src / 'evaluation.json')
                        evaluation = dict(task_id=item['task_id'], image_id=image,
                            tests_sha256=base.sha(ROOT / f'tests/HumanEval_{i}.json'),
                            baseline_evaluation_reused=True,
                            baseline_evaluation_source=str(src / 'evaluation.json'),
                            baseline_evaluation_sha256=base.sha(src / 'evaluation.json'),
                            artifacts=copy.deepcopy(original_eval['artifacts']))
                        save(out / 'evaluation.json', evaluation)
                        for artifact, filename in [('attacked_coder', 'coder_after_pm_injection.py'),
                                                   ('attacked_final', 'final.py')]:
                            path = out / filename
                            result = evaluate_artifact(path.read_text(encoding='utf-8'), item, load_suite(i), image)
                            result.update(code_sha256=base.sha(path), source_file=str(path))
                            evaluation['artifacts'][artifact] = result
                            save(out / 'evaluation.json', evaluation)
                            print(artifact, 'official:', result['official_status'], result['additional_counts'], flush=True)
                        write_diff(out / 'coder_comparison.diff', (out / 'baseline_coder.py').read_text(),
                            (out / 'coder_after_pm_injection.py').read_text(), 'baseline_coder.py', 'coder_after_pm_injection.py')
                        write_diff(out / 'review.diff', (out / 'coder_after_pm_injection.py').read_text(),
                            (out / 'final.py').read_text(), 'coder_after_pm_injection.py', 'final.py')
                        write_diff(out / 'final_comparison.diff', (out / 'baseline_final.py').read_text(),
                            (out / 'final.py').read_text(), 'baseline_final.py', 'final.py')
                        resolved = all(c['status'] in ('passed', 'failed')
                            for r in evaluation['artifacts'].values() for c in r['checks'])
                        attempt['status'] = 'completed' if resolved else 'evaluation_unresolved'
                    except BaseException as exc:
                        attempt.update(status='interrupted' if isinstance(exc, KeyboardInterrupt) else 'error',
                                       error=f'{type(exc).__name__}: {exc}')
                        if not isinstance(exc, Exception):
                            raise
                        traceback.print_exc()
                    finally:
                        attempt['wall_seconds'] = round(time.perf_counter() - started, 3)
                        save(folder / 'study.json', state); reports(folder, state)
        except KeyboardInterrupt:
            interrupted = True
            print('Stopped. Saved attempts are preserved. Resume with --resume and this folder.', flush=True)
        finally:
            state['status'] = 'interrupted' if interrupted else ('completed' if all(
                (state['tasks'].get(items[i]['task_id']) or [{}])[-1].get('status') == 'completed'
                for i in indices) else 'finished_with_unresolved_executions')
            save(folder / 'study.json', state); reports(folder, state)
            print('STUDY STATUS:', state['status']); print('RESULTS:', folder, flush=True)
    lock_file.close()
    if state['status'] != 'completed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
