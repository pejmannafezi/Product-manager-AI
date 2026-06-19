import sqlite3
from contextlib import contextmanager

from app import config


def connect() -> sqlite3.Connection:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: FastAPI may open the per-request connection in a
    # threadpool thread and use it from an async endpoint; each request still
    # gets its own connection, so there is no concurrent sharing.
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# Columns added to pre-existing tables after their original CREATE. SQLite has no
# "ADD COLUMN IF NOT EXISTS", so init_db() adds any that are missing (idempotent).
_COLUMN_MIGRATIONS = {
    "projects": [("requirements", "TEXT"), ("stakeholders", "TEXT"), ("resourcing", "TEXT")],
    "tasks": [("depends_on", "TEXT"), ("is_critical", "INTEGER DEFAULT 0"), ("milestone_id", "INTEGER")],
    "checklist_items": [("carried_over", "INTEGER DEFAULT 0")],
}


def _ensure_columns(conn):
    for table, cols in _COLUMN_MIGRATIONS.items():
        existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        for name, decl in cols:
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")


def init_db():
    conn = connect()
    try:
        conn.executescript(config.SCHEMA_PATH.read_text(encoding="utf-8"))
        _ensure_columns(conn)
        conn.commit()
    finally:
        conn.close()


def get_db():
    """FastAPI dependency yielding a per-request connection."""
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


@contextmanager
def db_session():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def query(conn, sql, params=()):
    return conn.execute(sql, params).fetchall()


def query_one(conn, sql, params=()):
    return conn.execute(sql, params).fetchone()


def execute(conn, sql, params=()):
    cur = conn.execute(sql, params)
    return cur.lastrowid


def get_setting(conn, key, default=None):
    row = query_one(conn, "SELECT value FROM settings WHERE key=?", (key,))
    return row["value"] if row else default


def set_setting(conn, key, value):
    conn.execute(
        "INSERT INTO settings(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )
