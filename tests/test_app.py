from datetime import date, datetime, timedelta

import pytest

import app as app_module
import db
import timecalc

ADMIN_PIN = "987654"
ANCHOR = date(2026, 1, 4)


@pytest.fixture
def conn(tmp_path):
    path = tmp_path / "test.db"
    connection = db.connect(path)
    db.init_db(connection)
    db.set_setting(connection, "admin_pin_hash", db.hash_pin(connection, ADMIN_PIN))
    db.set_setting(connection, "period_anchor", ANCHOR.isoformat())

    app_module.app.config.update(DB_PATH=path, TESTING=True)
    app_module._initialized = False
    app_module._failed_attempts.clear()

    yield connection
    connection.close()


@pytest.fixture
def client(conn):
    with app_module.app.test_client() as test_client:
        yield test_client


def add_employee(conn, name="Jane Smith", pin="1111"):
    cursor = conn.execute(
        "INSERT INTO employees (name, pin_hash) VALUES (?, ?)", (name, db.hash_pin(conn, pin))
    )
    conn.commit()
    return cursor.lastrowid


def log_in(client):
    response = client.post("/api/login", json={"pin": ADMIN_PIN})
    assert response.status_code == 200
    return response


def punch(client, pin="1111"):
    return client.post("/api/punch", json={"pin": pin})


# --- kiosk -------------------------------------------------------------------


def test_first_punch_of_the_day_clocks_in(client, conn):
    add_employee(conn)
    data = punch(client).get_json()
    assert data["name"] == "Jane Smith"
    assert data["direction"] == "in"
    assert data["warning"] is None
    assert conn.execute("SELECT COUNT(*) c FROM punches").fetchone()["c"] == 1


def test_kiosk_time_reads_like_8_34AM(client, conn):
    add_employee(conn)
    time_text = punch(client).get_json()["time"]
    assert time_text == datetime.now().strftime("%I:%M%p").lstrip("0")


def test_second_punch_clocks_out(client, conn):
    employee_id = add_employee(conn)
    two_hours_ago = datetime.now().replace(microsecond=0) - timedelta(hours=2)
    db.add_punch(conn, employee_id, timecalc.fmt(two_hours_ago), "in")

    assert punch(client).get_json()["direction"] == "out"


def test_forgotten_clock_out_starts_a_fresh_shift_and_warns(client, conn):
    """The core missed-punch rule: never close a stale shift and bill 30 hours."""
    employee_id = add_employee(conn)
    yesterday = datetime.now().replace(microsecond=0) - timedelta(hours=30)
    db.add_punch(conn, employee_id, timecalc.fmt(yesterday), "in")

    data = punch(client).get_json()
    assert data["direction"] == "in"
    assert "never clocked out" in data["warning"]

    directions = [r["direction"] for r in db.all_punches(conn, employee_id)]
    assert directions == ["in", "in"]


def test_unknown_pin_is_rejected(client, conn):
    add_employee(conn)
    response = punch(client, "9999")
    assert response.status_code == 400
    assert response.get_json()["error"] == "PIN not recognized."
    assert conn.execute("SELECT COUNT(*) c FROM punches").fetchone()["c"] == 0


def test_repeated_wrong_pins_lock_the_keypad(client, conn):
    add_employee(conn)
    for _ in range(app_module.LOCKOUT_AFTER):
        punch(client, "9999")
    response = punch(client, "1111")
    assert response.status_code == 429
    assert "Too many wrong PINs" in response.get_json()["error"]


def test_inactive_employee_cannot_clock_in(client, conn):
    employee_id = add_employee(conn)
    conn.execute("UPDATE employees SET active = 0 WHERE id = ?", (employee_id,))
    conn.commit()
    assert punch(client).status_code == 400


# --- admin -------------------------------------------------------------------


def test_admin_api_requires_login(client):
    for path in ("/api/period", "/api/employees", "/api/settings", "/api/backup"):
        response = client.get(path)
        assert response.status_code == 401, path


def test_wrong_admin_pin_is_rejected(client):
    response = client.post("/api/login", json={"pin": "000000"})
    assert response.status_code == 400
    assert response.get_json()["error"] == "Wrong PIN."


def test_logout_ends_the_session(client):
    log_in(client)
    assert client.get("/api/session").get_json() == {"admin": True}
    client.post("/api/logout")
    assert client.get("/api/period").status_code == 401


def test_period_totals_hours(client, conn):
    employee_id = add_employee(conn)
    db.add_punch(conn, employee_id, "2026-01-05 08:00:00", "in")
    db.add_punch(conn, employee_id, "2026-01-05 16:00:00", "out")

    log_in(client)
    data = client.get("/api/period?start=2026-01-05").get_json()
    assert data["period"]["start"] == "2026-01-04"
    assert data["period"]["end"] == "2026-01-17"
    assert data["employees"] == [{"id": employee_id, "name": "Jane Smith", "hours": "8.00", "open": 0}]
    assert data["total_hours"] == "8.00"
    assert data["missed_punches"] == 0


