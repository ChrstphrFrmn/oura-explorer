-- Each imported heart-rate reading: the seconds it counts for (until the next reading,
-- at most a minute) and whether it's hard. Hard is 80% or more of the person's top heart
-- rate, the level only the top 0.5% of their imported readings reach.
CREATE TABLE hard_readings AS
WITH top AS (
    SELECT quantile_cont(bpm, 0.995) AS top_bpm
    FROM imported_heart_rate
)
SELECT
    taken_at,
    least(epoch(lead(taken_at) OVER (ORDER BY taken_at)) - epoch(taken_at), 60) AS seconds,
    bpm >= 0.8 * top_bpm AS hard
FROM imported_heart_rate, top;
