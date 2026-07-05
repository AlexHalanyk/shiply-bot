import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# bot.py connects to sqlite at import time; point it at a throwaway file
# *before* anything imports bot, so the real data/sent_jobs.db is never touched.
os.environ.setdefault("JOBRADAR_DB_PATH", os.path.join(tempfile.mkdtemp(), "import_time.db"))

import bot  # noqa: E402


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(bot.time, "sleep", lambda seconds: None)


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    conn = sqlite3.connect(tmp_path / "test.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE sent_jobs (
            link TEXT PRIMARY KEY,
            decision TEXT,
            processed_at TEXT
        )
    """)
    cursor.execute("CREATE TABLE subscribers (chat_id INTEGER PRIMARY KEY)")
    cursor.execute("CREATE TABLE companies (slug TEXT PRIMARY KEY)")
    conn.commit()

    monkeypatch.setattr(bot, "db", conn)
    monkeypatch.setattr(bot, "db_cursor", cursor)

    yield conn
    conn.close()


@pytest.fixture
def get_decision():
    def _get_decision(link):
        bot.db_cursor.execute("SELECT decision FROM sent_jobs WHERE link = ?", (link,))
        row = bot.db_cursor.fetchone()
        return row[0] if row else None

    return _get_decision


@pytest.fixture
def sample_job():
    return {
        "title": "Graduate Software Engineer",
        "company": "Acme",
        "location": "London",
        "link": "https://example.com/jobs/1",
        "id": 1,
    }
