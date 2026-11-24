"""The bars in "What's linked to it": one per factor, how sure it is, and its label.

A bar compares nights at most 15 days apart. For every pair of the bar's nights 1 to 15
days apart, it takes the later night minus the earlier one, for the sleep measure, the
factor and everything the bar is matched on, and fits one slope through zero to all the
pairs' changes. Every night is in many pairs, so how sure the bar is gets worked out
night by night, each night counted once: Newey-West with 7 lags, nights in date order.

The month version compares nights within calendar months instead. It's kept for the
Advanced view.
"""

import math
from statistics import NormalDist
from typing import Callable, NamedTuple

import numpy as np
import pandas as pd

WINDOW = 15
LAGS = 7
MIN_NIGHTS = 60
MIN_PAIRED_YES = 20
LOOKALIKE_R = 0.5
Z = NormalDist().inv_cdf(0.975)


class Bar(NamedTuple):
    """A bar's label, its unit and what one unit means, its stage, and its columns.

    Stages: 0 background, 1 the day, 2 bedtime, 3 the last hours before bed.
    """

    label: str
    unit: float
    per: str
    stage: int
    yes_no: bool
    terms: tuple[str, ...]


BARS = {
    "last_sleep_h": Bar(
        "Last night's sleep", 1.0, "per hour more sleep", 0, False, ("last_sleep_h",)
    ),
    "weekend": Bar(
        "Weekday or weekend", 1.0, "weekend vs weekday", 0, True, ("weekend",)
    ),
    "spread_min": Bar(
        "Bedtime regularity", 30.0, "per 30 min more spread", 0, False, ("spread_min",)
    ),
    "stress_share": Bar(
        "Daytime stress",
        0.1,
        "per 10 points more of the readings",
        1,
        False,
        ("stress_share",),
    ),
    "calm_share": Bar(
        "Calm time",
        0.1,
        "per 10 points more of the readings",
        1,
        False,
        ("calm_share",),
    ),
    "steps_ph": Bar(
        "Steps", 100.0, "per 100 more steps an hour", 1, False, ("steps_ph",)
    ),
    "napped": Bar("Daytime naps", 1.0, "nap day vs not", 1, True, ("napped",)),
    "bedtime": Bar(
        "Earlier or later than normal", 1.0, "per hour", 2, False, ("earlier", "later")
    ),
    "hours_awake": Bar(
        "Hours awake", 1.5, "per 90 min more awake", 2, False, ("hours_awake",)
    ),
    "bb_stress": Bar(
        "Stress before bed",
        0.25,
        "per 25 points more of the readings",
        3,
        False,
        ("bb_stress",),
    ),
    "bb_hr": Bar(
        "Heart rate before bed", 5.0, "per 5 bpm higher", 3, False, ("bb_hr",)
    ),
    "bb_steps_k": Bar(
        "Steps before bed", 0.5, "per 500 steps", 3, False, ("bb_steps_k",)
    ),
    "evening_nap": Bar(
        "Evening nap", 1.0, "evening nap vs not", 3, True, ("evening_nap",)
    ),
}
# The bedtime bar has two sides. Look-alikes are judged on the signed distance from
# normal, and a later bar that holds it the same is matched on both sides and on the
# clock bedtime, so it compares nights that went to bed at the same time.
LOOKALIKE_COLUMN = {"bedtime": "dev"}
MATCHED_AS = {"bedtime": ("earlier", "later", "bed_h")}
GROUPS = ("early_group", "late_group")


def nightly_frame(con):
    """The nightly table, one row per night in date order, indexed by the night's date."""
    query = "SELECT * FROM nightly ORDER BY night"
    frame = pd.DataFrame(con.execute(query).fetchnumpy())
    return frame.set_index(pd.DatetimeIndex(frame.pop("night")))


def day_numbers(dates):
    """Calendar day numbers of the nights' dates, for how many days apart two nights are."""
    return dates.values.astype("datetime64[D]").astype(np.int64)


