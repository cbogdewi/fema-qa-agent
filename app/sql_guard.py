"""Validate LLM-generated SQL before it touches the database.

Defense in depth: the database is also opened read-only, but we still refuse
anything that is not a single SELECT over the known tables.
"""

from __future__ import annotations

import re

ALLOWED_TABLES = {"declarations", "disaster_summaries"}

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|copy|export|import|install|load|"
    r"pragma|set|call|checkpoint|vacuum|grant|revoke|truncate|merge|use)\b",
    re.IGNORECASE,
)
_FILE_FUNCS = re.compile(
    r"\b(read_csv\w*|read_parquet|read_json\w*|read_text|read_blob|glob|parquet_scan|"
    r"sniff_csv|getenv|current_setting|httpfs|http_get)\b",
    re.IGNORECASE,
)
_TABLE_REF = re.compile(r"\b(?:from|join)\s+([a-zA-Z_][\w\.\"]*)", re.IGNORECASE)
_STRING = re.compile(r"'(?:[^']|'')*'")
# FROM also appears inside EXTRACT(year FROM d), TRIM(x FROM y), SUBSTRING(s FROM 2): not table references.
_INNER_FROM = re.compile(r"\b(extract|trim|substring|overlay)\s*\(([^()]*?)\bfrom\b", re.IGNORECASE)


class UnsafeSQLError(ValueError):
    pass


def _strip_strings(sql: str) -> str:
    return _STRING.sub("''", sql)


def validate_sql(sql: str, max_rows: int = 200) -> str:
    """Return a safe, row-limited version of `sql` or raise UnsafeSQLError."""
    if not sql or not sql.strip():
        raise UnsafeSQLError("empty query")
    cleaned = sql.strip().rstrip(";").strip()
    bare = _strip_strings(cleaned)

    if ";" in bare:
        raise UnsafeSQLError("multiple statements are not allowed")
    if "--" in bare or "/*" in bare:
        raise UnsafeSQLError("comments are not allowed")
    if not re.match(r"^\s*(select|with)\b", bare, re.IGNORECASE):
        raise UnsafeSQLError("only SELECT queries are allowed")
    if _FORBIDDEN.search(bare):
        raise UnsafeSQLError("query contains a forbidden keyword")
    if _FILE_FUNCS.search(bare):
        raise UnsafeSQLError("file and system functions are not allowed")

    refs_text = bare
    while _INNER_FROM.search(refs_text):
        refs_text = _INNER_FROM.sub(r"\1(\2,", refs_text)
    cte_names = {m.lower() for m in re.findall(r"\b([a-zA-Z_]\w*)\s+as\s*\(", bare, re.IGNORECASE)}
    for ref in _TABLE_REF.findall(refs_text):
        name = ref.strip('"').lower()
        if name.startswith("("):
            continue
        if name not in ALLOWED_TABLES and name not in cte_names:
            raise UnsafeSQLError(f"unknown table: {ref}")

    return f"SELECT * FROM ({cleaned}) AS q LIMIT {int(max_rows)}"
