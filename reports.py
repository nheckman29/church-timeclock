"""CSV exports. Pure functions: rows in, rows out. No Flask and no database.

Each function takes `people`, a list of (name, shifts) pairs where shifts come from
timecalc.pair_punches and are already limited to the pay period.
"""

from datetime import timedelta

import timecalc


def summary_rows(people, start, end):
    """One line per employee with total hours. The file you key into payroll."""
    rows = [
        [
            "Employee",
            "Period Start",
            "Period End",
            "Total Hours (H:MM)",
            "Total Hours (Decimal)",
        ]
    ]
    for name, shifts in people:
        total = timecalc.total_minutes(shifts)
        rows.append(
            [
                name,
                start,
                end,
                timecalc.hours_minutes(total),
                timecalc.hours_text(total),
            ]
        )
    return rows


def _clock_out_text(shift):
    """Clock-out time, with the day added when a shift runs past midnight."""
    out_at = shift["out_at"]
    if out_at is None:
        return "MISSING"
    if out_at.date() != shift["date"]:
        return f"{out_at.strftime('%a')} {timecalc.clock(out_at)}"
    return timecalc.clock(out_at)


def timesheet_rows(people, start, end):
    """Every day of the period for every employee, one line per shift.

    Days with no punches still get a line so the 14 days are always visible. Open
    shifts show MISSING and count as zero, matching the totals on screen.
    """
    rows = [
        ["Employee", "Day", "Date", "Clock In", "Clock Out", "Hours (H:MM)", "Hours (Decimal)"]
    ]
    days = [start + timedelta(days=offset) for offset in range((end - start).days + 1)]

    for name, shifts in people:
        for day in days:
            weekday, iso = day.strftime("%A"), day.isoformat()
            day_shifts = [s for s in shifts if s["date"] == day]
            if not day_shifts:
                rows.append([name, weekday, iso, "", "", "", ""])
            for shift in day_shifts:
                worked = (
                    [timecalc.hours_minutes(shift["minutes"]), timecalc.hours_text(shift["minutes"])]
                    if shift["complete"]
                    else ["OPEN", "0.00"]
                )
                rows.append(
                    [
                        name,
                        weekday,
                        iso,
                        timecalc.clock(shift["in_at"]) or "MISSING",
                        _clock_out_text(shift),
                        *worked,
                    ]
                )

        total = timecalc.total_minutes(shifts)
        rows.append(
            [name, "Period Total", "", "", "", timecalc.hours_minutes(total), timecalc.hours_text(total)]
        )
        rows.append([])
    return rows
