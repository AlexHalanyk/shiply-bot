from types import SimpleNamespace

from sources import fetch_lever_jobs


def test_fetch_lever_jobs_maps_fields(monkeypatch):
    payload = [
        {
            "id": "abc-123",
            "text": "Graduate Software Engineer",
            "categories": {"location": "London, UK", "team": "Engineering"},
            "hostedUrl": "https://jobs.lever.co/acme/abc-123",
        },
        {
            "id": "def-456",
            "text": "Senior Product Manager",
            "categories": {"location": "Remote", "team": "Product"},
            "hostedUrl": "https://jobs.lever.co/acme/def-456",
        },
    ]

    captured_url = {}

    def fake_get(url, timeout=None):
        captured_url["url"] = url
        captured_url["timeout"] = timeout
        return SimpleNamespace(json=lambda: payload)

    monkeypatch.setattr("sources.requests.get", fake_get)

    jobs = fetch_lever_jobs("acme")

    assert captured_url["url"] == "https://api.lever.co/v0/postings/acme?mode=json"
    assert captured_url["timeout"] == 10
    assert jobs == [
        {
            "title": "Graduate Software Engineer",
            "company": "acme",
            "location": "London, UK",
            "link": "https://jobs.lever.co/acme/abc-123",
            "id": "abc-123",
        },
        {
            "title": "Senior Product Manager",
            "company": "acme",
            "location": "Remote",
            "link": "https://jobs.lever.co/acme/def-456",
            "id": "def-456",
        },
    ]


def test_fetch_lever_jobs_empty_board(monkeypatch):
    monkeypatch.setattr("sources.requests.get", lambda url, timeout=None: SimpleNamespace(json=lambda: []))

    assert fetch_lever_jobs("empty-co") == []
