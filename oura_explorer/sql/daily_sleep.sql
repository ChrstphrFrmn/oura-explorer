-- dailysleep.csv: Oura's sleep score, one per day that had a long sleep.
INSERT INTO daily_sleep
SELECT CAST(day AS DATE), CAST(score AS DOUBLE)
FROM read_csv($path, delim = ';', header = true, all_varchar = true);
