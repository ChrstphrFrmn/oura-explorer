"""The bars in "What's linked to it": one per factor, how sure it is, and its label.

A bar compares nights at most 15 days apart. For every pair of the bar's nights 1 to 15
days apart, it takes the later night minus the earlier one, for the sleep measure, the
factor and everything the bar is matched on, and fits one slope through zero to all the
pairs' changes. Every night is in many pairs, so how sure the bar is gets worked out
night by night, each night counted once: Newey-West with 7 lags, nights in date order.

The Advanced view also works out each bar four other ways, on the same nights: within
7 days, within 30 days, with no time limit, and within calendar months.
"""

import math
from functools import partial
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

    Stages, in the order things happen: 0 background, 1 workouts, 2 the rest of the
    day, 3 bedtime, 4 the last hours before bed. Workouts come before the rest of the
    day: a hard workout can raise the day's stress readings, change calm time and
    steps, and lead to a nap, so the workouts bar doesn't hold those the same.
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
    "hard_min": Bar(
        "Workouts", 15.0, "per 15 more hard minutes", 1, False, ("hard_min",)
    ),
    "stress_share": Bar(
        "Daytime stress",
        0.1,
        "per 10 points more of the readings",
        2,
        False,
        ("stress_share",),
    ),
    "calm_share": Bar(
        "Calm time",
        0.1,
        "per 10 points more of the readings",
        2,
        False,
        ("calm_share",),
    ),
    "steps_ph": Bar(
        "Steps", 100.0, "per 100 more steps an hour", 2, False, ("steps_ph",)
    ),
    "napped": Bar("Daytime naps", 1.0, "nap day vs not", 2, True, ("napped",)),
    "bedtime": Bar(
        "Earlier or later than normal", 1.0, "per hour", 3, False, ("earlier", "later")
    ),
    "hours_awake": Bar(
        "Hours awake", 1.5, "per 90 min more awake", 3, False, ("hours_awake",)
    ),
    "bb_stress": Bar(
        "Stress before bed",
        0.25,
        "per 25 points more of the readings",
        4,
        False,
        ("bb_stress",),
    ),
    "bb_hr": Bar(
        "Heart rate before bed", 5.0, "per 5 bpm higher", 4, False, ("bb_hr",)
    ),
    "bb_steps_k": Bar(
        "Steps before bed", 0.5, "per 500 steps", 4, False, ("bb_steps_k",)
    ),
    "evening_nap": Bar(
        "Evening nap", 1.0, "evening nap vs not", 4, True, ("evening_nap",)
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


def in_a_pair(dates, window=WINDOW):
    """Which nights have at least one other night within `window` days of them."""
    earlier, later = pairs(day_numbers(dates), window)
    return np.bincount(np.concatenate([earlier, later]), minlength=len(dates)) > 0


def newey_west(scores, lags=LAGS):
    """Newey-West (Bartlett) sum of the score rows' outer products, rows in date order."""
    total = scores.T @ scores
    for lag in range(1, lags + 1):
        cross = scores[lag:].T @ scores[:-lag]
        total = total + (1 - lag / (lags + 1)) * (cross + cross.T)
    return total


def fit_window(y, X, days, window=WINDOW):
    """Compare nights at most `window` days apart: one slope per column of X, through zero.

    Fits every pair's changes (later night minus earlier). With window=math.inf every
    two nights are a pair, which gives the same slopes as one regression with no time
    control. Returns the slopes and their standard errors. A night's score is the sum
    of its changes over its pairs times the average of its pair residuals, both taken
    as the night minus the other night; a night in no pair adds nothing.
    """
    earlier, later = pairs(days, window)
    dX, dy = X[later] - X[earlier], y[later] - y[earlier]
    bread = np.linalg.inv(dX.T @ dX)
    slopes = bread @ dX.T @ dy
    residuals = dy - dX @ slopes
    changes, own = np.zeros_like(X), np.zeros_like(y)
    for rows, sign in ((later, 1), (earlier, -1)):
        np.add.at(changes, rows, sign * dX)
        np.add.at(own, rows, sign * residuals)
    count = np.bincount(np.concatenate([earlier, later]), minlength=len(y))
    scores = changes * (own / np.maximum(count, 1))[:, None]
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


def within(window):
    """Compare nights at most `window` days apart, with the yes/no rule to match."""
    return Comparison(
        partial(fit_window, window=window),
        day_numbers,
        partial(paired_yes_nights, window=window),
    )


# The page uses the first; the Advanced view shows them all.
COMPARISONS = {
    "15 days": within(WINDOW),
    "7 days": within(7),
    "30 days": within(30),
    "no time limit": within(math.inf),
    "same month": Comparison(fit_month, month_numbers, paired_within_months),
}
MAIN = "15 days"


def lookalikes(nightly):
    """How closely each pair of the export's bars moves together (|r|), across all nights.

    Only bars whose own columns vary in this export are in it. A bar whose columns are
    empty, such as workouts for an export without imported heart rate, is left out, so
    no bar shows it and no other bar holds it the same.
    """
    bars = [
        bar
        for bar, spec in BARS.items()
        if nightly[list(spec.terms)].nunique().min() > 1
    ]
    columns = [LOOKALIKE_COLUMN.get(bar, bar) for bar in bars]
    corr = nightly[columns].corr().abs().to_numpy()
    return pd.DataFrame(corr, index=bars, columns=bars)


def held(bar, corr):
    """The bars a bar is matched on: earlier stages, and same-stage bars that aren't look-alikes."""
    stage = BARS[bar].stage
    return [
        other
        for other in corr.index
        if other != bar
        and (
            BARS[other].stage < stage
            or (BARS[other].stage == stage and corr.loc[bar, other] < LOOKALIKE_R)
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


def fit_bar(nightly, outcome, bar, corr, compare=MAIN, terms=None, scale=None):
    """One bar: what it's matched on, the nights behind it and, if enough, its terms.

    compare names one of COMPARISONS. Every way uses the same nights: those with
    another usable night within 15 days. The rest are lost.
    A bar with too few nights, or a yes/no bar with too few yes nights that can be
    paired with a no night, gets no terms: not enough data.
    terms and scale replace the bar's own columns and unit, for the bedtime groups.
    """
    spec, way = BARS[bar], COMPARISONS[compare]
    terms, scale = list(terms or spec.terms), scale or spec.unit
    matched = held_columns(bar, corr)
    usable = nightly[[outcome, *terms, *matched]].dropna()
    in_pair = in_a_pair(usable.index)
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


def linked_bars(nightly, outcome, compare=MAIN):
    """Every bar for one sleep measure, labelled, plus the bedtime bar's outlier groups.

    Labels use Benjamini-Hochberg across every term tested for the sleep measure:
    strong evidence when q < 0.05, some evidence when p < 0.05, else no clear link.
    The groups compare nights more than an hour earlier or later than normal with
    nights within an hour, matched as the bedtime bar is.
    """
    corr = lookalikes(nightly)
    bars = {bar: fit_bar(nightly, outcome, bar, corr, compare) for bar in corr.index}
    tested = [term for bar in bars.values() for term in bar.get("terms", {}).values()]
    for term, q in zip(tested, benjamini_hochberg([term["p"] for term in tested])):
        term["q"], term["label"] = float(q), label(q, term["p"])
    groups = fit_bar(nightly, outcome, "bedtime", corr, compare, GROUPS, 1.0)
    return {"bars": bars, "groups": groups}


def bedtime_breakdown(nightly, outcome, compare=MAIN):
    """Split each side of the bedtime bar into the part through time asleep and the rest.

    Going to bed later than normal usually means a shorter night, and a shorter night
    changes most sleep measures. Each side of the bar (per hour earlier, per hour later)
    is the sum of two parts: the change in time asleep times what an hour of sleep goes
    with, and the rest, which goes with the bedtime at the same length of sleep. Both
    come from the bar's own nights and matching. Returns None for time asleep itself,
    or when there are too few nights.
    """
    if outcome == "asleep_min":
        return None
    way, sides = COMPARISONS[compare], list(BARS["bedtime"].terms)
    matched = held_columns("bedtime", lookalikes(nightly))
    usable = nightly[[outcome, "asleep_min", *sides, *matched]].dropna()
    nights = usable[in_a_pair(usable.index)]
    if len(nights) < MIN_NIGHTS:
        return None
    place = way.place(nights.index)
    X = nights[[*sides, *matched]].to_numpy(float)
    y = nights[outcome].to_numpy(float)
    asleep = nights["asleep_min"].to_numpy(float)
    total, total_se = way.fit(y, X, place)
    sleep, sleep_se = way.fit(asleep, X, place)
    rest, rest_se = way.fit(y, np.column_stack([X, asleep / 60]), place)
    return {
        "nights": len(nights),
        "per_hour_asleep": estimate(rest[-1], rest_se[-1]),
        "sides": {
            side: {
                "total": estimate(total[k], total_se[k]),
                "sleep_min": estimate(sleep[k], sleep_se[k]),
                "through_sleep": float(sleep[k] / 60 * rest[-1]),
                "rest": estimate(rest[k], rest_se[k]),
            }
            for k, side in enumerate(sides)
        },
    }
