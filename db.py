import os
import json
import sqlite3
from contextlib import contextmanager


# DATABASE CONFIGURATION

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "devices.db")


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

    # CONNECTION
    # ========================================================

    def create_connection(self):

        conn = sqlite3.connect(
            self.db_name,
            timeout=30,
            check_same_thread=False
        )

        conn.row_factory = sqlite3.Row

        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA cache_size = -64000")
        conn.execute("PRAGMA temp_store = MEMORY")

        return conn

    # INITIALIZATION

    def init_db(self):

        conn = self.create_connection()

        try:

            cur = conn.cursor()

            # Integrity check

            integrity = cur.execute(
                "PRAGMA integrity_check"
            ).fetchone()

            if integrity and integrity[0] != "ok":
                raise RuntimeError(
                    f"Database integrity check failed: {integrity[0]}"
                )

            # Check if orders table exists

            orders_exists = cur.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                AND name = 'orders'
                """
            ).fetchone()

            if not orders_exists:

                self._create_orders_table(cur)

            else:

                # Existing table may contain old CHECK constraint.
                self._migrate_orders_table(cur)

            # Order Events

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS order_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    order_id INTEGER NOT NULL,

                    event_type TEXT NOT NULL,

                    person_id INTEGER,

                    person_name TEXT,

                    zone TEXT,

                    camera TEXT,

                    confidence REAL,

                    metadata TEXT,

                    created_at TEXT NOT NULL
                        DEFAULT (datetime('now')),

                    FOREIGN KEY(order_id)
                        REFERENCES orders(id)
                        ON DELETE CASCADE
                )
                """
            )

            # Indexes

            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_orders_status
                ON orders(status, created_at)
                """
            )

            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_order_events_order
                ON order_events(order_id, created_at)
                """
            )

            # Device indexes

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

            # User indexes

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

            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_users_role
                ON users(role)
                """
            )

            # Validate existing data

            self._validate_existing_data(cur)

            conn.commit()

        except Exception:

            conn.rollback()
            raise

        finally:

            conn.close()

    # CREATE ORDERS TABLE

    def _create_orders_table(self, cur):

        cur.execute(
            """
            CREATE TABLE orders (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                device_name TEXT NOT NULL,

                qty INTEGER NOT NULL
                    CHECK (qty > 0),

                item_type TEXT,

                requested_by_user_id INTEGER,

                pickup_user_id INTEGER,

                dropoff_user_id INTEGER,

                source_zone TEXT,

                destination_zone TEXT,

                status TEXT NOT NULL
                    DEFAULT 'CREATED'
                    CHECK (
                        status IN (
                            'CREATED',
                            'IN_TRANSIT',
                            'COMPLETED',
                            'TIMED_OUT'
                        )
                    ),

                flagged INTEGER NOT NULL
                    DEFAULT 0,

                flag_reason TEXT,

                created_at TEXT NOT NULL
                    DEFAULT (datetime('now')),

                updated_at TEXT NOT NULL
                    DEFAULT (datetime('now'))
            )
            """
        )

    # MIGRATE ORDERS TABLE

    def _migrate_orders_table(self, cur):

        # Get current schema

        schema_row = cur.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'table'
            AND name = 'orders'
            """
        ).fetchone()

        schema = schema_row["sql"] if schema_row else ""

        # If old CHECK constraint exists

        old_constraint = (
            "PENDING" in schema
            or "'PENDING'" in schema
        )

        if old_constraint:

            self._rebuild_orders_table(cur)

        else:

            # Safe column migrations

            existing_columns = {
                row["name"]
                for row in cur.execute(
                    "PRAGMA table_info(orders)"
                ).fetchall()
            }

            migrations = [

                ("item_type", "TEXT"),

                ("requested_by_user_id", "INTEGER"),

                ("pickup_user_id", "INTEGER"),

                ("dropoff_user_id", "INTEGER"),

                ("source_zone", "TEXT"),

                ("destination_zone", "TEXT"),

                ("flagged", "INTEGER NOT NULL DEFAULT 0"),

                ("flag_reason", "TEXT"),

                (
                    "created_at",
                    "TEXT NOT NULL DEFAULT (datetime('now'))"
                ),

                (
                    "updated_at",
                    "TEXT NOT NULL DEFAULT (datetime('now'))"
                )
            ]

            for column_name, column_type in migrations:

                if column_name not in existing_columns:

                    cur.execute(
                        f"""
                        ALTER TABLE orders
                        ADD COLUMN {column_name}
                        {column_type}
                        """
                    )

    # REBUILD ORDERS TABLE

    def _rebuild_orders_table(self, cur):

        # Rename old table

        cur.execute(
            """
            ALTER TABLE orders
            RENAME TO orders_old
            """
        )

        # Create new table

        self._create_orders_table(cur)

        # Detect available columns

        old_columns = {
            row["name"]
            for row in cur.execute(
                "PRAGMA table_info(orders_old)"
            ).fetchall()
        }

        # Build SELECT safely

        def column_or_null(column):

            if column in old_columns:
                return column

            return "NULL"

        device_name = column_or_null("device_name")
        qty = column_or_null("qty")
        item_type = column_or_null("item_type")
        requested_by_user_id = column_or_null(
            "requested_by_user_id"
        )
        pickup_user_id = column_or_null(
            "pickup_user_id"
        )
        dropoff_user_id = column_or_null(
            "dropoff_user_id"
        )
        source_zone = column_or_null(
            "source_zone"
        )
        destination_zone = column_or_null(
            "destination_zone"
        )
        flagged = column_or_null("flagged")
        flag_reason = column_or_null("flag_reason")
        created_at = column_or_null("created_at")
        updated_at = column_or_null("updated_at")

        # Normalize old status

        if "status" in old_columns:

            status_expression = """
                CASE
                    WHEN status = 'PENDING'
                        THEN 'CREATED'

                    WHEN status = 'CREATED'
                        THEN 'CREATED'

                    WHEN status = 'IN_TRANSIT'
                        THEN 'IN_TRANSIT'

                    WHEN status = 'COMPLETED'
                        THEN 'COMPLETED'

                    WHEN status = 'TIMED_OUT'
                        THEN 'TIMED_OUT'

                    ELSE 'CREATED'
                END
            """

        else:

            status_expression = "'CREATED'"

        # Copy data

        cur.execute(
            f"""
            INSERT INTO orders (
                id,
                device_name,
                qty,
                item_type,
                requested_by_user_id,
                pickup_user_id,
                dropoff_user_id,
                source_zone,
                destination_zone,
                status,
                flagged,
                flag_reason,
                created_at,
                updated_at
            )

            SELECT

                id,

                {device_name},

                CASE
                    WHEN {qty} IS NULL
                        OR {qty} <= 0
                    THEN 1
                    ELSE {qty}
                END,

                {item_type},

                {requested_by_user_id},

                {pickup_user_id},

                {dropoff_user_id},

                {source_zone},

                {destination_zone},

                {status_expression},

                COALESCE({flagged}, 0),

                {flag_reason},

                COALESCE(
                    {created_at},
                    datetime('now')
                ),

                COALESCE(
                    {updated_at},
                    datetime('now')
                )

            FROM orders_old
            """
        )

        # Remove old table

        cur.execute(
            """
            DROP TABLE orders_old
            """
        )

    # VALIDATION

    def _validate_existing_data(self, cur):

        # Users

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
                "Database contains users without a valid username."
            )

        # Passwords

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
                "Database contains users without a password."
            )

        # Roles

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

        # Devices

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
                "Database contains devices without a valid name."
            )

        # Prices

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
                "Database contains devices with negative prices."
            )

        # Quantities

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
                "Database contains devices with negative quantities."
            )

    # TRANSACTION CONNECTION

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


