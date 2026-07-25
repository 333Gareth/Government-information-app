"""UI-independent application state: favorites, tags, history, keywords, research profiles."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import os

from . import config
from .models import Document, normalize_keyword_rules
from .storage import load_json, save_json

# Safely reference the directory where KEYWORDS_FILE lives
PROFILES_FILE = os.path.join(os.path.dirname(config.KEYWORDS_FILE), "research_profiles.json")

DEFAULT_PROFILES = {
    "🏛️ UK Legislation & Compliance": {
        "Legal & Statutory": {"color": [1.0, 0.35, 0.35], "terms": {"statutory": True, "act": True, "clause": True, "compliance": True, "regulation*": True}},
        "Enforcement & Risks": {"color": [1.0, 0.6, 0.2], "terms": {"penalty": True, "offence": True, "breach*": True, "liability": True}},
    },
    "💻 Digital Strategy & AI": {
        "Technology & Cyber": {"color": [0.3, 0.65, 1.0], "terms": {"data*": True, "cyber": True, "cloud": True, "api": True, "artificial intelligence": True}},
        "Procurement & Vendors": {"color": [0.75, 0.4, 0.95], "terms": {"supplier": True, "vendor": True, "contract*": True, "tender": True}},
    },
    "💷 Financial Audit & Budget": {
        "Funding & Grants": {"color": [0.3, 0.85, 0.4], "terms": {"budget": True, "grant*": True, "funding": True, "expenditure": True, "allocation": True}},
        "Value for Money": {"color": [1.0, 0.9, 0.2], "terms": {"efficiency": True, "audit": True, "cost*": True, "savings": True}},
    },
    "🌱 Environmental & Sustainability": {
        "Net Zero & Carbon": {"color": [0.2, 0.8, 0.8], "terms": {"net zero": True, "carbon": True, "emission*": True, "sustainability": True}},
        "Impact & Assessment": {"color": [1.0, 0.5, 0.75], "terms": {"environmental impact": True, "biodiversity": True, "waste": True}},
    }
}


@dataclass
class AppState:
    favorite_topics: list[str] = field(default_factory=list)
    favorite_sources: dict[str, dict[str, Any]] = field(default_factory=dict)
    keyword_rules: dict[str, Any] = field(default_factory=dict)
    research_profiles: dict[str, Any] = field(default_factory=dict)
    search_history: list[dict[str, str]] = field(default_factory=list)
    document_tags: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls) -> "AppState":
        loaded_profiles = load_json(PROFILES_FILE, DEFAULT_PROFILES)
        if not isinstance(loaded_profiles, dict):
            loaded_profiles = dict(DEFAULT_PROFILES)
        
        # Instantiate AppState temporarily or parse profiles directly
        instance = cls(
            favorite_topics=load_json(config.FAV_TOPICS_FILE, []),
            favorite_sources=load_json(config.FAV_SOURCES_FILE, {}),
            keyword_rules=normalize_keyword_rules(
                load_json(config.KEYWORDS_FILE, config.DEFAULT_KEYWORDS)
            ),
            research_profiles=loaded_profiles,
            search_history=load_json(config.HISTORY_FILE, []),
            document_tags=load_json(config.TAGS_FILE, {}),
        )
        
        # Populate dynamic external profiles & master overview
        instance.reload_external_profiles()
        return instance

    def reload_external_profiles(self) -> None:
        """Dynamically re-scans the profiles folder, loads individual JSONs, and rebuilds the Master Overview."""
        external_profiles_dir = config.PROFILES_DIR
        scanned_rules_collection = {}
        
        try:
            config.ensure_data_dirs()
            if external_profiles_dir.exists():
                for file_path in external_profiles_dir.glob("*.json"):
                    if "master" in file_path.name.lower():
                        continue
                    data = load_json(file_path, {})
                    if isinstance(data, dict) and "profile_name" in data and "rules" in data:
                        profile_name = data["profile_name"]
                        profile_rules = data["rules"]
                        self.research_profiles[profile_name] = profile_rules
                        
                        if isinstance(profile_rules, dict):
                            for cat_name, cat_data in profile_rules.items():
                                if cat_name not in scanned_rules_collection:
                                    scanned_rules_collection[cat_name] = cat_data
        except Exception:
            pass

        if scanned_rules_collection:
            self.research_profiles["🌐 Master Intelligence Overview"] = scanned_rules_collection

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

    # -- keyword rules & persistence ------------------------------------
    def save_keywords(self) -> None:
        """Saves current category rules and colors permanently to disk."""
        save_json(config.KEYWORDS_FILE, self.keyword_rules)

    def add_keyword_category(self, name: str, color: list[float] | None = None) -> bool:
        name = name.strip()
        if not name or name in self.keyword_rules:
            return False
        self.keyword_rules[name] = {"color": color or [1.0, 0.9, 0.2], "terms": {}}
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

    # -- research profile management ------------------------------------
    def save_current_as_profile(self, profile_name: str) -> bool:
        name = profile_name.strip()
        if not name:
            return False
        self.research_profiles[name] = dict(self.keyword_rules)
        save_json(PROFILES_FILE, self.research_profiles)
        return True

    def delete_profile(self, profile_name: str) -> bool:
        if profile_name in self.research_profiles:
            del self.research_profiles[profile_name]
            save_json(PROFILES_FILE, self.research_profiles)
            return True
        return False

    def apply_preset_template(self, profile_name: str) -> bool:
        if profile_name not in self.research_profiles:
            return False
        profile_data = self.research_profiles[profile_name]
        self.keyword_rules = normalize_keyword_rules(profile_data)
        self.save_keywords()
        return True