from types import SimpleNamespace

import pytest

import bot


def _incoming(text):
    return {"result": [{"update_id": 1, "message": {"chat": {"id": 111}, "text": text}}]}


@pytest.mark.parametrize("text,expected_slug", [
    ("https://jobs.lever.co/github", "github"),
    ("http://jobs.lever.co/github", "github"),
    ("jobs.lever.co/github", "github"),
    ("https://jobs.lever.co/github/98765abc-1234-5678-uuid", "github"),  # trailing posting id
    ("https://jobs.lever.co/acme-corp?lever-origin=applied", "acme-corp"),
])
def test_extract_lever_slug_valid(text, expected_slug):
    assert bot.extract_lever_slug(text) == expected_slug


@pytest.mark.parametrize("text", [
    "github",
    "https://jobs.lever.co/",
    "https://boards-api.greenhouse.io/v1/boards/github/jobs",
    "https://lever.co/github",  # missing the jobs. subdomain
    "",
])
def test_extract_lever_slug_invalid(text):
    assert bot.extract_lever_slug(text) is None


def test_lever_url_added_when_board_is_valid(monkeypatch, isolated_db):
    monkeypatch.setattr(bot.requests, "get", lambda url, params=None: SimpleNamespace(json=lambda: _incoming("https://jobs.lever.co/github")))
    monkeypatch.setattr(bot, "is_valid_lever_board", lambda slug: True)
    sent = []
    monkeypatch.setattr(bot, "send_message", lambda chat_id, text: sent.append(text))

    bot.check_incoming_messages(0)

    assert "github" in bot.get_companies()
    assert bot.get_company_ats("github") == "lever"
    assert "Lever" in sent[0]


def test_lever_url_not_found_replies_and_does_not_add(monkeypatch, isolated_db):
    monkeypatch.setattr(bot.requests, "get", lambda url, params=None: SimpleNamespace(json=lambda: _incoming("https://jobs.lever.co/github")))
    monkeypatch.setattr(bot, "is_valid_lever_board", lambda slug: False)
    sent = []
    monkeypatch.setattr(bot, "send_message", lambda chat_id, text: sent.append(text))

    bot.check_incoming_messages(0)

    assert "github" not in bot.get_companies()
    assert "not found" in sent[0].lower()


def test_lever_url_never_probes_greenhouse(monkeypatch, isolated_db):
    monkeypatch.setattr(bot.requests, "get", lambda url, params=None: SimpleNamespace(json=lambda: _incoming("https://jobs.lever.co/github")))
    monkeypatch.setattr(bot, "is_valid_lever_board", lambda slug: True)
    monkeypatch.setattr(bot, "is_valid_greenhouse_board", lambda slug: (_ for _ in ()).throw(AssertionError("Greenhouse should not be probed")))
    monkeypatch.setattr(bot, "send_message", lambda chat_id, text: None)

    bot.check_incoming_messages(0)  # must not raise

    assert bot.get_company_ats("github") == "lever"


def test_unrecognised_input_always_gets_a_reply(monkeypatch, isolated_db):
    # Regression guard: previously an input matching none of Workday/Lever/
    # Greenhouse (and not a bare slug) produced no reply at all.
    monkeypatch.setattr(bot.requests, "get", lambda url, params=None: SimpleNamespace(json=lambda: _incoming("hello world, not a board")))
    sent = []
    monkeypatch.setattr(bot, "send_message", lambda chat_id, text: sent.append(text))

    bot.check_incoming_messages(0)

    assert len(sent) == 1
    assert "not found" in sent[0].lower()
