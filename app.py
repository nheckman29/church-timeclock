"""Church time clock: a JSON API for the React frontend, plus serving the built frontend.

Flask over SQLite. No ORM, no auth library. The rules live elsewhere: timecalc.py does
the time math, alerts.py finds missed punches, reports.py builds the CSVs. This file
only translates between HTTP and those modules.

Every API route is under /api. Anything else returns the React app (frontend/dist).
"""

import csv
import io
import os
import sqlite3
import tempfile
import time
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    Response,
    abort,
    g,
    jsonify,
    request,
    send_file,
    send_from_directory,
    session,
)
from werkzeug.exceptions import HTTPException

import alerts
import db
import reports
import timecalc

LOCKOUT_AFTER = 5
LOCKOUT_SECONDS = 30
FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist"

app = Flask(__name__, static_folder=None)
app.config["DB_PATH"] = db.DEFAULT_DB_PATH

_initialized = False
_failed_attempts = {}


# --- plumbing ----------------------------------------------------------------


def get_conn():
    if "conn" not in g:
        g.conn = db.connect(app.config["DB_PATH"])
    return g.conn


@app.teardown_appcontext
def _close_conn(_exception):
    conn = g.pop("conn", None)
    if conn is not None:
        conn.close()


@app.before_request
def _ensure_ready():
    """Create tables and load the session key on the first request. Idempotent."""
    global _initialized
    if not _initialized:
        conn = get_conn()
        new_pin = db.init_db(conn)
        if new_pin:
            print(f"\n*** First run: your admin PIN is {new_pin} ***\n", flush=True)
        app.secret_key = db.get_setting(conn, "secret_key")
        _initialized = True


@app.errorhandler(HTTPException)
def _json_errors(error):
    if request.path.startswith("/api/"):
        return jsonify(error=error.description), error.code
    return error


def fail(message, status=400):
    return jsonify(error=message), status


def body():
    return request.get_json(silent=True) or {}


def require_admin(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin"):
            return fail("Please log in.", 401)
        return view(*args, **kwargs)

    return wrapped


def locked_out(key):
    _, until = _failed_attempts.get(key, (0, 0))
    return time.time() < until


def record_failure(key):
    count, _ = _failed_attempts.get(key, (0, 0))
    count += 1
    until = time.time() + LOCKOUT_SECONDS if count >= LOCKOUT_AFTER else 0
    _failed_attempts[key] = (0 if until else count, until)


def clear_failures(key):
    _failed_attempts.pop(key, None)


def valid_pin(pin):
    return pin.isdigit() and len(pin) >= 4


# --- period helpers ----------------------------------------------------------


def selected_period(conn):
    try:
        day = timecalc.parse_date(request.args["start"])
    except (KeyError, ValueError):
        day = date.today()
    return timecalc.period_bounds(day, db.period_anchor(conn))


def employee_shifts(conn, employee_id, start, end):
    shifts = timecalc.pair_punches(db.punches_between(conn, employee_id, start, end))
    return [s for s in shifts if timecalc.in_period(s, start, end)]


def people_in_period(conn, start, end):
    """[(employee row, shifts)] for every active employee."""
    return [(e, employee_shifts(conn, e["id"], start, end)) for e in db.employees(conn)]


def period_json(start, end):
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "label": f"{timecalc.day_label(start)} – {timecalc.day_label(end)}",
        "prev_start": (start - timedelta(days=14)).isoformat(),
        "next_start": (start + timedelta(days=14)).isoformat(),
    }


def week_bounds(day):
    """The Sunday–Saturday week containing `day`."""
    start = day - timedelta(days=(day.weekday() + 1) % 7)
    return start, start + timedelta(days=6)


def shift_json(shift):
    return {
        "in_id": shift["in_id"],
        "out_id": shift["out_id"],
        "date": shift["date"].isoformat(),
        "day": timecalc.day_label(shift["date"]),
        "clock_in": timecalc.clock(shift["in_at"]),
        "clock_out": timecalc.clock(shift["out_at"]),
        "in_value": timecalc.input_value(shift["in_at"]),
        "out_value": timecalc.input_value(shift["out_at"]),
        "hours": timecalc.hours_text(shift["minutes"]) if shift["complete"] else None,
        "complete": shift["complete"],
    }


