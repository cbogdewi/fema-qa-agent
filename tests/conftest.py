"""Builds a small SYNTHETIC DuckDB (same schema as the real one) so tests run offline."""

from __future__ import annotations

import os
from pathlib import Path

import duckdb
import pytest

ROWS = [
    # disaster_number, decl_string, state, type, date, incident_type, title, area
    (4001, "DR-4001-FL", "FL", "DR", "2017-09-10", "Hurricane", "HURRICANE TEST A", "Alpha (County)"),
    (4001, "DR-4001-FL", "FL", "DR", "2017-09-10", "Hurricane", "HURRICANE TEST A", "Beta (County)"),
    (4001, "DR-4001-FL", "FL", "DR", "2017-09-10", "Hurricane", "HURRICANE TEST A", "Gamma (County)"),
    (4002, "DR-4002-VA", "VA", "DR", "2018-03-02", "Severe Storm", "SEVERE STORMS TEST", "Fairfax (County)"),
    (4003, "DR-4003-VA", "VA", "DR", "2020-01-15", "Snowstorm", "SNOWSTORM TEST", "Loudoun (County)"),
    (3001, "EM-3001-TX", "TX", "EM", "2020-03-13", "Biological", "COVID TEST", "Statewide"),
    (4004, "DR-4004-CA", "CA", "DR", "2021-08-20", "Fire", "WILDFIRES TEST", "Shasta (County)"),
]


@pytest.fixture(scope="session")
def db_path(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("db") / "fema.duckdb"
    con = duckdb.connect(str(path))
    con.execute("""CREATE TABLE declarations (
        disaster_number INTEGER, fema_declaration_string TEXT, state TEXT, declaration_type TEXT,
        declaration_date DATE, fy_declared INTEGER, incident_type TEXT, declaration_title TEXT,
        incident_begin_date DATE, incident_end_date DATE, designated_area TEXT, fips_state_code TEXT,
        fips_county_code TEXT, region INTEGER, ih_program_declared BOOLEAN, ia_program_declared BOOLEAN,
        pa_program_declared BOOLEAN, hm_program_declared BOOLEAN)""")
    for n, s, st, t, d, it, title, area in ROWS:
        con.execute(
            "INSERT INTO declarations VALUES (?,?,?,?,?,NULL,?,?,?,NULL,?,NULL,NULL,4,true,true,true,false)",
            [n, s, st, t, d, it, title, d, area],
        )
    con.execute("""CREATE TABLE disaster_summaries (disaster_number INTEGER, total_number_ia_approved BIGINT,
        total_amount_ihp_approved DOUBLE, total_amount_ha_approved DOUBLE, total_amount_ona_approved DOUBLE,
        total_obligated_amount_pa DOUBLE, total_obligated_amount_hmgp DOUBLE)""")
    con.execute("INSERT INTO disaster_summaries VALUES (4001, 1000, 5000000, 4000000, 1000000, 9000000, 0)")
    con.execute("CREATE TABLE _meta (key TEXT, value TEXT)")
    con.execute("INSERT INTO _meta VALUES ('loaded_at', 'synthetic-test-data')")
    con.close()
    return path


@pytest.fixture(scope="session", autouse=True)
def _env(db_path):
    os.environ["DB_PATH"] = str(db_path)
    os.environ["LLM_PROVIDER"] = "fake"
    os.environ["RATE_LIMIT_PER_MINUTE"] = "1000"
    os.environ["RATE_LIMIT_PER_DAY"] = "100000"