def month_numbers(dates):
    """One number per calendar month, counting years: same number, same month."""
    return np.asarray(dates.year * 12 + dates.month)


def pairs(days, window=WINDOW):
    """Every pair of nights 1 to `window` days apart, as (earlier, later) row numbers.

    days must be sorted, one per night.
    """
    earlier, later = np.triu_indices(len(days), k=1)
    near = days[later] - days[earlier] <= window
    return earlier[near], later[near]


def newey_west(scores, lags=LAGS):
    """Newey-West (Bartlett) sum of the score rows' outer products, rows in date order."""
    total = scores.T @ scores
    for lag in range(1, lags + 1):
        cross = scores[lag:].T @ scores[:-lag]
        total = total + (1 - lag / (lags + 1)) * (cross + cross.T)
    return total


def fit_window(y, X, days):
    """The 15-day comparison: one slope per column of X, through zero, over every pair.

    Every night must be in at least one pair. Returns the slopes and their standard
    errors. A night's score is the sum of its changes over its pairs times the average
    of its pair residuals, both taken as the night minus the other night.
    """
    earlier, later = pairs(days)
    dX, dy = X[later] - X[earlier], y[later] - y[earlier]
    bread = np.linalg.inv(dX.T @ dX)
    slopes = bread @ dX.T @ dy
    residuals = dy - dX @ slopes
    changes, own = np.zeros_like(X), np.zeros_like(y)
    for rows, sign in ((later, 1), (earlier, -1)):
        np.add.at(changes, rows, sign * dX)
        np.add.at(own, rows, sign * residuals)
    count = np.bincount(np.concatenate([earlier, later]), minlength=len(y))
    scores = changes * (own / count)[:, None]
    return slopes, np.sqrt(np.diag(bread @ newey_west(scores) @ bread))


def fit_month(y, X, months):
    """The month version: compared within calendar months, as with month indicators.

    Returns the slopes and their Newey-West standard errors.
    """
    Xd = X - pd.DataFrame(X).groupby(months).transform("mean").to_numpy()
    yd = y - pd.Series(y).groupby(months).transform("mean").to_numpy()
    bread = np.linalg.inv(Xd.T @ Xd)
    slopes = bread @ Xd.T @ yd
    scores = Xd * (yd - Xd @ slopes)[:, None]
    return slopes, np.sqrt(np.diag(bread @ newey_west(scores) @ bread))


def paired_yes_nights(x, days, window=WINDOW):
    """How many yes nights can each be paired with a different no night `window` days away.

    Going through the yes nights in date order and giving each the earliest free no
    night within reach pairs as many as possible.
    """
    no_days = days[x == 0]
    paired = free = 0
    for day in days[x == 1]:
        while free < len(no_days) and no_days[free] < day - window:
            free += 1
        if free < len(no_days) and no_days[free] <= day + window:
            paired += 1
            free += 1
    return paired


def paired_within_months(x, months):
    """How many yes nights can each be paired with a different no night in their month."""
    table = pd.crosstab(months, x)
    return 0 if table.shape[1] < 2 else int(table.min(axis=1).sum())


class Comparison(NamedTuple):
    """How a version compares nights: its fit, how it places nights, its yes/no rule."""

    fit: Callable
    place: Callable
    paired_yes: Callable


COMPARISONS = {
    "window": Comparison(fit_window, day_numbers, paired_yes_nights),
    "month": Comparison(fit_month, month_numbers, paired_within_months),
}


def lookalikes(nightly):
    """How closely each pair of bars moves together (|r|), across all nights."""
    columns = [LOOKALIKE_COLUMN.get(bar, bar) for bar in BARS]
    corr = nightly[columns].corr().abs().to_numpy()
    return pd.DataFrame(corr, index=list(BARS), columns=list(BARS))


def held(bar, corr):
    """The bars a bar is matched on: earlier stages, and same-stage bars that aren't look-alikes."""
    stage = BARS[bar].stage
    return [
        other
        for other, spec in BARS.items()
        if other != bar
        and (
            spec.stage < stage
            or (spec.stage == stage and corr.loc[bar, other] < LOOKALIKE_R)
        )
    ]


