from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.health import health


def test_health() -> None:
    assert health() == {"status": "ok", "project": "northstar"}
