import time
from types import SimpleNamespace

import bot


def test_stats_replies_only_to_sender_with_expected_content(monkeypatch, isolated_db):
    bot.add_company("acme")
    bot.add_subscriber(111)
    bot.add_subscriber(222)
    bot.mark_as_sent("https://example.com/jobs/1", "sent")
    bot.mark_as_sent("https://example.com/jobs/2", "cheap_filter")
    bot.mark_as_sent("https://example.com/jobs/3", "cheap_filter")
    bot.mark_as_sent("https://example.com/jobs/4", "gemini_rejected")

    update_payload = {
        "result": [
            {"update_id": 5000, "message": {"chat": {"id": 999}, "text": "/stats"}}
        ]
    }

    get_calls = []

    def fake_get(url, params=None):
        get_calls.append(params)
        return SimpleNamespace(json=lambda: update_payload)

    monkeypatch.setattr(bot.requests, "get", fake_get)

    sent_messages = []
    monkeypatch.setattr(bot, "send_message", lambda chat_id, text: sent_messages.append((chat_id, text)))

    start_time = time.time() - 3661  # ~1h 1m ago

    bot.check_incoming_messages(start_time)

    assert len(sent_messages) == 1
    chat_id, text = sent_messages[0]
    assert chat_id == 999

    assert "Total jobs processed: 4" in text
    assert "sent: 1 (25.0%)" in text
    assert "cheap_filter: 2 (50.0%)" in text
    assert "gemini_rejected: 1 (25.0%)" in text
    assert "Tracked companies: 1" in text
    assert "Subscribers: 2" in text
    assert "Uptime: 1h 1m" in text

    # the getUpdates offset ack should still happen, unaffected by /stats handling
    assert {"offset": 5001} in get_calls