def test_missed_punches_are_reported(client, conn):
    employee_id = add_employee(conn)
    db.add_punch(conn, employee_id, "2026-01-05 08:00:00", "in")

    log_in(client)
    alerts = client.get("/api/alerts").get_json()
    assert len(alerts) == 1
    assert alerts[0]["name"] == "Jane Smith"
    assert "never clocked out" in alerts[0]["problem"]
    assert client.get("/api/period?start=2026-01-05").get_json()["missed_punches"] == 1


def test_employee_shifts_show_clock_times(client, conn):
    employee_id = add_employee(conn)
    db.add_punch(conn, employee_id, "2026-01-05 08:00:00", "in")
    db.add_punch(conn, employee_id, "2026-01-05 16:30:00", "out")

    log_in(client)
    data = client.get(f"/api/employees/{employee_id}/shifts?start=2026-01-05").get_json()
    assert data["hours"] == "8.50"
    shift = data["shifts"][0]
    assert (shift["clock_in"], shift["clock_out"]) == ("8:00 AM", "4:30 PM")
    assert shift["in_value"] == "2026-01-05T08:00"


def test_office_can_add_a_missed_punch(client, conn):
    employee_id = add_employee(conn)
    db.add_punch(conn, employee_id, "2026-01-05 08:00:00", "in")

    log_in(client)
    response = client.post(
        f"/api/employees/{employee_id}/punches",
        json={"punch_at": "2026-01-05T16:00", "direction": "out"},
    )
    assert response.status_code == 200
    shifts = timecalc.pair_punches(db.all_punches(conn, employee_id))
    assert shifts[0]["minutes"] == 480


