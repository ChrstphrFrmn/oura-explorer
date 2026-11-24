-- importedheartrate.csv: heart rate from another device, such as a watch that syncs
-- workouts through Google Health Connect.
INSERT INTO imported_heart_rate
SELECT CAST(timestamp AS TIMESTAMPTZ), CAST(bpm AS DOUBLE)
FROM read_csv($path, delim = ';', header = true, all_varchar = true);
