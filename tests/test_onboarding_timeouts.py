from types import SimpleNamespace

import bot
import sources


def test_greenhouse_probe_uses_10s_timeout(monkeypatch):
    captured = {}

    def fake_get(url, timeout=None):
        captured["timeout"] = timeout
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr(bot.requests, "get", fake_get)

    bot.is_valid_greenhouse_board("acme")

    assert captured["timeout"] == 10


def test_lever_probe_uses_10s_timeout(monkeypatch):
    captured = {}

    def fake_get(url, timeout=None):
        captured["timeout"] = timeout
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr(bot.requests, "get", fake_get)

    bot.is_valid_lever_board("acme")

    assert captured["timeout"] == 10


def test_workday_probe_uses_10s_timeout(monkeypatch):
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["timeout"] = timeout
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr(bot.requests, "post", fake_post)

    bot.is_valid_workday_board("acme", "External", "wd1")

    assert captured["timeout"] == 10


def test_fetch_greenhouse_jobs_uses_10s_timeout(monkeypatch):
    captured = {}

    def fake_get(url, timeout=None):
        captured["timeout"] = timeout
        return SimpleNamespace(json=lambda: {"jobs": []})

    monkeypatch.setattr(sources.requests, "get", fake_get)

    sources.fetch_greenhouse_jobs("acme")

    assert captured["timeout"] == 10


def test_fetch_lever_jobs_uses_10s_timeout(monkeypatch):
    captured = {}

    def fake_get(url, timeout=None):
        captured["timeout"] = timeout
        return SimpleNamespace(json=lambda: [])

    monkeypatch.setattr(sources.requests, "get", fake_get)

    sources.fetch_lever_jobs("acme")

    assert captured["timeout"] == 10


def test_fetch_workday_jobs_uses_10s_timeout(monkeypatch):
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["timeout"] = timeout
        return SimpleNamespace(json=lambda: {"total": 0, "jobPostings": []})

    monkeypatch.setattr(sources.requests, "post", fake_post)

    sources.fetch_workday_jobs({"tenant": "acme", "site": "External", "host": "wd1"})

    assert captured["timeout"] == 10
