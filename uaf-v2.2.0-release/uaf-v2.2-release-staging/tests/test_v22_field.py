from __future__ import annotations
import subprocess, sys
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]; CLI=[sys.executable,str(ROOT/'tools/uaf.py')]
ARCHETYPES=['script','frontend','backend','data','fullstack']
def test_v22_field_archetypes(tmp_path):
    for name in ARCHETYPES:
        root=tmp_path/name
        root.mkdir()
        if name=='frontend': (root/'package.json').write_text('{"dependencies":{"react":"1"}}')
        elif name=='backend': (root/'requirements.txt').write_text('fastapi\n')
        elif name=='data': (root/'pipeline.py').write_text('print(1)')
        elif name=='fullstack':
            (root/'package.json').write_text('{"dependencies":{"react":"1"}}')
            (root/'requirements.txt').write_text('fastapi\n')
        p=subprocess.run([*CLI,'init',root,'--profile','full','--auto-detect','--extension','v2.2','--docs','auto'],capture_output=True,text=True,timeout=15)
        assert p.returncode==0,p.stdout+p.stderr
        m=yaml.safe_load((root/'.ai/manifest.yaml').read_text())
        assert m['framework']['version']=='2.2.0'
        assert (m.get('protocols') or {}).get('federation_intelligence')=='UAAF-FED-2.2'
        for rel in ['.ai/federation/policy/INHERITANCE.yaml','.ai/federation/intelligence/CONFLICT-ANALYSIS.yaml']:
            assert (root/rel).exists()
