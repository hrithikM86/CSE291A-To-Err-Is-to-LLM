"""Baseline ONLY: five MetaGPT roles, role-specific models, full call lineage.

No PM corruption, injector call, replay of historical baselines, or recovery.
"""
import argparse
import ast
import asyncio
from contextlib import contextmanager, redirect_stderr, redirect_stdout
import copy
import csv
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parent
from lineage import CallRecorder, instructions_text, model_settings_text, payload_routes
from runtime_utils import close_model_clients, model_identity, save
from role_lineage import RoleModelGraph

ROLES = ('product_manager', 'architect', 'project_manager', 'coder', 'test_engineer')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Tee:
    def __init__(self, stream, log):
        self.stream, self.log = stream, log

    def write(self, text):
        self.stream.write(text)
        self.log.write(text)
        self.log.flush()
        return len(text)

    def flush(self):
        self.stream.flush()
        self.log.flush()

    def __getattr__(self, name):
        return getattr(self.stream, name)


@contextmanager
def capture_console(folder):
    with (folder / 'console.log').open('a', encoding='utf-8') as log:
        with redirect_stdout(Tee(sys.stdout, log)), redirect_stderr(Tee(sys.stderr, log)):
            yield


@contextmanager
def capture_library_log(folder, runtime):
    logger = runtime.get('logger')
    sink = None
    if logger is not None:
        sink = logger.add(str(folder / 'metagpt.log'), encoding='utf-8',
                          backtrace=False, diagnose=False)
    try:
        yield
    finally:
        if sink is not None:
            logger.remove(sink)


def runtime_modules():
    from loguru import logger
    from metagpt_clean import ArtifactAction, Config, ROLE_SPECS, Role, unwrap_code
    return dict(Action=ArtifactAction, Config=Config, specs=ROLE_SPECS,
                Role=Role, unwrap=unwrap_code, logger=logger)


def settings(config):
    return json.loads(model_settings_text(config.llm))


def load_configs(path, runtime):
    import yaml
    data = yaml.safe_load(path.read_text(encoding='utf-8'))
    models = data.get('role_models', {})
    if set(models) != set(ROLES):
        raise ValueError('role_models must contain exactly the five workflow roles.')
    base = runtime['Config'](llm=data['llm'])
    configs = {}
    for role in ROLES:
        config = base.model_copy(deep=True)
        config.llm.model = models[role]
        configs[role] = config
    return configs


def save_trace(folder, trace, graph):
    save(folder / 'trace.json', trace)
    save(folder / 'lineage.json', graph.to_json())


