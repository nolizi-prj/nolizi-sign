"""Tests for lazy database engine construction in app.db."""

import pytest

from app import db as db_module


def test_get_engine_raises_when_database_url_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Engine construction must fail loudly, not silently fall back to a local default."""
    monkeypatch.setattr(db_module.settings, "database_url", "")
    db_module.get_engine.cache_clear()

    with pytest.raises(RuntimeError, match="DATABASE_URL is not set"):
        db_module.get_engine()
