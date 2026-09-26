from __future__ import annotations
import subprocess, sys
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]
CLI=[sys.executable,str(ROOT/'tools'/'uaf.py')]
KINDS=['automation','frontend','backend','data','fullstack']

def run(*args): return subprocess.run([*CLI,*map(str,args)],capture_output=True,text=True,timeout=20)

def test_v27_field_archetypes(tmp_path):
    for i, kind in enumerate(KINDS):
        r=tmp_path/f'p{i}'
        p=run('init',r,'--profile','full','--extension','v2.7','--name',kind,'--type',kind)
        assert p.returncode==0,p.stdout+p.stderr
        m=yaml.safe_load((r/'.ai/manifest.yaml').read_text())
        assert m['framework']['version']=='2.7.0'
        assert m['extensions']['version']=='2.7'
        assert (r/'.ai/federation/secure/KEY-STORAGE.yaml').exists()
        assert (r/'.ai/federation/secure/LIFECYCLE.yaml').exists()
