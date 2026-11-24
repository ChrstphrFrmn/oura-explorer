"""Tests for the bars: the 15-day comparison, the yes/no rule, the labels, the demo export."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from oura_explorer.bars import (
    benjamini_hochberg,
    day_numbers,
    fit_window,
    linked_bars,
    nightly_frame,
    paired_within_months,
    paired_yes_nights,
    pairs,
)
from oura_explorer.load import load_export

DEMO_EXPORT = Path(__file__).parent.parent / "demo-data"
# REM on the demo export, minutes of REM per unit of each term and its label: with the
# Workouts bar (Change 2 run) and without it (Change 4 run, an export with no watch).
REM_TERMS = {
    "last_sleep_h": (-1.79, "No clear link"),
    "weekend": (-1.71, "No clear link"),
    "spread_min": (-1.54, "No clear link"),
    "stress_share": (-1.10, "No clear link"),
    "calm_share": (2.84, "No clear link"),
    "steps_ph": (-1.59, "No clear link"),
    "hard_min": (-0.46, "No clear link"),
    "napped": (7.08, "Some evidence"),
    "earlier": (3.98, "No clear link"),
    "later": (-5.24, "Strong evidence"),
    "hours_awake": (-3.94, "Some evidence"),
    "bb_stress": (0.98, "No clear link"),
    "bb_hr": (0.99, "No clear link"),
    "bb_steps_k": (1.56, "No clear link"),
}
REM_TERMS_WITHOUT_WORKOUTS = {
    "last_sleep_h": (-1.79, "No clear link"),
    "weekend": (-1.71, "No clear link"),
    "spread_min": (-1.54, "No clear link"),
    "stress_share": (-1.24, "No clear link"),
    "calm_share": (2.89, "No clear link"),
    "steps_ph": (-1.59, "No clear link"),
    "napped": (7.24, "Some evidence"),
    "earlier": (4.04, "No clear link"),
    "later": (-5.22, "Strong evidence"),
    "hours_awake": (-3.93, "Some evidence"),
    "bb_stress": (0.96, "No clear link"),
    "bb_hr": (1.03, "No clear link"),
    "bb_steps_k": (1.52, "No clear link"),
}


@pytest.fixture(scope="module")
def demo():
    """The demo export's nightly table."""
    return nightly_frame(load_export(DEMO_EXPORT))


def test_the_worked_example():
    """Four made-up nights: three pairs, none for Jul 20, and -0.3 min of REM a point."""
    nights = pd.DatetimeIndex(["2026-06-28", "2026-06-30", "2026-07-02", "2026-07-20"])
    earlier, later = pairs(day_numbers(nights))
    assert list(zip(earlier, later)) == [(0, 1), (0, 2), (1, 2)]
    stress = np.array([[10.0], [20.0], [30.0]])
    rem = np.array([50.0, 46.0, 44.0])
    slopes, _ = fit_window(rem, stress, day_numbers(nights[:3]))
    assert slopes[0] == pytest.approx(-0.3)


def test_each_yes_night_needs_its_own_no_night():
    """Yes nights on days 0, 1 and 40, no nights on days 10 and 50."""
    days = np.array([0, 1, 10, 40, 50])
    napped = np.array([1.0, 1.0, 0.0, 1.0, 0.0])
    assert paired_yes_nights(napped, days) == 2
    assert paired_within_months(napped, np.array([1, 1, 1, 2, 3])) == 1


def test_benjamini_hochberg():
    """q values for four p values, worked by hand."""
    q = benjamini_hochberg([0.01, 0.04, 0.03, 0.5])
    assert q == pytest.approx([0.04, 0.16 / 3, 0.16 / 3, 0.5])


def rem_terms(result):
    """Every tested term of the REM bars, by name."""
    return {
        term: found
        for bar in result["bars"].values()
        for term, found in bar.get("terms", {}).items()
    }


def check_terms(terms, expected):
    """Each term's size and label are as expected, and no other term was tested."""
    assert set(terms) == set(expected)
    for term, (effect, label) in expected.items():
        assert terms[term]["effect"] == pytest.approx(effect, abs=0.005)
        assert terms[term]["label"] == label


def test_demo_rem_bars_match_the_change_2_run(demo):
    """Every REM bar's size and label, evening nap short of data, and no night lost."""
    result = linked_bars(demo, "rem_min")
    check_terms(rem_terms(result), REM_TERMS)
    assert "terms" not in result["bars"]["evening_nap"]
    assert all(bar["lost"] == [] for bar in result["bars"].values())
    late = result["groups"]["terms"]["late_group"]
    assert late["effect"] == pytest.approx(-10.92, abs=0.005)


def test_without_a_watch_there_is_no_workouts_bar(demo):
    """With no hard minutes, no bar holds workouts and REM is back to the Change 4 run."""
    result = linked_bars(demo.assign(hard_min=np.nan), "rem_min")
    assert "hard_min" not in result["bars"]
    assert not any("hard_min" in bar["held"] for bar in result["bars"].values())
    check_terms(rem_terms(result), REM_TERMS_WITHOUT_WORKOUTS)


def test_demo_month_version_matches_the_change_3_run(demo):
    """Without workouts, the month version gives the Change 3 numbers for two REM bars."""
    without = demo.assign(hard_min=np.nan)
    bars = linked_bars(without, "rem_min", compare="month")["bars"]
    later = bars["bedtime"]["terms"]["later"]
    assert later["effect"] == pytest.approx(-4.63, abs=0.005)
    assert bars["napped"]["terms"]["napped"]["effect"] == pytest.approx(6.87, abs=0.005)
