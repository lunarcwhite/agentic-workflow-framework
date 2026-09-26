from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "tools/uaf_init.py"
CHECK = ROOT / "tools/uaf_check.py"
RCE = ROOT / "tools/uaf_reconcile.py"


CASES = {
    "automation": {
        "profile": "minimal",
        "files": ["backup.py"],
        "true": [],
        "false": ["frontend", "backend", "api", "database", "mobile", "data"],
        "docs": [],
    },
    "frontend": {
        "profile": "standard",
        "files": ["package.json", "src/components/Button.tsx"],
        "true": ["frontend", "ui", "design_system"],
        "false": ["backend", "api", "database", "mobile"],
        "docs": ["docs/architecture/ARCHITECTURE.md", "docs/design/DESIGN.md"],
    },
    "backend": {
        "profile": "standard",
        "files": ["requirements.txt", "openapi.yaml", "app/main.py", "tests/test_api.py"],
        "true": ["backend", "api", "testing"],
        "false": ["frontend", "ui", "database", "mobile"],
        "docs": ["docs/architecture/ARCHITECTURE.md", "docs/development/API.md", "docs/quality/TESTING.md"],
    },
    "data": {
        "profile": "standard",
        "files": ["pyproject.toml", "pipeline/job.py", "migrations/001.sql"],
        "true": ["data", "database"],
        "false": ["backend", "frontend", "api", "mobile"],
        "docs": ["docs/architecture/ARCHITECTURE.md", "docs/data/DATABASE-SCHEMA.md"],
    },
    "complex": {
        "profile": "full",
        "files": ["package.json", "prisma/schema.prisma", ".github/workflows/ci.yml", "android/README.md", "src/components/App.tsx", "tests/test_app.ts"],
        "true": ["frontend", "ui", "design_system", "database", "mobile", "testing", "infrastructure", "deployment"],
        "false": ["backend", "api"],
        "docs": ["docs/architecture/ARCHITECTURE.md", "docs/design/DESIGN.md", "docs/data/DATABASE-SCHEMA.md", "docs/operations/DEPLOYMENT.md", "docs/quality/TESTING.md"],
    },
}


def run(*args: str):
    return subprocess.run([sys.executable, *args], text=True, capture_output=True)


def test_representative_project_archetypes(tmp_path: Path):
    for name, case in CASES.items():
        project = tmp_path / name
        for rel in case["files"]:
            fp = project / rel
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text("# field-validation fixture\n", encoding="utf-8")
        init = run(str(INIT), str(project), "--profile", case["profile"], "--name", name, "--auto-detect", "--docs", "auto")
        assert init.returncode == 0, init.stderr
        manifest = yaml.safe_load((project / ".ai/manifest.yaml").read_text(encoding="utf-8"))
        caps = manifest["capabilities"]
        for cap in case["true"]:
            assert caps[cap] is True, (name, cap, caps)
        for cap in case["false"]:
            assert caps[cap] is False, (name, cap, caps)
        check = run(str(CHECK), str(project), "--level", case["profile"])
        assert check.returncode == 0, check.stdout
        rce = run(str(RCE), str(project))
        assert rce.returncode == 0, rce.stdout
        assert rce.stdout.splitlines()[0] == "CONSISTENT"
        for rel in case["docs"]:
            assert (project / rel).exists(), (name, rel)
