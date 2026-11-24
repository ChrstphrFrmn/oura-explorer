-- The last hours before the actual bedtime. These move with tonight's bedtime, so their
-- bars compare nights with the same bedtime.
--   bb_stress: the share of awake readings in the last 2 hours that are stress readings
--     (6 readings needed).
--   bb_hr: the average awake heart rate in the last 2 hours (20 readings needed).
--   bb_steps_k: thousands of steps in the last 3 hours (90 step records needed).
CREATE TABLE before_bed AS
WITH stress AS (
    SELECT
        n.night,
        count(r.taken_at) AS readings,
        count(r.taken_at) FILTER (WHERE r.kind = 'stress') AS stress_readings
    FROM nights AS n
    LEFT JOIN awake_readings AS r
        ON r.taken_at >= n.start_at - INTERVAL 2 HOUR AND r.taken_at < n.start_at
    GROUP BY n.night
),
heart AS (
    SELECT n.night, count(h.bpm) AS beats, avg(h.bpm) AS bpm
    FROM nights AS n
    LEFT JOIN heart_rate AS h
        ON h.source = 'awake'
        AND h.taken_at >= n.start_at - INTERVAL 2 HOUR
        AND h.taken_at < n.start_at
    GROUP BY n.night
),
walked AS (
    SELECT n.night, count(s.taken_at) AS records, sum(s.steps) AS steps
    FROM nights AS n
    LEFT JOIN steps AS s
        ON s.taken_at >= n.start_at - INTERVAL 3 HOUR AND s.taken_at < n.start_at
    GROUP BY n.night
)
SELECT
    night,
    CASE WHEN readings >= 6 THEN stress_readings / readings END AS bb_stress,
    CASE WHEN beats >= 20 THEN bpm END AS bb_hr,
    CASE WHEN records >= 90 THEN steps / 1000 END AS bb_steps_k
FROM stress
JOIN heart USING (night)
JOIN walked USING (night)
ORDER BY night;
