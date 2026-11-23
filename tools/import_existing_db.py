"""Safely snapshot a previously used StudyX SQLite database into this folder.

Usage (before launching the new folder):
    python tools/import_existing_db.py "C:\\path\\to\\old\\instance\\studyx_blue.sqlite3"
This DOES NOT delete or modify the source. It refuses to replace an existing target.
"""
import argparse
import sqlite3
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
TARGET = PROJECT / "instance" / "studyx_blue.sqlite3"


def main():
    parser = argparse.ArgumentParser(description="Copy your EXISTING StudyX data safely")
    parser.add_argument("old_database", help="Full path to the old studyx_blue.sqlite3")
    args = parser.parse_args()
    source = Path(args.old_database).expanduser().resolve()
    if not source.is_file():
        sys.exit(f"ERROR: Source database not found: {source}")
    if source == TARGET.resolve():
        sys.exit("ERROR: Source and destination must be different.")
    if TARGET.exists():
        sys.exit(f"STOP: Destination already exists: {TARGET}\n"
                 "This tool will NOT overwrite any database. Do not delete it blindly.\n"
                 "If you want to migrate, first BACK UP this destination and move it away.")
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    temp = TARGET.with_suffix(".importing.sqlite3")
    if temp.exists():
        sys.exit(f"STOP: Temporary file already exists: {temp}")
    try:
        with sqlite3.connect(str(source), timeout=30) as old:
            old.execute("PRAGMA query_only=ON")
            with sqlite3.connect(temp, timeout=30) as new:
                old.backup(new, pages=100)
                result = new.execute("PRAGMA integrity_check").fetchone()[0]
                if result.lower() != "ok":
                    raise RuntimeError(f"Imported database failed integrity check: {result}")
                tables = {item[0] for item in new.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}
                if "users" not in tables or "subjects" not in tables:
                    raise RuntimeError("This is not a recognizable StudyX database; import stopped.")
                print("Safe snapshot includes:", len(tables), "tables")
                print("Registered users:", new.execute("SELECT COUNT(*) FROM users").fetchone()[0])
        temp.replace(TARGET)
    except Exception:
        temp.unlink(missing_ok=True)
        raise
    print("SUCCESS: imported to", TARGET)
    print("Original database untouched:", source)
    print("Now run: python run.py  (or python run.py --lan)")


if __name__ == "__main__":
    main()
