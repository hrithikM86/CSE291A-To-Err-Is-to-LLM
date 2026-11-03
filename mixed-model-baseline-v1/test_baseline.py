"""Model-routing, lineage, reporting and export tests with simulated providers."""
import asyncio
import copy
import csv
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

import run_baseline as workflow
from export_baseline import make_export


class FakeConfig:
    def __init__(self, llm):
        self.llm = SimpleNamespace(**llm)

    def model_copy(self, deep=False):
        return copy.deepcopy(self)


class FakeProvider:
    requests = []
    fail_next = False

    def __init__(self, config):
        self.config = config.llm
        self.prompt = self.completion = 0

    def get_costs(self):
        return SimpleNamespace(total_prompt_tokens=self.prompt, total_completion_tokens=self.completion)

    async def aask(self, prompt, system_msgs=None):
        if self.fail_next:
            raise RuntimeError('Simulated request failure')
        self.requests.append((self.config.model, json.loads(prompt), system_msgs))
        self.prompt += 11
        self.completion += 7
        return 'def f(x):\n    return x\n'


class FakeAction:
    def __init__(self, guidance, config):
        self.guidance, self.llm, self.prefix = guidance, FakeProvider(config), ''


class FakeRole:
    def __init__(self, name, profile, goal, actions, config):
        self.name, self.actions, self.llm = name, actions, actions[0].llm
        actions[0].prefix = f'You are {name}.'

    async def run(self, prompt):
        action = self.actions[0]
        return SimpleNamespace(content=await action.llm.aask(prompt,
            system_msgs=[action.prefix, action.guidance]))


def runtime():
    return dict(Config=FakeConfig, Action=FakeAction, Role=FakeRole,
                specs=[(r, r, f'Guidance for {r}') for r in workflow.ROLES],
                unwrap=lambda text: text,
                recording=dict(llm_classes=[FakeProvider], role_classes=[FakeRole]))


