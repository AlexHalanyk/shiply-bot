import bot
import main


def _job(link="https://example.com/jobs/1"):
    return {
        "title": "Graduate Software Engineer",
        "company": "Acme",
        "location": "London",
        "link": link,
        "id": 1,
    }


def test_same_job_two_profiles_evaluated_twice(monkeypatch, isolated_db):
    monkeypatch.setattr(main, "LLM_BACKEND", "gemini")
    monkeypatch.setattr(main, "get_companies", lambda: ["acme"])
    job = _job()
    monkeypatch.setattr(main, "fetch_greenhouse_jobs", lambda slug: [job])
    monkeypatch.setattr(main, "send_notification", lambda job, chat_ids: None)

    bot.set_profile(111, "graduate software engineering roles")
    bot.set_profile(222, "senior data engineer roles")

    calls = []

    def fake_is_relevant_ai(j, profile):
        calls.append(profile)
        return True

    monkeypatch.setattr(main, "is_relevant_ai", fake_is_relevant_ai)

    main.check_jobs()

    # One evaluation per distinct profile among subscribers, plus the
    # always-on default profile baseline.
    assert set(calls) == {"graduate software engineering roles", "senior data engineer roles", bot.DEFAULT_PROFILE}
    assert len(calls) == 3


def test_same_profile_two_users_evaluated_once(monkeypatch, isolated_db):
    monkeypatch.setattr(main, "LLM_BACKEND", "gemini")
    monkeypatch.setattr(main, "get_companies", lambda: ["acme"])
    job = _job()
    monkeypatch.setattr(main, "fetch_greenhouse_jobs", lambda slug: [job])
    monkeypatch.setattr(main, "send_notification", lambda job, chat_ids: None)

    bot.set_profile(111, "graduate software engineering roles")
    bot.set_profile(222, "graduate software engineering roles")

    calls = []

    def fake_is_relevant_ai(j, profile):
        calls.append(profile)
        return True

    monkeypatch.setattr(main, "is_relevant_ai", fake_is_relevant_ai)

    main.check_jobs()

    # Both subscribers share one profile text, so it's evaluated once, plus
    # the always-on default profile baseline (no subscriber uses it here).
    assert calls.count("graduate software engineering roles") == 1
    assert calls.count(bot.DEFAULT_PROFILE) == 1
    assert len(calls) == 2


def test_notification_routing_only_to_matching_profile_subscribers(monkeypatch, isolated_db):
    monkeypatch.setattr(main, "LLM_BACKEND", "gemini")
    monkeypatch.setattr(main, "get_companies", lambda: ["acme"])
    job = _job()
    monkeypatch.setattr(main, "fetch_greenhouse_jobs", lambda slug: [job])

    bot.set_profile(111, "graduate software engineering roles")
    bot.set_profile(222, "senior data engineer roles")

    def fake_is_relevant_ai(j, profile):
        # Only the "graduate" profile approves this job.
        return profile == "graduate software engineering roles"

    monkeypatch.setattr(main, "is_relevant_ai", fake_is_relevant_ai)

    notified = []
    monkeypatch.setattr(main, "send_notification", lambda job, chat_ids: notified.append(list(chat_ids)))

    main.check_jobs()

    assert notified == [[111]]


def test_dedup_is_per_profile_not_global(monkeypatch, isolated_db, get_decision):
    monkeypatch.setattr(main, "LLM_BACKEND", "gemini")
    monkeypatch.setattr(main, "get_companies", lambda: ["acme"])
    job = _job()
    monkeypatch.setattr(main, "fetch_greenhouse_jobs", lambda slug: [job])
    monkeypatch.setattr(main, "send_notification", lambda job, chat_ids: None)

    bot.set_profile(111, "profile A")
    bot.set_profile(222, "profile B")
    monkeypatch.setattr(main, "is_relevant_ai", lambda j, profile: True)

    main.check_jobs()

    assert bot.already_sent(job["link"], "profile A") is True
    assert bot.already_sent(job["link"], "profile B") is True
    assert get_decision(job["link"], "profile A") == "sent"
    assert get_decision(job["link"], "profile B") == "sent"


def test_second_cycle_does_not_re_evaluate_already_processed_profile(monkeypatch, isolated_db):
    monkeypatch.setattr(main, "LLM_BACKEND", "gemini")
    monkeypatch.setattr(main, "get_companies", lambda: ["acme"])
    job = _job()
    monkeypatch.setattr(main, "fetch_greenhouse_jobs", lambda slug: [job])
    monkeypatch.setattr(main, "send_notification", lambda job, chat_ids: None)

    bot.set_profile(111, "graduate software engineering roles")

    calls = []
    monkeypatch.setattr(main, "is_relevant_ai", lambda j, profile: calls.append(profile) or True)

    main.check_jobs()
    main.check_jobs()

    assert calls.count("graduate software engineering roles") == 1
