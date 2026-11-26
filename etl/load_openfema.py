"""Pull fresh data from the public OpenFEMA API into a local DuckDB file.

    python etl/load_openfema.py --out data/fema.duckdb

Datasets:
  - DisasterDeclarationsSummaries (v2): one row per disaster x designated area
  - FemaWebDisasterSummaries (v1):    one row per disaster with assistance dollar totals
Docs: https://www.fema.gov/about/openfema/data-sets
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import tempfile
import time
from pathlib import Path

import duckdb
import httpx

BASE = "https://www.fema.gov/api/open"
PAGE = 10_000

DECL_FIELDS = [
    "disasterNumber",
    "femaDeclarationString",
    "state",
    "declarationType",
    "declarationDate",
    "fyDeclared",
    "incidentType",
    "declarationTitle",
    "incidentBeginDate",
    "incidentEndDate",
    "designatedArea",
    "fipsStateCode",
    "fipsCountyCode",
    "region",
    "ihProgramDeclared",
    "iaProgramDeclared",
    "paProgramDeclared",
    "hmProgramDeclared",
]
SUMMARY_FIELDS = [
    "disasterNumber",
    "totalNumberIaApproved",
    "totalAmountIhpApproved",
    "totalAmountHaApproved",
    "totalAmountOnaApproved",
    "totalObligatedAmountPa",
    "totalObligatedAmountHmgp",
]


def fetch_all(client: httpx.Client, path: str, entity: str, fields: list[str]) -> list[dict]:
    rows: list[dict] = []
    skip = 0
    while True:
        params = {"$top": PAGE, "$skip": skip, "$select": ",".join(fields), "$orderby": "id"}
        for attempt in range(5):
            r = client.get(f"{BASE}/{path}", params=params)
            if r.status_code < 500 and r.status_code != 429:
                break
            time.sleep(2**attempt)
        r.raise_for_status()
        page = r.json().get(entity, [])
        rows.extend(page)
        print(f"  {entity}: {len(rows):,} rows", file=sys.stderr)
        if len(page) < PAGE:
            return rows
        skip += PAGE


def snake(name: str) -> str:
    out = "".join("_" + c.lower() if c.isupper() else c for c in name)
    return out.lstrip("_")


def load(out: Path) -> dict:
    with httpx.Client(timeout=120, headers={"User-Agent": "fema-qa-agent (github.com/cbogdewi/fema-qa-agent)"}) as c:
        decl = fetch_all(c, "v2/DisasterDeclarationsSummaries", "DisasterDeclarationsSummaries", DECL_FIELDS)
        summ = fetch_all(c, "v1/FemaWebDisasterSummaries", "FemaWebDisasterSummaries", SUMMARY_FIELDS)
    if len(decl) < 1000:
        raise SystemExit(f"refusing to build: only {len(decl)} declaration rows returned")

    tmp_out = out.with_suffix(".tmp")
    tmp_out.parent.mkdir(parents=True, exist_ok=True)
    tmp_out.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory() as td:
        d_path, s_path = Path(td, "decl.json"), Path(td, "summ.json")
        d_path.write_text("\n".join(json.dumps({snake(k): v for k, v in r.items()}) for r in decl))
        s_path.write_text("\n".join(json.dumps({snake(k): v for k, v in r.items()}) for r in summ))

        con = duckdb.connect(str(tmp_out))
        con.execute(f"""
            CREATE TABLE declarations AS
            SELECT CAST(disaster_number AS INTEGER) AS disaster_number,
                   fema_declaration_string, state, declaration_type,
                   CAST(declaration_date AS DATE) AS declaration_date,
                   CAST(fy_declared AS INTEGER) AS fy_declared,
                   incident_type, declaration_title,
                   CAST(incident_begin_date AS DATE) AS incident_begin_date,
                   CAST(incident_end_date AS DATE) AS incident_end_date,
                   designated_area, fips_state_code, fips_county_code,
                   CAST(region AS INTEGER) AS region,
                   CAST(ih_program_declared AS BOOLEAN) AS ih_program_declared,
                   CAST(ia_program_declared AS BOOLEAN) AS ia_program_declared,
                   CAST(pa_program_declared AS BOOLEAN) AS pa_program_declared,
                   CAST(hm_program_declared AS BOOLEAN) AS hm_program_declared
            FROM read_json('{d_path}', format='newline_delimited', union_by_name=true)
        """)
        con.execute(f"""
            CREATE TABLE disaster_summaries AS
            SELECT CAST(disaster_number AS INTEGER) AS disaster_number,
                   CAST(total_number_ia_approved AS BIGINT) AS total_number_ia_approved,
                   CAST(total_amount_ihp_approved AS DOUBLE) AS total_amount_ihp_approved,
                   CAST(total_amount_ha_approved AS DOUBLE) AS total_amount_ha_approved,
                   CAST(total_amount_ona_approved AS DOUBLE) AS total_amount_ona_approved,
                   CAST(total_obligated_amount_pa AS DOUBLE) AS total_obligated_amount_pa,
                   CAST(total_obligated_amount_hmgp AS DOUBLE) AS total_obligated_amount_hmgp
            FROM read_json('{s_path}', format='newline_delimited', union_by_name=true)
        """)
    meta = {
        "loaded_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "declaration_rows": len(decl),
        "summary_rows": len(summ),
        "source": "OpenFEMA API (fema.gov/api/open)",
    }
    con.execute("CREATE TABLE _meta (key TEXT, value TEXT)")
    con.executemany("INSERT INTO _meta VALUES (?, ?)", [(k, str(v)) for k, v in meta.items()])
    con.close()
    tmp_out.replace(out)
    return meta


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("data/fema.duckdb"))
    print(json.dumps(load(ap.parse_args().out), indent=2))
