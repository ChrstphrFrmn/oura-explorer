"""The bars in "What's linked to it": one per factor, how sure it is, and its label.

A bar compares nights at most 15 days apart. For every pair of the bar's nights 1 to 15
days apart, it takes the later night minus the earlier one, for the sleep measure, the
factor and everything the bar is matched on, and fits one slope through zero to all the
pairs' changes. Every night is in many pairs, so how sure the bar is gets worked out
night by night, each night counted once: Newey-West with 7 lags, nights in date order.
"""

import numpy as np

WINDOW = 15
LAGS = 7


def day_numbers(dates):
    """Calendar day numbers of the nights' dates, for how many days apart two nights are."""
    return dates.values.astype("datetime64[D]").astype(np.int64)


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
