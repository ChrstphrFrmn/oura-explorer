"""Tests for the nightly table: the counting windows, shares, steps and naps."""

import csv
import shutil
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


DAY_OF_JAN_7 = """
    SELECT epoch(t.day_stop), d.steps_ph, sum(s.steps)
    FROM nights AS n
    JOIN night_times AS t USING (night)
    JOIN day_factors AS d USING (night)
    JOIN steps AS s ON s.taken_at >= n.woke_at AND s.taken_at < n.start_at
    WHERE n.night = '2026-01-07'
    GROUP BY ALL
"""


def made_up_day(folder, bedtime_hour):
    """Six nights from 8 PM to 2 AM, the last from bedtime_hour instead.

    The ring logs 1 step a minute from wake-up at 2 AM on Jan 6 until 8 PM.
    """
    folder.mkdir()
    sleep = [SLEEP_COLUMNS]
    for day in range(1, 7):
        start = local(day, bedtime_hour if day == 6 else 20)
        sleep.append(sleep_row(day, day + 1, start, local(day + 1, 2), 300))
    (folder / "sleepmodel.csv").write_text("\n".join(sleep) + "\n")
    minutes = (local(6, 2) + timedelta(minutes=m) for m in range(18 * 60))
    steps = ["timestamp;steps", *(f"{utc(minute)};1" for minute in minutes)]
    (folder / "stepcount.csv").write_text("\n".join(steps) + "\n")
    return load_export(folder)


def test_counting_up_to_bedtime_would_leak(tmp_path):
    """To bed at 7 PM instead of 8 PM: the day stop (5 PM) and steps per hour (60) stay.

    Counting from wake-up to bedtime, the old way, would lose an hour of steps
    (1,080 down to 1,020), so a later bedtime would look like more steps.
    """
    at_8 = made_up_day(tmp_path / "at_8", 20).execute(DAY_OF_JAN_7).fetchone()
    at_7 = made_up_day(tmp_path / "at_7", 19).execute(DAY_OF_JAN_7).fetchone()
    assert at_8[:2] == at_7[:2]
    assert at_8[1] == 60.0
    assert (at_8[2], at_7[2]) == (1080.0, 1020.0)


DAY_OF_AUG_29 = """
    SELECT epoch(day_stop), day_ok, stress_share, calm_share, steps_ph,
           nap_min, evening_nap, hard_min, bed_h, hours_awake
    FROM nightly
    WHERE night = '2026-08-29'
"""


def move_bedtime(folder, period, hours):
    """Start one sleep period `hours` earlier in an export, keeping its end."""
    path = folder / "sleepmodel.csv"
    with path.open(newline="") as f:
        rows = list(csv.reader(f, delimiter=";"))
    start, in_bed = rows[0].index("bedtime_start"), rows[0].index("time_in_bed")
    for row in rows[1:]:
        if row[0] == period:
            moved = datetime.fromisoformat(row[start]) - timedelta(hours=hours)
            row[start] = moved.isoformat(timespec="milliseconds")
            row[in_bed] = str(int(row[in_bed]) + hours * 3600)
    with path.open("w", newline="") as f:
        csv.writer(f, delimiter=";").writerows(rows)


def test_a_real_night_moved_an_hour_earlier_keeps_its_day(tmp_path):
    """Fri Aug 28: in bed at 7:50 PM, day stop 5:18 PM, no nap.

    Moved to 6:50 PM in a copy of the demo export, the day's stop, stress, calm,
    steps, naps and hard minutes don't move. Only bedtime and hours awake do.
    """
    before = load_export(DEMO_EXPORT).execute(DAY_OF_AUG_29).fetchone()
    export = tmp_path / "export"
    shutil.copytree(DEMO_EXPORT, export)
    move_bedtime(export, "436ba8b4-5101-4a91-8b9c-d0da568fbfc9", 1)
    after = load_export(export).execute(DAY_OF_AUG_29).fetchone()
    assert after[:8] == before[:8]
    assert before[8] - after[8] == pytest.approx(1)
    assert before[9] - after[9] == pytest.approx(1)
