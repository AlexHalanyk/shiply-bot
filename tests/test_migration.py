import sqlite3

import bot


def test_migration_adds_columns_and_preserves_existing_rows(tmp_path):
    db_path = tmp_path / "old_schema.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE sent_jobs (link TEXT PRIMARY KEY)")
    cursor.execute("INSERT INTO sent_jobs (link) VALUES (?)", ("https://example.com/old-job",))
    conn.commit()

    bot._migrate_sent_jobs_schema(cursor, conn)

    cursor.execute("PRAGMA table_info(sent_jobs)")
    columns = {row[1] for row in cursor.fetchall()}
    assert {"link", "decision", "processed_at"} <= columns

    cursor.execute(
        "SELECT link, decision, processed_at FROM sent_jobs WHERE link = ?",
        ("https://example.com/old-job",),
    )
    assert cursor.fetchone() == ("https://example.com/old-job", None, None)

    conn.close()


def test_migration_is_idempotent_on_already_migrated_db(tmp_path):
    db_path = tmp_path / "new_schema.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE sent_jobs (link TEXT PRIMARY KEY)")
    conn.commit()

    bot._migrate_sent_jobs_schema(cursor, conn)
    bot._migrate_sent_jobs_schema(cursor, conn)  # must not raise or duplicate columns

    cursor.execute("PRAGMA table_info(sent_jobs)")
    column_names = [row[1] for row in cursor.fetchall()]
    assert column_names.count("decision") == 1
    assert column_names.count("processed_at") == 1

    conn.close()


def test_migration_adds_profile_column_and_backfills_default(tmp_path):
    db_path = tmp_path / "pre_profile_schema.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE sent_jobs (link TEXT PRIMARY KEY, decision TEXT, processed_at TEXT)")
    cursor.execute(
        "INSERT INTO sent_jobs (link, decision, processed_at) VALUES (?, ?, ?)",
        ("https://example.com/old-job", "sent", "2026-01-01T00:00:00+00:00"),
    )
    conn.commit()

    bot._migrate_sent_jobs_schema(cursor, conn)

    cursor.execute("PRAGMA table_info(sent_jobs)")
    columns = {row[1] for row in cursor.fetchall()}
    assert "profile" in columns

    cursor.execute(
        "SELECT profile, decision, processed_at FROM sent_jobs WHERE link = ?",
        ("https://example.com/old-job",),
    )
    assert cursor.fetchone() == (bot.DEFAULT_PROFILE, "sent", "2026-01-01T00:00:00+00:00")

    conn.close()


def test_migration_allows_same_link_under_two_profiles(tmp_path):
    # The composite (link, profile) key is the whole point of the rework:
    # the same job link must be storable once per distinct profile.
    db_path = tmp_path / "composite_key_schema.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE sent_jobs (link TEXT PRIMARY KEY)")
    conn.commit()

    bot._migrate_sent_jobs_schema(cursor, conn)

    cursor.execute(
        "INSERT INTO sent_jobs (link, profile, decision, processed_at) VALUES (?, ?, ?, ?)",
        ("https://example.com/job", "profile A", "sent", "2026-01-01T00:00:00+00:00"),
    )
    cursor.execute(
        "INSERT INTO sent_jobs (link, profile, decision, processed_at) VALUES (?, ?, ?, ?)",
        ("https://example.com/job", "profile B", "cheap_filter", "2026-01-01T00:00:00+00:00"),
    )
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM sent_jobs WHERE link = ?", ("https://example.com/job",))
    assert cursor.fetchone()[0] == 2

    conn.close()


def test_subscribers_migration_adds_profile_and_first_name_and_backfills_default(tmp_path):
    db_path = tmp_path / "pre_profile_subscribers.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE subscribers (chat_id INTEGER PRIMARY KEY)")
    cursor.execute("INSERT INTO subscribers (chat_id) VALUES (?)", (111,))
    conn.commit()

    bot._migrate_subscribers_schema(cursor, conn)

    cursor.execute("PRAGMA table_info(subscribers)")
    columns = {row[1] for row in cursor.fetchall()}
    assert {"profile", "first_name"} <= columns

    cursor.execute("SELECT profile, first_name FROM subscribers WHERE chat_id = ?", (111,))
    assert cursor.fetchone() == (bot.DEFAULT_PROFILE, None)

    conn.close()


def test_subscribers_migration_is_idempotent(tmp_path):
    db_path = tmp_path / "new_subscribers.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE subscribers (chat_id INTEGER PRIMARY KEY)")
    conn.commit()

    bot._migrate_subscribers_schema(cursor, conn)
    bot._migrate_subscribers_schema(cursor, conn)  # must not raise or duplicate columns

    cursor.execute("PRAGMA table_info(subscribers)")
    column_names = [row[1] for row in cursor.fetchall()]
    assert column_names.count("profile") == 1
    assert column_names.count("first_name") == 1

    conn.close()
