import os
import sqlite3
from contextlib import contextmanager


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "devices.db")


class DatabaseManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)

        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        self.db_name = DB_NAME
        self._initialized = True

    def create_connection(self):
        conn = sqlite3.connect(
            self.db_name,
            timeout=30,
            check_same_thread=False,
        )

        conn.row_factory = sqlite3.Row

        # SQLite concurrency settings
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-64000")
        conn.execute("PRAGMA temp_store=MEMORY")

        return conn

    def init_db(self):
        conn = self.create_connection()

        try:
            cur = conn.cursor()

            # Devices indexes
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_devices_name "
                "ON devices(name COLLATE NOCASE)"
            )

            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_devices_tags "
                "ON devices(tags)"
            )

            # Users indexes
            cur.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='users'"
            )

            if cur.fetchone():
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_users_email "
                    "ON users(email)"
                )

                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_users_username "
                    "ON users(username)"
                )

            conn.commit()

        finally:
            conn.close()

    @contextmanager
    def get_connection(self):
        conn = self.create_connection()

        try:
            yield conn
            conn.commit()

        except Exception:
            conn.rollback()
            raise

        finally:
            conn.close()


# Singleton
db = DatabaseManager()


def init_db():
    db.init_db()


@contextmanager
def get_db():
    with db.get_connection() as conn:
        yield conn