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


def normalize_keyword_rules(data: dict) -> dict:
    """Upgrade legacy list-based ``terms`` (old format) to the dict format.

    Older keyword-brain files stored terms as a list of strings; the
    current format stores them as ``{term: enabled_bool}`` so individual
    terms can be toggled on/off. This makes loading old files a no-op
    instead of a crash.
    """
    for cat, payload in data.items():
        terms = payload.get("terms")
        if isinstance(terms, list):
            payload["terms"] = {t: True for t in terms}
    return data