async def generate_baseline(configs, item, folder, runtime, dataset_sha256):
    folder.mkdir(parents=True, exist_ok=True)
    trace = dict(schema_version='mixed-baseline/v1', experiment='five_role_mixed_baseline',
                 condition='clean', task_id=item['task_id'], entry_point=item['entry_point'],
                 specification=item['prompt'], dataset_sha256=dataset_sha256,
                 model_config=settings(configs['product_manager']),
                 role_model_configs={r: settings(c) for r, c in configs.items()},
                 status='running', stages=[], new_inference=[],
                 evaluation_file='evaluation.json', generated_code_executed_by_agents=False)
    graph = RoleModelGraph()
    recorder = CallRecorder(graph)
    graph.add_source('specification', item['prompt'])
    for name, config in configs.items():
        graph.add_source(f'model_config:{name}', model_settings_text(config.llm),
                         kind='configuration')
    payload = dict(original_specification=item['prompt'], previous_stage=None,
                   previous_artifact=None)
    started = time.perf_counter()
    save_trace(folder, trace, graph)
    try:
        with recorder.recording(**runtime.get('recording', {})):
            for name, title, guidance in runtime['specs']:
                config = configs[name]
                action = runtime['Action'](guidance=guidance, config=config)
                initial_provider = action.llm
                role = runtime['Role'](name=name, profile=title,
                    goal='Produce a correct solution to the supplied function specification.',
                    actions=[action], config=config)
                intended_instructions = [role.actions[0].prefix, guidance]
                graph.add_source(f'instructions:{name}', instructions_text(intended_instructions),
                                 kind='configuration')
                stage = dict(stage=name, depends_on=['specification'] +
                             ([payload['previous_stage']] if payload['previous_stage'] else []),
                             guidance=guidance, role_prefix=role.actions[0].prefix,
                             input=copy.deepcopy(payload), model_config=settings(config),
                             status='running', execution='original')
                trace['stages'].append(stage)
                save(folder / f'{name}_input.json', dict(
                    payload=payload, system_messages=intended_instructions,
                    model_config=settings(config)))
                save_trace(folder, trace, graph)
                before = action.llm.get_costs()
                stage_started = time.perf_counter()
                first_node = len(graph.nodes)
                try:
                    print(f'Running {name}: {config.llm.model}', flush=True)
                    with graph.model_scope(name), recorder.routing(payload_routes(stage['depends_on'], payload)):
                        response = await role.run(json.dumps(payload))
                    if response is None or not response.content.strip():
                        raise RuntimeError('Role returned no usable output.')
                    text = response.content
                    stage.update(status='completed', original_output=text, delivered_output=text)
                    (folder / f'{name}.txt').write_text(text, encoding='utf-8')
                    print(text, flush=True)
                    if name in ('coder', 'test_engineer'):
                        code = runtime['unwrap'](text)
                        filename = 'coder.py' if name == 'coder' else 'final.py'
                        (folder / filename).write_text(code, encoding='utf-8')
                        try:
                            tree = ast.parse(code)
                            stage['syntax_check'] = 'passed'
                            stage['entry_point_found'] = any(
                                isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                                and n.name == item['entry_point'] for n in tree.body)
                        except SyntaxError as exc:
                            stage.update(syntax_check='failed', syntax_error=str(exc))
                    payload = dict(original_specification=item['prompt'], previous_stage=name,
                                   previous_artifact=text)
                except BaseException as exc:
                    stage.update(status='error', error=f'{type(exc).__name__}: {exc}')
                    raise
                finally:
                    after = action.llm.get_costs()
                    stage['elapsed_seconds'] = round(time.perf_counter() - stage_started, 3)
                    stage['reported_prompt_tokens'] = after.total_prompt_tokens - before.total_prompt_tokens
                    stage['reported_completion_tokens'] = after.total_completion_tokens - before.total_completion_tokens
                    stage['reported_total_tokens'] = stage['reported_prompt_tokens'] + stage['reported_completion_tokens']
                    trace['new_inference'].append(dict(model=config.llm.model, **{
                        k: stage.get(k) for k in ['stage', 'status', 'elapsed_seconds',
                           'reported_prompt_tokens', 'reported_completion_tokens', 'reported_total_tokens']}))
                    for node in list(graph.nodes.values())[first_node:]:
                        node['trace_stage'] = len(trace['stages']) - 1
                    try:
                        save_trace(folder, trace, graph)
                    finally:
                        await close_model_clients([initial_provider, action.llm, role.llm])
        trace['status'] = 'completed'
    except BaseException as exc:
        trace.update(status='error', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        trace['wall_seconds'] = round(time.perf_counter() - started, 3)
        save_trace(folder, trace, graph)
    return trace


def fingerprint(config_path, configs, indices, image):
    paths = [Path(__file__), ROOT / 'role_lineage.py', config_path]
    paths += [ROOT / n for n in ['lineage.py', 'metagpt_clean.py', 'runtime_utils.py',
              'check_suites.py', 'evaluate_humaneval.py', 'data/HumanEval.jsonl']]
    paths += [ROOT / f'tests/HumanEval_{i}.json' for i in indices]
    def label(path):
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return str(path)
    unique = {c.llm.model: c for c in configs.values()}
    return dict(role_model_configs={r: settings(c) for r, c in configs.items()},
                models={name: model_identity(settings(c)) for name, c in unique.items()},
                image_id=image, packages={p: version(p) for p in ['metagpt', 'openai', 'pydantic', 'PyYAML']},
                files={label(p): sha(p) for p in paths})


def write_csv(path, rows, fields):
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def reports(folder, state):
    calls, results, checks, edges, lineage_rows = [], [], [], [], []
    for task_id, attempts in state['tasks'].items():
        if not attempts:
            continue
        for attempt in attempts:
            path = folder / attempt['folder'] / 'trace.json'
            if path.is_file():
                trace = json.loads(path.read_text())
                calls += [dict(task_id=task_id, attempt=attempt['attempt'], **c)
                          for c in trace.get('new_inference', [])]
        latest = max(attempts, key=lambda a: a['attempt'])
        out = folder / latest['folder']
        evaluation_path = out / 'evaluation.json'
        if evaluation_path.is_file():
            evaluation = json.loads(evaluation_path.read_text())
            for artifact, result in evaluation['artifacts'].items():
                results.append(dict(task_id=task_id, attempt=latest['attempt'], artifact=artifact,
                    execution=latest['status'], official=result['official_status'],
                    additional_total=result['additional_total'], **result['additional_counts']))
                checks += [dict(task_id=task_id, artifact=artifact, **c) for c in result['checks']]
        else:
            results.append(dict(task_id=task_id, attempt=latest['attempt'], execution=latest['status']))
        graph_path = out / 'lineage.json'
        if graph_path.is_file():
            graph = json.loads(graph_path.read_text())
            counts = {}
            for node in graph['nodes']:
                for edge in node['inputs']:
                    counts[edge['status']] = counts.get(edge['status'], 0) + 1
                    edges.append(dict(task_id=task_id, attempt=latest['attempt'], target=node['id'],
                        source=edge['node'], via=edge.get('via'), status=edge['status'],
                        in_prompt=edge.get('in_prompt'), sent_sha256=edge.get('sent_sha256'),
                        received_sha256=edge.get('received_sha256'), weak=edge.get('weak'),
                        ambiguous_with=json.dumps(edge.get('ambiguous_with', []))))
            lineage_rows.append(dict(task_id=task_id, attempt=latest['attempt'],
                nodes=len(graph['nodes']), **{s: counts.get(s, 0) for s in
                ['verified', 'mismatch', 'unverified', 'captured', 'undeclared']}))
    write_csv(folder / 'calls.csv', calls, ['task_id', 'attempt', 'stage', 'model', 'status',
              'elapsed_seconds', 'reported_prompt_tokens', 'reported_completion_tokens', 'reported_total_tokens'])
    write_csv(folder / 'results.csv', results, ['task_id', 'attempt', 'artifact', 'execution',
              'official', 'additional_total', 'passed', 'failed', 'timeout', 'unresolved'])
    write_csv(folder / 'checks.csv', checks, ['task_id', 'artifact', 'name', 'kind', 'status',
              'expected_literal', 'actual_repr', 'error', 'reason'])
    write_csv(folder / 'lineage_edges.csv', edges, ['task_id', 'attempt', 'source', 'target',
              'via', 'status', 'in_prompt', 'sent_sha256', 'received_sha256', 'weak', 'ambiguous_with'])
    write_csv(folder / 'lineage_summary.csv', lineage_rows, ['task_id', 'attempt', 'nodes',
              'verified', 'mismatch', 'unverified', 'captured', 'undeclared'])
    save(folder / 'totals.json', dict(
        tasks_selected=len(state['indices']), tasks_attempted=sum(bool(a) for a in state['tasks'].values()),
        tasks_completed=sum(bool(a) and a[-1]['status'] == 'completed' for a in state['tasks'].values()),
        recorded_model_calls=len(calls),
        reported_prompt_tokens=sum(c.get('reported_prompt_tokens') or 0 for c in calls),
        reported_completion_tokens=sum(c.get('reported_completion_tokens') or 0 for c in calls),
        reported_total_tokens=sum(c.get('reported_total_tokens') or 0 for c in calls),
        reported_model_seconds=round(sum(c.get('elapsed_seconds') or 0 for c in calls), 3),
        note='Calls include saved earlier attempts; interrupted requests can consume unreported computation.'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--limit', type=int, default=1)
    parser.add_argument('--resume', type=Path)
    parser.add_argument('--config', type=Path, default=ROOT / 'config/config2.yaml')
    parser.add_argument('--image', default='python:3.11-slim')
    args = parser.parse_args()
    args.config = args.config.resolve()
    from check_suites import evaluate_artifact, load_items, load_suite
    runtime = runtime_modules()
    configs = load_configs(args.config, runtime)
    items = load_items()
    subprocess.run(['docker', 'info'], check=True, stdout=subprocess.DEVNULL)
    image = subprocess.check_output(['docker', 'image', 'inspect', args.image,
                                    '--format', '{{.Id}}'], text=True).strip()
    if args.resume:
        folder = args.resume.resolve()
        state = json.loads((folder / 'study.json').read_text())
        indices = state['indices']
        if state['snapshot'] != fingerprint(args.config, configs, indices, image):
            raise SystemExit('Code, inputs, models or environment changed. Restore them; do not edit the checkpoint.')
    else:
        if args.start < 0 or args.limit < 1 or args.start + args.limit > len(items):
            parser.error('Invalid task selection')
        indices = list(range(args.start, args.start + args.limit))
        snapshot = fingerprint(args.config, configs, indices, image)
        folder = ROOT / 'runs' / ('baseline-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
        folder.mkdir(parents=True)
        state = dict(schema_version='mixed-baseline-study/v1', status='running',
                     indices=indices, tasks={}, snapshot=snapshot, condition='clean')
    save(folder / 'study.json', state)
    interrupted = False
    dataset_sha = sha(ROOT / 'data/HumanEval.jsonl')
    with capture_console(folder), capture_library_log(folder, runtime), asyncio.Runner() as loop:
        print('BASELINE STUDY:', folder, flush=True)
        for role in ROLES:
            print(f'{role}: {configs[role].llm.model}', flush=True)
        try:
            for i in indices:
                item = items[i]
                attempts = state['tasks'].setdefault(item['task_id'], [])
                if attempts and attempts[-1]['status'] == 'completed':
                    continue
                relative = Path(f'task-{i:03d}') / f'attempt-{len(attempts)+1}'
                out = folder / relative
                out.mkdir(parents=True)
                attempt = dict(attempt=len(attempts)+1, folder=str(relative), status='running')
                attempts.append(attempt)
                save(folder / 'study.json', state)
                started = time.perf_counter()
                with capture_console(out), capture_library_log(out, runtime):
                    print('\nTASK:', item['task_id'], 'attempt', attempt['attempt'], flush=True)
                    try:
                        loop.run(generate_baseline(configs, item, out, runtime, dataset_sha))
                        evaluation = dict(task_id=item['task_id'], image_id=image,
                            tests_sha256=sha(ROOT / f'tests/HumanEval_{i}.json'), artifacts={})
                        for artifact, filename in [('baseline_coder', 'coder.py'), ('baseline_final', 'final.py')]:
                            path = out / filename
                            result = evaluate_artifact(path.read_text(), item, load_suite(i), image)
                            result.update(code_sha256=sha(path), source_file=str(path))
                            evaluation['artifacts'][artifact] = result
                            save(out / 'evaluation.json', evaluation)
                            print(artifact, 'official:', result['official_status'], result['additional_counts'], flush=True)
                        resolved = all(c['status'] in ['passed', 'failed']
                            for r in evaluation['artifacts'].values() for c in r['checks'])
                        attempt['status'] = 'completed' if resolved else 'evaluation_unresolved'
                    except Exception as exc:
                        attempt.update(status='error', error=f'{type(exc).__name__}: {exc}')
                        traceback.print_exc()
                    finally:
                        attempt['wall_seconds'] = round(time.perf_counter() - started, 3)
                        save(folder / 'study.json', state)
                        reports(folder, state)
        except KeyboardInterrupt:
            interrupted = True
            print('Stopped. Saved work is preserved; resume using this study folder.')
        finally:
            state['status'] = ('interrupted' if interrupted else 'completed' if all(
                (state['tasks'].get(items[i]['task_id']) or [{}])[-1].get('status') == 'completed'
                for i in indices) else 'finished_with_unresolved_executions')
            save(folder / 'study.json', state)
            reports(folder, state)
            print('STUDY STATUS:', state['status'])
            print('RESULTS:', folder, flush=True)
    if state['status'] != 'completed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
