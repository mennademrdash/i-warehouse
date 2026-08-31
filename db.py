import os
import sqlite3
from contextlib import contextmanager


# DATABASE CONFIGURATION

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

DB_NAME = os.path.join(
    BASE_DIR,
    "devices.db"
)


# DATABASE MANAGER

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


    # CREATE DATABASE CONNECTION

    def create_connection(self):

        conn = sqlite3.connect(
            self.db_name,
            timeout=30,
            check_same_thread=False
        )

        conn.row_factory = sqlite3.Row


        # FOREIGN KEY ENFORCEMENT

        conn.execute(
            "PRAGMA foreign_keys = ON"
        )


        # CONCURRENCY

        conn.execute(
            "PRAGMA journal_mode = WAL"
        )

        conn.execute(
            "PRAGMA busy_timeout = 30000"
        )


        # DATA DURABILITY

        conn.execute(
            "PRAGMA synchronous = NORMAL"
        )

        conn.execute(
            "PRAGMA foreign_keys = ON"
        )


        # PERFORMANCE

        conn.execute(
            "PRAGMA cache_size = -64000"
        )

        conn.execute(
            "PRAGMA temp_store = MEMORY"
        )


        return conn


    # DATABASE INITIALIZATION

    def init_db(self):

        conn = self.create_connection()

        try:

            cur = conn.cursor()


            # DATABASE INTEGRITY CHECK

            integrity = cur.execute(
                "PRAGMA integrity_check"
            ).fetchone()


            if integrity and integrity[0] != "ok":

                raise RuntimeError(
                    f"Database integrity check failed: "
                    f"{integrity[0]}"
                )


            # ORDERS TABLE
            # Tracks a device handoff from creation through pickup and
            # arrival. status transitions:
            # PENDING -> IN_TRANSIT -> COMPLETED (or TIMED_OUT)

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_name TEXT NOT NULL,
                    qty INTEGER NOT NULL CHECK (qty > 0),
                    status TEXT NOT NULL DEFAULT 'PENDING'
                        CHECK (status IN ('PENDING', 'IN_TRANSIT', 'COMPLETED', 'TIMED_OUT')),
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )

            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_orders_status
                ON orders(status, created_at)
                """
            )


            # DEVICES INDEXES

            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_devices_name
                ON devices(name COLLATE NOCASE)
                """
            )


            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_devices_tags
                ON devices(tags)
                """
            )


            # USERS INDEXES

            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_users_email
                ON users(email COLLATE NOCASE)
                """
            )


            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_users_username
                ON users(username COLLATE NOCASE)
                """
            )


            # USER ROLE INDEX

            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_users_role
                ON users(role)
                """
            )


            # VALIDATE EXISTING DATA

            self._validate_existing_data(cur)


            # COMMIT

            conn.commit()


        except Exception:

            conn.rollback()

            raise


        finally:

            conn.close()


    # EXISTING DATA VALIDATION

    def _validate_existing_data(self, cur):

        # USERS WITHOUT USERNAME

        invalid_users = cur.execute(
            """
            SELECT COUNT(*)
            FROM users
            WHERE username IS NULL
               OR TRIM(username) = ''
            """
        ).fetchone()[0]


        if invalid_users > 0:

            raise RuntimeError(
                "Database contains users "
                "without a valid username."
            )


        # USERS WITHOUT PASSWORD

        invalid_passwords = cur.execute(
            """
            SELECT COUNT(*)
            FROM users
            WHERE password IS NULL
               OR TRIM(password) = ''
            """
        ).fetchone()[0]


        if invalid_passwords > 0:

            raise RuntimeError(
                "Database contains users "
                "without a password."
            )


        # INVALID USER ROLES

        invalid_roles = cur.execute(
            """
            SELECT COUNT(*)
            FROM users
            WHERE role IS NULL
               OR role NOT IN ('user', 'admin')
            """
        ).fetchone()[0]


        if invalid_roles > 0:

            raise RuntimeError(
                "Database contains invalid user roles."
            )


        # DEVICES WITHOUT NAME

        invalid_devices = cur.execute(
            """
            SELECT COUNT(*)
            FROM devices
            WHERE name IS NULL
               OR TRIM(name) = ''
            """
        ).fetchone()[0]


        if invalid_devices > 0:

            raise RuntimeError(
                "Database contains devices "
                "without a valid name."
            )


        # INVALID DEVICE PRICE

        invalid_prices = cur.execute(
            """
            SELECT COUNT(*)
            FROM devices
            WHERE price IS NOT NULL
              AND price < 0
            """
        ).fetchone()[0]


        if invalid_prices > 0:

            raise RuntimeError(
                "Database contains devices "
                "with negative prices."
            )


        # INVALID DEVICE QUANTITY

        invalid_quantities = cur.execute(
            """
            SELECT COUNT(*)
            FROM devices
            WHERE quantity IS NOT NULL
              AND quantity < 0
            """
        ).fetchone()[0]


        if invalid_quantities > 0:

            raise RuntimeError(
                "Database contains devices "
                "with negative quantities."
            )


    # TRANSACTION-SAFE CONNECTION

    @contextmanager
    def get_connection(self):

        conn = self.create_connection()

        try:

            yield conn

            # Commit only if everything succeeded
            conn.commit()


        except Exception:

            # Roll back all changes
            conn.rollback()

            raise


        finally:

            conn.close()