db = DatabaseManager()


def init_db():
    db.init_db()


@contextmanager
def get_db():

    with db.get_connection() as conn:

        yield conn


# FACE RECOGNITION

def get_all_face_encodings():

    with get_db() as conn:

        rows = conn.execute(
            """
            SELECT
                id,
                username,
                face_encoding

            FROM users

            WHERE face_encoding IS NOT NULL
            """
        ).fetchall()

    results = []

    for row in rows:

        try:

            encoding_list = json.loads(
                row["face_encoding"]
            )

        except (ValueError, TypeError):

            continue

        results.append(
            (
                row["id"],
                row["username"],
                encoding_list
            )
        )

    return results


# ORDER CREATION

def create_order(
    device_name: str,
    qty: int,
    item_type: str,
    requested_by_user_id: int,
    source_zone: str = "i-core-room",
    destination_zone: str = "i-warehouse"
):

    with get_db() as conn:

        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO orders (
                device_name,
                qty,
                item_type,
                requested_by_user_id,
                source_zone,
                destination_zone,
                status,
                created_at,
                updated_at
            )

            VALUES (
                ?, ?, ?, ?, ?, ?,
                'CREATED',
                datetime('now'),
                datetime('now')
            )
            """,
            (
                device_name,
                qty,
                item_type,
                requested_by_user_id,
                source_zone,
                destination_zone
            )
        )

        order_id = cur.lastrowid

        # Initial event

        cur.execute(
            """
            INSERT INTO order_events (
                order_id,
                event_type,
                person_id,
                metadata
            )

            VALUES (
                ?,
                'ORDER_CREATED',
                ?,
                ?
            )
            """,
            (
                order_id,
                requested_by_user_id,
                json.dumps({
                    "device_name": device_name,
                    "quantity": qty,
                    "item_type": item_type
                })
            )
        )

        return order_id


# GET ORDER

def get_order(order_id: int):

    with get_db() as conn:

        row = conn.execute(
            """
            SELECT *
            FROM orders
            WHERE id = ?
            """,
            (order_id,)
        ).fetchone()

        return dict(row) if row else None


# GET ORDER EVENTS

def get_order_events(order_id: int):

    with get_db() as conn:

        rows = conn.execute(
            """
            SELECT *
            FROM order_events

            WHERE order_id = ?

            ORDER BY
                created_at ASC,
                id ASC
            """,
            (order_id,)
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]


# ACTIVE ORDER

def get_active_order(status: str):

    with get_db() as conn:

        row = conn.execute(
            """
            SELECT *

            FROM orders

            WHERE status = ?

            ORDER BY created_at ASC

            LIMIT 1
            """,
            (status,)
        ).fetchone()

        return dict(row) if row else None


# UPDATE ORDER STATUS

def update_order_status(
    order_id: int,
    status: str,
    actor_user_id: int = None,
    actor_name: str = None,
    zone: str = None,
    camera: str = None,
    confidence: float = None,
    event_type: str = None,
    metadata: dict = None
):

    allowed_statuses = {
        "CREATED",
        "IN_TRANSIT",
        "COMPLETED",
        "TIMED_OUT"
    }

    if status not in allowed_statuses:

        raise ValueError(
            f"Invalid order status: {status}"
        )

    with get_db() as conn:

        cur = conn.cursor()

        # Pickup

        if (
            status == "IN_TRANSIT"
            and actor_user_id
        ):

            cur.execute(
                """
                UPDATE orders

                SET
                    status = ?,
                    pickup_user_id = ?,
                    updated_at = datetime('now')

                WHERE id = ?
                """,
                (
                    status,
                    actor_user_id,
                    order_id
                )
            )

        # Dropoff

        elif (
            status == "COMPLETED"
            and actor_user_id
        ):

            cur.execute(
                """
                UPDATE orders

                SET
                    status = ?,
                    dropoff_user_id = ?,
                    updated_at = datetime('now')

                WHERE id = ?
                """,
                (
                    status,
                    actor_user_id,
                    order_id
                )
            )

        # Normal status update

        else:

            cur.execute(
                """
                UPDATE orders

                SET
                    status = ?,
                    updated_at = datetime('now')

                WHERE id = ?
                """,
                (
                    status,
                    order_id
                )
            )

        # Event

        if event_type is None:

            event_type = status

        cur.execute(
            """
            INSERT INTO order_events (
                order_id,
                event_type,
                person_id,
                person_name,
                zone,
                camera,
                confidence,
                metadata
            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_id,
                event_type,
                actor_user_id,
                actor_name,
                zone,
                camera,
                confidence,
                json.dumps(
                    metadata or {}
                )
            )
        )


