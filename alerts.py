"""Missed-punch detection.

One definition of "stale" drives the kiosk warning, the admin banner and the export
guard: an unmatched punch older than the `max_shift_hours` setting.
"""

from datetime import datetime

import db
import timecalc


def _employee_shifts(conn, employee_id, start=None, end=None):
    rows = (
        db.punches_between(conn, employee_id, start, end)
        if start
        else db.all_punches(conn, employee_id)
    )
    shifts = timecalc.pair_punches(rows)
    if start:
        shifts = [s for s in shifts if timecalc.in_period(s, start, end)]
    return shifts


def stale_shifts(conn, start=None, end=None, now=None):
    """Forgotten punches, newest first. Optionally limited to one pay period."""
    now = now or datetime.now()
    threshold = db.max_shift_hours(conn)
    found = []
    for employee in db.employees(conn):
        for shift in _employee_shifts(conn, employee["id"], start, end):
            if timecalc.is_stale(shift, threshold, now):
                found.append({**shift, "employee_id": employee["id"], "name": employee["name"]})
    return sorted(found, key=lambda s: s["in_at"] or s["out_at"], reverse=True)
