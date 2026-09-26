from pathlib import Path
import tempfile, subprocess, sys, yaml
ROOT=Path(__file__).resolve().parents[1]; CLI=[sys.executable,str(ROOT/'tools/uaf.py')]
def run(*args,timeout=20): return subprocess.run([*CLI,*map(str,args)],capture_output=True,text=True,timeout=timeout)
archetypes=[
 ('script', {'main.py':'print(1)'}),
 ('frontend', {'package.json':'{}','src/components/App.jsx':'export default function App(){}'}),
 ('backend', {'app/main.py':'print("api")'}),
 ('data', {'pipeline/job.py':'print("etl")','notebooks/demo.ipynb':'{}'}),
 ('infra', {'Dockerfile':'FROM python:3.12-slim'}),
]
with tempfile.TemporaryDirectory(prefix='uaf29-field-') as td:
 base=Path(td)
 for name,files in archetypes:
  r=base/name; r.mkdir()
  for rel,content in files.items():
   p=r/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
  q=run('init',r,'--profile','full','--extension','v2.9','--name',name,'--type',name,'--auto-detect')
  assert q.returncode==0,q.stdout+q.stderr
  m=yaml.safe_load((r/'.ai/manifest.yaml').read_text())
  assert m['framework']['version']=='2.9.0' and m['extensions']['version']=='2.9'
  assert (r/'.ai/federation/secure/KEY-OPERATIONS-AUDIT.jsonl').exists()
 # preserve existing user file on forced reinit
 r=base/'preserve'; r.mkdir(); (r/'README.user.md').write_text('KEEP')
 assert run('init',r,'--profile','full','--extension','v2.9','--force','--name','preserve','--type','utility').returncode==0
 assert (r/'README.user.md').read_text()=='KEEP'
 # downgrade preserves v2.8 custody while removing v2.9 operations
 assert run('init',r,'--profile','full','--extension','v2.8','--force','--name','preserve','--type','utility').returncode==0
 assert not (r/'.ai/federation/secure/KEY-OPERATIONS-AUDIT.jsonl').exists()
 assert (r/'.ai/federation/secure/KEY-PROVIDERS.yaml').exists()
print('FIELD 5/5 + PRESERVE + DOWNGRADE PASS')
