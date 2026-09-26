"""Minimal Northstar reference application surface."""


def health() -> dict[str, str]:
    return {"status": "ok", "project": "northstar"}
