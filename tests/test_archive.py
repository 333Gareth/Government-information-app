import gov_intel.config as config
from gov_intel import archive


def _patch_topics_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "TOPICS_DIR", tmp_path / "topics")
    monkeypatch.setattr(archive, "TOPICS_DIR", tmp_path / "topics")


def test_build_and_save_archive_with_no_results_returns_none(tmp_path, monkeypatch):
    _patch_topics_dir(tmp_path, monkeypatch)
    logs = []
    result = archive.build_and_save_archive("empty topic", [], log_cb=logs.append)
    assert result == (None, None, [])
    assert any("No documents found" in m for m in logs)


def test_build_and_save_archive_writes_documents_and_briefing(tmp_path, monkeypatch):
    _patch_topics_dir(tmp_path, monkeypatch)
    raw_results = [
        {"title": "Digital Government Blueprint", "description": "A strategic overview of reform.",
         "link": "/government/publications/blueprint", "public_timestamp": "2026-02-01T00:00:00Z"},
        {"title": "Digital Government Funding", "description": "Short.",
         "link": "/government/publications/funding", "public_timestamp": "2026-02-02T00:00:00Z"},
    ]
    topic_dir, docs, suggestions = archive.build_and_save_archive(
        "digital government", raw_results, attachment_fetcher=lambda path: [f"https://x{path}.pdf"]
    )
    assert topic_dir is not None
    assert len(docs) == 2
    assert docs[0].attachments == ["https://x/government/publications/blueprint.pdf"]
    assert (topic_dir / "documents.json").exists()
    assert (topic_dir / "briefing.txt").exists()
    assert isinstance(suggestions, list)


def test_load_archive_round_trips_saved_documents(tmp_path, monkeypatch):
    _patch_topics_dir(tmp_path, monkeypatch)
    raw_results = [
        {"title": "Some Policy", "description": "Detail text here.", "link": "/x", "public_timestamp": "2026-01-01T00:00:00Z"},
    ]
    topic_dir, docs, _ = archive.build_and_save_archive(
        "test topic", raw_results, attachment_fetcher=lambda path: []
    )
    reloaded = archive.load_archive(topic_dir)
    assert reloaded == docs


def test_briefing_only_includes_documents_with_substantial_description(tmp_path, monkeypatch):
    _patch_topics_dir(tmp_path, monkeypatch)
    raw_results = [
        {"title": "Has Detail", "description": "This description is long enough to include.", "link": "/a", "public_timestamp": "2026-01-01"},
        {"title": "Too Short", "description": "short", "link": "/b", "public_timestamp": "2026-01-01"},
    ]
    topic_dir, _, _ = archive.build_and_save_archive("t", raw_results, attachment_fetcher=lambda p: [])
    briefing = archive.load_briefing_text(topic_dir)
    assert "Has Detail" in briefing
    assert "Too Short" not in briefing
