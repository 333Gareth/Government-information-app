"""UI-independent application state: favorites, tags, history, keywords."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from . import config
from .models import Document, normalize_keyword_rules
from .storage import load_json, save_json

PRESET_POLICY_TEMPLATES = {
    "🏛️ UK Legislation & Compliance": {
        "Legal & Statutory": {"color": [1, 0.2, 0.2], "terms": {"statutory": True, "act": True, "clause": True, "compliance": True, "regulation*": True}},
        "Enforcement & Risks": {"color": [0.9, 0.4, 0.1], "terms": {"penalty": True, "offence": True, "breach*": True, "liability": True}},
    },
    "💻 Digital Strategy & AI": {
        "Technology & Cyber": {"color": [0.2, 0.6, 1.0], "terms": {"data*": True, "cyber": True, "cloud": True, "api": True, "artificial intelligence": True}},
        "Procurement & Vendors": {"color": [0.8, 0.3, 0.9], "terms": {"supplier": True, "vendor": True, "contract*": True, "tender": True}},
    },
    "💷 Financial Audit & Budget": {
        "Funding & Grants": {"color": [0.2, 0.9, 0.2], "terms": {"budget": True, "grant*": True, "funding": True, "expenditure": True, "allocation": True}},
        "Value for Money": {"color": [0.9, 0.8, 0.1], "terms": {"efficiency": True, "audit": True, "cost*": True, "savings": True}},
    },
    "🌱 Environmental & Sustainability": {
        "Net Zero & Carbon": {"color": [0.1, 0.7, 0.4], "terms": {"net zero": True, "carbon": True, "emission*": True, "sustainability": True}},
        "Impact & Assessment": {"color": [0.7, 0.6, 0.2], "terms": {"environmental impact": True, "biodiversity": True, "waste": True}},
    }
}


@dataclass
class AppState:
    favorite_topics: list[str] = field(default_factory=list)
    favorite_sources: dict[str, dict[str, Any]] = field(default_factory=dict)
    keyword_rules: dict[str, Any] = field(default_factory=dict)
    search_history: list[dict[str, str]] = field(default_factory=list)
    document_tags: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls) -> "AppState":
        return cls(
            favorite_topics=load_json(config.FAV_TOPICS_FILE, []),
            favorite_sources=load_json(config.FAV_SOURCES_FILE, {}),
            keyword_rules=normalize_keyword_rules(
                load_json(config.KEYWORDS_FILE, config.DEFAULT_KEYWORDS)
            ),
            search_history=load_json(config.HISTORY_FILE, []),
            document_tags=load_json(config.TAGS_FILE, {}),
        )

    # -- favorite topics ------------------------------------------------
    def add_favorite_topic(self, topic: str) -> bool:
        topic = topic.strip()
        if not topic or topic in self.favorite_topics:
            return False
        self.favorite_topics.append(topic)
        save_json(config.FAV_TOPICS_FILE, self.favorite_topics)
        return True

    def remove_favorite_topic(self, topic: str) -> bool:
        if topic not in self.favorite_topics:
            return False
        self.favorite_topics.remove(topic)
        save_json(config.FAV_TOPICS_FILE, self.favorite_topics)
        return True

    # -- favorite sources -------------------------------------------------
    def is_favorite(self, doc: Document) -> bool:
        return doc.id in self.favorite_sources

    def toggle_favorite_source(self, doc: Document) -> bool:
        if doc.id in self.favorite_sources:
            del self.favorite_sources[doc.id]
            is_fav = False
        else:
            self.favorite_sources[doc.id] = {
                "title": doc.title, "url": doc.url, "topic": doc.topic, "attachments": doc.attachments,
            }
            is_fav = True
        save_json(config.FAV_SOURCES_FILE, self.favorite_sources)
        return is_fav

    # -- search history ---------------------------------------------------
    def record_search(self, query: str, dept: str, doc_type: str) -> None:
        rec = {
            "query": query,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "dept": dept,
            "type": doc_type,
        }
        self.search_history.insert(0, rec)
        self.search_history = self.search_history[: config.MAX_HISTORY_ITEMS]
        save_json(config.HISTORY_FILE, self.search_history)

    # -- tags ---------------------------------------------------------------
    def set_tag(self, doc: Document, tag: str) -> None:
        self.document_tags[doc.id] = tag
        save_json(config.TAGS_FILE, self.document_tags)

    def get_tag(self, doc: Document) -> str | None:
        return self.document_tags.get(doc.id)

    # -- keyword rules --------------------------------------------------
    def save_keywords(self) -> None:
        save_json(config.KEYWORDS_FILE, self.keyword_rules)

    def add_keyword_category(self, name: str, color: list[float] | None = None) -> bool:
        name = name.strip()
        if not name or name in self.keyword_rules:
            return False
        self.keyword_rules[name] = {"color": color or [1.0, 0.8, 0.0], "terms": {}}
        self.save_keywords()
        return True

    def set_category_color(self, category: str, color: list[float]) -> None:
        if category in self.keyword_rules:
            self.keyword_rules[category]["color"] = color
            self.save_keywords()

    def remove_keyword_category(self, name: str) -> bool:
        if name not in self.keyword_rules:
            return False
        del self.keyword_rules[name]
        self.save_keywords()
        return True

    def add_keyword_term(self, category: str, term: str) -> bool:
        term = term.strip().lower()
        if category not in self.keyword_rules or not term:
            return False
        self.keyword_rules[category]["terms"][term] = True
        self.save_keywords()
        return True

    def remove_keyword_term(self, category: str, term: str) -> bool:
        terms = self.keyword_rules.get(category, {}).get("terms", {})
        if term not in terms:
            return False
        del terms[term]
        self.save_keywords()
        return True

    def toggle_keyword_term(self, category: str, term: str) -> None:
        terms = self.keyword_rules[category]["terms"]
        terms[term] = not terms.get(term, True)
        self.save_keywords()

    def apply_preset_template(self, template_key: str) -> bool:
        if template_key not in PRESET_POLICY_TEMPLATES:
            return False
        tpl = PRESET_POLICY_TEMPLATES[template_key]
        for cat, data in tpl.items():
            if cat not in self.keyword_rules:
                self.keyword_rules[cat] = {"color": data["color"], "terms": {}}
            self.keyword_rules[cat]["color"] = data["color"]
            for term, state in data["terms"].items():
                self.keyword_rules[cat]["terms"][term] = state
        self.save_keywords()
        return True