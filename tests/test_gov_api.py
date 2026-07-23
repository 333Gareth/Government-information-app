from unittest.mock import MagicMock

import pytest

from gov_intel.gov_api import (
    classify_attachment_url,
    clean_folder_name,
    deep_harvest_gov_uk,
    fetch_attachments,
    sanitize_filename,
)


# -- pure functions: no mocking needed -----------------------------------

@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://example.com/report.pdf", "📕 PDF"),
        ("https://example.com/report.pdf?download=true", "📕 PDF"),
        ("https://example.com/chart.png", "🖼️ Image"),
        ("https://example.com/data.csv", "📊 Data"),
        ("https://example.com/data.CSV", "📊 Data"),
        ("https://example.com/policy.docx", "📄 Doc"),
        ("https://example.com/page", "🌐 Link"),
    ],
)
def test_classify_attachment_url(url, expected):
    assert classify_attachment_url(url) == expected


def test_clean_folder_name_strips_unsafe_chars_and_lowercases():
    assert clean_folder_name('My: Topic/Name?') == "my_topicname"


def test_clean_folder_name_never_returns_empty():
    assert clean_folder_name('???') != ""


def test_sanitize_filename_strips_path_separators():
    assert sanitize_filename("https://x.gov.uk/files/report.pdf") == "report.pdf"


def test_sanitize_filename_handles_query_strings():
    result = sanitize_filename("https://x.gov.uk/files/report.pdf?token=abc/../etc")
    assert "/" not in result and ".." not in result


# -- functions that hit the network: use a mocked requests.Session -------

def _mock_session(json_payloads):
    """Return a mock session whose .get() yields the given JSON payloads in order."""
    session = MagicMock()
    responses = []
    for payload in json_payloads:
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = payload
        responses.append(resp)
    session.get.side_effect = responses
    return session


def test_deep_harvest_stops_at_target_total():
    page = {"results": [{"title": f"Doc {i}"} for i in range(50)]}
    session = _mock_session([page, page])
    results = deep_harvest_gov_uk(
        "digital government", target_total=60, sort_order="Best Match",
        dept_filter="All Departments", doc_type_filter="All Types",
        exact_match=False, session=session,
    )
    assert len(results) == 60


def test_deep_harvest_stops_when_api_returns_no_more_results():
    page = {"results": [{"title": "Only doc"}]}
    empty = {"results": []}
    session = _mock_session([page, empty])
    results = deep_harvest_gov_uk(
        "niche topic", target_total=100, sort_order="Best Match",
        dept_filter="All Departments", doc_type_filter="All Types",
        exact_match=False, session=session,
    )
    assert len(results) == 1


def test_deep_harvest_handles_network_error_gracefully():
    import requests

    session = MagicMock()
    session.get.side_effect = requests.ConnectionError("boom")
    log_messages = []
    results = deep_harvest_gov_uk(
        "topic", target_total=10, sort_order="Best Match",
        dept_filter="All Departments", doc_type_filter="All Types",
        exact_match=False, log_cb=log_messages.append, session=session,
    )
    assert results == []
    assert any("Network error" in m for m in log_messages)


def test_fetch_attachments_collects_attachment_urls():
    payload = {
        "details": {
            "attachments": [{"url": "/media/report.pdf"}, {"url": "https://external.example/report2.pdf"}],
            "parts": [],
        },
        "links": {},
    }
    session = _mock_session([payload])
    atts = fetch_attachments("/government/publications/example", session=session)
    assert "https://www.gov.uk/media/report.pdf" in atts
    assert "https://external.example/report2.pdf" in atts


def test_fetch_attachments_returns_empty_list_on_http_error():
    session = MagicMock()
    resp = MagicMock()
    resp.status_code = 404
    session.get.return_value = resp
    assert fetch_attachments("/some/path", session=session) == []


def test_fetch_attachments_returns_empty_list_on_network_error():
    import requests

    session = MagicMock()
    session.get.side_effect = requests.ConnectionError("boom")
    assert fetch_attachments("/some/path", session=session) == []
