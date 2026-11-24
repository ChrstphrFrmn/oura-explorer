-- daytimestress.csv: the ring's timed stress and calm readings, about 5 minutes apart.
-- The export swaps the column labels: recovery_value holds the stress readings
-- and stress_value holds the calm ones.
INSERT INTO readings
SELECT
    CAST(timestamp AS TIMESTAMPTZ),
    CASE WHEN recovery_value IS NOT NULL THEN 'stress' ELSE 'calm' END,
    CAST(coalesce(recovery_value, stress_value) AS DOUBLE)
FROM read_csv($path, delim = ';', header = true, all_varchar = true)
WHERE recovery_value IS NOT NULL OR stress_value IS NOT NULL;
