-- stepcount.csv: steps per minute, stamped at the start of the minute.
INSERT INTO steps
SELECT CAST(timestamp AS TIMESTAMPTZ), CAST(steps AS DOUBLE)
FROM read_csv($path, delim = ';', header = true, all_varchar = true);
