"""SQLite access. Thin helpers over the stdlib sqlite3 module, no ORM."""

import hashlib
import hmac
import os
import secrets
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import timecalc

HERE = Path(__file__).parent
DEFAULT_DB_PATH = Path(os.environ.get("TIMECLOCK_DB", HERE / "timeclock.db"))

DEFAULT_MAX_SHIFT_HOURS = 16


def connect(path=None):
    conn = sqlite3.connect(path or DEFAULT_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_setting(conn, key, default=None):
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(conn, key, value):
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )
    conn.commit()


def max_shift_hours(conn):
    return int(get_setting(conn, "max_shift_hours", DEFAULT_MAX_SHIFT_HOURS))


def period_anchor(conn):
    return timecalc.parse_date(get_setting(conn, "period_anchor"))


def _last_sunday(day):
    return day - timedelta(days=(day.weekday() + 1) % 7)


def init_db(conn):
    """Create tables and first-run settings. Idempotent, safe to call on every start.

    Returns the generated admin PIN on a genuine first run, otherwise None.
    """
    conn.executescript((HERE / "schema.sql").read_text())

    if get_setting(conn, "secret_key") is None:
        set_setting(conn, "secret_key", secrets.token_hex(32))
    if get_setting(conn, "pin_pepper") is None:
        set_setting(conn, "pin_pepper", secrets.token_hex(32))
    if get_setting(conn, "max_shift_hours") is None:
        set_setting(conn, "max_shift_hours", DEFAULT_MAX_SHIFT_HOURS)
    if get_setting(conn, "period_anchor") is None:
        set_setting(conn, "period_anchor", _last_sunday(date.today()).isoformat())

    if get_setting(conn, "admin_pin_hash") is None:
        admin_pin = f"{secrets.randbelow(1_000_000):06d}"
        set_setting(conn, "admin_pin_hash", hash_pin(conn, admin_pin))
        return admin_pin
    return None


def hash_pin(conn, pin):
    """Keyed hash of a PIN.

    Deterministic on purpose: it lets the database enforce UNIQUE PINs (two employees
    sharing a PIN would make punches ambiguous) and keeps lookup a single indexed query.
    A 4-digit PIN cannot be made cryptographically strong anyway; the real security
    boundary is physical and network access to the church machine. See README.
    """
    pepper = get_setting(conn, "pin_pepper").encode()
    return hmac.new(pepper, pin.strip().encode(), hashlib.sha256).hexdigest()


def employee_by_pin(conn, pin):
    return conn.execute(
        "SELECT * FROM employees WHERE pin_hash = ? AND active = 1",
        (hash_pin(conn, pin),),
    ).fetchone()


def check_admin_pin(conn, pin):
    return hmac.compare_digest(hash_pin(conn, pin), get_setting(conn, "admin_pin_hash", ""))


def employees(conn, include_inactive=False):
    sql = "SELECT * FROM employees"
    if not include_inactive:
        sql += " WHERE active = 1"
    return conn.execute(sql + " ORDER BY name COLLATE NOCASE").fetchall()


def employee(conn, employee_id):
    return conn.execute("SELECT * FROM employees WHERE id = ?", (employee_id,)).fetchone()


def punches_between(conn, employee_id, start, end):
    """Punches for an employee across a date range, padded a day either side.

    The padding matters: a shift that starts on the last night of a period must still
    find its clock-out on the following morning in order to pair correctly.
    """
    return conn.execute(
        "SELECT * FROM punches WHERE employee_id = ? AND punch_at >= ? AND punch_at < ? "
        "ORDER BY punch_at, id",
        (
            employee_id,
            (start - timedelta(days=1)).isoformat() + " 00:00:00",
            (end + timedelta(days=2)).isoformat() + " 00:00:00",
        ),
    ).fetchall()


def all_punches(conn, employee_id):
    return conn.execute(
        "SELECT * FROM punches WHERE employee_id = ? ORDER BY punch_at, id", (employee_id,)
    ).fetchall()


def last_punch(conn, employee_id):
    return conn.execute(
        "SELECT * FROM punches WHERE employee_id = ? ORDER BY punch_at DESC, id DESC LIMIT 1",
        (employee_id,),
    ).fetchone()


def add_punch(conn, employee_id, punch_at, direction, note=""):
    cursor = conn.execute(
        "INSERT INTO punches (employee_id, punch_at, direction, note) VALUES (?, ?, ?, ?)",
        (employee_id, punch_at, direction, note),
    )
    conn.commit()
    return cursor.lastrowid