# SINGLETON INSTANCE

db = DatabaseManager()


# PUBLIC API

def init_db():

    db.init_db()


@contextmanager
def get_db():

    with db.get_connection() as conn:

        yield conn


# ORDERS API

def create_order(device_name: str, qty: int) -> int:
    """Creates a new order in PENDING status and returns its id."""

    with get_db() as conn:

        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO orders (device_name, qty, status, created_at, updated_at)
            VALUES (?, ?, 'PENDING', datetime('now'), datetime('now'))
            """,
            (device_name, qty),
        )

        return cur.lastrowid


def get_order(order_id: int):
    """Returns a single order by id, or None if it doesn't exist."""

    with get_db() as conn:

        cur = conn.cursor()

        cur.execute(
            "SELECT * FROM orders WHERE id = ?",
            (order_id,),
        )

        row = cur.fetchone()

        return dict(row) if row else None


def update_order_status(order_id: int, status: str) -> None:
    """Updates an order's status and refreshes updated_at."""

    with get_db() as conn:

        cur = conn.cursor()

        cur.execute(
            """
            UPDATE orders
            SET status = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (status, order_id),
        )


def get_active_order(status: str):
    """Returns the oldest order currently in the given status.

    LIMITATION (documented on purpose, not an oversight): this assumes
    only ONE order is in-flight at a time. With two+ concurrent
    handoffs, a Frigate event on either camera would get attributed to
    the oldest matching order, which is wrong. Fine for a
    single-order prototype -- before this handles concurrent
    deliveries, correlate Frigate events to a specific order via a
    session token (e.g. a QR code the courier scans at pickup).
    """

    with get_db() as conn:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT * FROM orders
            WHERE status = ?
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (status,),
        )

        row = cur.fetchone()

        return dict(row) if row else None


# INVENTORY UPDATE (on order arrival)

def update_inventory(device_name: str, qty: int) -> None:
    """Increments quantity for an existing device, or inserts a new one.

    Matches against devices.name case-insensitively, consistent with
    idx_devices_name (COLLATE NOCASE) already defined in init_db().
    """

    with get_db() as conn:

        cur = conn.cursor()

        cur.execute(
            "SELECT rowid AS row_id FROM devices WHERE name = ? COLLATE NOCASE",
            (device_name,),
        )

        existing = cur.fetchone()

        if existing:

            cur.execute(
                "UPDATE devices SET quantity = quantity + ? WHERE rowid = ?",
                (qty, existing["row_id"]),
            )

        else:

            cur.execute(
                """
                INSERT INTO devices (name, quantity, createdAt)
                VALUES (?, ?, datetime('now'))
                """,
                (device_name, qty),
            )