from pathlib import Path
import subprocess, sys, yaml
import pytest

ROOT = Path(__file__).resolve().parents[1]
CLI = [sys.executable, str(ROOT / 'tools' / 'uaf.py')]

@pytest.mark.parametrize('kind', ['script', 'frontend', 'backend', 'data', 'fullstack'])
def test_v26_field_archetype(tmp_path, kind):
    root = tmp_path / kind
    p = subprocess.run([*CLI, 'init', str(root), '--profile', 'full', '--extension', 'v2.6', '--name', kind, '--type', kind], capture_output=True, text=True, timeout=20)
    assert p.returncode == 0, p.stdout + p.stderr
    m = yaml.safe_load((root / '.ai/manifest.yaml').read_text())
    assert m['framework']['version'] == '2.6.0'
    assert m['extensions']['version'] == '2.6'
    assert (root / '.ai/federation/secure/CONFIG.yaml').exists()
