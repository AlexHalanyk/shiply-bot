import pytest

from bot import extract_greenhouse_slug


@pytest.mark.parametrize("text,expected", [
    ("monzo", "monzo"),
    ("skyscanner", "skyscanner"),
    ("https://boards.greenhouse.io/skyscanner", "skyscanner"),
    ("https://job-boards.greenhouse.io/monzo/jobs/12345", "monzo"),
    ("https://boards-api.greenhouse.io/v1/boards/monzo/jobs", "monzo"),
    ("hello world", None),
    ("/start", None),
    ("", None),
])
def test_extract_greenhouse_slug(text, expected):
    assert extract_greenhouse_slug(text) == expected
