-- heartrate.csv: heart rate readings, each marked with what the ring was doing
-- (awake, rest, workout or live).
INSERT INTO heart_rate
SELECT CAST(timestamp AS TIMESTAMPTZ), CAST(bpm AS DOUBLE), source
FROM read_csv($path, delim = ';', header = true, all_varchar = true);
