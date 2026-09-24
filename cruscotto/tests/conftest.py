import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db  # noqa: E402


@pytest.fixture
def conn(tmp_path):
    c = db.connetti(tmp_path / "test.db")
    yield c
    c.close()
