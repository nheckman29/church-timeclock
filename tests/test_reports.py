from datetime import date, datetime

import reports
import timecalc

START, END = date(2026, 1, 4), date(2026, 1, 17)


def punch(punch_id, at, direction):
    return {"id": punch_id, "punch_at": at, "direction": direction}


def shifts(*punches):
    return timecalc.pair_punches(list(punches))


def test_formatters_are_minute_accurate():
    assert timecalc.clock(datetime(2026, 1, 5, 8, 4)) == "8:04 AM"
    assert timecalc.clock(datetime(2026, 1, 5, 12, 32)) == "12:32 PM"
    assert timecalc.hours_minutes(464) == "7:44"
    assert timecalc.hours_minutes(5) == "0:05"
    assert timecalc.hours_text(464) == "7.73"
    assert timecalc.day_label(date(2026, 1, 5)) == "Mon 01/05"


def test_timesheet_lists_all_14_days_per_employee():
    rows = reports.timesheet_rows([("Jane", []), ("Bob", [])], START, END)
    jane_days = [row for row in rows if row and row[0] == "Jane" and row[1] != "Period Total"]
    assert len(jane_days) == 14
    assert [row[1] for row in jane_days[:7]] == [
        "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"
    ]
    assert ["Jane", "Period Total", "", "", "", "0:00", "0.00"] in rows
    assert ["Bob", "Period Total", "", "", "", "0:00", "0.00"] in rows


def test_timesheet_marks_open_shifts():
    jane = shifts(punch(1, "2026-01-05 08:00:00", "in"))
    rows = reports.timesheet_rows([("Jane", jane)], START, END)
    assert ["Jane", "Monday", "2026-01-05", "8:00 AM", "MISSING", "OPEN", "0.00"] in rows


def test_timesheet_shows_the_day_for_an_overnight_clock_out():
    jane = shifts(
        punch(1, "2026-01-05 22:00:00", "in"), punch(2, "2026-01-06 02:15:00", "out")
    )
    rows = reports.timesheet_rows([("Jane", jane)], START, END)
    assert ["Jane", "Monday", "2026-01-05", "10:00 PM", "Tue 2:15 AM", "4:15", "4.25"] in rows


def test_summary_has_one_line_per_employee():
    jane = shifts(punch(1, "2026-01-05 08:00:00", "in"), punch(2, "2026-01-05 16:30:00", "out"))
    rows = reports.summary_rows([("Jane", jane)], START, END)
    assert rows == [
        ["Employee", "Period Start", "Period End", "Total Hours"],
        ["Jane", START, END, "8.50"],
    ]
