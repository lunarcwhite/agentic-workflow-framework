from __future__ import annotations
import subprocess, sys
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]
CLI=[sys.executable,str(ROOT/"tools/uaf.py")]
ARCHES=["automation","frontend","backend","data","fullstack"]
def test_field_archetypes(tmp_path):
    for arch in ARCHES:
        root=tmp_path/arch;root.mkdir()
        signals={"automation":"script.py","frontend":"vite.config.js","backend":"artisan","data":"etl.py","fullstack":"package.json"}
        (root/signals[arch]).write_text("{}",encoding="utf-8")
        p=subprocess.run([*CLI,"init",str(root),"--profile","full","--extension","v2.3","--auto-detect","--docs","auto"],capture_output=True,text=True,timeout=20)
        assert p.returncode==0,p.stdout+p.stderr
        m=yaml.safe_load((root/".ai/manifest.yaml").read_text())
        assert m["extensions"]["version"]=="2.3"
        assert m["protocols"]["federation_policy"]=="UAAF-FED-2.3"
        assert (root/".ai/federation/negotiation").exists()