# FLAG ORDER

def flag_order(
    order_id: int,
    reason: str
):

    with get_db() as conn:

        cur = conn.cursor()

        cur.execute(
            """
            UPDATE orders

            SET
                flagged = 1,
                flag_reason = ?,
                updated_at = datetime('now')

            WHERE id = ?
            """,
            (
                reason,
                order_id
            )
        )

        cur.execute(
            """
            INSERT INTO order_events (
                order_id,
                event_type,
                metadata
            )

            VALUES (
                ?,
                'MANUAL_REVIEW_REQUIRED',
                ?
            )
            """,
            (
                order_id,
                json.dumps({
                    "reason": reason
                })
            )
        )


# INVENTORY

def update_inventory(
    device_name: str,
    qty: int
):

    with get_db() as conn:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                rowid AS row_id

            FROM devices

            WHERE name = ?
            COLLATE NOCASE
            """,
            (device_name,)
        )

        existing = cur.fetchone()

        if existing:

            cur.execute(
                """
                UPDATE devices

                SET quantity = quantity + ?

                WHERE rowid = ?
                """,
                (
                    qty,
                    existing["row_id"]
                )
            )

        else:

            cur.execute(
                """
                INSERT INTO devices (
                    name,
                    quantity,
                    createdAt
                )

                VALUES (
                    ?,
                    ?,
                    datetime('now')
                )
                """,
                (
                    device_name,
                    qty
                )
            )