"""Central configuration: filesystem layout and default data.

Nothing in this module has import-time side effects (no directory
creation, no I/O) so it is safe to import from tests or other tools
without touching the filesystem. Call ``ensure_data_dirs()`` explicitly
when you actually need the directories to exist.
"""

from __future__ import annotations

from pathlib import Path

# Base directory for all persisted application data. Can be overridden
# (e.g. in tests) by constructing paths relative to a different root.
DATA_DIR = Path("gov_intelligence")

FAV_TOPICS_FILE = DATA_DIR / "favorite_topics.json"
FAV_SOURCES_FILE = DATA_DIR / "favorite_sources.json"
KEYWORDS_FILE = DATA_DIR / "keywords.json"
HISTORY_FILE = DATA_DIR / "search_history.json"
TAGS_FILE = DATA_DIR / "document_tags.json"
TOPICS_DIR = DATA_DIR / "topics"

MAX_HISTORY_ITEMS = 50
CSV_PREVIEW_ROW_LIMIT = 500

DEFAULT_KEYWORDS = {
    "Mandates & Legal 🟥": {
        "color": [1, 0.2, 0.2],
        "terms": {
            "must": True, "shall": True, "prohibited": True, "illegal": True,
            "enforcement": True, "penalty": True, "mandate": True, "required": True,
        },
    },
    "Financial & Budget 🟩": {
        "color": [0.2, 0.9, 0.2],
        "terms": {
            "budget": True, "funding": True, "allocation": True, "expenditure": True,
            "grant": True, "investment": True, "cost": True,
        },
    },
    "Deadlines & Timelines 🟦": {
        "color": [0.3, 0.6, 1],
        "terms": {
            "deadline": True, "expires": True, "timeline": True, "target date": True,
            "milestone": True, "effective date": True,
        },
    },
    "Strategic Focus 🟨": {
        "color": [1, 0.9, 0.2],
        "terms": {
            "blueprint": True, "priority": True, "key objective": True, "reform": True,
            "standard": True, "strategy": True, "framework": True,
        },
    },
}

DEPARTMENT_SLUGS = {
    "Department for Transport": "department-for-transport",
    "DSIT (Science & Tech)": "department-for-science-innovation-and-technology",
    "HMRC": "hm-revenue-customs",
    "Cabinet Office": "cabinet-office",
    "Home Office": "home-office",
}

DOC_TYPE_SLUGS = {
    "Guidance & Regulation": "guidance",
    "Policy Papers": "policy_paper",
    "Research & Stats": "official_statistics",
    "News & Press": "news_story",
}


def ensure_data_dirs() -> None:
    """Create the on-disk data directories if they don't already exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TOPICS_DIR.mkdir(parents=True, exist_ok=True)
