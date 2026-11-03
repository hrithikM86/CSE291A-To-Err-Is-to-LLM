"""Compare only corrupted-PM Qwen-Coder vs Qwen Coder runs (raw + reviewed).

Save in PROJECT/experiment/experiment-1/. Standard library only. No inference,
Docker, or clean-baseline evaluation. Default output is this experiment's
runs/final comparison qwen coder vs qwen.html.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import difflib
import hashlib
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
LABELS={'coder_model':'Qwen2.5-Coder Coder','qwen_model':'Qwen2.5 Coder'}
ARTS=('attacked_coder','attacked_final')
ROLES=('coder','test_engineer')
STATES=('passed','failed','timeout','unresolved')
SCHEMAS={'coder_model':'mixed-pm-replay-study/v1','qwen_model':'all-qwen-pm-experiment-1/v1'}


def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(data):return hashlib.sha256(data).hexdigest()
def txhash(value):return sha(value.encode('utf-8')) if isinstance(value,str) else None
def finite(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) and x>=0

def text(path):return path.read_text(encoding='utf-8') if path.is_file() else None

def safe_path(root,rel):
 p=(root/rel).resolve()
 if not p.is_relative_to(root.resolve()):raise ValueError('Attempt path escapes study folder.')
 return p

def metric(s):
 s=s or {};out={k:s.get(v) if finite(s.get(v)) else None for k,v in [('seconds','elapsed_seconds'),('prompt','reported_prompt_tokens'),('completion','reported_completion_tokens'),('tokens','reported_total_tokens')]}
 if out['tokens'] is None and out['prompt'] is not None and out['completion'] is not None:out['tokens']=out['prompt']+out['completion']
 if s.get('token_usage_available') is False:out.update(prompt=None,completion=None,tokens=None)
 out['model']=s.get('model',(s.get('model_config') or {}).get('model','unknown'));return out

def totals(metrics):
 metrics=list(metrics)
 return {k:sum(m[k] for m in metrics) if metrics and all(m[k] is not None for m in metrics) else None for k in ['seconds','prompt','completion','tokens']}

def unwrap(value):
 if not isinstance(value,str):return None
 s=value.strip();lines=s.splitlines()
 if len(lines)>=2 and lines[0].strip() in {'```python','```py','```'} and lines[-1].strip()=='```':s='\n'.join(lines[1:-1]).strip()
 return s+'\n'

def diff(a,b,left,right):
 if a is None or b is None:return '[Saved code/message missing.]'
 return '\n'.join(difflib.unified_diff(a.splitlines(),b.splitlines(),fromfile=left,tofile=right,lineterm='')) or '[No textual difference.]'

def optional(path,issues,label):
 try:return read(path)
 except (ValueError,OSError) as e:issues.append(f'{label} missing/unreadable: {e}');return {}


def lineage(g,original,corrupted,payload):
 nodes={n['id']:n for n in g.get('nodes',[])};coders=sorted([n for n in nodes.values() if n.get('role')=='coder'],key=lambda n:n.get('seq',0))
 all_edges=[dict(target=n['id'],**e) for n in nodes.values() for e in n.get('inputs',[])]
 candidates=[e for e in (coders[-1].get('inputs',[]) if coders else []) if nodes.get(e['node'],{}).get('role')=='project_manager']
 result=dict(caught='UNKNOWN',comments=[],edges=all_edges,other=[],pm_edge=None)
 if len(candidates)==1:
  e=candidates[0];result['pm_edge']=dict(target=coders[-1]['id'],**e)
  oh,ch=txhash(original),txhash(corrupted)
  expected=[oh is not None,ch is not None,oh!=ch,nodes[e['node']].get('output_sha256')==oh,
   e.get('sent_sha256')==oh,e.get('received_sha256')==ch,
   txhash(payload.get('previous_artifact'))==ch,payload.get('previous_stage')=='project_manager',e.get('in_prompt') is True]
  if all(expected) and e.get('status')=='mismatch':result['caught']='YES'
  elif e.get('status')=='verified' and e.get('sent_sha256')==e.get('received_sha256'):result['caught']='NO'
  elif e.get('status') in ['mismatch','verified']:result['caught']='INCONSISTENT'
  result['comments'].append('PM delivery: '+result['caught']+'.')
 else:result['comments'].append('Expected one PM dependency on latest Coder call; found '+str(len(candidates))+'.')
 for e in all_edges:
  intended=result['pm_edge'] or {}
  if (e['node'],e['target'],e.get('via'))==(intended.get('node'),intended.get('target'),'previous_artifact'):continue
  if e.get('status')!='verified':result['other'].append(e)
 result['comments'].append('Other non-verified edges: '+('; '.join(f"{e['node']} → {e['target']}: {e.get('status')}" for e in result['other']) or 'none')+'.')
 return result


def load_side(folder,state,index,project,dataset_hash):
 tid=f'HumanEval/{index}';out=dict(task_id=tid,attempt=None,execution='not_attempted',issues=[],artifacts={},checks={},operations={},calls=[],attempts=[],verified=False,contents={},lineage={})
 attempts=state.get('tasks',{}).get(tid,[])
 if not attempts:out['issues'].append('No attempt recorded.');return out
 max_n=max(int(a['attempt']) for a in attempts);latest=[a for a in attempts if int(a['attempt'])==max_n]
 if len(latest)!=1:raise ValueError('Duplicate latest attempt numbers.')
 a=latest[0];p=safe_path(folder,a['folder']);out.update(attempt=a['attempt'],execution=a.get('status','unknown'),folder=str(p.relative_to(folder)),wall_seconds=a.get('wall_seconds'))
 for old in attempts:
  op=safe_path(folder,old['folder']);tr=optional(op/'trace.json',out['issues'],f"Attempt {old['attempt']} trace")
  calls=[dict(stage=c.get('stage'),status=c.get('status'),**metric(c)) for c in tr.get('new_inference',[])]
  if any(c['stage'] not in ROLES for c in calls):out['issues'].append('Unexpected new role calls outside Coder/Test Engineer.')
  out['calls']+=calls;out['attempts'].append(dict(attempt=old['attempt'],status=old.get('status'),wall_seconds=old.get('wall_seconds'),calls=calls,trace_available=bool(tr)))
 trace=optional(p/'trace.json',out['issues'],'Latest trace');ev=optional(p/'evaluation.json',out['issues'],'Latest evaluation')
 g=optional(p/'lineage.json',out['issues'],'Latest lineage');ci=optional(p/'coder_input.json',out['issues'],'Coder input');ti=optional(p/'test_engineer_input.json',out['issues'],'Test Engineer input')
 stages={s['stage']:s for s in trace.get('stages',[])}
 out['entry_point']=trace.get('entry_point','unknown');out['specification']=trace.get('specification');out['role_settings']=trace.get('role_model_configs',{})
 for record,label in [(trace,'trace'),(ev,'evaluation')]:
  if record.get('task_id')!=tid:out['issues'].append(label+': wrong/missing task ID.')
 if trace.get('dataset_sha256')!=dataset_hash:out['issues'].append('Dataset hash differs from current project data.')
 test_path=project/'tests'/f'HumanEval_{index}.json';suite=optional(test_path,out['issues'],'Existing test file')
 if not test_path.is_file() or sha(test_path.read_bytes())!=ev.get('tests_sha256'):out['issues'].append('Existing additional-test hash differs from graded hash.')
 expected={('additional',c['name']) for c in suite.get('cases',[])}|{('official','official_humaneval')}
 expected_literals={c['name']:c.get('expected_literal') for c in suite.get('cases',[])}
 for role,inp in [('coder',ci),('test_engineer',ti)]:
  s=stages.get(role,{})
  if s.get('status')!='completed':out['issues'].append(role+': generation incomplete.')
  if inp.get('payload')!=s.get('input'):out['issues'].append(role+': input file and trace disagree.')
  if inp.get('system_messages')!=[s.get('role_prefix'),s.get('guidance')]:out['issues'].append(role+': system-message evidence differs from trace.')
  if inp.get('model_config')!=s.get('model_config') or s.get('model_config')!=out['role_settings'].get(role):out['issues'].append(role+': model configuration records disagree.')
  if inp.get('payload',{}).get('original_specification')!=out['specification']:out['issues'].append(role+': original specification differs.')
  out['operations'][role]=metric(s)
 out['system_messages']={r:v.get('system_messages') for r,v in [('coder',ci),('test_engineer',ti)]}
 out['coder_payload']=ci.get('payload',{})
 if ti.get('payload',{}).get('previous_artifact')!=stages.get('coder',{}).get('original_output'):out['issues'].append('Test Engineer did not receive the saved raw Coder output.')
 out['upstream_original_hashes']={r:txhash(stages.get(r,{}).get('original_output')) for r in ['product_manager','architect','project_manager']}
 original=text(p/'project_manager_original.txt');corrupted=text(p/'project_manager_corrupted.txt')
 out['pm_original_hash']=txhash(original);out['pm_corrupted_hash']=txhash(corrupted);out['contents']['corrupted_pm']=corrupted
 if corrupted!=stages.get('project_manager',{}).get('delivered_output'):out['issues'].append('Saved corrupted PM differs from the delivered PM in trace.')
 if original!=stages.get('project_manager',{}).get('original_output'):out['issues'].append('Original PM copy differs from trace.')
 out['lineage']=lineage(g,original,corrupted,ci.get('payload',{}))
 coder_nodes=sorted([n for n in g.get('nodes',[]) if n.get('role')=='coder'],key=lambda n:n.get('seq',0))
 out['coder_prompt_sha256']=coder_nodes[-1].get('prompt_sha256') if coder_nodes else None
 out['input_hashes']={name:sha((p/name).read_bytes()) for name in ['trace.json','evaluation.json','lineage.json','coder_input.json','test_engineer_input.json','project_manager_corrupted.txt'] if (p/name).is_file()}
 out['test_hash']=ev.get('tests_sha256');out['dataset_hash']=trace.get('dataset_sha256');out['image_id']=ev.get('image_id')
 for artifact,filename,role in [('attacked_coder','coder_after_pm_injection.py','coder'),('attacked_final','final.py','test_engineer')]:
  result=ev.get('artifacts',{}).get(artifact)
  if not result:out['issues'].append(artifact+': evaluation missing.');continue
  checks={}
  for c in result.get('checks',[]):
   key=(c.get('kind'),c.get('name'))
   if key in checks:out['issues'].append(artifact+': duplicate check.')
   checks[key]=c
   if c.get('kind')=='additional' and c.get('expected_literal')!=expected_literals.get(c.get('name')):out['issues'].append(artifact+': recorded expected value differs from test file.')
  if set(checks)!=expected:out['issues'].append(artifact+': check coverage differs from suite.')
  counts=Counter(c.get('status') for (kind,_),c in checks.items() if kind=='additional')
  official=checks.get(('official','official_humaneval'),{}).get('status','missing')
  if official!=result.get('official_status') or any(result.get('additional_counts',{}).get(k)!=counts[k] for k in STATES) or result.get('additional_total')!=sum(counts.values()):out['issues'].append(artifact+': summary/check counts disagree.')
  if set(counts)-set(STATES):out['issues'].append(artifact+': unsupported check status.')
  codepath=p/filename;code=text(codepath);out['contents'][artifact]=code
  if not codepath.is_file() or sha(codepath.read_bytes())!=result.get('code_sha256'):out['issues'].append(artifact+': code hash differs from graded code.')
  if unwrap(stages.get(role,{}).get('original_output'))!=code:out['issues'].append(artifact+': code differs from agent response.')
  out['artifacts'][artifact]=dict(official=official,total=sum(counts.values()),**{k:counts[k] for k in STATES},docker_seconds=result.get('docker',{}).get('wall_seconds'))
  out['checks'][artifact]=[dict(kind=k[0],name=k[1],**{x:y for x,y in v.items() if x not in ['kind','name']}) for k,v in checks.items()]
 out['latest_cost']=totals(out['operations'].get(r,metric({})) for r in ROLES)
 out['all_attempts_cost']=totals(out['calls'])
 if any(not a['trace_available'] for a in out['attempts']):out['all_attempts_cost']=dict(seconds=None,prompt=None,completion=None,tokens=None)
 out['review_diff']=diff(out['contents'].get('attacked_coder'),out['contents'].get('attacked_final'),'raw Coder','reviewed final')
 raw=out['artifacts'].get('attacked_coder',{}).get('official');final=out['artifacts'].get('attacked_final',{}).get('official')
 out['review_outcome']=('Raw failed → final passed' if raw=='failed' and final=='passed' else 'Raw passed → final failed' if raw=='passed' and final=='failed' else 'Both passed' if raw==final=='passed' else 'Both failed' if raw==final=='failed' else 'Unresolved')
 out['verified']=not out['issues'] and all(x in out['artifacts'] for x in ARTS)
 return out


def compare(index,sides,states):
 r=dict(index=index,task_id=f'HumanEval/{index}',sides=sides,control_issues=[],eligible=False,tests=[],wins={})
 a,b=sides['coder_model'],sides['qwen_model'];r['entry_point']=a.get('entry_point',b.get('entry_point','unknown'))
 for key,label in [('pm_corrupted_hash','identical corrupted PM bytes'),('pm_original_hash','identical original PM'),('specification','identical original specification'),('dataset_hash','same official dataset'),('test_hash','same additional tests'),('image_id','same Docker image'),('coder_payload','identical Coder input payload'),('coder_prompt_sha256','identical recorded Coder request'),('system_messages','identical Coder/reviewer instructions'),('upstream_original_hashes','identical reused upstream outputs')]:
  if a.get(key) is None or b.get(key) is None or a.get(key)!=b.get(key):r['control_issues'].append('Could not verify '+label+'.')
 for key,side in sides.items():
  configs=side.get('role_settings',{})
  expected='qwen2.5-coder:7b' if key=='coder_model' else 'qwen2.5:7b'
  if configs.get('coder',{}).get('model')!=expected:r['control_issues'].append(LABELS[key]+': unexpected Coder model.')
  if configs.get('test_engineer',{}).get('model')!='qwen2.5:7b':r['control_issues'].append(LABELS[key]+': unexpected Test Engineer model.')
 for helper in ['check_suites.py','evaluate_humaneval.py']:
  hashes=[states[k].get('snapshot',{}).get('files',{}).get(helper) for k in ['coder_model','qwen_model']]
  if not hashes[0] or hashes[0]!=hashes[1]:r['control_issues'].append('Grader implementation differs/missing: '+helper)
 for role in ROLES:
  ca=dict(a.get('role_settings',{}).get(role,{}));cb=dict(b.get('role_settings',{}).get(role,{}));ca.pop('model',None);cb.pop('model',None)
  if not ca or ca!=cb:r['control_issues'].append(role+': non-model settings differ/missing.')
 def model_digest(st):return st.get('snapshot',{}).get('models',{}).get('qwen2.5:7b',{}).get('digest')
 if not model_digest(states['coder_model']) or model_digest(states['coder_model'])!=model_digest(states['qwen_model']):r['control_issues'].append('qwen2.5:7b weight digest differs/missing across studies.')
 for artifact in ARTS:
  ac={(c['kind'],c['name']):c for c in a.get('checks',{}).get(artifact,[])};bc={(c['kind'],c['name']):c for c in b.get('checks',{}).get(artifact,[])}
  for kind,name in sorted(set(ac)|set(bc)):
   av=ac.get((kind,name),{});bv=bc.get((kind,name),{})
   result='Qwen-Coder only passes' if av.get('status')=='passed' and bv.get('status')=='failed' else 'Qwen only passes' if av.get('status')=='failed' and bv.get('status')=='passed' else 'Both pass' if av.get('status')==bv.get('status')=='passed' else 'Both fail' if av.get('status')==bv.get('status')=='failed' else 'Unresolved'
   r['tests'].append(dict(artifact=artifact,kind=kind,name=name,coder_model=av,qwen_model=bv,result=result))
  r['wins'][artifact]={label:sum(c['kind']=='additional' and c['artifact']==artifact and c['result']==label for c in r['tests']) for label in ['Qwen-Coder only passes','Qwen only passes']}
 r['eligible']=not r['control_issues'] and all(s.get('verified') and s.get('execution')=='completed' for s in sides.values()) and all(c['result']!='Unresolved' for c in r['tests']) and bool(r['tests'])
 r['cost_delta']={k:(b.get('latest_cost',{}).get(k)-a.get('latest_cost',{}).get(k)) if b.get('latest_cost',{}).get(k) is not None and a.get('latest_cost',{}).get(k) is not None else None for k in ['seconds','prompt','completion','tokens']}
 r['raw_diff']=diff(a.get('contents',{}).get('attacked_coder'),b.get('contents',{}).get('attacked_coder'),'Qwen-Coder raw output','Qwen raw output')
 r['final_diff']=diff(a.get('contents',{}).get('attacked_final'),b.get('contents',{}).get('attacked_final'),'Qwen-Coder pipeline final','Qwen pipeline final')
 r['pm_diff']=diff(a.get('contents',{}).get('corrupted_pm'),b.get('contents',{}).get('corrupted_pm'),'Qwen-Coder delivered PM','Qwen delivered PM')
 return r


def summary(rows):
 valid=[r for r in rows if r['eligible']];out=dict(selected=len(rows),eligible=len(valid),excluded=len(rows)-len(valid),sides={},matrices={})
 for side in LABELS:
  values=[r['sides'][side] for r in valid];allvalues=[r['sides'][side] for r in rows];calls=[c for v in allvalues for c in v.get('calls',[])]
  out['sides'][side]=dict(latest_cost=totals(v.get('latest_cost',{}) for v in values) if values else None,
    all_attempts_cost=totals(calls),calls=len(calls),missing_token_calls=sum(c['tokens'] is None for c in calls),
    known_tokens=sum(c['tokens'] for c in calls if c['tokens'] is not None),
    known_seconds=sum(c['seconds'] for c in calls if c['seconds'] is not None),
    pm_detected=sum(v.get('lineage',{}).get('caught')=='YES' for v in allvalues),
    other_lineage_tasks=sum(bool(v.get('lineage',{}).get('other')) for v in allvalues),
    missing_attempt_traces=sum(not a['trace_available'] for v in allvalues for a in v.get('attempts',[])),
    reviewer_pass_after_raw_failure=sum(v.get('review_outcome')=='Raw failed → final passed' for v in values),artifacts={})
  s=out['sides'][side]
  if s['missing_attempt_traces']:s['all_attempts_cost']=dict(seconds=None,prompt=None,completion=None,tokens=None)
  for art in ARTS:s['artifacts'][art]=dict(official_passed=sum(v['artifacts'][art]['official']=='passed' for v in values),additional_passed=sum(v['artifacts'][art]['passed'] for v in values),additional_total=sum(v['artifacts'][art]['total'] for v in values))
 out['cost_delta']={k:(out['sides']['qwen_model']['latest_cost'][k]-out['sides']['coder_model']['latest_cost'][k]) if out['sides']['qwen_model']['latest_cost'] is not None and out['sides']['coder_model']['latest_cost'] is not None and out['sides']['qwen_model']['latest_cost'][k] is not None and out['sides']['coder_model']['latest_cost'][k] is not None else None for k in ['seconds','prompt','completion','tokens']}
 for art in ARTS:
  c=Counter()
  for r in valid:
   a=r['sides']['coder_model']['artifacts'][art]['official'];b=r['sides']['qwen_model']['artifacts'][art]['official']
   c['both_pass' if a==b=='passed' else 'both_fail' if a==b=='failed' else 'coder_only' if a=='passed' else 'qwen_only']+=1
  out['matrices'][art]=dict(c)
 return out


HTML=r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Final comparison Qwen Coder vs Qwen</title><style>
body{margin:0;background:#f3f6fa;color:#203247;font:14px/1.55 system-ui,sans-serif}main{max-width:1850px;margin:auto;padding:24px}h1{font-size:27px;margin:0}h2{font-size:20px}.panel,details.task{background:white;border:1px solid #d7e3ed;border-radius:8px;padding:18px;margin:16px 0}.muted{font-size:12px;color:#52677d}.warning{background:#fff3d7;border-left:4px solid #cd9318;padding:12px}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}.card{padding:16px;background:white;border:1px solid #d7e3ed;border-radius:7px}.big{font-size:28px;font-weight:750}.scroll{overflow:auto;max-height:75vh}table{border-collapse:collapse;width:100%;font-size:12px}td,th{border:1px solid #d7e3ed;padding:9px;vertical-align:top;text-align:left}th{background:#e7eff7;position:sticky;top:0}tr:nth-child(even){background:#f8fafc}.main{min-width:2200px}.badge{font-weight:650;border-radius:4px;padding:3px 6px;display:inline-block;white-space:nowrap}.good{color:#166436;background:#e4f5e9}.bad{color:#a12c34;background:#ffe6e8}.warn{color:#80590e;background:#fff0c9}.toolbar{display:flex;gap:10px;flex-wrap:wrap}input,select,button{font:inherit;padding:8px;border:1px solid #bccdda;border-radius:5px;background:white}button,summary{cursor:pointer}summary{font-weight:650}pre{font:12px/1.55 ui-monospace,monospace;background:#f5f7fa;padding:12px;white-space:pre-wrap;overflow-wrap:anywhere;max-height:430px;overflow:auto}details details{margin:12px 0;padding-top:10px;border-top:1px solid #e1e8ef}.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.removed{color:#166436;background:#e4f5e9}.added{color:#a12c34;background:#ffe6e8}.hidden{display:none}a{color:#155f99}.comments{min-width:230px;max-width:340px}.hash{word-break:break-all;max-width:240px}@media(max-width:800px){main{padding:12px}.grid{grid-template-columns:1fr}}@media print{.toolbar{display:none}.scroll{max-height:none;overflow:visible}}
</style></head><body><main><h1>Final comparison: Qwen2.5-Coder vs Qwen2.5</h1><p id="subtitle" class="muted"></p><div class="panel"><p><strong>Both conditions receive the same corrupted PM instructions.</strong> Only the Coder model changes. Test Engineer remains <code>qwen2.5:7b</code>. This report shows only new Coder/Test Engineer outputs and their costs—no clean benchmark results or reused upstream costs.</p><p class="warning">“PM detected” means lineage confirmed a changed PM delivery. It does not prove semantic error detection or prevention. Neither condition is a clean control, so differences describe performance under these fixed corruptions, not injection-induced degradation.</p><p>Paired summaries include only completed tasks with verified code/test evidence and matching controlled inputs/settings. Latest attempts supply outcomes; all saved attempts supply actual cost. Unknown metrics remain “—”. Tokens are usage counts, not monetary estimates. Runtime is recorded stage latency, not calendar duration. Different run times/cache states can affect latency.</p></div><div id="cards" class="cards"></div><div class="panel"><h2>Paired test results</h2><div id="aggregate"></div><p id="eligibility" class="muted"></p><h3>Official suite agreement</h3><div id="matrix"></div></div><div class="panel"><h2>Coder + Test Engineer cost only</h2><div id="costs"></div><p class="muted">Latest-pair totals use eligible comparisons. All-attempt totals cover every selected task's saved new calls, including retries. Interrupted requests can consume unreported computation. No first-three-agent costs are included.</p></div><div class="panel"><div class="toolbar"><input id="search" placeholder="Search task or function"><select id="filter"><option value="all">All tasks</option><option value="coder">Raw official: Qwen-Coder only passes</option><option value="qwen">Raw official: Qwen only passes</option><option value="final-coder">Final official: Qwen-Coder only passes</option><option value="final-qwen">Final official: Qwen only passes</option><option value="different">Any different test outcome</option><option value="lineage">Lineage flags / PM not confirmed</option><option value="unverified">Incomplete or unverified comparison</option></select><button id="expand">Expand visible tasks</button><button id="collapse">Collapse tasks</button><button id="csv">Download visible CSV</button></div><p id="shown" class="muted"></p><div class="scroll"><table class="main"><thead><tr><th>Task / function</th><th>Qwen-Coder run<br>attempt / execution</th><th>Qwen run<br>attempt / execution</th><th>Qwen-Coder raw<br>additional passed / total; F; T/U</th><th>Qwen raw<br>additional passed / total; F; T/U</th><th>Raw official<br>Qwen-Coder / Qwen</th><th>Final additional<br>Qwen-Coder / Qwen</th><th>Final official<br>Qwen-Coder / Qwen</th><th>Additional raw checks<br>Qwen-Coder only / Qwen only passes</th><th>Paired evidence</th><th>PM detected<br>Qwen-Coder / Qwen</th><th>Lineage comments</th><th>Latest Coder + Tester<br>Qwen-Coder seconds / tokens</th><th>Latest Coder + Tester<br>Qwen seconds / tokens</th><th>All saved attempts<br>Qwen-Coder seconds / tokens</th><th>All saved attempts<br>Qwen seconds / tokens</th></tr></thead><tbody id="rows"></tbody></table></div></div><h2>Task details</h2><p class="muted">Diff colors: Qwen-Coder/left removed lines green, Qwen/right replacement lines red. Colors identify versions, not correctness.</p><div id="details"></div><div class="panel"><h2>Interpretation</h2><ul><li>“Only passes” means one recorded check passed while the same check failed in the other condition. Timeouts/unresolved outcomes are not converted into failures.</li><li>Raw failed → final passed is a reviewer test recovery within that condition, not proof of a particular reasoning repair.</li><li>Both systems may have inherent errors. Passing the available tests does not establish complete correctness.</li><li>Missing evidence and input differences are displayed and excluded from paired summary statistics, never replaced with older successful attempts.</li><li>This HTML embeds its data, has no external assets, and executes no generated Python. It includes prompts, code and source paths.</li></ul><details><summary>Report provenance</summary><pre id="provenance"></pre></details></div><noscript>JavaScript is required to display this report's embedded data.</noscript></main><script id="data" type="application/json">__DATA__</script><script>
'use strict';const D=JSON.parse(document.getElementById('data').textContent),S=D.summary,rows=D.rows,$=id=>document.getElementById(id),esc=x=>String(x??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const names={coder_model:'Qwen-Coder Coder',qwen_model:'Qwen Coder'},arts={attacked_coder:'Raw Coder',attacked_final:'Reviewed final'},num=x=>x==null?'—':Number(x).toLocaleString('en-US',{maximumFractionDigits:0}),sec=x=>x==null?'—':Number(x).toFixed(3),badge=x=>`<span class="badge ${['passed','verified','YES'].includes(x)?'good':['failed','NO','INCONSISTENT'].includes(x)?'bad':'warn'}">${esc(x||'missing')}</span>`,A=(s,a)=>s.artifacts?.[a]||{},count=a=>a.total==null?'—':`${num(a.passed)} / ${num(a.total)}`,cost=m=>`${sec(m?.seconds)} s<br>${num(m?.tokens)} tokens`;
$('subtitle').textContent=`Generated ${D.generated} · Paired corrupted-PM studies · No inference or test execution`;
const cards=[['Selected task IDs',S.selected],['Reliable paired tasks',S.eligible],['Excluded / incomplete tasks',S.excluded],['PM caught: Qwen-Coder',S.sides.coder_model.pm_detected],['PM caught: Qwen',S.sides.qwen_model.pm_detected],['Reviewer official recoveries: Qwen-Coder',S.sides.coder_model.reviewer_pass_after_raw_failure],['Reviewer official recoveries: Qwen',S.sides.qwen_model.reviewer_pass_after_raw_failure]];$('cards').innerHTML=cards.map(([a,b])=>`<div class="card"><div class="muted">${esc(a)}</div><div class="big">${esc(b)}</div></div>`).join('');
$('aggregate').innerHTML='<table><thead><tr><th>Artifact</th><th>Qwen-Coder official passed / paired tasks</th><th>Qwen official passed / paired tasks</th><th>Qwen-Coder additional passed / total</th><th>Qwen additional passed / total</th></tr></thead><tbody>'+Object.entries(arts).map(([a,n])=>{const x=S.sides.coder_model.artifacts[a],y=S.sides.qwen_model.artifacts[a];return `<tr><td>${n}</td><td>${x.official_passed} / ${S.eligible}</td><td>${y.official_passed} / ${S.eligible}</td><td>${x.additional_passed} / ${x.additional_total}</td><td>${y.additional_passed} / ${y.additional_total}</td></tr>`}).join('')+'</tbody></table>';$('eligibility').textContent=`${S.excluded} tasks excluded from aggregate paired results. All selected tasks remain visible below.`;
$('matrix').innerHTML='<table><thead><tr><th>Artifact</th><th>Both pass</th><th>Qwen-Coder only passes</th><th>Qwen only passes</th><th>Both fail</th></tr></thead><tbody>'+Object.entries(arts).map(([a,n])=>{const m=S.matrices[a];return `<tr><td>${n}</td><td>${m.both_pass||0}</td><td>${m.coder_only||0}</td><td>${m.qwen_only||0}</td><td>${m.both_fail||0}</td></tr>`}).join('')+'</tbody></table>';
function costrow(label,m){return `<tr><td>${esc(label)}</td><td>${sec(m?.seconds)}</td><td>${num(m?.prompt)}</td><td>${num(m?.completion)}</td><td>${num(m?.tokens)}</td></tr>`}
$('costs').innerHTML='<table><thead><tr><th>Scope</th><th>Seconds</th><th>Prompt tokens</th><th>Completion tokens</th><th>Total tokens</th></tr></thead><tbody>'+Object.entries(names).map(([s,n])=>costrow(n+': latest eligible pairs',S.sides[s].latest_cost)+costrow(n+': all saved attempts',S.sides[s].all_attempts_cost)).join('')+costrow('Qwen minus Qwen-Coder: latest eligible pairs',S.cost_delta)+'</tbody></table>'+Object.entries(names).map(([s,n])=>{const v=S.sides[s];return `<p class="muted">${n}: ${v.calls} recorded new calls; ${v.missing_token_calls} missing token counters; ${v.missing_attempt_traces} missing attempt traces; known token subtotal ${num(v.known_tokens)}; known call seconds ${sec(v.known_seconds)}.</p>`}).join('');
function row(r){const x=r.sides.coder_model,y=r.sides.qwen_model,a=A(x,'attacked_coder'),b=A(y,'attacked_coder'),f=A(x,'attacked_final'),g=A(y,'attacked_final'),w=r.wins.attacked_coder||{};return `<tr data-index="${r.index}"><td><a class="link" data-index="${r.index}" href="#task-${r.index}">${esc(r.task_id)}</a><br>${esc(r.entry_point)}</td><td>${esc(x.attempt)}<br>${esc(x.execution)}</td><td>${esc(y.attempt)}<br>${esc(y.execution)}</td><td>${count(a)}<br>F ${num(a.failed)}; ${num(a.timeout)} / ${num(a.unresolved)}</td><td>${count(b)}<br>F ${num(b.failed)}; ${num(b.timeout)} / ${num(b.unresolved)}</td><td>${badge(a.official)}<br>${badge(b.official)}</td><td>${count(f)}<br>${count(g)}</td><td>${badge(f.official)}<br>${badge(g.official)}</td><td>${w['Qwen-Coder only passes']||0} / ${w['Qwen only passes']||0}</td><td>${badge(r.eligible?'YES':'UNKNOWN')}<br>${esc(r.control_issues.join(' '))}</td><td>${badge(x.lineage?.caught)}<br>${badge(y.lineage?.caught)}</td><td class="comments">Qwen-Coder: ${esc(x.lineage?.comments?.join(' '))}<br>Qwen: ${esc(y.lineage?.comments?.join(' '))}</td><td>${cost(x.latest_cost)}</td><td>${cost(y.latest_cost)}</td><td>${cost(x.all_attempts_cost)}</td><td>${cost(y.all_attempts_cost)}</td></tr>`}
$('rows').innerHTML=rows.map(row).join('');function diffs(t){return String(t||'No data').split('\n').map(l=>`<span class="${l.startsWith('-')&&!l.startsWith('---')?'removed':l.startsWith('+')&&!l.startsWith('+++')?'added':''}">${esc(l)}</span>`).join('\n')}
function detail(r){const x=r.sides.coder_model,y=r.sides.qwen_model;return `<details class="task" id="task-${r.index}" data-index="${r.index}"><summary>${esc(r.task_id)} · ${esc(r.entry_point)} · paired evidence ${r.eligible?'verified':'incomplete/unverified'}</summary><p>${esc(r.control_issues.join(' '))}</p><div class="grid">${Object.entries(names).map(([s,n])=>`<div><h3>${n}</h3><p>${esc(r.sides[s].folder)}</p><p>${esc(r.sides[s].review_outcome)}</p><p class="warning">${esc(r.sides[s].issues.join(' ')||'Code/test/input evidence checks passed.')}</p></div>`).join('')}</div><h3>Per-operation time and token usage</h3><div class="scroll"><table><thead><tr><th>Operation</th><th>Condition / model</th><th>Seconds</th><th>Prompt tokens</th><th>Completion tokens</th><th>Total tokens</th></tr></thead><tbody>${['coder','test_engineer'].map(role=>Object.entries(names).map(([s,n])=>{const m=r.sides[s].operations[role]||{};return `<tr><td>${role==='coder'?'Coder':'Test Engineer'}</td><td>${n}<br>${esc(m.model)}</td><td>${sec(m.seconds)}</td><td>${num(m.prompt)}</td><td>${num(m.completion)}</td><td>${num(m.tokens)}</td></tr>`}).join('')).join('')}</tbody></table></div><table><thead><tr><th>Complete-example scope: Coder + Test Engineer only</th><th>Seconds</th><th>Prompt tokens</th><th>Completion tokens</th><th>Total tokens</th></tr></thead><tbody>${Object.entries(names).map(([s,n])=>costrow(n+': latest attempt',r.sides[s].latest_cost)+costrow(n+': all attempts',r.sides[s].all_attempts_cost)).join('')}${costrow('Qwen minus Qwen-Coder: latest attempt',r.cost_delta)}</tbody></table><p class="muted">Latest elapsed attempt wall time (Docker/orchestration included): Qwen-Coder ${sec(x.wall_seconds)} s; Qwen ${sec(y.wall_seconds)} s.</p><details><summary>Identical corrupted PM / control checks</summary><pre>${esc(JSON.stringify({control_issues:r.control_issues,qwen_coder_pm_hash:x.pm_corrupted_hash,qwen_pm_hash:y.pm_corrupted_hash,qwen_coder_settings:x.role_settings,qwen_settings:y.role_settings},null,2))}</pre><pre>${esc(x.contents.corrupted_pm)}</pre><pre>${diffs(r.pm_diff)}</pre></details><details><summary>Raw Coder code comparison</summary><div class="grid"><pre>${esc(x.contents.attacked_coder)}</pre><pre>${esc(y.contents.attacked_coder)}</pre></div><pre>${diffs(r.raw_diff)}</pre></details><details><summary>Reviewed final code comparison</summary><div class="grid"><pre>${esc(x.contents.attacked_final)}</pre><pre>${esc(y.contents.attacked_final)}</pre></div><pre>${diffs(r.final_diff)}</pre></details><details><summary>Reviewer edits within each condition</summary><div class="grid"><div><h3>Qwen-Coder condition</h3><pre>${diffs(x.review_diff)}</pre></div><div><h3>Qwen condition</h3><pre>${diffs(y.review_diff)}</pre></div></div></details><details><summary>Individual official and additional checks</summary><div class="scroll"><table><thead><tr><th>Artifact / check</th><th>Qwen-Coder</th><th>Qwen</th><th>Comparison</th></tr></thead><tbody>${r.tests.map(c=>`<tr><td>${arts[c.artifact]}<br>${esc(c.kind)}: ${esc(c.name)}</td>${['coder_model','qwen_model'].map(s=>{const v=c[s];return `<td>${badge(v.status)}<br>${esc(v.error||v.reason||'')}${v.actual_repr!=null?'<br>Actual: '+esc(v.actual_repr):''}${v.expected_literal!=null?'<br>Expected: '+esc(v.expected_literal):''}</td>`}).join('')}<td>${esc(c.result)}</td></tr>`).join('')}</tbody></table></div></details><details><summary>PM detection and other lineage flags</summary><div class="grid">${Object.entries(names).map(([s,n])=>`<div><h3>${n}</h3><p>${badge(r.sides[s].lineage?.caught)}</p><pre>${esc(JSON.stringify(r.sides[s].lineage,null,2))}</pre></div>`).join('')}</div></details><details><summary>Attempts / all saved new calls</summary><div class="grid"><pre>${esc(JSON.stringify(x.attempts,null,2))}</pre><pre>${esc(JSON.stringify(y.attempts,null,2))}</pre></div></details></details>`}
$('details').innerHTML=rows.map(detail).join('');$('provenance').textContent=JSON.stringify(D.provenance,null,2);let visible=rows;
function apply(){const q=$('search').value.toLowerCase(),f=$('filter').value;visible=rows.filter(r=>{if(![r.task_id,r.entry_point,...r.control_issues].join(' ').toLowerCase().includes(q))return false;const x=r.sides.coder_model,y=r.sides.qwen_model;let art=f.startsWith('final-')?'attacked_final':'attacked_coder';const a=A(x,art).official,b=A(y,art).official;if(f==='coder'||f==='final-coder')return a==='passed'&&b==='failed';if(f==='qwen'||f==='final-qwen')return a==='failed'&&b==='passed';if(f==='unverified')return !r.eligible;if(f==='different')return r.tests.some(c=>c.coder_model.status!==c.qwen_model.status);if(f==='lineage')return Object.values(r.sides).some(s=>s.lineage?.caught!=='YES'||s.lineage?.other?.length);return true});const ids=new Set(visible.map(r=>String(r.index)));document.querySelectorAll('tr[data-index],details.task').forEach(e=>e.classList.toggle('hidden',!ids.has(e.dataset.index)));$('shown').textContent=`Showing ${visible.length} / ${rows.length} tasks. Summary totals remain for the whole study.`}
$('search').addEventListener('input',apply);$('filter').addEventListener('change',apply);apply();document.addEventListener('click',e=>{const a=e.target.closest('.link');if(a)$('task-'+a.dataset.index).open=true});$('expand').onclick=()=>visible.forEach(r=>$('task-'+r.index).open=true);$('collapse').onclick=()=>document.querySelectorAll('details.task').forEach(e=>e.open=false);
$('csv').onclick=()=>{const heads=['task','paired_evidence','coder_model_raw_official','qwen_model_raw_official','coder_model_final_official','qwen_model_final_official','coder_model_seconds','qwen_model_seconds','coder_model_tokens','qwen_model_tokens','coder_model_pm_detected','qwen_model_pm_detected','control_issues'];const data=visible.map(r=>{const x=r.sides.coder_model,y=r.sides.qwen_model;return [r.task_id,r.eligible,A(x,'attacked_coder').official,A(y,'attacked_coder').official,A(x,'attacked_final').official,A(y,'attacked_final').official,x.latest_cost?.seconds,y.latest_cost?.seconds,x.latest_cost?.tokens,y.latest_cost?.tokens,x.lineage?.caught,y.lineage?.caught,r.control_issues.join(' ')]});const quote=v=>{let s=String(v??'');if(typeof v==='string'&&/^[=+@\-\t\r]/.test(s))s="'"+s;return '"'+s.replace(/"/g,'""')+'"'};const b=new Blob(['\ufeff'+[heads,...data].map(r=>r.map(quote).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'}),u=URL.createObjectURL(b),a=document.createElement('a');a.href=u;a.download='qwen_coder_vs_qwen.csv';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)};
</script></body></html>'''


def build(coder_folder,qwen_folder,project,output):
 folders={'coder_model':coder_folder,'qwen_model':qwen_folder};states={k:read(p/'study.json') for k,p in folders.items()}
 for key,state in states.items():
  if state.get('schema_version')!=SCHEMAS[key]:raise ValueError(f'{key}: unexpected study schema.')
  ids=state.get('indices',[])
  if not all(isinstance(i,int) and not isinstance(i,bool) and i>=0 for i in ids) or len(ids)!=len(set(ids)):raise ValueError('Invalid/duplicate task indices.')
 dataset_hash=sha((project/'data/HumanEval.jsonl').read_bytes());rows=[]
 indices=sorted(set(states['coder_model']['indices'])|set(states['qwen_model']['indices']))
 for i in indices:
  sides={}
  for key,folder in folders.items():
   try:sides[key]=load_side(folder,states[key],i,project,dataset_hash)
   except (ValueError,OSError,KeyError,TypeError) as exc:sides[key]=dict(task_id=f'HumanEval/{i}',execution='report_evidence_error',attempt=None,issues=[str(exc)],verified=False,artifacts={},checks={},operations={},contents={},lineage={},calls=[],attempts=[])
  rows.append(compare(i,sides,states))
 data=dict(generated=datetime.now(timezone.utc).isoformat(),rows=rows,summary=summary(rows),provenance=dict(
  studies={k:dict(path=str(p),status=states[k].get('status'),study_sha256=sha((p/'study.json').read_bytes())) for k,p in folders.items()},
  selected_input_hashes={r['task_id']:{s:v.get('input_hashes',{}) for s,v in r['sides'].items()} for r in rows},
  project=str(project),generator_sha256=sha(Path(__file__).read_bytes()),dataset_sha256=dataset_hash,
  selection='Union of selected task IDs; latest attempt per side; all attempts for actual new-call cost.',
  no_clean_benchmark_included=True,model_calls_performed=0,tests_executed=False))
 payload=json.dumps(data,ensure_ascii=False,allow_nan=False).replace('&','\\u0026').replace('<','\\u003c').replace('>','\\u003e').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
 output.parent.mkdir(parents=True,exist_ok=True);temp=output.with_suffix('.html.tmp');temp.write_text(HTML.replace('__DATA__',payload),encoding='utf-8');temp.replace(output)
 return data


def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--project',type=Path,default=HERE.parents[1],help='mixed-model-baseline-v1 folder')
 parser.add_argument('--coder-study',type=Path,help='Old corrupted run with qwen2.5-coder:7b Coder')
 parser.add_argument('--qwen-study',type=Path,help='New all-Qwen corrupted run; auto-select unique full study if omitted')
 parser.add_argument('--output',type=Path,default=HERE/'runs/final comparison qwen coder vs qwen.html')
 args=parser.parse_args();project=args.project.resolve()
 old=(args.coder_study or project/'runs/pm-replay-20261030T190256124954Z').resolve()
 if args.qwen_study:new=args.qwen_study.resolve()
 else:
  candidates=[]
  for p in (HERE/'runs').glob('all-qwen-pm-*'):
   if (p/'study.json').is_file():
    s=read(p/'study.json')
    if s.get('schema_version')==SCHEMAS['qwen_model'] and s.get('indices')==list(range(164)):candidates.append(p)
  if len(candidates)!=1:parser.error('Expected exactly one full all-Qwen study. Specify --qwen-study with its actual folder. Found: '+', '.join(str(p) for p in candidates))
  new=candidates[0].resolve()
 if args.output.suffix.lower()!='.html':parser.error('--output must end in .html')
 data=build(old,new,project,args.output.resolve())
 print('Report:',args.output.resolve());print('Selected tasks:',data['summary']['selected'],'Reliable paired comparisons:',data['summary']['eligible'])
 print('Compared only corrupted-PM runs. No models or Docker tests were run.')


if __name__=='__main__':main()
