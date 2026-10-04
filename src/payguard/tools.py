"""Agent tools. Transaction tool enforces: read-only SELECT, single statement, allow-listed table,
row cap, and row-level security (queries run on an in-memory copy holding ONLY the caller's rows)."""
import re
import sqlite3
from pathlib import Path

from .config import settings

_FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|alter|attach|pragma|create|replace|vacuum|load_extension)\b", re.I)
ALLOWED_TABLES = {"transactions"}
MAX_ROWS = 50


class UnsafeSQL(ValueError):
    pass


def validate_select(sql: str) -> str:
    s = sql.strip().rstrip(";").strip()
    if ";" in s or "--" in s or "/*" in s:
        raise UnsafeSQL("multiple statements or comments not allowed")
    if not s.lower().startswith("select"):
        raise UnsafeSQL("only SELECT is allowed")
    if _FORBIDDEN.search(s):
        raise UnsafeSQL("forbidden keyword")
    tables = set(t.lower() for t in re.findall(r"\b(?:from|join)\s+([a-zA-Z_]\w*)", s, re.I))
    if not tables or not tables <= ALLOWED_TABLES:
        raise UnsafeSQL(f"table not allowed: {tables - ALLOWED_TABLES or 'none'}")
    if not re.search(r"\blimit\s+\d+", s, re.I):
        s += f" LIMIT {MAX_ROWS}"
    return s


class TransactionTool:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or settings.artifacts / "payguard.db"

    def run(self, customer_id: str, sql: str) -> list[dict]:
        sql = validate_select(sql)
        src = sqlite3.connect(self.db_path)
        src.row_factory = sqlite3.Row
        rows = src.execute("SELECT * FROM transactions WHERE customer_id=?", (customer_id,)).fetchall()
        cols = rows[0].keys() if rows else [r[1] for r in src.execute("PRAGMA table_info(transactions)")]
        src.close()
        mem = sqlite3.connect(":memory:")
        mem.row_factory = sqlite3.Row
        mem.execute(f"CREATE TABLE transactions({','.join(cols)})")
        mem.executemany(f"INSERT INTO transactions VALUES ({','.join('?' * len(cols))})", [tuple(r) for r in rows])
        out = [dict(r) for r in mem.execute(sql).fetchall()]
        mem.close()
        return out


_TXN = re.compile(r"\bTXN\d{5}\b", re.I)


def plan_sql(question: str) -> str | None:
    """Deterministic intent -> SQL templates. (An LLM text-to-SQL planner can replace this;
    its output still goes through validate_select.)"""
    q = question.lower()
    m = _TXN.search(question)
    if m:
        return f"SELECT txn_id, merchant, amount, status, txn_date, dispute_status FROM transactions WHERE txn_id='{m.group(0).upper()}'"
    if re.search(r"\bmy (open |recent )?(disputed )?(disputes?|transactions?)\b", q) and "dispute" in q:
        return "SELECT txn_id, merchant, amount, dispute_status FROM transactions WHERE dispute_status != 'none'"
    if re.search(r"total (spend|spent|amount)|how much (have i|did i) spen[dt]|my spend", q):
        return "SELECT ROUND(SUM(amount),2) AS total_spend, COUNT(*) AS settled_transactions FROM transactions WHERE status='settled'"
    if re.search(r"how many (of )?my (transactions|purchases)", q):
        return "SELECT COUNT(*) AS transactions FROM transactions"
    return None
