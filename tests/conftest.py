import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Point the app at a temp data dir before app.config is imported.
_tmpdir = tempfile.mkdtemp(prefix="pmai-test-")
os.environ["PMAI_DATA_DIR"] = _tmpdir
os.environ.pop("ANTHROPIC_API_KEY", None)

import pytest  # noqa: E402

from app import db as dbmod  # noqa: E402
from app.seed import run_seeds  # noqa: E402


@pytest.fixture()
def conn():
    dbmod.init_db()
    c = dbmod.connect()
    run_seeds(c)
    c.commit()  # the app reads through its own connections; seeds must be visible
    try:
        yield c
        c.commit()
    finally:
        c.close()
