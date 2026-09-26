from __future__ import annotations
import shutil, subprocess, sys
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]; CLI=[sys.executable,str(ROOT/'tools/uaf.py')]
ARCHETYPES={
    'script': {},
    'frontend': {'src/components/Button.tsx':'export const Button=()=>null;','package.json':'{}'},
    'backend': {'app/main.py':'def app(): pass'},
    'data': {'etl.py':'print("etl")'},
    'infrastructure': {'Dockerfile':'FROM python:3.13'},
}

def test_v24_field_archetypes(tmp_path):
    for name, files in ARCHETYPES.items():
        root=tmp_path/name; root.mkdir()
        for rel, content in files.items():
            p=root/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(content)
        p=subprocess.run([*CLI,'init',str(root),'--profile','full','--auto-detect','--extension','v2.4','--name',name,'--type',name],capture_output=True,text=True,timeout=20)
        assert p.returncode==0,p.stdout+p.stderr
        m=yaml.safe_load((root/'.ai/manifest.yaml').read_text())
        assert str(m['extensions']['version'])=='2.4'
        assert m['protocols']['federation_protocol']=='UAAF-FED-2.4'
        assert (root/'.ai/federation/protocol/CAPABILITIES.yaml').exists()
