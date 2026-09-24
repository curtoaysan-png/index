import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db  # noqa: E402

# Per provare anche Postgres: CRUSCOTTO_TEST_PG=postgresql://... python -m pytest
PG_URL = os.environ.get("CRUSCOTTO_TEST_PG")


@pytest.fixture(params=["sqlite", "postgres"])
def conn(request, tmp_path, monkeypatch):
    if request.param == "sqlite":
        monkeypatch.delenv("DATABASE_URL", raising=False)
        c = db.connetti(tmp_path / "test.db")
        yield c
        c.close()
        return
    if not PG_URL:
        pytest.skip("CRUSCOTTO_TEST_PG non impostata")
    import psycopg
    with psycopg.connect(PG_URL, autocommit=True) as pulizia:
        pulizia.execute("DROP TABLE IF EXISTS " + ", ".join(db.TABELLE) + " CASCADE")
    db._pg.clear()
    monkeypatch.setenv("DATABASE_URL", PG_URL)
    c = db.connetti()
    yield c
    c.close()
    db._pg.clear()
