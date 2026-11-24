"""Downstream: what a night's sleep may affect the next day.

Each row is one next-day thing. Like the bars, it compares nights at most 15 days apart:
it fits the next day's value on the night's sleep measure, over every pair of nights,
matched on everything from before the person fell asleep. That's every Upstream bar's
columns for that night, which includes the row's own value that day. A row isn't
matched on other next-day things, or on the night's other sleep measures.
"""

from typing import NamedTuple

import numpy as np
import pandas as pd

from oura_explorer.bars import (
    BARS,
    MATCHED_AS,
    MIN_NIGHTS,
    MIN_PAIRED_YES,
    benjamini_hochberg,
    day_numbers,
    estimate,
    fit_window,
    label,
    lookalikes,
    pairs,
    paired_yes_nights,
)

# How much more of each sleep measure a Downstream row is "per": a round number close
# to how much it usually changes from one night to the next.
SLEEP_UNITS = {
    "rem_min": (15.0, "per 15 more minutes of REM"),
    "asleep_min": (60.0, "per hour more asleep"),
    "deep_min": (15.0, "per 15 more minutes of deep sleep"),
    "average_hrv": (10.0, "per 10 ms higher HRV"),
    "lowest_heart_rate": (3.0, "per 3 bpm higher lowest heart rate"),
    "average_heart_rate": (4.0, "per 4 bpm higher average heart rate"),
    "latency_min": (5.0, "per 5 more minutes to fall asleep"),
    "wake_h": (1.0, "per hour later wake-up"),
    "sleep_score": (10.0, "per 10 points higher sleep score"),
    "efficiency": (3.0, "per 3 points higher efficiency"),
}


class Row(NamedTuple):
    """A next-day thing: its label, how to show it in its unit, and whether it's yes/no."""

    label: str
    shown: float
    unit: str
    yes_no: bool


ROWS = {
    "stress_share": Row(
        "Daytime stress the next day", 100.0, "points of the readings", False
    ),
    "calm_share": Row("Calm time the next day", 100.0, "points of the readings", False),
    "steps_ph": Row("Steps the next day", 1.0, "steps an hour", False),
    "hard_min": Row("Workout the next day", 1.0, "hard minutes", False),
    "napped": Row("Daytime nap the next day", 100.0, "points more likely", True),
    "dev": Row("Bedtime the next night", 60.0, "minutes later than normal", False),
    "bb_stress": Row(
        "Stress before bed the next night", 100.0, "points of the readings", False
    ),
    "bb_hr": Row("Heart rate before bed the next night", 1.0, "bpm", False),
    "bb_steps_k": Row("Steps before bed the next night", 1000.0, "steps", False),
    "evening_nap": Row("Evening nap the next day", 100.0, "points more likely", True),
}


def next_day(nightly, column):
    """Each night's next-day value of a column: its value in the next night's row.

    Night d's next day starts when night d ends, so its day, bedtime and last hours
    before bed are in the row for night d + 1.
    """
    return nightly[column].reindex(nightly.index + pd.Timedelta(days=1)).to_numpy()


def fit_row(nightly, outcome, column, matched):
    """One row: the nights behind it and, if there are enough, its estimate."""
    row, (unit, _) = ROWS[column], SLEEP_UNITS[outcome]
    frame = pd.concat([nightly[outcome] / unit, nightly[matched]], axis=1)
    frame = frame.assign(next=next_day(nightly, column)).dropna()
    earlier, later = pairs(day_numbers(frame.index))
    in_pair = np.bincount(np.concatenate([earlier, later]), minlength=len(frame)) > 0
    nights = frame[in_pair]
    days = day_numbers(nights.index)
    result = {
        "nights": len(nights),
        "lost": [f"{night:%Y-%m-%d}" for night in frame.index[~in_pair]],
    }
    enough = len(nights) >= MIN_NIGHTS
    if row.yes_no:
        result["paired_yes"] = paired_yes_nights(nights["next"].to_numpy(), days)
        enough = enough and result["paired_yes"] >= MIN_PAIRED_YES
    if enough:
        X = nights.drop(columns="next").to_numpy(float)
        y = nights["next"].to_numpy(float) * row.shown
        slopes, errors = fit_window(y, X, days)
        result["estimate"] = estimate(slopes[0], errors[0])
    return result


def downstream(nightly, outcome):
    """Every Downstream row for one sleep measure, labelled together.

    Labels use Benjamini-Hochberg across the rows, as for the bars. A row whose
    next-day thing this export doesn't have (workouts without a watch) is left out;
    a row with too few nights, or a nap row with too few nights to pair, gets no
    estimate: not enough data.
    """
    corr = lookalikes(nightly)
    matched = [
        column for bar in corr.index for column in MATCHED_AS.get(bar, BARS[bar].terms)
    ]
    rows = {
        column: fit_row(nightly, outcome, column, matched)
        for column in ROWS
        if nightly[column].nunique() > 1
    }
    tested = [row["estimate"] for row in rows.values() if "estimate" in row]
    for result, q in zip(tested, benjamini_hochberg([r["p"] for r in tested])):
        result["q"], result["label"] = float(q), label(q, result["p"])
    return rows
