"""Non-destructive SQLite status check: python tools/check_database.py"""
from pathlib import Path
import sqlite3

DB_PATH = Path(__file__).resolve().parent.parent / "instance" / "studyx_blue.sqlite3"
print("Database path:", DB_PATH)
if not DB_PATH.is_file():
    print("No database file at this path. Verify the project folder you launched.")
    raise SystemExit(1)

try:
    # mode=ro ensures this diagnostic never silently creates an empty database.
    with sqlite3.connect(DB_PATH.as_uri() + "?mode=ro", uri=True, timeout=5) as conn:
        journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    print("Journal mode:", journal)
    print("Users in this database:", count)
    print("Database read: OK")
except sqlite3.Error as error:
    print("Database read failed:", error)
    print("Close DB Browser or resolve its pending transaction, then retry.")
    raise SystemExit(1)
