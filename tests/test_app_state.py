import gov_intel.config as config
from gov_intel.app_state import AppState
from gov_intel.models import Document


def _fresh_state(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "FAV_TOPICS_FILE", tmp_path / "favorite_topics.json")
    monkeypatch.setattr(config, "FAV_SOURCES_FILE", tmp_path / "favorite_sources.json")
    monkeypatch.setattr(config, "KEYWORDS_FILE", tmp_path / "keywords.json")
    monkeypatch.setattr(config, "HISTORY_FILE", tmp_path / "search_history.json")
    monkeypatch.setattr(config, "TAGS_FILE", tmp_path / "document_tags.json")
    return AppState.load()


def _sample_doc(doc_id="abc123"):
    return Document(id=doc_id, title="Example", description="d", url="https://x", date="2026-01-01", topic="t")


def test_load_returns_defaults_when_no_files_exist(tmp_path, monkeypatch):
    state = _fresh_state(tmp_path, monkeypatch)
    assert state.favorite_topics == []
    assert state.favorite_sources == {}
    assert "Mandates & Legal 🟥" in state.keyword_rules


def test_favorite_topic_add_remove_persists(tmp_path, monkeypatch):
    state = _fresh_state(tmp_path, monkeypatch)
    assert state.add_favorite_topic("digital government") is True
    assert state.add_favorite_topic("digital government") is False  # no duplicates
    reloaded = _fresh_state(tmp_path, monkeypatch)
    assert reloaded.favorite_topics == ["digital government"]

    assert state.remove_favorite_topic("digital government") is True
    reloaded = _fresh_state(tmp_path, monkeypatch)
    assert reloaded.favorite_topics == []


def test_toggle_favorite_source_by_stable_id(tmp_path, monkeypatch):
    state = _fresh_state(tmp_path, monkeypatch)
    doc = _sample_doc()
    assert state.is_favorite(doc) is False

    assert state.toggle_favorite_source(doc) is True
    assert state.is_favorite(doc) is True

    reloaded = _fresh_state(tmp_path, monkeypatch)
    assert reloaded.is_favorite(doc) is True

    assert state.toggle_favorite_source(doc) is False
    assert state.is_favorite(doc) is False


def test_record_search_caps_history_length(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MAX_HISTORY_ITEMS", 3)
    state = _fresh_state(tmp_path, monkeypatch)
    for i in range(5):
        state.record_search(f"query {i}", "All Departments", "All Types")
    assert len(state.search_history) == 3
    assert state.search_history[0]["query"] == "query 4"  # most recent first


def test_tags_set_and_get(tmp_path, monkeypatch):
    state = _fresh_state(tmp_path, monkeypatch)
    doc = _sample_doc()
    assert state.get_tag(doc) is None
    state.set_tag(doc, "High Priority")
    assert state.get_tag(doc) == "High Priority"


def test_keyword_category_and_term_lifecycle(tmp_path, monkeypatch):
    state = _fresh_state(tmp_path, monkeypatch)
    assert state.add_keyword_category("Custom") is True
    assert state.add_keyword_category("Custom") is False

    assert state.add_keyword_term("Custom", "example") is True
    assert state.keyword_rules["Custom"]["terms"]["example"] is True

    state.toggle_keyword_term("Custom", "example")
    assert state.keyword_rules["Custom"]["terms"]["example"] is False

    assert state.remove_keyword_term("Custom", "example") is True
    assert "example" not in state.keyword_rules["Custom"]["terms"]

    assert state.remove_keyword_category("Custom") is True