def held_columns(bar, corr):
    """The columns behind the bars a bar is matched on."""
    return [
        column
        for other in held(bar, corr)
        for column in MATCHED_AS.get(other, BARS[other].terms)
    ]


def estimate(slope, error):
    """A slope with its standard error, 95% range and two-sided p (normal curve)."""
    return {
        "effect": float(slope),
        "se": float(error),
        "low": float(slope - Z * error),
        "high": float(slope + Z * error),
        "p": math.erfc(abs(slope / error) / math.sqrt(2)),
    }


def fit_bar(nightly, outcome, bar, corr, compare="window", terms=None, scale=None):
    """One bar: what it's matched on, the nights behind it and, if enough, its terms.

    compare is "window" (nights at most 15 days apart) or "month" (the same month).
    Nights with no other usable night within 15 days are lost, in both versions.
    A bar with too few nights, or a yes/no bar with too few yes nights that can be
    paired with a no night, gets no terms: not enough data.
    terms and scale replace the bar's own columns and unit, for the bedtime groups.
    """
    spec, way = BARS[bar], COMPARISONS[compare]
    terms, scale = list(terms or spec.terms), scale or spec.unit
    matched = held_columns(bar, corr)
    usable = nightly[[outcome, *terms, *matched]].dropna()
    earlier, later = pairs(day_numbers(usable.index))
    in_pair = np.bincount(np.concatenate([earlier, later]), minlength=len(usable)) > 0
    nights = usable[in_pair]
    place = way.place(nights.index)
    result = {
        "held": held(bar, corr),
        "nights": len(nights),
        "lost": [f"{night:%Y-%m-%d}" for night in usable.index[~in_pair]],
    }
    enough = len(nights) >= MIN_NIGHTS
    if spec.yes_no:
        result["paired_yes"] = way.paired_yes(nights[terms[0]].to_numpy(), place)
        enough = enough and result["paired_yes"] >= MIN_PAIRED_YES
    if enough:
        y = nights[outcome].to_numpy(float)
        X = pd.concat([nights[terms] / scale, nights[matched]], axis=1).to_numpy(float)
        slopes, errors = way.fit(y, X, place)
        result["terms"] = {
            term: estimate(slopes[k], errors[k]) for k, term in enumerate(terms)
        }
    return result


def benjamini_hochberg(p):
    """Benjamini-Hochberg q values for a list of p values."""
    p = np.asarray(p, float)
    order = np.argsort(p)
    ranked = p[order] * len(p) / np.arange(1, len(p) + 1)
    q = np.empty_like(p)
    q[order] = np.minimum(np.minimum.accumulate(ranked[::-1])[::-1], 1)
    return q


def label(q, p):
    """The evidence label on a bar."""
    if q < 0.05:
        return "Strong evidence"
    return "Some evidence" if p < 0.05 else "No clear link"


def linked_bars(nightly, outcome, compare="window"):
    """Every bar for one sleep measure, labelled, plus the bedtime bar's outlier groups.

    Labels use Benjamini-Hochberg across every term tested for the sleep measure:
    strong evidence when q < 0.05, some evidence when p < 0.05, else no clear link.
    The groups compare nights more than an hour earlier or later than normal with
    nights within an hour, matched as the bedtime bar is.
    """
    corr = lookalikes(nightly)
    bars = {bar: fit_bar(nightly, outcome, bar, corr, compare) for bar in BARS}
    tested = [term for bar in bars.values() for term in bar.get("terms", {}).values()]
    for term, q in zip(tested, benjamini_hochberg([term["p"] for term in tested])):
        term["q"], term["label"] = float(q), label(q, term["p"])
    groups = fit_bar(nightly, outcome, "bedtime", corr, compare, GROUPS, 1.0)
    return {"bars": bars, "groups": groups}
