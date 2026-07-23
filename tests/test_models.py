from gov_intel.models import Document, make_doc_id, normalize_keyword_rules


def test_make_doc_id_is_stable():
    url = "https://www.gov.uk/government/publications/example"
    assert make_doc_id(url) == make_doc_id(url)


def test_make_doc_id_differs_for_different_urls():
    a = make_doc_id("https://www.gov.uk/a")
    b = make_doc_id("https://www.gov.uk/b")
    assert a != b


def test_document_from_api_result_builds_absolute_url():
    raw = {
        "title": "Example Policy",
        "description": "A description.",
        "link": "/government/publications/example",
        "public_timestamp": "2026-01-15T00:00:00.000Z",
    }
    doc = Document.from_api_result(raw, topic="digital government", attachments=["https://x/y.pdf"])
    assert doc.url == "https://www.gov.uk/government/publications/example"
    assert doc.date == "2026-01-15"
    assert doc.attachments == ["https://x/y.pdf"]
    assert doc.id == make_doc_id(doc.url)


def test_document_from_api_result_handles_missing_fields():
    doc = Document.from_api_result({}, topic="t", attachments=[])
    assert doc.title == "Official Publication"
    assert doc.date == "Recent"


def test_document_round_trips_through_dict():
    doc = Document(id="abc123", title="T", description="D", url="https://x", date="2026-01-01", topic="t")
    restored = Document.from_dict(doc.to_dict())
    assert restored == doc


def test_normalize_keyword_rules_upgrades_legacy_list_terms():
    legacy = {"Cat A": {"color": [1, 0, 0], "terms": ["alpha", "beta"]}}
    normalized = normalize_keyword_rules(legacy)
    assert normalized["Cat A"]["terms"] == {"alpha": True, "beta": True}


def test_normalize_keyword_rules_leaves_dict_terms_untouched():
    current = {"Cat A": {"color": [1, 0, 0], "terms": {"alpha": False}}}
    normalized = normalize_keyword_rules(current)
    assert normalized["Cat A"]["terms"] == {"alpha": False}
