import pytest

from app.sql_guard import UnsafeSQLError, validate_sql

SAFE = [
    "SELECT COUNT(DISTINCT disaster_number) FROM declarations",
    "select state, count(*) from declarations group by 1 order by 2 desc limit 5;",
    "WITH t AS (SELECT * FROM declarations) SELECT COUNT(*) FROM t",
    "SELECT d.state, SUM(s.total_obligated_amount_pa) FROM declarations d "
    "JOIN disaster_summaries s ON d.disaster_number = s.disaster_number GROUP BY 1",
    "SELECT * FROM declarations WHERE declaration_title ILIKE '%drop table%'",
    "SELECT replace(state, 'V', 'v') FROM declarations",
    "SELECT EXTRACT(year FROM declaration_date) AS y, COUNT(*) FROM declarations GROUP BY 1",
    "SELECT TRIM(BOTH ' ' FROM state) FROM declarations",
]

UNSAFE = [
    "DROP TABLE declarations",
    "SELECT 1; DROP TABLE declarations",
    "DELETE FROM declarations",
    "SELECT * FROM read_csv('/etc/passwd')",
    "SELECT * FROM users",
    "SELECT * FROM declarations -- hi",
    "ATTACH 'x.db' AS x",
    "SELECT getenv('GROQ_API_KEY')",
    "COPY declarations TO 'out.csv'",
    "",
    "SELECT EXTRACT(year FROM declaration_date) FROM secrets",
]


@pytest.mark.parametrize("sql", SAFE)
def test_safe_queries_pass_and_get_limited(sql):
    out = validate_sql(sql, max_rows=50)
    assert out.endswith("LIMIT 50")


@pytest.mark.parametrize("sql", UNSAFE)
def test_unsafe_queries_rejected(sql):
    with pytest.raises(UnsafeSQLError):
        validate_sql(sql)
