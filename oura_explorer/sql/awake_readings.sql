-- Stress and calm readings taken while awake: outside every sleep period, naps included.
CREATE TABLE awake_readings AS
SELECT r.*
FROM readings AS r
WHERE NOT EXISTS (
    SELECT 1
    FROM sleep_periods AS p
    WHERE r.taken_at >= p.start_at AND r.taken_at < p.end_at
);
