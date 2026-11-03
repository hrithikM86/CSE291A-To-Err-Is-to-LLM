"""Experiment 1: existing PM corruptions, new Coder and reviewer both qwen2.5:7b.

No new clean baseline. Place in PROJECT/experiment/experiment-1/.
Reuses PROJECT dependencies, original upstream messages, and unchanged tests.
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
import sys

EXPERIMENT = Path(__file__).resolve().parent
PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))

import run_baseline as base
from lineage import CallGraph, CallRecorder, instructions_text, model_settings_text, payload_routes
from role_lineage import RoleModelGraph
from runtime_utils import close_model_clients, model_identity, save

ROOT = PROJECT
ROLES = base.ROLES
NEW_ROLES = ('coder', 'test_engineer')
SCHEMA = 'all-qwen-pm-experiment-1/v1'
MODEL = 'qwen2.5:7b'


class ExperimentGraph(RoleModelGraph):
    def check_configuration(self, name, received, via):
        if name == 'model_config':
            # Retain historical sources; new calls explicitly consume the new
            # all-Qwen config instead of flagging the planned model change as a fault.
            return CallGraph.check_configuration(self, 'model_config:experiment_1_all_qwen', received, via)
        return super().check_configuration(name, received, via)


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
        expected_settings = copy.deepcopy(baseline_state['snapshot']['role_model_configs'])
        expected_settings['coder']['model'] = MODEL
        require_equal(role_settings, expected_settings, 'Only the planned Coder model change is allowed')
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
    graph = ExperimentGraph.from_json(dict(schema=source_graph['schema'], nodes=kept))
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
    graph.add_source('model_config:experiment_1_all_qwen', model_settings_text(configs['coder'].llm),
        kind='configuration', planned_change='Coder now uses qwen2.5:7b; reviewer unchanged')
    trace = dict(schema_version='all-qwen-pm-task/v1', experiment='experiment_1_all_qwen_pm_injection',
                 condition='all_qwen_pm_message_injection', new_clean_baseline=False, task_id=item['task_id'], entry_point=item['entry_point'],
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
    base.reports(folder, state)
    rows=[];calls=[]
    for tid, attempts in state['tasks'].items():
        for attempt in attempts:
            p=folder/attempt['folder']/'trace.json'
            if p.is_file():
                calls.extend(dict(task_id=tid,attempt=attempt['attempt'],**c)
                             for c in read_json(p).get('new_inference',[]))
        if not attempts:continue
        latest=attempts[-1];out=folder/latest['folder']
        row=dict(task_id=tid,attempt=latest['attempt'],execution=latest['status'])
        if (out/'evaluation.json').is_file():
            ev=read_json(out/'evaluation.json')
            for name,r in ev['artifacts'].items():
                row[name+'_official']=r['official_status']
                row[name+'_additional_total']=r['additional_total']
                row.update({name+'_additional_'+k:v for k,v in r['additional_counts'].items()})
        if (out/'lineage.json').is_file():
            g=read_json(out/'lineage.json');nodes={n['id']:n for n in g['nodes']}
            edges=[e for n in g['nodes'] if n.get('role')=='coder' for e in n['inputs']
                   if nodes.get(e['node'],{}).get('role')=='project_manager']
            row['pm_delivery_mismatch']=('YES' if len(edges)==1 and edges[0]['status']=='mismatch'
                and edges[0].get('in_prompt') is True else 'UNKNOWN')
        rows.append(row)
    fields=['task_id','attempt','execution','pm_delivery_mismatch']
    for a in ['attacked_coder','attacked_final']:
        fields += [a+'_official',a+'_additional_total']+[a+'_additional_'+k for k in ['passed','failed','timeout','unresolved']]
    base.write_csv(folder/'summary.csv',rows,fields)
    base.write_csv(folder/'calls.csv',calls,['task_id','attempt','stage','model','status','elapsed_seconds',
        'reported_prompt_tokens','reported_completion_tokens','reported_total_tokens','token_usage_available'])
    totals=read_json(folder/'totals.json');done=[r for r in rows if r['execution']=='completed']
    totals.update(experiment='experiment_1_all_qwen_pm_injection',coder_model=MODEL,test_engineer_model=MODEL,
        new_clean_baseline=False,source_baseline_used_for='Frozen upstream outputs and provenance only',
        calls_missing_token_counters=sum(not c.get('token_usage_available') for c in calls))
    for a in ['attacked_coder','attacked_final']:
        totals[a+'_official_passes']=sum(r.get(a+'_official')=='passed' for r in done)
        totals[a+'_additional_passes']=sum(r.get(a+'_additional_passed',0) for r in done)
        totals[a+'_additional_total']=sum(r.get(a+'_additional_total',0) for r in done)
    save(folder/'totals.json',totals)
    text=['# Experiment 1: all-Qwen PM injection','',f"Status: {state['status']}",
        f"Completed tasks: {len(done)} / {len(state['indices'])}",'',
        'The original upstream outputs and exact same corrupted PM messages were reused.',
        'Only Coder and Test Engineer ran anew, both using qwen2.5:7b.',
        'No clean all-Qwen baseline was generated. Historical mixed-model outputs are provenance, not an all-Qwen control.','',
        '| Artifact | Official passes / completed tasks | Additional passed / total |',
        '|---|---:|---:|']
    for a in ['attacked_coder','attacked_final']:
        text.append(f"| {a} | {totals[a+'_official_passes']} / {len(done)} | {totals[a+'_additional_passes']} / {totals[a+'_additional_total']} |")
    text += ['',f"New recorded calls, all attempts: {totals['recorded_model_calls']}",
        f"New reported tokens, all attempts: {totals['reported_total_tokens']}",
        f"New recorded call seconds, all attempts: {totals['reported_model_seconds']}",'',
        'See summary.csv, calls.csv, checks.csv, lineage_edges.csv and per-task artifacts.',
        'A delivery mismatch is not proof of fault adoption; test passes are not proof of complete correctness.',
        'Without a clean all-Qwen run, do not attribute every failure to injection.','']
    (folder/'overview.md').write_text('\n'.join(text),encoding='utf-8')


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
        for candidate in (EXPERIMENT / 'runs').glob('all-qwen-pm-*'):
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
        baseline = (args.baseline or ROOT / 'runs/baseline-20261030T082523974587Z').resolve()
        package = (args.injections or ROOT / 'pm-message-injections-v1').resolve()
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
    # Override in memory only; never edit the parent YAML or prior experiments.
    configs['coder'].llm.model = MODEL
    if any(c.llm.model != MODEL for c in configs.values()):
        raise ValueError('All five role models must be qwen2.5:7b for this experiment.')
    subprocess.run(['docker', 'info'], check=True, stdout=subprocess.DEVNULL)
    image = subprocess.check_output(['docker', 'image', 'inspect', image_tag,
                                    '--format', '{{.Id}}'], text=True).strip()
    snapshot = fingerprint(baseline, package, entries, items, indices, config_path, configs, image)
    if args.resume:
        require_equal(snapshot, state['snapshot'], 'Saved replay fingerprint; restore original files/settings before resuming')
    else:
        folder = EXPERIMENT / 'runs' / ('all-qwen-pm-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
        folder.mkdir(parents=True)
        state = dict(schema_version=SCHEMA, condition='all_qwen_pm_message_injection', new_clean_baseline=False, status='running',
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
        print('EXPERIMENT 1 — ALL QWEN:', folder, flush=True)
        print('Reused roles: product_manager, architect, project_manager generation', flush=True)
        print('Exact existing PM substitution; Coder and Test Engineer: ' + MODEL, flush=True)
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
                            condition='all_qwen_pm_message_injection',
                            dataset_sha256=base.sha(ROOT / 'data/HumanEval.jsonl'),
                            pm_original_sha256=entry['original_pm']['sha256'],
                            pm_delivered_sha256=entry['corrupted_pm']['sha256'],
                            artifacts={})
                        save(out / 'evaluation.json', evaluation)
                        for artifact, filename in [('attacked_coder', 'coder_after_pm_injection.py'),
                                                   ('attacked_final', 'final.py')]:
                            path = out / filename
                            result = evaluate_artifact(path.read_text(encoding='utf-8'), item, load_suite(i), image)
                            result.update(code_sha256=base.sha(path), source_file=str(path))
                            evaluation['artifacts'][artifact] = result
                            save(out / 'evaluation.json', evaluation)
                            print(artifact, 'official:', result['official_status'], result['additional_counts'], flush=True)
                        write_diff(out / 'review.diff', (out / 'coder_after_pm_injection.py').read_text(),
                            (out / 'final.py').read_text(), 'all-Qwen raw Coder', 'all-Qwen reviewed final')
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
            print('No new clean baseline was run; compare this with the older corrupted study.'); print('STUDY STATUS:', state['status']); print('RESULTS:', folder, flush=True)
    lock_file.close()
    if state['status'] != 'completed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
