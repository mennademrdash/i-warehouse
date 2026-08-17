import os
import sqlite3
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "devices.db")


def init_db():
    conn = sqlite3.connect(DB_NAME, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")
    conn.execute("PRAGMA temp_store=MEMORY")

    cur = conn.cursor()
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_devices_name "
        "ON devices(name COLLATE NOCASE)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_devices_tags ON devices(tags)"
    )

    cur.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name='users'"
    )
    if cur.fetchone():
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)"
        )

    conn.commit()
    conn.close()


@contextmanager
def get_db():
    conn = sqlite3.connect(
        DB_NAME,
        timeout=30,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
