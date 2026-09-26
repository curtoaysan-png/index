import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db  # noqa: E402


@pytest.fixture(params=["sqlite"] + (["postgres"] if os.environ.get("ARMADIO_TEST_PG") else []))
def conn(request, tmp_path):
    """Database vuoto: SQLite sempre, Postgres se ARMADIO_TEST_PG è impostata."""
    if request.param == "sqlite":
        c = db.connetti(tmp_path / "t.db")
        yield c
        c.close()
        return
    c = db.ConnessionePg(os.environ["ARMADIO_TEST_PG"])
    for tabella in db.TABELLE:
        c.execute(f"DROP TABLE IF EXISTS {tabella}")
    c.commit()
    c.close()
    db._pg.clear()
    c = db._connessione_pg(os.environ["ARMADIO_TEST_PG"])
    yield c
    c.close()
    db._pg.clear()
