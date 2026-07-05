from datetime import datetime

import pytest

import bot
import main


def test_mark_as_sent_records_decision_and_iso_timestamp(isolated_db):
    bot.mark_as_sent("https://example.com/jobs/1", "sent")

    bot.db_cursor.execute(
        "SELECT decision, processed_at FROM sent_jobs WHERE link = ?",
        ("https://example.com/jobs/1",),
    )
    decision, processed_at = bot.db_cursor.fetchone()

    assert decision == "sent"
    datetime.fromisoformat(processed_at)  # raises if not a valid ISO timestamp


@pytest.fixture
def job():
    return {
        "title": "Graduate Software Engineer",
        "company": "Acme",
        "location": "London",
        "link": "https://example.com/jobs/1",
        "id": 1,
    }


@pytest.fixture
def single_backend_env(monkeypatch, isolated_db):
    monkeypatch.setattr(main, "get_companies", lambda: ["acme"])
    sent = []
    monkeypatch.setattr(main, "send_notification", lambda job: sent.append(job["title"]))
    return sent


def test_cheap_filter_rejection_is_recorded(monkeypatch, single_backend_env, get_decision):
    job = {"title": "Senior Product Manager", "company": "Acme", "location": "London",
           "link": "https://example.com/jobs/2", "id": 2}
    monkeypatch.setattr(main, "fetch_greenhouse_jobs", lambda slug: [job])

    main.check_jobs()

    assert single_backend_env == []
    assert get_decision(job["link"]) == "cheap_filter"


def test_gemini_backend_sent_is_recorded(monkeypatch, single_backend_env, job, get_decision):
    monkeypatch.setattr(main, "LLM_BACKEND", "gemini")
    monkeypatch.setattr(main, "fetch_greenhouse_jobs", lambda slug: [job])
    monkeypatch.setattr(main, "is_relevant_ai", lambda j: True)

    main.check_jobs()

    assert single_backend_env == [job["title"]]
    assert get_decision(job["link"]) == "sent"


def test_gemini_backend_rejection_is_recorded(monkeypatch, single_backend_env, job, get_decision):
    monkeypatch.setattr(main, "LLM_BACKEND", "gemini")
    monkeypatch.setattr(main, "fetch_greenhouse_jobs", lambda slug: [job])
    monkeypatch.setattr(main, "is_relevant_ai", lambda j: False)

    main.check_jobs()

    assert single_backend_env == []
    assert get_decision(job["link"]) == "gemini_rejected"


def test_ollama_backend_rejection_is_recorded(monkeypatch, single_backend_env, job, get_decision):
    monkeypatch.setattr(main, "LLM_BACKEND", "ollama")
    monkeypatch.setattr(main, "fetch_greenhouse_jobs", lambda slug: [job])
    monkeypatch.setattr(main, "is_relevant_ai_ollama", lambda j: False)

    main.check_jobs()

    assert single_backend_env == []
    assert get_decision(job["link"]) == "gemma_rejected"


def test_ai_error_does_not_record_a_decision(monkeypatch, single_backend_env, job, get_decision):
    monkeypatch.setattr(main, "LLM_BACKEND", "gemini")
    monkeypatch.setattr(main, "fetch_greenhouse_jobs", lambda slug: [job])
    monkeypatch.setattr(main, "is_relevant_ai", lambda j: None)

    main.check_jobs()

    assert single_backend_env == []
    assert get_decision(job["link"]) is None
