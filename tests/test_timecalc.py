from datetime import date, datetime, timedelta

import timecalc


def punch(punch_id, at, direction):
    return {"id": punch_id, "punch_at": at, "direction": direction}


def test_simple_shift_pairs_to_exact_minutes():
    shifts = timecalc.pair_punches(
        [punch(1, "2026-03-02 08:00:00", "in"), punch(2, "2026-03-02 16:30:00", "out")]
    )
    assert len(shifts) == 1
    assert shifts[0]["minutes"] == 510
    assert timecalc.hours(shifts[0]["minutes"]) == 8.5
    assert shifts[0]["complete"]


def test_multiple_pairs_in_one_day_for_a_lunch_break():
    shifts = timecalc.pair_punches(
        [
            punch(1, "2026-03-02 08:00:00", "in"),
            punch(2, "2026-03-02 12:00:00", "out"),
            punch(3, "2026-03-02 13:00:00", "in"),
            punch(4, "2026-03-02 17:00:00", "out"),
        ]
    )
    assert [s["minutes"] for s in shifts] == [240, 240]
    assert timecalc.total_minutes(shifts) == 480


def test_missing_clock_out_leaves_an_open_shift_worth_zero():
    shifts = timecalc.pair_punches([punch(1, "2026-03-02 08:00:00", "in")])
    assert len(shifts) == 1
    assert shifts[0]["complete"] is False
    assert shifts[0]["out_at"] is None
    assert timecalc.total_minutes(shifts) == 0


def test_two_clock_ins_in_a_row_leave_the_first_open():
    shifts = timecalc.pair_punches(
        [
            punch(1, "2026-03-02 08:00:00", "in"),
            punch(2, "2026-03-03 08:00:00", "in"),
            punch(3, "2026-03-03 16:00:00", "out"),
        ]
    )
    assert [s["complete"] for s in shifts] == [False, True]
    assert shifts[1]["minutes"] == 480


def test_orphan_clock_out_is_kept_not_discarded():
    shifts = timecalc.pair_punches([punch(1, "2026-03-02 16:00:00", "out")])
    assert len(shifts) == 1
    assert shifts[0]["in_at"] is None
    assert shifts[0]["complete"] is False


def test_overnight_shift_spans_midnight():
    shifts = timecalc.pair_punches(
        [punch(1, "2026-03-02 22:00:00", "in"), punch(2, "2026-03-03 02:30:00", "out")]
    )
    assert shifts[0]["minutes"] == 270
    assert shifts[0]["date"] == date(2026, 3, 2)


def test_punches_are_sorted_before_pairing():
    shifts = timecalc.pair_punches(
        [punch(2, "2026-03-02 16:00:00", "out"), punch(1, "2026-03-02 08:00:00", "in")]
    )
    assert shifts[0]["minutes"] == 480


def test_day_totals_group_by_calendar_date():
    shifts = timecalc.pair_punches(
        [
            punch(1, "2026-03-02 08:00:00", "in"),
            punch(2, "2026-03-02 12:00:00", "out"),
            punch(3, "2026-03-03 09:00:00", "in"),
        ]
    )
    totals = timecalc.day_totals(shifts)
    assert totals == [(date(2026, 3, 2), 240, False), (date(2026, 3, 3), 0, True)]


def test_stale_threshold_boundary():
    now = datetime(2026, 3, 3, 9, 0, 0)
    shift = timecalc.pair_punches([punch(1, "2026-03-02 08:00:00", "in")])[0]
    assert timecalc.is_stale(shift, 16, now) is True
    assert timecalc.is_stale(shift, 48, now) is False


def test_completed_shifts_are_never_stale():
    now = datetime(2030, 1, 1, 0, 0, 0)
    shift = timecalc.pair_punches(
        [punch(1, "2026-03-02 08:00:00", "in"), punch(2, "2026-03-02 16:00:00", "out")]
    )[0]
    assert timecalc.is_stale(shift, 16, now) is False


def test_period_bounds_are_fourteen_days_from_the_anchor():
    anchor = date(2026, 1, 4)
    assert timecalc.period_bounds(date(2026, 1, 4), anchor) == (date(2026, 1, 4), date(2026, 1, 17))
    assert timecalc.period_bounds(date(2026, 1, 17), anchor) == (date(2026, 1, 4), date(2026, 1, 17))
    assert timecalc.period_bounds(date(2026, 1, 18), anchor) == (
        date(2026, 1, 18),
        date(2026, 1, 31),
    )


def test_period_bounds_work_before_the_anchor():
    anchor = date(2026, 1, 4)
    assert timecalc.period_bounds(date(2026, 1, 3), anchor) == (
        date(2025, 12, 21),
        date(2026, 1, 3),
    )


def test_periods_do_not_drift_over_a_year():
    anchor = date(2026, 1, 4)
    start, end = timecalc.period_bounds(anchor + timedelta(days=364), anchor)
    assert (start - anchor).days % 14 == 0
    assert (end - start).days == 13


def test_parse_form_datetime_accepts_browser_value():
    assert timecalc.parse_form_datetime("2026-03-02T08:30") == datetime(2026, 3, 2, 8, 30)