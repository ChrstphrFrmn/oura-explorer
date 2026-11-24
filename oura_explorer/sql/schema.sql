-- Tables for the export files the site reads. Times are exact instants (TIMESTAMPTZ).
-- Sleep periods also keep the person's own clock time, taken from the export's UTC offset.
SET TimeZone = 'UTC';

CREATE TABLE sleep_periods (
    id VARCHAR,
    day DATE,
    type VARCHAR,
    start_at TIMESTAMPTZ,
    end_at TIMESTAMPTZ,
    start_local TIMESTAMP,
    end_local TIMESTAMP,
    time_in_bed_min DOUBLE,
    asleep_min DOUBLE,
    rem_min DOUBLE,
    deep_min DOUBLE,
    latency_min DOUBLE,
    efficiency DOUBLE,
    average_hrv DOUBLE,
    average_heart_rate DOUBLE,
    lowest_heart_rate DOUBLE
);

CREATE TABLE readings (taken_at TIMESTAMPTZ, kind VARCHAR, value DOUBLE);

CREATE TABLE heart_rate (taken_at TIMESTAMPTZ, bpm DOUBLE, source VARCHAR);

CREATE TABLE imported_heart_rate (taken_at TIMESTAMPTZ, bpm DOUBLE);

CREATE TABLE steps (taken_at TIMESTAMPTZ, steps DOUBLE);

CREATE TABLE daily_sleep (day DATE, score DOUBLE);
