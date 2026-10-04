"""Data pipeline: documents -> chunks -> index, and synthetic transactions CSV -> SQLite."""
import csv
import pickle
import random
import re
import sqlite3
from pathlib import Path

from .config import settings
from .models import Chunk
from .retriever import Retriever


def chunk_text(text: str, max_words: int = 90, overlap: int = 20) -> list[str]:
    heading, chunks = "", []
    for para in (p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()):
        if para.startswith("#"):
            heading = para.lstrip("# ").strip()
            continue
        words = para.split()
        i = 0
        while i < len(words):
            body = " ".join(words[i:i + max_words])
            chunks.append(f"{heading}: {body}" if heading else body)
            if i + max_words >= len(words):
                break
            i += max_words - overlap
    return chunks


def load_chunks(docs_dir: Path = settings.docs_dir) -> list[Chunk]:
    chunks = []
    for f in sorted(docs_dir.glob("*.md")):
        for n, t in enumerate(chunk_text(f.read_text())):
            chunks.append(Chunk(id=f"{f.stem}#{n}", source=f.name, text=t))
    return chunks


def build_index() -> Retriever:
    settings.artifacts.mkdir(exist_ok=True)
    r = Retriever(load_chunks())
    with open(settings.artifacts / "index.pkl", "wb") as fh:
        pickle.dump(r, fh)
    return r


def load_index() -> Retriever:
    p = settings.artifacts / "index.pkl"
    if p.exists():
        with open(p, "rb") as fh:
            return pickle.load(fh)
    return build_index()


def generate_transactions(path: Path, n: int = 300, seed: int = 7) -> None:
    rnd = random.Random(seed)
    merchants = ["Amazon", "Swiggy", "Uber", "BigBasket", "Flipkart", "Netflix", "Airline X", "Pharmacy Y"]
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["txn_id", "customer_id", "merchant", "amount", "status", "txn_date", "dispute_status"])
        for i in range(1, n + 1):
            disputed = rnd.random() < 0.08
            w.writerow([f"TXN{i:05d}", f"C{rnd.randint(1, 10):03d}", rnd.choice(merchants),
                        round(rnd.uniform(50, 15000), 2), rnd.choice(["settled"] * 8 + ["failed", "refunded"]),
                        f"2026-0{rnd.randint(1, 9)}-{rnd.randint(10, 28)}",
                        rnd.choice(["open", "resolved", "rejected"]) if disputed else "none"])


def build_db() -> Path:
    settings.artifacts.mkdir(exist_ok=True)
    csv_path, db_path = settings.artifacts / "transactions.csv", settings.artifacts / "payguard.db"
    generate_transactions(csv_path)
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    con.execute("""CREATE TABLE transactions(txn_id TEXT PRIMARY KEY, customer_id TEXT, merchant TEXT,
                   amount REAL, status TEXT, txn_date TEXT, dispute_status TEXT)""")
    with open(csv_path) as fh:
        rows = [tuple(r.values()) for r in csv.DictReader(fh)]
    con.executemany("INSERT INTO transactions VALUES (?,?,?,?,?,?,?)", rows)
    con.commit()
    con.close()
    return db_path


if __name__ == "__main__":
    r = build_index()
    db = build_db()
    print(f"Indexed {len(r.chunks)} chunks; built DB at {db}")
