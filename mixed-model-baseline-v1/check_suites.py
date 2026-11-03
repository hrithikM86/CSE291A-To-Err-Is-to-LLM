"""Additional, independently named checks. All candidate execution is in Docker."""
import ast
import json
import math
import re
from pathlib import Path
from evaluate_humaneval import run_check

ROOT = Path(__file__).resolve().parent

# Executed only inside a restricted container by the existing Docker runner.
CHECK_HELPERS = '''
import ast, copy, json, math, runpy, signal
def alarm_handler(signum, frame):
    raise TimeoutError('individual check exceeded time limit')
signal.signal(signal.SIGALRM, alarm_handler)
def equal_result(actual, expected):
    if isinstance(expected, bool):
        return type(actual) is bool and actual == expected
    if expected is None:
        return actual is None
    if isinstance(expected, int) and not isinstance(expected, bool):
        return isinstance(actual,(int,float)) and not isinstance(actual,bool) and actual==expected
    if isinstance(expected, float):
        return (isinstance(actual, (int, float)) and not isinstance(actual, bool)
                and math.isfinite(actual)
                and math.isclose(actual, expected, rel_tol=1e-8, abs_tol=1e-8))
    if isinstance(expected, (tuple, list)):
        return (type(actual) is type(expected) and len(actual)==len(expected)
                and all(equal_result(a,b) for a,b in zip(actual,expected)))
    if isinstance(expected, dict):
        return (isinstance(actual, dict) and actual.keys()==expected.keys()
                and all(equal_result(actual[k],v) for k,v in expected.items()))
    return type(actual) is type(expected) and actual == expected
rows=[]
'''

def evaluate_artifact(code, item, suite, image, timeout=120):
    prefix='SUITE_RESULTS_'
    body = CHECK_HELPERS + '\n'
    # Each check gets a freshly imported namespace and copied arguments.
    # Signal limits allow later checks to continue after a candidate hangs.
    for case in suite['cases']:
        literal=repr(case)
        body += f'''
case = {literal}
row = {{'name':case['name'], 'kind':'additional', 'expected_literal':case['expected_literal']}}
try:
    signal.alarm(5)
    scope = {{'__name__':'<run_path>','__file__':'/work/candidate.py'}}
    exec(compile(namespace['__CANDIDATE_SOURCE__'],'candidate.py','exec'),scope)
    args = copy.deepcopy(case['args'])
    actual = scope[{item['entry_point']!r}](*args)
    if case['comparison'] == 'polynomial_residual':
        residual = sum(c * actual**i for i,c in enumerate(case['args'][0]))
        ok = isinstance(actual,(float,int)) and not isinstance(actual,bool) and math.isfinite(actual) and abs(residual) <= case.get('absolute_tolerance',1e-6)
    else:
        ok = equal_result(actual, ast.literal_eval(case['expected_literal']))
    row.update(status='passed' if ok else 'failed', actual_repr=repr(actual)[:2000])
except TimeoutError as exc:
    row.update(status='timeout',error=str(exc))
except BaseException as exc:
    row.update(status='failed',error=type(exc).__name__+': '+str(exc)[:2000])
finally:
    signal.alarm(0)
rows.append(row)
'''
    # Keep the official suite outcome separate from per-case additional counts.
    body += f'''
row={{'name':'official_humaneval', 'kind':'official'}}
try:
    signal.alarm(20)
    scope={{'__name__':'<run_path>','__file__':'/work/candidate.py'}}
    exec(compile(namespace['__CANDIDATE_SOURCE__'],'candidate.py','exec'),scope)
    test_scope={{}}
    # Several supplied suites call poly/encode_* or the reference function
    # by name. Give them trusted reference globals, NEVER candidate globals.
    exec({(item['prompt']+item['canonical_solution'])!r}, test_scope)
    exec({item['test']!r}, test_scope)
    test_scope['check'](scope[{item['entry_point']!r}])
    row['status']='passed'
except TimeoutError as exc:
    row.update(status='timeout',error=str(exc))
except BaseException as exc:
    row.update(status='failed',error=type(exc).__name__+': '+str(exc)[:2000])
finally:
    signal.alarm(0)
rows.append(row)
print({prefix!r}+json.dumps(rows),flush=True)
'''
    # The uploaded primitive imports candidate.py before its check body. Store
    # source as inert data there, then compile/execute inside each guarded check.
    # Syntax/import errors are thus per-check failures, not lost suite results.
    wrapper='__CANDIDATE_SOURCE__ = '+repr(code)+'\n'
    result=run_check(wrapper,body,image,timeout)
    rows=None
    for line in result.get('stdout','').splitlines():
        if line.startswith(prefix):
            rows=json.loads(line[len(prefix):])
    if result['status']!='passed' or rows is None:
        status=result['status'] if result['status']!='passed' else 'incomplete_check'
        rows=[dict(name=c['name'],kind='additional',status='unresolved',reason=status) for c in suite['cases']]
        rows.append(dict(name='official_humaneval',kind='official',status='unresolved',reason=status))
    additional=[r for r in rows if r['kind']=='additional']
    counts={s:sum(r['status']==s for r in additional) for s in ['passed','failed','timeout','unresolved']}
    return dict(docker=result,checks=rows,additional_total=len(additional),additional_counts=counts,official_status=next(r['status'] for r in rows if r['kind']=='official'))

def load_items():
    return [json.loads(line) for line in (ROOT/'data/HumanEval.jsonl').read_text().splitlines() if line.strip()]

def load_suite(i):
    return json.loads((ROOT/'tests'/f'HumanEval_{i}.json').read_text())
