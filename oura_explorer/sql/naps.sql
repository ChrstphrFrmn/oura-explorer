-- Naps: sleep periods with 10+ minutes asleep that aren't part of a night.
CREATE TABLE naps AS
SELECT id, start_at, end_at, asleep_min
FROM sleep_periods AS p
WHERE
    asleep_min >= 10
    AND NOT EXISTS (
        SELECT 1
        FROM nights AS n
        WHERE p.start_at >= n.start_at AND p.end_at <= n.end_at
    )
ORDER BY start_at;
