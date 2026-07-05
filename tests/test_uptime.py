import time
from types import SimpleNamespace

import pytest

import bot


@pytest.mark.parametrize("seconds,expected", [
    (0, "0m 0s"),
    (59, "0m 59s"),
    (61, "1m 1s"),
    (3661, "1h 1m"),
    (90000, "1d 1h 0m"),
])
def test_format_uptime(seconds, expected):
    assert bot._format_uptime(seconds) == expected


def test_uptime_reflects_elapsed_time_since_start(isolated_db):
    start_time = time.time() - 125  # process "started" 2m5s ago

    reply = bot.build_stats_reply(start_time)

    assert "Uptime: 2m 5s" in reply


def test_uptime_is_not_hardcoded_to_zero(isolated_db):
    recent_start = time.time()
    older_start = time.time() - 7200  # 2 hours ago

    recent_reply = bot.build_stats_reply(recent_start)
    older_reply = bot.build_stats_reply(older_start)

    assert "Uptime: 0m 0s" in recent_reply
    assert "Uptime: 2h 0m" in older_reply
    assert recent_reply != older_reply


def test_check_incoming_messages_passes_through_the_same_start_time_to_stats(monkeypatch, isolated_db):
    # Guards against start_time being recomputed (e.g. via time.time()) instead
    # of being the single value captured once at process launch in main.py.
    update_payload = {
        "result": [
            {"update_id": 1, "message": {"chat": {"id": 999}, "text": "/stats"}}
        ]
    }
    monkeypatch.setattr(bot.requests, "get", lambda url, params=None: SimpleNamespace(json=lambda: update_payload))

    seen_start_times = []

    def fake_build_stats_reply(start_time):
        seen_start_times.append(start_time)
        return "stats"

    monkeypatch.setattr(bot, "build_stats_reply", fake_build_stats_reply)
    monkeypatch.setattr(bot, "send_message", lambda chat_id, text: None)

    fixed_start_time = 12345.0
    bot.check_incoming_messages(fixed_start_time)

    assert seen_start_times == [fixed_start_time]
