"""Read-only access to the local DuckDB copy of OpenFEMA data."""

from __future__ import annotations

import datetime as dt
import decimal
import threading
from pathlib import Path
from typing import Any

import duckdb

SCHEMA_DOC = """
Table declarations  -- OpenFEMA "Disaster Declarations Summaries" (v2).
  IMPORTANT: one row per (disaster, designated area). A single disaster appears on many rows.
  To count disasters use COUNT(DISTINCT disaster_number), never COUNT(*).
  Columns:
    disaster_number INTEGER      -- FEMA disaster number (e.g. 4673)
    fema_declaration_string TEXT -- e.g. 'DR-4673-FL'
    state TEXT                   -- 2-letter postal code, e.g. 'VA', 'FL', 'PR'
    declaration_type TEXT        -- 'DR' major disaster, 'EM' emergency, 'FM' fire management
    declaration_date DATE
    fy_declared INTEGER          -- federal fiscal year
    incident_type TEXT           -- e.g. 'Hurricane', 'Severe Storm', 'Flood', 'Fire', 'Snowstorm',
                                 --      'Tornado', 'Biological', 'Severe Ice Storm', 'Earthquake'
    declaration_title TEXT       -- e.g. 'HURRICANE IAN'
    incident_begin_date DATE
    incident_end_date DATE
    designated_area TEXT         -- county/parish/tribal area, e.g. 'Fairfax (County)'
    fips_state_code TEXT
    fips_county_code TEXT
    region INTEGER               -- FEMA region 1-10
    ih_program_declared BOOLEAN  -- Individuals & Households program
    ia_program_declared BOOLEAN
    pa_program_declared BOOLEAN  -- Public Assistance
    hm_program_declared BOOLEAN  -- Hazard Mitigation

Table disaster_summaries  -- OpenFEMA "FEMA Web Disaster Summaries": one row per disaster, dollar totals.
  Join with declarations ON disaster_number.
  Columns:
    disaster_number INTEGER
    total_number_ia_approved INTEGER          -- individual assistance applications approved
    total_amount_ihp_approved DOUBLE          -- USD, Individuals & Households Program
    total_amount_ha_approved DOUBLE           -- USD, Housing Assistance
    total_amount_ona_approved DOUBLE          -- USD, Other Needs Assistance
    total_obligated_amount_pa DOUBLE          -- USD, Public Assistance obligated
    total_obligated_amount_hmgp DOUBLE        -- USD, Hazard Mitigation Grant Program obligated
""".strip()


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._con: duckdb.DuckDBPyConnection | None = None

    def _connect(self) -> duckdb.DuckDBPyConnection:
        if self._con is None:
            if not self.path.exists():
                raise FileNotFoundError(f"database not found: {self.path} (run etl/load_openfema.py)")
            self._con = duckdb.connect(
                str(self.path),
                read_only=True,
                config={"enable_external_access": False, "threads": 2},
            )
        return self._con

    def query(self, sql: str, params: list[Any] | None = None) -> tuple[list[str], list[list[Any]]]:
        with self._lock:
            cur = self._connect().execute(sql, params or [])
            cols = [d[0] for d in cur.description]
            rows = [[_jsonable(v) for v in r] for r in cur.fetchall()]
        return cols, rows

    def metadata(self) -> dict[str, Any]:
        try:
            _, rows = self.query("SELECT key, value FROM _meta")
            return {k: v for k, v in rows}
        except Exception:
            return {}


def _jsonable(v: Any) -> Any:
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()
    if isinstance(v, decimal.Decimal):
        return float(v)
    return v
