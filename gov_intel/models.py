"""Typed data models.

The original app represented documents/favorites as loose dicts parsed
back out of hand-formatted text files (``TITLE: ...``, ``URL: ...``
lines). That's fragile: a title containing a newline, or text that
happens to start with "URL:", silently corrupts parsing.

Here, a ``Document`` is a plain dataclass, serialized to/from JSON, and
identified by a stable id derived from its URL -- so favorites/tags can
reference a document by id instead of by a brittle, environment-specific
filesystem path.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any


def make_doc_id(url: str) -> str:
    """Return a short, stable identifier derived from a document URL."""
    return hashlib.sha1(url.strip().encode("utf-8")).hexdigest()[:16]


@dataclass
class Document:
    """A single harvested GOV.UK publication."""

    id: str
    title: str
    description: str
    url: str
    date: str
    topic: str
    attachments: list[str] = field(default_factory=list)

    @classmethod
    def from_api_result(cls, raw: dict[str, Any], topic: str, attachments: list[str]) -> "Document":
        """Build a Document from a raw GOV.UK search-API result dict."""
        link = raw.get("link", "")
        url = f"https://www.gov.uk{link}" if link and not link.startswith("http") else link
        return cls(
            id=make_doc_id(url),
            title=raw.get("title", "Official Publication"),
            description=raw.get("description", ""),
            url=url,
            date=(raw.get("public_timestamp") or "Recent")[:10],
            topic=topic,
            attachments=attachments,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Document":
        return cls(
            id=data["id"],
            title=data.get("title", ""),
            description=data.get("description", ""),
            url=data.get("url", ""),
            date=data.get("date", ""),
            topic=data.get("topic", ""),
            attachments=list(data.get("attachments", [])),
        )


def normalize_keyword_rules(raw: dict) -> dict:
    """Normalizes raw dictionary input into a consistent keyword rule structure."""
    normalized = {}
    for cat, data in raw.items():
        if isinstance(data, dict):
            color = data.get("color", [1.0, 0.8, 0.0])
            terms = data.get("terms", {})
            if isinstance(terms, list):
                terms = {t: True for t in terms}
            normalized[cat] = {"color": color, "terms": terms}
        elif isinstance(data, list):
            normalized[cat] = {"color": [1.0, 0.8, 0.0], "terms": {t: True for t in data}}
    return normalized
