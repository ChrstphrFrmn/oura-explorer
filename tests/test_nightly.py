"""Tests for the nightly table: the counting windows, shares, steps and naps."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from oura_explorer.load import load_export

DEMO_EXPORT = Path(__file__).parent.parent / "demo-data"
CENTRAL = timezone(timedelta(hours=-6))
SLEEP_COLUMNS = (
    "id;day;type;bedtime_start;bedtime_end;time_in_bed;total_sleep_duration;"
    "rem_sleep_duration;deep_sleep_duration;latency;efficiency;average_hrv;"
    "average_heart_rate;lowest_heart_rate"
)


def local(day, hour, minute=0):
    """A clock time in January 2026 on US Central time (UTC-6)."""
    return datetime(2026, 1, day, hour, minute, tzinfo=CENTRAL)


def sleep_row(number, day, start, end, asleep_min):
    """One line of sleepmodel.csv for a period from start to end on Oura's day."""
    in_bed = int((end - start).total_seconds())
    times = [start.isoformat(), end.isoformat(), str(in_bed), str(asleep_min * 60)]
    return ";".join([str(number), f"2026-01-{day:02d}", "sleep", *times, "0;0;0;;;;"])


def utc(moment):
    """The UTC timestamp text the export uses for readings and steps."""
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


@pytest.fixture
def one_day(tmp_path):
    """An export with six nights, 8 PM to 2 AM, then a known day before the sixth.

    The normal bedtime is 8 PM, so the day stop on Jan 6 is 5 PM. That day has 30
    readings from 6 AM (12 high stress, 3 low stress, 9 high calm, 6 low calm),
    2 steps a minute from wake-up at 2 AM to the stop, a nap from 4:00 to 5:20 PM
    (middle before the stop) and one from 5:40 to 6:20 PM (middle after it).
    Imported heart rate: 10 minutes at 150 bpm and 10 at 100 from 8 AM, then 5 minutes
    at 150 after the stop. The top heart rate is 150, so 120 or more is hard.
    A reading, steps and hard minutes after the stop must not count toward the day.
    """
    sleep = [SLEEP_COLUMNS]
    for day in range(1, 7):
        start, end = local(day, 20), local(day + 1, 2)
        sleep.append(sleep_row(day, day + 1, start, end, 300))
    sleep.append(sleep_row(7, 7, local(6, 16), local(6, 17, 20), 60))
    sleep.append(sleep_row(8, 7, local(6, 17, 40), local(6, 18, 20), 30))
    (tmp_path / "sleepmodel.csv").write_text("\n".join(sleep) + "\n")

    kinds = [("70;", 12), ("30;", 3), (";80", 9), (";20", 6)]
    values = [value for value, count in kinds for _ in range(count)]
    readings = ["timestamp;recovery_value;stress_value"]
    for step, value in enumerate(values):
        readings.append(f"{utc(local(6, 6) + timedelta(minutes=5 * step))};{value}")
    readings.append(f"{utc(local(6, 18))};90;")
    (tmp_path / "daytimestress.csv").write_text("\n".join(readings) + "\n")

    steps = ["timestamp;steps"]
    for minute in range(15 * 60):
        steps.append(f"{utc(local(6, 2) + timedelta(minutes=minute))};2")
    steps.append(f"{utc(local(6, 17, 30))};500")
    (tmp_path / "stepcount.csv").write_text("\n".join(steps) + "\n")

    beats = [
        (local(6, 8), 150, 10),
        (local(6, 8, 10), 100, 10),
        (local(6, 18, 30), 150, 5),
    ]
    imported = ["timestamp;bpm;imported_from;origin_source"]
    for start, bpm, minutes in beats:
        for minute in range(minutes):
            moment = utc(start + timedelta(minutes=minute))
            imported.append(f"{moment};{bpm};google_health_connect;")
    (tmp_path / "importedheartrate.csv").write_text("\n".join(imported) + "\n")
    return load_export(tmp_path)


def test_the_day_is_counted_up_to_the_stop(one_day):
    """Shares, steps per hour, naps and hard minutes for the night of Jan 7 come out as built."""
    row = one_day.execute("""
        SELECT normal_bed_h, day_ok, stress_share, calm_share, steps_ph,
               nap_min, napped, evening_nap, hard_min
        FROM nightly
        WHERE night = '2026-01-07'
        """).fetchone()
    assert row == (8.0, True, 0.4, 0.3, 120.0, 60.0, 1.0, 1.0, 10.0)


def test_no_imported_heart_rate_leaves_hard_minutes_empty(one_day, tmp_path):
    """Without an imported heart-rate file no night gets hard minutes, not even 0."""
    (tmp_path / "importedheartrate.csv").unlink()
    con = load_export(tmp_path)
    assert con.execute("SELECT count(hard_min) FROM nightly").fetchone() == (0,)


def test_demo_export_matches_the_change_3_counts():
    """The demo export gives the night counts from the Change 3 and Change 2 runs."""
    con = load_export(DEMO_EXPORT)
    counts = con.execute("""
        SELECT
            count(*),
            count(stress_share),
            count(steps_ph),
            sum(napped),
            sum(evening_nap),
            count(bb_stress),
            count(bb_hr),
            count(bb_steps_k),
            sum(early_group),
            sum(late_group),
            count(hard_min),
            count(*) FILTER (WHERE hard_min > 0)
        FROM nightly
        """).fetchone()
    assert counts == (269, 248, 248, 36, 12, 250, 233, 259, 40, 44, 262, 200)
