from types import SimpleNamespace

import bot


def _incoming(chat_id, text):
    return {"result": [{"update_id": 1, "message": {"chat": {"id": chat_id}, "text": text}}]}


def test_profile_with_text_saves_and_confirms(monkeypatch, isolated_db):
    monkeypatch.setattr(
        bot.requests, "get", lambda url, params=None: SimpleNamespace(json=lambda: _incoming(111, "/profile senior data engineer roles in London"))
    )
    sent_messages = []
    monkeypatch.setattr(bot, "send_message", lambda chat_id, text: sent_messages.append((chat_id, text)))

    bot.check_incoming_messages(0)

    assert bot.get_profile(111) == "senior data engineer roles in London"
    assert len(sent_messages) == 1
    chat_id, text = sent_messages[0]
    assert chat_id == 111
    assert "senior data engineer roles in London" in text


def test_profile_without_text_replies_with_current_profile(monkeypatch, isolated_db):
    bot.set_profile(222, "backend roles in Berlin")

    monkeypatch.setattr(bot.requests, "get", lambda url, params=None: SimpleNamespace(json=lambda: _incoming(222, "/profile")))
    sent_messages = []
    monkeypatch.setattr(bot, "send_message", lambda chat_id, text: sent_messages.append((chat_id, text)))

    bot.check_incoming_messages(0)

    assert len(sent_messages) == 1
    chat_id, text = sent_messages[0]
    assert chat_id == 222
    assert "backend roles in Berlin" in text


def test_profile_without_text_defaults_to_default_profile_for_new_chat(monkeypatch, isolated_db):
    monkeypatch.setattr(bot.requests, "get", lambda url, params=None: SimpleNamespace(json=lambda: _incoming(333, "/profile")))
    sent_messages = []
    monkeypatch.setattr(bot, "send_message", lambda chat_id, text: sent_messages.append((chat_id, text)))

    bot.check_incoming_messages(0)

    assert sent_messages[0] == (333, f"Current profile:\n{bot.DEFAULT_PROFILE}")


def test_profile_does_not_reset_on_subsequent_start(monkeypatch, isolated_db):
    bot.set_profile(444, "custom profile text")

    monkeypatch.setattr(bot.requests, "get", lambda url, params=None: SimpleNamespace(json=lambda: _incoming(444, "/start")))
    monkeypatch.setattr(bot, "send_message", lambda chat_id, text: None)

    bot.check_incoming_messages(0)

    assert bot.get_profile(444) == "custom profile text"


def test_start_captures_first_name(monkeypatch, isolated_db):
    update_payload = {
        "result": [
            {"update_id": 1, "message": {"chat": {"id": 555, "first_name": "Alex"}, "text": "/start"}}
        ]
    }
    monkeypatch.setattr(bot.requests, "get", lambda url, params=None: SimpleNamespace(json=lambda: update_payload))

    bot.check_incoming_messages(0)

    bot.db_cursor.execute("SELECT first_name FROM subscribers WHERE chat_id = ?", (555,))
    assert bot.db_cursor.fetchone() == ("Alex",)
