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
