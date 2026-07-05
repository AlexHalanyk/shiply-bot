from types import SimpleNamespace

import pytest

import bot

TRUE_RESPONSES = ["YES", "yes.", " YES ", "YES", "Yes, it is"]
FALSE_RESPONSES = ["NO", "no.", ""]


class FakeModels:
    def __init__(self, text):
        self._text = text

    def generate_content(self, model, contents):
        return SimpleNamespace(text=self._text)


@pytest.mark.parametrize("raw_response", TRUE_RESPONSES)
def test_is_relevant_ai_recognises_yes(monkeypatch, sample_job, raw_response):
    monkeypatch.setattr(bot, "client", SimpleNamespace(models=FakeModels(raw_response)))
    assert bot.is_relevant_ai(sample_job) is True


@pytest.mark.parametrize("raw_response", FALSE_RESPONSES)
def test_is_relevant_ai_recognises_no(monkeypatch, sample_job, raw_response):
    monkeypatch.setattr(bot, "client", SimpleNamespace(models=FakeModels(raw_response)))
    assert bot.is_relevant_ai(sample_job) is False
