"""Pure time math: pairing punches, totalling hours, biweekly periods.

No Flask and no database imports live here, so every function is trivially testable.
All timestamps are naive local time.
"""

from datetime import datetime, timedelta

FMT = "%Y-%m-%d %H:%M:%S"
DATE_FMT = "%Y-%m-%d"


def parse(timestamp):
    return datetime.strptime(timestamp, FMT)


def fmt(moment):
    return moment.strftime(FMT)


def parse_date(text):
    return datetime.strptime(text, DATE_FMT).date()


def parse_form_datetime(text):
    """Accept the 'YYYY-MM-DDTHH:MM' value an <input type="datetime-local"> submits."""
    text = text.strip().replace("T", " ")
    if len(text) == 16:
        text += ":00"
    return parse(text)


def _shift(in_punch, out_punch):
    in_at = parse(in_punch["punch_at"]) if in_punch else None
    out_at = parse(out_punch["punch_at"]) if out_punch else None
    minutes = None
    if in_at and out_at:
        minutes = max(0, int((out_at - in_at).total_seconds() // 60))
    return {
        "in_id": in_punch["id"] if in_punch else None,
        "out_id": out_punch["id"] if out_punch else None,
        "in_at": in_at,
        "out_at": out_at,
        "minutes": minutes,
        "complete": minutes is not None,
        "date": (in_at or out_at).date(),
    }


def pair_punches(punches):
    """Pair each 'in' with the next 'out' for a single employee.

    Unmatched punches are kept rather than dropped, so bad data stays visible to the
    practitioner instead of silently disappearing from the totals.
    """
    shifts = []
    open_in = None
    for punch in sorted(punches, key=lambda p: (p["punch_at"], p["id"])):
        if punch["direction"] == "in":
            if open_in is not None:
                shifts.append(_shift(open_in, None))
            open_in = punch
        elif open_in is None:
            shifts.append(_shift(None, punch))
        else:
            shifts.append(_shift(open_in, punch))
            open_in = None
    if open_in is not None:
        shifts.append(_shift(open_in, None))
    return shifts


def is_stale(shift, max_shift_hours, now=None):
    """An incomplete shift older than the threshold: almost always a forgotten punch."""
    if shift["complete"]:
        return False
    now = now or datetime.now()
    reference = shift["in_at"] or shift["out_at"]
    return reference < now - timedelta(hours=max_shift_hours)


def in_period(shift, start, end):
    return start <= shift["date"] <= end


def total_minutes(shifts):
    return sum(s["minutes"] for s in shifts if s["complete"])


def hours(minutes):
    return round(minutes / 60, 2)


def day_totals(shifts):
    """[(date, minutes, has_open_shift)] sorted by date."""
    days = {}
    for shift in shifts:
        minutes, has_open = days.get(shift["date"], (0, False))
        days[shift["date"]] = (
            minutes + (shift["minutes"] or 0),
            has_open or not shift["complete"],
        )
    return [(day, m, open_) for day, (m, open_) in sorted(days.items())]


def period_bounds(day, anchor):
    """The 14-day period containing `day`, counted from `anchor` so periods never drift."""
    index = (day - anchor).days // 14
    start = anchor + timedelta(days=14 * index)
    return start, start + timedelta(days=13)


# --- display formatting ------------------------------------------------------
# All date and time text the screens and reports show is produced here, so the
# frontend never has to do date math.


def clock(moment):
    """'8:34 AM'"""
    return moment.strftime("%I:%M %p").lstrip("0") if moment else ""


def day_label(value):
    """'Mon 01/05'"""
    return value.strftime("%a %m/%d") if value else ""


def hours_text(minutes):
    """'8.57'"""
    return f"{hours(minutes or 0):.2f}"


def hours_minutes(minutes):
    """'8:34'. Exact to the minute, unlike decimal hours."""
    minutes = minutes or 0
    return f"{minutes // 60}:{minutes % 60:02d}"


def input_value(moment):
    """The 'YYYY-MM-DDTHH:MM' format an <input type="datetime-local"> expects."""
    return moment.strftime("%Y-%m-%dT%H:%M") if moment else ""