def alert_json(shift):
    if shift["in_at"]:
        moment = shift["in_at"]
        problem = f"clocked in on {timecalc.day_label(moment)} at {timecalc.clock(moment)} and never clocked out"
    else:
        moment = shift["out_at"]
        problem = f"clocked out on {timecalc.day_label(moment)} at {timecalc.clock(moment)} with no clock in"
    return {
        "employee_id": shift["employee_id"],
        "name": shift["name"],
        "date": shift["date"].isoformat(),
        "problem": problem,
    }


# --- kiosk -------------------------------------------------------------------


@app.post("/api/punch")
def punch():
    conn = get_conn()
    key = request.remote_addr or "unknown"

    if locked_out(key):
        return fail("Too many wrong PINs. Wait a moment.", 429)

    employee = db.employee_by_pin(conn, str(body().get("pin", "")))
    if employee is None:
        record_failure(key)
        return fail("PIN not recognized.")
    clear_failures(key)

    now = datetime.now().replace(microsecond=0)
    last = db.last_punch(conn, employee["id"])
    warning = None

    if last is None or last["direction"] == "out":
        direction = "in"
    elif timecalc.parse(last["punch_at"]) < now - timedelta(hours=db.max_shift_hours(conn)):
        # Stale open shift. Closing it would bill a multi-day "shift", so start a fresh
        # one and leave the old punch open for the office to correct.
        direction = "in"
        warning = (
            f"You never clocked out on {timecalc.parse(last['punch_at']).strftime('%A')}. "
            "Please tell the office."
        )
    else:
        direction = "out"

    db.add_punch(conn, employee["id"], timecalc.fmt(now), direction)

    return jsonify(
        name=employee["name"],
        direction=direction,
        time=now.strftime("%I:%M%p").lstrip("0"),
        warning=warning,
    )