def test_bad_punch_time_is_rejected(client, conn):
    employee_id = add_employee(conn)
    log_in(client)
    response = client.post(
        f"/api/employees/{employee_id}/punches", json={"punch_at": "garbage", "direction": "in"}
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "Enter a valid date and time."


def test_office_can_correct_and_delete_a_punch(client, conn):
    employee_id = add_employee(conn)
    punch_id = db.add_punch(conn, employee_id, "2026-01-05 08:00:00", "in")

    log_in(client)
    client.put(f"/api/punches/{punch_id}", json={"punch_at": "2026-01-05T09:15"})
    assert db.all_punches(conn, employee_id)[0]["punch_at"] == "2026-01-05 09:15:00"

    client.delete(f"/api/punches/{punch_id}")
    assert db.all_punches(conn, employee_id) == []


# --- employees ---------------------------------------------------------------


def test_adding_an_employee(client, conn):
    log_in(client)
    client.post("/api/employees", json={"name": "Bob Ray", "pin": "4242"})
    assert db.employee_by_pin(conn, "4242")["name"] == "Bob Ray"


def test_duplicate_pins_are_refused(client, conn):
    add_employee(conn, "Jane Smith", "1111")
    log_in(client)
    response = client.post("/api/employees", json={"name": "Bob Ray", "pin": "1111"})
    assert "already in use" in response.get_json()["error"]
    assert conn.execute("SELECT COUNT(*) c FROM employees").fetchone()["c"] == 1


def test_short_pins_are_refused(client, conn):
    log_in(client)
    response = client.post("/api/employees", json={"name": "Bob Ray", "pin": "12"})
    assert response.status_code == 400
    assert conn.execute("SELECT COUNT(*) c FROM employees").fetchone()["c"] == 0


def test_deactivating_an_employee_keeps_their_punches(client, conn):
    employee_id = add_employee(conn)
    db.add_punch(conn, employee_id, "2026-01-05 08:00:00", "in")

    log_in(client)
    client.put(f"/api/employees/{employee_id}", json={"name": "Jane Smith", "active": False})
    assert db.employee(conn, employee_id)["active"] == 0
    assert len(db.all_punches(conn, employee_id)) == 1
    assert client.get("/api/employees").get_json()[0]["active"] is False


def test_changing_an_employee_pin(client, conn):
    employee_id = add_employee(conn)
    log_in(client)
    client.put(f"/api/employees/{employee_id}", json={"name": "Jane Smith", "pin": "2222", "active": True})
    assert db.employee_by_pin(conn, "2222")["id"] == employee_id
    assert db.employee_by_pin(conn, "1111") is None


# --- exports -----------------------------------------------------------------


def test_export_is_blocked_while_a_punch_is_missing(client, conn):
    employee_id = add_employee(conn)
    db.add_punch(conn, employee_id, "2026-01-05 08:00:00", "in")

    log_in(client)
    for path in ("/api/export/summary.csv", "/api/export/timesheet.csv"):
        response = client.get(f"{path}?start=2026-01-05")
        assert response.status_code == 409
        assert "text/csv" not in response.headers["Content-Type"]


def test_export_can_be_forced_and_counts_open_shifts_as_zero(client, conn):
    employee_id = add_employee(conn)
    db.add_punch(conn, employee_id, "2026-01-05 08:00:00", "in")

    log_in(client)
    response = client.get("/api/export/summary.csv?start=2026-01-05&force=1")
    assert "text/csv" in response.headers["Content-Type"]
    assert "Jane Smith,2026-01-04,2026-01-17,0.00" in response.get_data(as_text=True)


def test_summary_csv_reports_total_hours(client, conn):
    employee_id = add_employee(conn)
    db.add_punch(conn, employee_id, "2026-01-05 08:00:00", "in")
    db.add_punch(conn, employee_id, "2026-01-05 16:30:00", "out")
    db.add_punch(conn, employee_id, "2026-01-06 08:00:00", "in")
    db.add_punch(conn, employee_id, "2026-01-06 12:00:00", "out")

    log_in(client)
    body = client.get("/api/export/summary.csv?start=2026-01-05").get_data(as_text=True)
    assert "Employee,Period Start,Period End,Total Hours" in body
    assert "Jane Smith,2026-01-04,2026-01-17,12.50" in body


def test_timesheet_report_breaks_the_period_down_by_day(client, conn):
    employee_id = add_employee(conn)
    db.add_punch(conn, employee_id, "2026-01-05 08:34:00", "in")
    db.add_punch(conn, employee_id, "2026-01-05 12:32:00", "out")
    db.add_punch(conn, employee_id, "2026-01-05 13:15:00", "in")
    db.add_punch(conn, employee_id, "2026-01-05 17:01:00", "out")

    log_in(client)
    response = client.get("/api/export/timesheet.csv?start=2026-01-05")
    assert 'filename="timesheet-report-2026-01-04.csv"' in response.headers["Content-Disposition"]
    lines = response.get_data(as_text=True).splitlines()

    assert lines[0] == "Employee,Day,Date,Clock In,Clock Out,Hours (H:MM),Hours (Decimal)"
    assert lines[1] == "Jane Smith,Sunday,2026-01-04,,,,"
    assert lines[2] == "Jane Smith,Monday,2026-01-05,8:34 AM,12:32 PM,3:58,3.97"
    assert lines[3] == "Jane Smith,Monday,2026-01-05,1:15 PM,5:01 PM,3:46,3.77"
    assert lines[4] == "Jane Smith,Tuesday,2026-01-06,,,,"
    assert lines[15] == "Jane Smith,Saturday,2026-01-17,,,,"
    assert lines[16] == "Jane Smith,Period Total,,,,7:44,7.73"


def test_punches_outside_the_period_are_excluded(client, conn):
    employee_id = add_employee(conn)
    db.add_punch(conn, employee_id, "2026-01-05 08:00:00", "in")
    db.add_punch(conn, employee_id, "2026-01-05 16:00:00", "out")
    db.add_punch(conn, employee_id, "2026-01-20 08:00:00", "in")
    db.add_punch(conn, employee_id, "2026-01-20 16:00:00", "out")

    log_in(client)
    body = client.get("/api/export/summary.csv?start=2026-01-05").get_data(as_text=True)
    assert "8.00" in body and "16.00" not in body


def test_backup_downloads_a_database_file(client, conn):
    add_employee(conn)
    log_in(client)
    response = client.get("/api/backup")
    assert response.status_code == 200
    assert response.data.startswith(b"SQLite format 3")


# --- settings ----------------------------------------------------------------


def save_settings(client, **changes):
    values = {"admin_pin": "", "max_shift_hours": "16", "period_anchor": ANCHOR.isoformat()}
    return client.put("/api/settings", json={**values, **changes})


def test_settings_change_the_stale_threshold(client, conn):
    log_in(client)
    save_settings(client, max_shift_hours="10")
    assert db.max_shift_hours(conn) == 10
    assert client.get("/api/settings").get_json()["max_shift_hours"] == 10


def test_invalid_settings_change_nothing(client, conn):
    log_in(client)
    response = save_settings(client, max_shift_hours="10", period_anchor="not a date")
    assert response.status_code == 400
    assert db.max_shift_hours(conn) == 16


def test_changing_the_admin_pin_works(client, conn):
    log_in(client)
    save_settings(client, admin_pin="555555")
    client.post("/api/logout")
    assert client.post("/api/login", json={"pin": "555555"}).status_code == 200


# --- serving the frontend ----------------------------------------------------


def test_unknown_api_routes_are_json_404s(client):
    response = client.get("/api/nope")
    assert response.status_code == 404
    assert "error" in response.get_json()


def test_page_routes_serve_the_react_app(client, tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<div id=root></div>")
    monkeypatch.setattr(app_module, "FRONTEND_DIST", tmp_path)
    for path in ("/", "/admin", "/admin/employees/3"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert b"<div id=root>" in response.data
