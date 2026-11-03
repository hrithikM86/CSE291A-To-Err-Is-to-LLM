"""Local copies of the existing atomic-save, Ollama identity and cleanup helpers."""
import json
import urllib.request
from urllib.parse import urlsplit, urlunsplit
import warnings

def save(path, value):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2),encoding='utf-8')
    temporary.replace(path)

def model_identity(model_config):
    url=urlsplit(model_config['base_url'])
    endpoint=urlunsplit((url.scheme,url.netloc,'/api/tags','',''))
    with urllib.request.urlopen(endpoint,timeout=15) as response:
        available=json.load(response)['models']
    match=next((m for m in available if model_config['model'] in [m.get('name'),m.get('model')]),None)
    if match is None:raise RuntimeError('Configured model not found in Ollama; pull it before running.')
    return dict(name=match.get('name'),digest=match.get('digest'),details=match.get('details'))

async def close_model_clients(providers):
    """Close owned HTTP clients on their live event loop; never change results."""
    closed=set()
    for provider in providers:
        client=getattr(provider,'aclient',None)
        if client is None or id(client) in closed:
            continue
        closed.add(id(client))
        try:
            await client.close()
        except Exception as exc:
            warnings.warn(f'Model connection cleanup failed: {type(exc).__name__}: {exc}',RuntimeWarning)
