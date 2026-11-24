-- sleepmodel.csv: one row per sleep period, nights and naps alike.
-- Durations arrive in seconds and are kept in minutes.
INSERT INTO sleep_periods
SELECT
    id,
    CAST(day AS DATE),
    type,
    CAST(bedtime_start AS TIMESTAMPTZ),
    CAST(bedtime_end AS TIMESTAMPTZ),
    strptime(left(bedtime_start, 19), '%Y-%m-%dT%H:%M:%S'),
    strptime(left(bedtime_end, 19), '%Y-%m-%dT%H:%M:%S'),
    CAST(time_in_bed AS DOUBLE) / 60,
    CAST(total_sleep_duration AS DOUBLE) / 60,
    CAST(rem_sleep_duration AS DOUBLE) / 60,
    CAST(deep_sleep_duration AS DOUBLE) / 60,
    CAST(latency AS DOUBLE) / 60,
    CAST(efficiency AS DOUBLE),
    CAST(average_hrv AS DOUBLE),
    CAST(average_heart_rate AS DOUBLE),
    CAST(lowest_heart_rate AS DOUBLE)
FROM read_csv($path, delim = ';', header = true, all_varchar = true);
