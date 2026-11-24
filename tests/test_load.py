"""Tests for loading an Oura export into DuckDB."""

from datetime import date, datetime
from pathlib import Path

from oura_explorer.load import load_export, night_summary

DEMO_EXPORT = Path(__file__).parent.parent / "demo-data"
SLEEP_COLUMNS = [
    "id",
    "day",
    "type",
    "bedtime_start",
    "bedtime_end",
    "time_in_bed",
    "total_sleep_duration",
    "rem_sleep_duration",
    "deep_sleep_duration",
    "latency",
    "efficiency",
    "average_hrv",
    "average_heart_rate",
    "lowest_heart_rate",
]


def write_sleep(folder, periods):
    """Write a sleepmodel.csv into folder.

    periods holds (Oura day, start, end, minutes asleep) for each sleep period,
    with start and end as ISO times that carry their UTC offset.
    """
    lines = [";".join(SLEEP_COLUMNS)]
    for number, (day, start, end, asleep) in enumerate(periods):
        span = datetime.fromisoformat(end) - datetime.fromisoformat(start)
        seconds = [int(span.total_seconds()), asleep * 60, 0, 0, 0]
        values = [str(number), day, "sleep", start, end, *map(str, seconds)]
        lines.append(";".join(values + [""] * 4))
    (folder / "sleepmodel.csv").write_text("\n".join(lines) + "\n")


def test_demo_export_gives_the_nights_in_the_analysis_log():
    """269 nights from Jan 3 to Sep 29, 2026, none for May 25, each paired with the one before."""
    con = load_export(DEMO_EXPORT)
    assert night_summary(con) == (269, date(2026, 1, 3), date(2026, 9, 29))
    assert con.execute(
        "SELECT count(*) FROM nights WHERE night = '2026-05-25'"
    ).fetchone() == (0,)
    assert con.execute(
        "SELECT woke_at FROM nights WHERE night = '2026-05-26'"
    ).fetchone() == (None,)
    mismatched = con.execute("""
        SELECT count(*)
        FROM nights AS tonight
        JOIN nights AS before ON before.night = tonight.night - 1
        WHERE tonight.woke_at <> before.end_at
        """).fetchone()
    assert mismatched == (0,)


def test_sleep_less_than_an_hour_away_joins_the_night(tmp_path):
    """A doze 30 minutes before bed joins the night; a nap 5 hours before stays a nap."""
    write_sleep(
        tmp_path,
        [
            (
                "2026-03-21",
                "2026-03-20T20:00:00-05:00",
                "2026-03-21T02:00:00-05:00",
                300,
            ),
            (
                "2026-03-21",
                "2026-03-20T19:00:00-05:00",
                "2026-03-20T19:30:00-05:00",
                20,
            ),
            (
                "2026-03-21",
                "2026-03-20T14:00:00-05:00",
                "2026-03-20T15:00:00-05:00",
                40,
            ),
            ("2026-03-21", "2026-03-20T16:30:00-05:00", "2026-03-20T16:40:00-05:00", 5),
        ],
    )
    con = load_export(tmp_path)
    nights = con.execute("SELECT night, start_local, asleep_min, pieces FROM nights")
    assert nights.fetchall() == [
        (date(2026, 3, 21), datetime(2026, 3, 20, 19), 320.0, 2)
    ]
    assert con.execute("SELECT asleep_min FROM naps").fetchall() == [(40.0,)]


def test_stress_labels_come_back_the_right_way_round(tmp_path):
    """The export puts stress readings under recovery_value and calm ones under stress_value."""
    (tmp_path / "daytimestress.csv").write_text(
        "timestamp;recovery_value;stress_value\n"
        "2026-01-10T07:00:00.000Z;80;\n"
        "2026-01-10T07:05:00.000Z;;60\n"
    )
    con = load_export(tmp_path)
    readings = con.execute("SELECT kind, value FROM readings ORDER BY taken_at")
    assert readings.fetchall() == [("stress", 80.0), ("calm", 60.0)]


def test_missing_and_header_only_files_give_empty_tables(tmp_path):
    """An export with a header-only sleepmodel.csv and no other files still loads."""
    (tmp_path / "sleepmodel.csv").write_text(";".join(SLEEP_COLUMNS) + "\n")
    con = load_export(tmp_path)
    assert night_summary(con) == (0, None, None)
    assert con.execute("SELECT count(*) FROM steps").fetchone() == (0,)
