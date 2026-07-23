"""Persist a batch of harvested search results as a topic archive.

Documents are stored as a single JSON list (``documents.json``) instead
of one hand-formatted ``.txt`` file per document. This removes the
fragile "parse TITLE:/URL:/ATTACHMENTS: lines back out of a text file"
logic that appeared throughout the original UI code, and makes it
trivial to reload a topic without regex.

A human-readable ``briefing.txt`` is still produced alongside it, since
that's a genuinely useful plain-text artifact for copy/paste and export.
"""

from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path
from typing import Callable

from .config import TOPICS_DIR
from .gov_api import LogCallback, clean_folder_name, fetch_attachments
from .models import Document
from .storage import save_json

logger = logging.getLogger(__name__)

STOP_WORDS = {"and", "the", "for", "with", "from", "guidance", "report", "policy", "national", "government"}


def topic_dir_for(topic: str) -> Path:
    return TOPICS_DIR / clean_folder_name(topic)


def build_and_save_archive(
    topic: str,
    raw_results: list[dict],
    log_cb: LogCallback | None = None,
    attachment_fetcher: Callable[[str], list[str]] = fetch_attachments,
) -> tuple[Path, list[Document], list[str]] | tuple[None, None, list]:
    """Convert raw search results into Documents, save them, and return suggestions.

    Returns ``(topic_dir, documents, keyword_suggestions)``, or
    ``(None, None, [])`` if there were no results.
    """
    log_cb = log_cb or (lambda _msg: None)
    if not raw_results:
        log_cb("❌ No documents found.")
        return None, None, []

    t_dir = topic_dir_for(topic)
    t_dir.mkdir(parents=True, exist_ok=True)

    documents: list[Document] = []
    title_words: list[str] = []

    for raw in raw_results:
        link_path = raw.get("link", "")
        attachments = attachment_fetcher(link_path)
        doc = Document.from_api_result(raw, topic=topic, attachments=attachments)
        documents.append(doc)
        title_words.extend(
            w.strip(".,!?").lower()
            for w in doc.title.split()
            if len(w) > 3 and w.lower() not in STOP_WORDS
        )

    save_json(t_dir / "documents.json", [d.to_dict() for d in documents])
    _write_briefing(t_dir, topic, documents)

    suggestions = [f"{topic} {word}" for word, _count in Counter(title_words).most_common(3)]
    return t_dir, documents, suggestions


def _write_briefing(topic_dir: Path, topic: str, documents: list[Document]) -> None:
    lines = [f"🇬🇧 BRIEFING: {topic.upper()}", f"TOTAL: {len(documents)}", "=" * 50, ""]
    for i, doc in enumerate(documents):
        if len(doc.description) <= 20:
            continue
        lines.append(f"📌 [{i + 1}] {doc.title}")
        lines.append(f"   🔗 Link: {doc.url}")
        lines.append(f"   ↳ {doc.description}")
        lines.append("")
    briefing_path = topic_dir / "briefing.txt"
    try:
        briefing_path.write_text("\n".join(lines), encoding="utf-8")
    except OSError:
        logger.exception("Failed to write briefing file at %s", briefing_path)


def load_archive(topic_dir: Path) -> list[Document]:
    """Reload a previously-saved topic archive."""
    from .storage import load_json

    raw = load_json(topic_dir / "documents.json", [])
    return [Document.from_dict(d) for d in raw]


def load_briefing_text(topic_dir: Path) -> str:
    briefing_path = topic_dir / "briefing.txt"
    if briefing_path.exists():
        try:
            return briefing_path.read_text(encoding="utf-8")
        except OSError:
            logger.exception("Failed to read briefing file at %s", briefing_path)
    return ""
