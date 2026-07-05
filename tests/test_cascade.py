import pytest

import bot
import main


@pytest.fixture
def cascade_env(monkeypatch, isolated_db):
    monkeypatch.setattr(main, "LLM_BACKEND", "cascade")
    monkeypatch.setattr(main, "get_companies", lambda: ["acme"])
    sent = []
    monkeypatch.setattr(main, "send_notification", lambda job: sent.append(job["title"]))
    return sent


@pytest.fixture
def job():
    return {
        "title": "Graduate Software Engineer",
        "company": "Acme",
        "location": "London",
        "link": "https://example.com/jobs/1",
        "id": 1,
    }


def test_gemma_false_rejects_without_calling_gemini(monkeypatch, cascade_env, job, get_decision):
    monkeypatch.setattr(main, "fetch_greenhouse_jobs", lambda slug: [job])

    gemini_calls = []
    monkeypatch.setattr(main, "is_relevant_ai_ollama", lambda j: False)
    monkeypatch.setattr(main, "is_relevant_ai", lambda j: gemini_calls.append(j) or True)

    main.check_jobs()

    assert gemini_calls == []
    assert cascade_env == []
    assert bot.already_sent(job["link"]) is True
    assert get_decision(job["link"]) == "gemma_rejected"


def test_gemma_true_gemini_true_sends_notification(monkeypatch, cascade_env, job, get_decision):
    monkeypatch.setattr(main, "fetch_greenhouse_jobs", lambda slug: [job])
    monkeypatch.setattr(main, "is_relevant_ai_ollama", lambda j: True)
    monkeypatch.setattr(main, "is_relevant_ai", lambda j: True)

    main.check_jobs()

    assert cascade_env == [job["title"]]
    assert bot.already_sent(job["link"]) is True
    assert get_decision(job["link"]) == "sent"


def test_gemma_true_gemini_false_does_not_send(monkeypatch, cascade_env, job, get_decision):
    monkeypatch.setattr(main, "fetch_greenhouse_jobs", lambda slug: [job])
    monkeypatch.setattr(main, "is_relevant_ai_ollama", lambda j: True)
    monkeypatch.setattr(main, "is_relevant_ai", lambda j: False)

    main.check_jobs()

    assert cascade_env == []
    assert bot.already_sent(job["link"]) is True
    assert get_decision(job["link"]) == "gemini_rejected"


def test_gemma_none_skips_without_marking(monkeypatch, cascade_env, job, get_decision):
    monkeypatch.setattr(main, "fetch_greenhouse_jobs", lambda slug: [job])

    gemini_calls = []
    monkeypatch.setattr(main, "is_relevant_ai_ollama", lambda j: None)
    monkeypatch.setattr(main, "is_relevant_ai", lambda j: gemini_calls.append(j) or True)

    main.check_jobs()

    assert gemini_calls == []
    assert cascade_env == []
    assert bot.already_sent(job["link"]) is False
    assert get_decision(job["link"]) is None


def test_gemini_none_skips_without_marking(monkeypatch, cascade_env, job, get_decision):
    monkeypatch.setattr(main, "fetch_greenhouse_jobs", lambda slug: [job])
    monkeypatch.setattr(main, "is_relevant_ai_ollama", lambda j: True)
    monkeypatch.setattr(main, "is_relevant_ai", lambda j: None)

    main.check_jobs()

    assert cascade_env == []
    assert bot.already_sent(job["link"]) is False
    assert get_decision(job["link"]) is None
