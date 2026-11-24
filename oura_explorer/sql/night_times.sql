-- Clock times and background for each night.
--   bed_h, wake_h: bedtime and final wake-up, in hours after noon on the person's clock.
--   normal_bed_h: the average bedtime over the 60 days before (5 nights needed).
--   dev: tonight's bedtime minus normal, split into an earlier and a later side,
--     and into groups: more than an hour earlier or later.
--   day_stop: 3 hours before the normal bedtime, on the evening the night starts.
--     The day's factors are counted up to it, so tonight's bedtime can't move them.
--   day_ok: the person was up by the day stop and still awake at it.
--   last_sleep_h, hours_awake, spread_min (how much bedtime varied over the
--   7 nights before; 5 needed) and weekend (the night starts on a Friday or Saturday).
CREATE TABLE night_times AS
WITH clock AS (
    SELECT
        tonight.night,
        tonight.start_at,
        tonight.woke_at,
        tonight.start_local,
        tonight.start_local - CAST(tonight.start_at AS TIMESTAMP) AS utc_offset,
        (hour(tonight.start_local) + 12) % 24 + minute(tonight.start_local) / 60
            AS bed_h,
        (hour(tonight.end_local) + 12) % 24 + minute(tonight.end_local) / 60 AS wake_h,
        before.asleep_min / 60 AS last_sleep_h
    FROM nights AS tonight
    LEFT JOIN nights AS before ON before.night = tonight.night - 1
),
recent AS (
    SELECT
        *,
        CASE WHEN count(bed_h) OVER sixty >= 5 THEN avg(bed_h) OVER sixty END
            AS normal_bed_h,
        CASE WHEN count(bed_h) OVER seven >= 5 THEN stddev_samp(bed_h) OVER seven END
            * 60 AS spread_min
    FROM clock
    WINDOW
        sixty AS (
            ORDER BY night
            RANGE BETWEEN INTERVAL 60 DAYS PRECEDING AND INTERVAL 1 DAY PRECEDING
        ),
        seven AS (
            ORDER BY night
            RANGE BETWEEN INTERVAL 7 DAYS PRECEDING AND INTERVAL 1 DAY PRECEDING
        )
),
stops AS (
    SELECT
        *,
        bed_h - normal_bed_h AS dev,
        CAST(
            date_trunc('day', start_local - INTERVAL 12 HOUR)
            + INTERVAL 12 HOUR
            + to_microseconds(CAST(round((normal_bed_h - 3) * 3600e6) AS BIGINT))
            - utc_offset
            AS TIMESTAMPTZ
        ) AS day_stop
    FROM recent
)
SELECT
    night,
    bed_h,
    wake_h,
    normal_bed_h,
    dev,
    CASE WHEN dev IS NOT NULL THEN greatest(-dev, 0) END AS earlier,
    CASE WHEN dev IS NOT NULL THEN greatest(dev, 0) END AS later,
    CAST(dev < -1 AS DOUBLE) AS early_group,
    CAST(dev > 1 AS DOUBLE) AS late_group,
    day_stop,
    coalesce(woke_at < day_stop AND day_stop <= start_at, false) AS day_ok,
    last_sleep_h,
    (epoch(start_at) - epoch(woke_at)) / 3600 AS hours_awake,
    spread_min,
    CAST(isodow(start_local - INTERVAL 12 HOUR) IN (5, 6) AS DOUBLE) AS weekend
FROM stops
ORDER BY night;
