from __future__ import annotations
import subprocess, sys
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]
CLI=[sys.executable,str(ROOT/'tools'/'uaf.py')]

def run(*args):
    return subprocess.run([*CLI,*map(str,args)],capture_output=True,text=True,timeout=15)

def test_field_archetypes(tmp_path):
    kinds={
      'script': ['main.py'],
      'frontend': ['package.json','src/main.js'],
      'backend': ['pyproject.toml','server.py'],
      'data': ['requirements.txt','pipeline.py'],
      'fullstack': ['package.json','server.py','src/main.js','schema.sql'],
    }
    for kind, files in kinds.items():
        src=tmp_path/kind
        src.mkdir()
        for rel in files:
            p=src/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text('{}' if p.suffix=='.json' else '')
        dest=src
        p=run('init',dest,'--profile','full','--extension','v2.8','--name',kind,'--type',kind)
        assert p.returncode==0,p.stdout+p.stderr
        m=yaml.safe_load((dest/'.ai/manifest.yaml').read_text())
        assert m['framework']['version']=='2.8.0'
        assert m['extensions']['version']=='2.8'
        assert (dest/'.ai/federation/secure/KEY-PROVIDERS.yaml').exists()
        assert (dest/'.ai/federation/secure/KEY-CUSTODY.md').exists()

def test_git_project_smoke(tmp_path):
    root=tmp_path/'gitproj'; root.mkdir(); (root/'README.md').write_text('project')
    subprocess.run(['git','init','-q',str(root)],check=True)
    p=run('init',root,'--profile','full','--extension','v2.8','--name','GitV28','--type','fullstack')
    assert p.returncode==0,p.stdout+p.stderr
    p=run('check',root,'--level','full')
    assert 'CONF-V28-' not in p.stdout
