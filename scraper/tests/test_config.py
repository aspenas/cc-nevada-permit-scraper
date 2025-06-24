import os
import pytest
from scraper.config import get_database_url

def test_get_database_url_env(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///test.db')
    assert get_database_url() == 'sqlite:///test.db'

def test_get_database_url_missing(monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.delenv('DB_SECRET_NAME', raising=False)
    monkeypatch.delenv('AWS_REGION', raising=False)
    # Should raise since no env or AWS secret
    with pytest.raises(RuntimeError):
        get_database_url() 