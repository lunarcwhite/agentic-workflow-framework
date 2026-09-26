def test_health() -> None:
    from src.health import health
    assert health() == "ok"
