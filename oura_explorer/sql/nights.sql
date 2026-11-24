-- One row per night, labeled with Oura's day for it (the date the night ends).
--   1. A day's night is its longest time in bed among sleep periods starting
--      between 3 PM and 3 AM on the person's clock.
--   2. Sleep of 10+ minutes less than an hour before or after a night is part of it:
--      one sleep with a waking in the middle. Pieces chain, so the gaps are checked in
--      time order. Two nights less than an hour apart become one, under the later day.
--   3. Each night is paired with the end of the night before: when its day began.
CREATE TABLE nights AS
WITH ranked AS (
    SELECT
        id,
        day,
        row_number() OVER (
            PARTITION BY day ORDER BY time_in_bed_min DESC, start_at
        ) AS rank
    FROM sleep_periods
    WHERE hour(start_local) >= 15 OR hour(start_local) < 3
),
pieces AS (
    SELECT p.*, r.day AS night
    FROM sleep_periods AS p
    LEFT JOIN ranked AS r ON r.id = p.id AND r.rank = 1
    WHERE r.id IS NOT NULL OR p.asleep_min >= 10
),
gaps AS (
    SELECT
        *,
        start_at - max(end_at) OVER (
            ORDER BY start_at ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
        ) AS gap
    FROM pieces
),
episodes AS (
    SELECT
        *,
        sum(CASE WHEN gap IS NULL OR gap >= INTERVAL 1 HOUR THEN 1 ELSE 0 END)
            OVER (ORDER BY start_at) AS episode
    FROM gaps
),
joined AS (
    SELECT
        max(night) AS night,
        min(start_at) AS start_at,
        max(end_at) AS end_at,
        arg_min(start_local, start_at) AS start_local,
        arg_max(end_local, end_at) AS end_local,
        sum(asleep_min) AS asleep_min,
        sum(rem_min) AS rem_min,
        sum(deep_min) AS deep_min,
        count(*) AS pieces
    FROM episodes
    GROUP BY episode
    HAVING count(night) > 0
)
SELECT tonight.*, before.end_at AS woke_at
FROM joined AS tonight
LEFT JOIN joined AS before ON before.night = tonight.night - 1
ORDER BY tonight.night;
