import time
from types import SimpleNamespace

import bot


def test_start_command_adds_subscriber(monkeypatch, isolated_db):
    update_payload = {
        "result": [
            {"update_id": 1, "message": {"chat": {"id": 555}, "text": "/start"}}
        ]
    }

    monkeypatch.setattr(bot.requests, "get", lambda url, params=None: SimpleNamespace(json=lambda: update_payload))

    bot.check_incoming_messages(time.time())

    assert 555 in bot.get_subscribers()


def test_start_command_does_not_reply_or_broadcast(monkeypatch, isolated_db):
    update_payload = {
        "result": [
            {"update_id": 1, "message": {"chat": {"id": 555}, "text": "/start"}}
        ]
    }

    monkeypatch.setattr(bot.requests, "get", lambda url, params=None: SimpleNamespace(json=lambda: update_payload))

    sent_messages = []
    monkeypatch.setattr(bot, "send_message", lambda chat_id, text: sent_messages.append((chat_id, text)))

    bot.check_incoming_messages(time.time())

    assert sent_messages == []