@app.post("/api/time-card")
def time_card():
    conn = get_conn()
    key = f"time-card:{request.remote_addr or 'unknown'}"
    if locked_out(key):
        return fail("Too many wrong PINs. Wait a moment.", 429)

    employee = db.employee_by_pin(conn, str(body().get("pin", "")))
    if employee is None:
        record_failure(key)
        return fail("PIN not recognized.")
    clear_failures(key)

    now = datetime.now().replace(microsecond=0)
    try:
        week_day = timecalc.parse_date(request.args["start"])
    except (KeyError, ValueError):
        week_day = now.date()
    start, end = week_bounds(week_day)
    punches = db.punches_between(conn, employee["id"], start, end)
    shifts = [
        shift
        for shift in timecalc.pair_punches(punches)
        if timecalc.in_period(shift, start, end)
    ]
    active_shift = (
        shifts[-1]
        if shifts
        and not shifts[-1]["complete"]
        and shifts[-1]["in_at"] is not None
        and shifts[-1]["in_at"] <= now
        and not timecalc.is_stale(shifts[-1], db.max_shift_hours(conn), now)
        else None
    )
    daily_minutes = {start + timedelta(days=offset): 0 for offset in range(7)}

    for shift in shifts:
        minutes = shift["minutes"] or 0
        if shift is active_shift:
            minutes = max(0, int((now - shift["in_at"]).total_seconds() // 60))
        daily_minutes[shift["date"]] += minutes

    days = [
        {
            "date": day.isoformat(),
            "day": day.strftime("%A"),
            "hours": timecalc.hours_text(minutes),
            "in_progress": bool(active_shift and active_shift["date"] == day),
        }
        for day, minutes in daily_minutes.items()
    ]
    return jsonify(
        employee={"name": employee["name"]},
        week={
            "start": start.isoformat(),
            "end": end.isoformat(),
            "label": f"{timecalc.day_label(start)} – {timecalc.day_label(end)}",
            "prev_start": (start - timedelta(days=7)).isoformat(),
            "next_start": (start + timedelta(days=7)).isoformat(),
        },
        hours=timecalc.hours_text(sum(daily_minutes.values())),
        days=days,
    )


# --- admin auth --------------------------------------------------------------


@app.get("/api/session")
def get_session():
    return jsonify(admin=bool(session.get("admin")))


@app.post("/api/login")
def login():
    key = f"admin:{request.remote_addr}"
    if locked_out(key):
        return fail("Too many wrong PINs. Wait a moment.", 429)
    if not db.check_admin_pin(get_conn(), str(body().get("pin", ""))):
        record_failure(key)
        return fail("Wrong PIN.")
    clear_failures(key)
    session["admin"] = True
    return jsonify(ok=True)


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


# --- timesheets --------------------------------------------------------------


@app.get("/api/alerts")
@require_admin
def get_alerts():
    """Missed punches. All of them, or only one period's when ?start= is given."""
    conn = get_conn()
    if "start" in request.args:
        start, end = selected_period(conn)
        stale = alerts.stale_shifts(conn, start, end)
    else:
        stale = alerts.stale_shifts(conn)
    return jsonify([alert_json(s) for s in stale])


@app.get("/api/period")
@require_admin
def get_period():
    conn = get_conn()
    start, end = selected_period(conn)
    people = people_in_period(conn, start, end)
    rows = [
        {
            "id": employee["id"],
            "name": employee["name"],
            "hours": timecalc.hours_text(timecalc.total_minutes(shifts)),
            "open": sum(1 for s in shifts if not s["complete"]),
        }
        for employee, shifts in people
    ]
    total = sum(timecalc.total_minutes(shifts) for _, shifts in people)
    return jsonify(
        period=period_json(start, end),
        employees=rows,
        total_hours=timecalc.hours_text(total),
        missed_punches=len(alerts.stale_shifts(conn, start, end)),
    )


@app.get("/api/employees/<int:employee_id>/shifts")
@require_admin
def get_employee_shifts(employee_id):
    conn = get_conn()
    employee = db.employee(conn, employee_id) or abort(404, "No such employee.")
    start, end = selected_period(conn)
    shifts = employee_shifts(conn, employee_id, start, end)
    return jsonify(
        employee={"id": employee["id"], "name": employee["name"]},
        period=period_json(start, end),
        hours=timecalc.hours_text(timecalc.total_minutes(shifts)),
        shifts=[shift_json(s) for s in shifts],
    )


def _punch_time():
    try:
        return timecalc.parse_form_datetime(str(body().get("punch_at", "")))
    except ValueError:
        abort(400, "Enter a valid date and time.")


@app.post("/api/employees/<int:employee_id>/punches")
@require_admin
def add_punch(employee_id):
    conn = get_conn()
    db.employee(conn, employee_id) or abort(404, "No such employee.")
    punch_at = _punch_time()
    direction = body().get("direction")
    if direction not in ("in", "out"):
        return fail("Choose Clock In or Clock Out.")

    db.add_punch(conn, employee_id, timecalc.fmt(punch_at), direction, note="added by office")
    return jsonify(message=f"Added clock {direction.upper()} at {timecalc.clock(punch_at)}.")


@app.put("/api/punches/<int:punch_id>")
@require_admin
def edit_punch(punch_id):
    conn = get_conn()
    conn.execute("SELECT id FROM punches WHERE id = ?", (punch_id,)).fetchone() or abort(
        404, "No such punch."
    )
    punch_at = _punch_time()
    conn.execute(
        "UPDATE punches SET punch_at = ?, note = 'corrected by office' WHERE id = ?",
        (timecalc.fmt(punch_at), punch_id),
    )
    conn.commit()
    return jsonify(message="Punch updated.")


@app.delete("/api/punches/<int:punch_id>")
@require_admin
def delete_punch(punch_id):
    conn = get_conn()
    conn.execute("SELECT id FROM punches WHERE id = ?", (punch_id,)).fetchone() or abort(
        404, "No such punch."
    )
    conn.execute("DELETE FROM punches WHERE id = ?", (punch_id,))
    conn.commit()
    return jsonify(message="Punch deleted.")


# --- employees ---------------------------------------------------------------


@app.get("/api/employees")
@require_admin
def list_employees():
    return jsonify(
        [
            {"id": e["id"], "name": e["name"], "active": bool(e["active"])}
            for e in db.employees(get_conn(), include_inactive=True)
        ]
    )


@app.post("/api/employees")
@require_admin
def add_employee():
    conn = get_conn()
    name = str(body().get("name", "")).strip()
    pin = str(body().get("pin", "")).strip()
    if not name or not valid_pin(pin):
        return fail("Enter a name and a PIN of at least 4 digits.")
    try:
        conn.execute(
            "INSERT INTO employees (name, pin_hash) VALUES (?, ?)",
            (name, db.hash_pin(conn, pin)),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        return fail("That PIN is already in use. Pick a different one.")
    return jsonify(message=f"Added {name}.")


@app.put("/api/employees/<int:employee_id>")
@require_admin
def edit_employee(employee_id):
    conn = get_conn()
    db.employee(conn, employee_id) or abort(404, "No such employee.")
    name = str(body().get("name", "")).strip()
    pin = str(body().get("pin", "")).strip()
    active = 1 if body().get("active") else 0
    if not name:
        return fail("Name cannot be empty.")
    if pin and not valid_pin(pin):
        return fail("A PIN must be at least 4 digits.")
    try:
        conn.execute(
            "UPDATE employees SET name = ?, active = ? WHERE id = ?", (name, active, employee_id)
        )
        if pin:
            conn.execute(
                "UPDATE employees SET pin_hash = ? WHERE id = ?",
                (db.hash_pin(conn, pin), employee_id),
            )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        return fail("That PIN is already in use. Pick a different one.")
    return jsonify(message=f"Saved {name}.")


# --- exports -----------------------------------------------------------------
# Plain GET downloads, so the browser saves the file. The frontend checks for missed
# punches first and shows a warning page; the 409 here is the backstop.


def _csv_response(rows, filename):
    buffer = io.StringIO()
    csv.writer(buffer).writerows(rows)
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _export(build_rows, filename_prefix):
    conn = get_conn()
    start, end = selected_period(conn)
    if not request.args.get("force") and alerts.stale_shifts(conn, start, end):
        return fail("This pay period has missed punches. Fix them or export anyway.", 409)
    people = [(e["name"], shifts) for e, shifts in people_in_period(conn, start, end)]
    return _csv_response(build_rows(people, start, end), f"{filename_prefix}-{start}.csv")


@app.get("/api/export/summary.csv")
@require_admin
def export_summary():
    return _export(reports.summary_rows, "timesheet-summary")


@app.get("/api/export/timesheet.csv")
@require_admin
def export_timesheet():
    return _export(reports.timesheet_rows, "timesheet-report")


@app.get("/api/backup")
@require_admin
def backup():
    handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    path = handle.name
    handle.close()

    try:
        destination = sqlite3.connect(path)
        try:
            get_conn().backup(destination)
        finally:
            destination.close()
        backup_file = io.BytesIO(Path(path).read_bytes())
    finally:
        os.unlink(path)

    return send_file(
        backup_file,
        as_attachment=True,
        download_name=f"timeclock-backup-{date.today()}.db",
    )


# --- settings ----------------------------------------------------------------


@app.get("/api/settings")
@require_admin
def get_settings():
    conn = get_conn()
    return jsonify(
        max_shift_hours=db.max_shift_hours(conn),
        period_anchor=db.period_anchor(conn).isoformat(),
    )


@app.put("/api/settings")
@require_admin
def save_settings():
    """Validate everything first, then save, so a bad field never half-applies."""
    conn = get_conn()
    data = body()
    pin = str(data.get("admin_pin", "")).strip()
    hours_value = str(data.get("max_shift_hours", "")).strip()

    if pin and not valid_pin(pin):
        return fail("The admin PIN must be at least 4 digits.")
    if not (hours_value.isdigit() and 1 <= int(hours_value) <= 24):
        return fail("The longest possible shift must be between 1 and 24 hours.")
    try:
        anchor = timecalc.parse_date(str(data.get("period_anchor", "")).strip())
    except ValueError:
        return fail("Enter a valid pay period start date.")

    if pin:
        db.set_setting(conn, "admin_pin_hash", db.hash_pin(conn, pin))
    db.set_setting(conn, "max_shift_hours", int(hours_value))
    db.set_setting(conn, "period_anchor", anchor.isoformat())
    return jsonify(message="Admin PIN changed. Settings saved." if pin else "Settings saved.")


# --- the React app -----------------------------------------------------------


@app.get("/", defaults={"path": ""})
@app.get("/<path:path>")
def frontend(path):
    """Serve the built frontend. Unknown paths get index.html so React can route them."""
    if path.startswith("api/"):
        abort(404, "No such API route.")
    if not (FRONTEND_DIST / "index.html").is_file():
        return "Frontend not built. Run: cd frontend && npm install && npm run build", 500
    if path and (FRONTEND_DIST / path).is_file():
        return send_from_directory(FRONTEND_DIST, path)
    return send_from_directory(FRONTEND_DIST, "index.html")
