import os
import shutil
import sqlite3
import threading
import time
from pathlib import Path

# DATA_DIR is set to the Railway Volume mount path in production (/app/data).
# Falls back to the repo root for local development.
_DATA_DIR = Path(os.getenv("DATA_DIR", "."))
DB_PATH = _DATA_DIR / "hackathon.db"
BACKUP_DIR = _DATA_DIR / "backups"
MAX_BACKUPS = 20

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    date TEXT,
    venue TEXT,
    city TEXT,
    org_name TEXT,
    org_address TEXT,
    org_website TEXT,
    organizer_name TEXT,
    organizer_title TEXT,
    logo_path TEXT,
    hours_expected REAL DEFAULT 4.0,
    admin_password_hash TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS judges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id),
    name TEXT NOT NULL,
    email TEXT,
    expertise TEXT,
    pin TEXT NOT NULL,
    token_hash TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id),
    title TEXT NOT NULL,
    team_name TEXT,
    table_number TEXT,
    track TEXT,
    description TEXT,
    devpost_url TEXT,
    imported_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    judge_id INTEGER NOT NULL REFERENCES judges(id),
    project_id INTEGER NOT NULL REFERENCES projects(id),
    innovation REAL DEFAULT 0,
    technical REAL DEFAULT 0,
    impact REAL DEFAULT 0,
    presentation REAL DEFAULT 0,
    total_raw REAL DEFAULT 0,
    total_weighted REAL DEFAULT 0,
    notes TEXT,
    submitted_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    sync_status TEXT DEFAULT 'synced',
    UNIQUE(judge_id, project_id)
);
"""


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    BACKUP_DIR.mkdir(exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA_SQL)


def backup_db():
    if not DB_PATH.exists():
        return
    ts = int(time.time())
    dest = BACKUP_DIR / f"scores_{ts}.db"
    shutil.copy2(DB_PATH, dest)
    backups = sorted(BACKUP_DIR.glob("scores_*.db"))
    for old in backups[:-MAX_BACKUPS]:
        old.unlink(missing_ok=True)


def start_backup_scheduler():
    def loop():
        while True:
            time.sleep(60)
            try:
                backup_db()
            except Exception:
                pass

    t = threading.Thread(target=loop, daemon=True)
    t.start()


def row_to_dict(row) -> dict:
    if row is None:
        return None
    return dict(row)


def rows_to_list(rows) -> list:
    return [dict(r) for r in rows]
