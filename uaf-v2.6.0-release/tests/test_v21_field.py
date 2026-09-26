from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "tools/uaf_init.py"
DOCTOR = ROOT / "tools/uaf_doctor.py"
CASES = {
    "automation": ["backup.py"],
    "frontend": ["package.json", "src/components/Button.tsx"],
    "backend": ["requirements.txt", "openapi.yaml", "app/main.py", "tests/test_api.py"],
    "data": ["pyproject.toml", "pipeline/job.py", "migrations/001.sql"],
    "complex": ["package.json", "prisma/schema.prisma", ".github/workflows/ci.yml", "android/README.md", "src/components/App.tsx", "tests/test_app.ts"],
}

def run(*args: str):
    return subprocess.run([sys.executable, *args], text=True, capture_output=True)

def test_v21_full_archetypes(tmp_path: Path):
    for name, files in CASES.items():
        project = tmp_path / name
        for rel in files:
            fp = project / rel
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text("# v2.1 field fixture\n", encoding="utf-8")
        p = run(str(INIT), str(project), "--profile", "full", "--auto-detect", "--extension", "v2.1", "--docs", "auto")
        assert p.returncode == 0, p.stdout + p.stderr
        manifest = yaml.safe_load((project / ".ai/manifest.yaml").read_text())
        assert str(manifest["extensions"]["version"]) == "2.1"
        assert manifest["protocols"]["federation_ops"] == "UAAF-FED-2.1"
        ops = project / ".ai/federation/ops"
        assert (ops / "MODE.yaml").exists()
        assert (ops / "REVOCATIONS.yaml").exists()
        assert (ops / "CHECKPOINTS.yaml").exists()
