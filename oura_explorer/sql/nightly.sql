-- The table every page queries: one row per night with the 10 sleep measures and the
-- factors. Workouts, tags and cycle phase come later.
CREATE TABLE nightly AS
SELECT
    n.night,
    n.rem_min,
    n.asleep_min,
    n.deep_min,
    n.average_hrv,
    n.lowest_heart_rate,
    n.average_heart_rate,
    n.latency_min,
    t.wake_h,
    s.score AS sleep_score,
    100 * n.asleep_min / n.in_bed_min AS efficiency,
    t.bed_h,
    t.normal_bed_h,
    t.dev,
    t.earlier,
    t.later,
    t.early_group,
    t.late_group,
    t.day_stop,
    t.day_ok,
    t.last_sleep_h,
    t.hours_awake,
    t.spread_min,
    t.weekend,
    d.day_readings,
    d.stress_share,
    d.calm_share,
    d.steps_ph,
    d.nap_min,
    d.napped,
    d.evening_nap,
    b.bb_stress,
    b.bb_hr,
    b.bb_steps_k
FROM nights AS n
JOIN night_times AS t USING (night)
LEFT JOIN day_factors AS d USING (night)
LEFT JOIN before_bed AS b USING (night)
LEFT JOIN daily_sleep AS s ON s.day = n.night
ORDER BY n.night;
