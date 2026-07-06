from types import SimpleNamespace

import bot


def _incoming(*texts_by_chat):
    return {
        "result": [
            {"update_id": i + 1, "message": {"chat": {"id": chat_id}, "text": text}}
            for i, (chat_id, text) in enumerate(texts_by_chat)
        ]
    }


def test_exception_handling_one_update_does_not_stop_the_next(monkeypatch, isolated_db):
    payload = _incoming((111, "/start"), (222, "/stats"))
    monkeypatch.setattr(bot.requests, "get", lambda url, params=None: SimpleNamespace(json=lambda: payload))
    monkeypatch.setattr(bot, "add_subscriber", lambda chat_id, first_name=None: (_ for _ in ()).throw(RuntimeError("boom")))
    sent = []
    monkeypatch.setattr(bot, "send_message", lambda chat_id, text: sent.append((chat_id, text)))

    bot.check_incoming_messages(0)  # must not raise

    assert any(chat_id == 222 for chat_id, _ in sent)  # /stats for the second chat still replied


def test_exception_handling_one_update_still_advances_the_offset(monkeypatch, isolated_db):
    payload = _incoming((111, "/start"))
    monkeypatch.setattr(bot, "add_subscriber", lambda chat_id, first_name=None: (_ for _ in ()).throw(RuntimeError("boom")))

    calls = []

    def fake_get(url, params=None):
        calls.append(params)
        return SimpleNamespace(json=lambda: payload if params is None else {"result": []})

    monkeypatch.setattr(bot.requests, "get", fake_get)

    bot.check_incoming_messages(0)  # must not raise

    assert {"offset": 2} in calls  # the failing update was still acknowledged


def test_malformed_update_missing_message_key_is_skipped(monkeypatch, isolated_db):
    payload = {
        "result": [
            {"update_id": 1},  # no "message" key at all
            {"update_id": 2, "message": {"chat": {"id": 222}, "text": "/stats"}},
        ]
    }
    monkeypatch.setattr(bot.requests, "get", lambda url, params=None: SimpleNamespace(json=lambda: payload))
    sent = []
    monkeypatch.setattr(bot, "send_message", lambda chat_id, text: sent.append((chat_id, text)))

    bot.check_incoming_messages(0)  # must not raise

    assert any(chat_id == 222 for chat_id, _ in sent)
