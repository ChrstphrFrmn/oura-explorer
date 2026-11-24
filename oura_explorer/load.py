"""Load an Oura export into a DuckDB database that lives only for this visit.

The SQL is in the sql/ folder next to this file, one file per table.
"""

from importlib.resources import files
from pathlib import Path

import duckdb

SQL = files(__package__) / "sql"
EXPORT_FILES = {
    "sleep_periods": "sleepmodel.csv",
    "readings": "daytimestress.csv",
    "heart_rate": "heartrate.csv",
    "steps": "stepcount.csv",
    "daily_sleep": "dailysleep.csv",
}


def sql(name):
    """Return the text of one file in the sql/ folder, given its name without .sql."""
    return (SQL / f"{name}.sql").read_text()


def load_export(folder):
    """Load the Oura export in folder into a new in-memory DuckDB database.

    Reads the files the site uses into tables, then builds the nights and the naps.
    A file that is missing or empty gives an empty table.
    Returns the open connection.
    """
    con = duckdb.connect()
    con.execute(sql("schema"))
    for table, name in EXPORT_FILES.items():
        path = Path(folder) / name
        if path.is_file() and path.stat().st_size > 0:
            con.execute(sql(table), {"path": str(path)})
    con.execute(sql("nights"))
    con.execute(sql("naps"))
    return con


def night_summary(con):
    """Return the number of nights and the dates of the first and the last one."""
    query = "SELECT count(*), min(night), max(night) FROM nights"
    return con.cursor().execute(query).fetchone()
