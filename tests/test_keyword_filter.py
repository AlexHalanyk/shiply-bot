import pytest

from main import is_relevant


@pytest.mark.parametrize("title", [
    "Graduate Software Engineer",
    "Junior Backend Engineer",
])
def test_relevant_titles_pass(title):
    assert is_relevant({"title": title}) is True


@pytest.mark.parametrize("title", [
    "Accounts Payable",
    "Senior Product Manager",
])
def test_irrelevant_titles_fail(title):
    assert is_relevant({"title": title}) is False
