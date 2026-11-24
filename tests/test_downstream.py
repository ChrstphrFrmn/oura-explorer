"""Tests for Downstream on made-up nights: the matching, the next day and missing rows."""

import numpy as np
import pandas as pd
import pytest

from oura_explorer.bars import BARS, MATCHED_AS, lookalikes
from oura_explorer.downstream import ROWS, downstream, fit_row, next_day


@pytest.fixture
def made_up():
    """150 made-up nights where stress carries over and REM lowers the next day's stress.

    Today's stress lowers tonight's REM and carries into tomorrow, so it's a confounder.
    Every night, next-day stress = 0.6 x today's stress - 0.002 x tonight's REM (in
    minutes) + 0.001 x today's steps an hour - 0.12, plus a little noise. Everything
    else is random; the clock bedtime is a drifting normal bedtime plus the distance
    from it.
    """
    rng = np.random.default_rng(395)
    count = 150
    steps = rng.uniform(200, 600, count)
    stress, rem = np.empty(count), np.empty(count)
    stress[0] = 0.4
    for d in range(count):
        rem[d] = 100 - 100 * stress[d] + rng.normal(0, 8)
        if d + 1 < count:
            carried = 0.6 * stress[d] - 0.002 * rem[d] + 0.001 * steps[d] - 0.12
            stress[d + 1] = carried + rng.normal(0, 0.002)
    dev = rng.normal(0, 1, count)
    nights = pd.DatetimeIndex(pd.date_range("2026-01-01", periods=count, name="night"))
    frame = pd.DataFrame(
        {
            "rem_min": rem,
            "stress_share": stress,
            "last_sleep_h": rng.normal(5, 1, count),
            "weekend": (np.arange(count) % 7 >= 5).astype(float),
            "spread_min": rng.uniform(20, 90, count),
            "hard_min": rng.uniform(0, 40, count),
            "calm_share": rng.uniform(0.1, 0.4, count),
            "steps_ph": steps,
            "napped": (rng.random(count) < 0.3).astype(float),
            "dev": dev,
            "earlier": np.maximum(-dev, 0),
            "later": np.maximum(dev, 0),
            "bed_h": rng.normal(8, 0.5, count) + dev,
            "hours_awake": rng.normal(18, 1.5, count),
            "bb_stress": rng.uniform(0, 1, count),
            "bb_hr": rng.normal(75, 5, count),
            "bb_steps_k": rng.uniform(0, 2, count),
            "evening_nap": (rng.random(count) < 0.3).astype(float),
        },
        index=nights,
    )
    return frame


def test_next_day_is_the_next_nights_row(made_up):
    """Night d's next day is the row for night d + 1; the last night has none."""
    following = next_day(made_up, "stress_share")
    assert following[0] == made_up["stress_share"].iloc[1]
    assert np.isnan(following[-1])


def test_the_stress_row_is_matched_on_todays_stress(made_up):
    """REM's stress row finds -0.002 a minute: 3 points less per 15 more minutes."""
    rows = downstream(made_up, "rem_min")
    assert set(rows) == set(ROWS)
    assert all("estimate" in row for row in rows.values())
    assert rows["stress_share"]["estimate"]["effect"] == pytest.approx(-3.0, abs=0.3)


def test_without_matching_on_todays_stress_the_row_is_wrong(made_up):
    """Leaving today's stress out credits REM with stress that just carried over."""
    corr = lookalikes(made_up)
    matched = [c for b in corr.index for c in MATCHED_AS.get(b, BARS[b].terms)]
    unmatched = [column for column in matched if column != "stress_share"]
    wrong = fit_row(made_up, "rem_min", "stress_share", unmatched)["estimate"]
    assert wrong["effect"] < -5


def test_without_a_watch_there_is_no_workout_row(made_up):
    """With no hard minutes there's no workout row, and nothing is matched on it."""
    rows = downstream(made_up.assign(hard_min=np.nan), "rem_min")
    assert "hard_min" not in rows
    assert rows["stress_share"]["estimate"]["effect"] == pytest.approx(-3.0, abs=0.3)
