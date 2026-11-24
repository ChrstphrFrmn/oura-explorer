-- The day, from wake-up to the day stop, for nights where the person was awake at the stop.
--   stress_share, calm_share: of the 5-minute blocks with an awake reading, the share with
--     a stress (or calm) reading of 50 or more. 24 awake readings needed.
--   steps_ph: steps per hour. Step records for half the minutes needed.
--   A nap counts where its middle falls: before the stop it's a day nap (nap_min, napped),
--   after it an evening nap.
--   hard_min: minutes at a hard heart rate, from imported heart rate (0 on a day without
--     any). Left empty when the export has no imported heart rate at all.
CREATE TABLE day_factors AS
WITH days AS (
    SELECT night, woke_at, day_stop, start_at
    FROM night_times
    JOIN nights USING (night)
    WHERE day_ok
),
read AS (
    SELECT
        d.night,
        count(r.taken_at) AS day_readings,
        count(DISTINCT time_bucket(INTERVAL 5 MINUTE, r.taken_at)) AS blocks,
        count(DISTINCT time_bucket(INTERVAL 5 MINUTE, r.taken_at))
            FILTER (WHERE r.kind = 'stress' AND r.value >= 50) AS stress_blocks,
        count(DISTINCT time_bucket(INTERVAL 5 MINUTE, r.taken_at))
            FILTER (WHERE r.kind = 'calm' AND r.value >= 50) AS calm_blocks
    FROM days AS d
    LEFT JOIN awake_readings AS r
        ON r.taken_at >= d.woke_at AND r.taken_at < d.day_stop
    GROUP BY d.night
),
walked AS (
    SELECT
        d.night,
        sum(s.steps) AS steps,
        count(s.taken_at) AS records,
        (epoch(d.day_stop) - epoch(d.woke_at)) / 60 AS minutes
    FROM days AS d
    LEFT JOIN steps AS s ON s.taken_at >= d.woke_at AND s.taken_at < d.day_stop
    GROUP BY d.night, d.day_stop, d.woke_at
),
napped AS (
    SELECT
        d.night,
        sum(n.asleep_min) FILTER (
            WHERE (epoch(n.start_at) + epoch(n.end_at)) / 2 < epoch(d.day_stop)
        ) AS nap_min,
        count(n.id) FILTER (
            WHERE (epoch(n.start_at) + epoch(n.end_at)) / 2 >= epoch(d.day_stop)
        ) AS evening_naps
    FROM days AS d
    LEFT JOIN naps AS n ON n.start_at >= d.woke_at AND n.end_at <= d.start_at
    GROUP BY d.night
),
trained AS (
    SELECT d.night, coalesce(sum(h.seconds) FILTER (WHERE h.hard), 0) / 60 AS hard_min
    FROM days AS d
    LEFT JOIN hard_readings AS h
        ON h.taken_at >= d.woke_at AND h.taken_at < d.day_stop
    GROUP BY d.night
)
SELECT
    night,
    day_readings,
    CASE WHEN day_readings >= 24 THEN stress_blocks / blocks END AS stress_share,
    CASE WHEN day_readings >= 24 THEN calm_blocks / blocks END AS calm_share,
    CASE WHEN records >= minutes / 2 THEN steps / (minutes / 60) END AS steps_ph,
    coalesce(nap_min, 0) AS nap_min,
    CAST(coalesce(nap_min, 0) >= 10 AS DOUBLE) AS napped,
    CAST(evening_naps > 0 AS DOUBLE) AS evening_nap,
    CASE WHEN EXISTS (SELECT 1 FROM hard_readings) THEN hard_min END AS hard_min
FROM read
JOIN walked USING (night)
JOIN napped USING (night)
JOIN trained USING (night)
ORDER BY night;
