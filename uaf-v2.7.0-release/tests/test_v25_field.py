from __future__ import annotations
import subprocess, sys, yaml
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CLI=[sys.executable,str(ROOT/'tools/uaf.py')]
ARCHETYPES=['automation','frontend','backend','data','fullstack']

def test_five_archetypes_initialize_v25(tmp_path):
    for kind in ARCHETYPES:
        p=tmp_path/kind; p.mkdir()
        if kind=='frontend': (p/'package.json').write_text('{}'); (p/'src/components').mkdir(parents=True)
        if kind=='backend': (p/'app/main.py').parent.mkdir(parents=True); (p/'app/main.py').write_text('')
        if kind=='data': (p/'pipelines').mkdir()
        if kind=='fullstack': (p/'package.json').write_text('{}'); (p/'src/components').mkdir(parents=True); (p/'artisan').write_text('')
        args=[*CLI,'init',str(p),'--profile','full','--extension','v2.5','--name',kind,'--type',kind]
        r=subprocess.run(args,capture_output=True,text=True,timeout=20); assert r.returncode==0,r.stdout+r.stderr
        m=yaml.safe_load((p/'.ai/manifest.yaml').read_text())
        assert str(m['extensions']['version'])=='2.5'
        assert m['protocols']['federation_transport']=='UAAF-FED-2.5'
        assert (p/'.ai/federation/transport/CHANNELS').exists()