class BaselineTests(unittest.TestCase):
    def setUp(self):
        FakeProvider.requests = []
        FakeProvider.fail_next = False

    def test_local_dataset_and_tests_are_complete(self):
        import check_suites
        items = check_suites.load_items()
        self.assertEqual(len(items), 164)
        self.assertEqual(Path(check_suites.__file__).resolve().parent, workflow.ROOT)
        cases = 0
        for index, item in enumerate(items):
            suite = check_suites.load_suite(index)
            self.assertEqual(suite['task_id'], item['task_id'])
            cases += len(suite['cases'])
        self.assertEqual(cases, 504)

    def test_all_five_roles_are_clean_and_recorded(self):
        rt = runtime()
        configs = workflow.load_configs(workflow.ROOT / 'config/config2.yaml', rt)
        item = dict(task_id='HumanEval/0', entry_point='f', prompt='Implement f(x).')
        with tempfile.TemporaryDirectory() as directory, asyncio.Runner() as loop:
            folder = Path(directory)
            trace = loop.run(workflow.generate_baseline(configs, item, folder, rt, 'dataset-fixture'))
            self.assertEqual(trace['status'], 'completed')
            self.assertEqual(trace['condition'], 'clean')
            self.assertEqual(len(FakeProvider.requests), 5)
            self.assertEqual([r[0] for r in FakeProvider.requests],
                             ['qwen2.5:7b'] * 3 + ['qwen2.5-coder:7b', 'qwen2.5:7b'])
            for i, stage in enumerate(trace['stages']):
                self.assertEqual(stage['original_output'], stage['delivered_output'])
                self.assertTrue((folder / f'{stage["stage"]}_input.json').is_file())
                self.assertTrue((folder / f'{stage["stage"]}.txt').is_file())
                self.assertEqual(set(stage['input']), {'original_specification', 'previous_stage', 'previous_artifact'})
                if i:
                    self.assertEqual(stage['input']['previous_artifact'], trace['stages'][i-1]['original_output'])
            graph = json.loads((folder / 'lineage.json').read_text())
            nodes = {n['id']: n for n in graph['nodes']}
            model_calls = [n for n in nodes.values() if n['kind'] == 'model_call']
            self.assertEqual(len(model_calls), 5)
            for node in model_calls:
                for edge in node['inputs']:
                    self.assertLess(nodes[edge['node']]['seq'], node['seq'])
                    if edge['status'] != 'undeclared':
                        self.assertEqual(edge['status'], 'verified')
            self.assertEqual(sum(c['reported_total_tokens'] for c in trace['new_inference']), 90)

    def test_failed_call_preserves_partial_trace_and_lineage(self):
        rt = runtime()
        configs = workflow.load_configs(workflow.ROOT / 'config/config2.yaml', rt)
        FakeProvider.fail_next = True
        with tempfile.TemporaryDirectory() as directory, asyncio.Runner() as loop:
            folder = Path(directory)
            with self.assertRaisesRegex(RuntimeError, 'Simulated request failure'):
                loop.run(workflow.generate_baseline(configs,
                    dict(task_id='HumanEval/0', entry_point='f', prompt='Implement f.'), folder, rt, 'fixture'))
            trace = json.loads((folder / 'trace.json').read_text())
            self.assertEqual(trace['status'], 'error')
            self.assertEqual(trace['new_inference'][0]['status'], 'error')
            graph = json.loads((folder / 'lineage.json').read_text())
            self.assertEqual(next(n for n in graph['nodes'] if n['kind'] == 'model_call')['status'], 'error')

    def test_main_reports_resume_and_export(self):
        import check_suites
        rt = runtime()
        project = workflow.ROOT
        config_path = project / 'config/config2.yaml'
        def evaluate(*args):
            return dict(official_status='passed', additional_total=1,
                additional_counts=dict(passed=1, failed=0, timeout=0, unresolved=0),
                checks=[dict(name='fixture', kind='additional', status='passed'),
                        dict(name='official_humaneval', kind='official', status='passed')])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(workflow, 'ROOT', root), \
                 patch.object(workflow, 'runtime_modules', return_value=rt), \
                 patch.object(workflow, 'fingerprint', return_value={'fixture': 'stable'}), \
                 patch.object(workflow, 'sha', return_value='fixture-hash'), \
                 patch.object(workflow.subprocess, 'run'), \
                 patch.object(workflow.subprocess, 'check_output', return_value='image-fixture'), \
                 patch.object(check_suites, 'evaluate_artifact', side_effect=evaluate), \
                 patch.object(workflow.sys, 'argv', ['run_baseline.py', '--limit', '1', '--config', str(config_path)]):
                workflow.main()
                study = next((root / 'runs').iterdir())
                totals = json.loads((study / 'totals.json').read_text())
                self.assertEqual(totals['recorded_model_calls'], 5)
                self.assertEqual(totals['reported_total_tokens'], 90)
                with (study / 'results.csv').open() as f:
                    self.assertEqual({r['artifact'] for r in csv.DictReader(f)}, {'baseline_coder', 'baseline_final'})
                with (study / 'lineage_edges.csv').open() as f:
                    self.assertTrue(list(csv.DictReader(f)))
                self.assertIn('Running coder: qwen2.5-coder:7b', (study / 'console.log').read_text())
                workflow.sys.argv = ['run_baseline.py', '--resume', str(study), '--config', str(config_path)]
                workflow.main()
                self.assertEqual(len(FakeProvider.requests), 5)
                export = root / 'baseline.zip'
                manifest = make_export(study, export, project=project)
                self.assertEqual(manifest['tasks'][0]['status'], 'completed')
                with zipfile.ZipFile(export) as z:
                    self.assertIn('tasks/task-000/attempt-1/project_manager.txt', z.namelist())
                    self.assertIn('tasks/task-000/attempt-1/lineage.json', z.namelist())
                    self.assertIn('data/HumanEval.jsonl', z.namelist())
                    self.assertIn('tests/HumanEval_0.json', z.namelist())


if __name__ == '__main__':
    unittest.main()
