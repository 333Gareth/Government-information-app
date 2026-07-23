"""Client functions for the public GOV.UK search and content APIs.

This module has no Tkinter dependency and does no file I/O beyond what
callers explicitly ask for, so it can be exercised directly in unit
tests with ``requests`` mocked out -- no GUI needed.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Callable, Iterable
from urllib.parse import urlsplit

import requests

from .config import DEPARTMENT_SLUGS, DOC_TYPE_SLUGS

logger = logging.getLogger(__name__)

SEARCH_API_URL = "https://www.gov.uk/api/search.json"
CONTENT_API_BASE = "https://www.gov.uk/api/content/"
SITE_BASE = "https://www.gov.uk"

# Fragments that identify non-document assets we don't want in the
# attachments list (stylesheets, scripts, static site chrome, etc).
IGNORED_URL_FRAGMENTS = (".css", ".js", ".ico", "w3.org", "assets.publishing.service.gov.uk/static")

_PDF_EXTS = (".pdf",)
_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")
_DATA_EXTS = (".csv", ".xlsx", ".ods", ".tsv")
_DOC_EXTS = (".doc", ".docx", ".odt", ".rtf")

LogCallback = Callable[[str], None]


def _silent_log(_msg: str) -> None:
    return None


def clean_folder_name(name: str) -> str:
    """Turn an arbitrary topic string into a filesystem-safe folder name."""
    cleaned = re.sub(r'[\\/*?:"<>|]', "", name).strip().replace(" ", "_").lower()
    return cleaned or "untitled_topic"


def sanitize_filename(name: str) -> str:
    """Strip characters that are unsafe/ambiguous in filenames.

    Used for filenames derived from remote URLs, which are not
    trustworthy input (query strings, path separators, etc. can end up
    embedded in the "filename" portion of a URL).
    """
    name = urlsplit(name).path.rsplit("/", 1)[-1] if "://" in name else name
    name = re.sub(r'[\\/*?:"<>|]', "", name).strip()
    return name or "download"


def _extension_matches(url: str, extensions: Iterable[str]) -> bool:
    """Check the URL's path (ignoring query string/fragment) against extensions."""
    path = urlsplit(url).path.lower()
    return any(path.endswith(ext) for ext in extensions)


def classify_attachment_url(url: str) -> str:
    """Return a labelled emoji tag describing the kind of asset a URL points to."""
    if _extension_matches(url, _PDF_EXTS):
        return "📕 PDF"
    if _extension_matches(url, _IMAGE_EXTS):
        return "🖼️ Image"
    if _extension_matches(url, _DATA_EXTS):
        return "📊 Data"
    if _extension_matches(url, _DOC_EXTS):
        return "📄 Doc"
    return "🌐 Link"


def deep_harvest_gov_uk(
    query: str,
    target_total: int,
    sort_order: str,
    dept_filter: str,
    doc_type_filter: str,
    exact_match: bool,
    log_cb: LogCallback | None = None,
    session: requests.Session | None = None,
) -> list[dict]:
    """Page through the GOV.UK search API until ``target_total`` results are collected.

    ``session`` can be injected (e.g. a mocked ``requests.Session``) for
    testing; a fresh session is created if not provided.
    """
    log_cb = log_cb or _silent_log
    session = session or requests.Session()

    results: list[dict] = []
    current_start = 0
    q_str = f'"{query}"' if exact_match else query

    while len(results) < target_total:
        params = {
            "q": q_str,
            "count": 50,
            "start": current_start,
            "fields": "title,description,link,content_store_document_type,public_timestamp,organisations",
        }
        if sort_order == "Most Recent":
            params["order"] = "-public_timestamp"
        if dept_filter in DEPARTMENT_SLUGS:
            params["filter_organisations"] = DEPARTMENT_SLUGS[dept_filter]
        if doc_type_filter in DOC_TYPE_SLUGS:
            params["filter_content_store_document_type"] = DOC_TYPE_SLUGS[doc_type_filter]

        try:
            res = session.get(SEARCH_API_URL, params=params, timeout=15)
        except requests.RequestException as exc:
            logger.warning("Network error querying GOV.UK search API: %s", exc)
            log_cb(f"⚠️ Network error: {exc}")
            break

        if res.status_code != 200:
            logger.warning("GOV.UK search API returned status %s", res.status_code)
            break

        try:
            batch = res.json().get("results", [])
        except ValueError as exc:
            logger.warning("Could not decode GOV.UK search API response: %s", exc)
            break

        if not batch:
            break

        results.extend(batch)
        log_cb(f"📥 Collected {len(results)} sources matching criteria...")
        current_start += 50
        time.sleep(0.1)  # be a polite API citizen

    return results[:target_total]


def fetch_attachments(gov_path: str, session: requests.Session | None = None) -> list[str]:
    """Look up the attachments/parts/related links for a GOV.UK content item."""
    session = session or requests.Session()
    api_url = f"{CONTENT_API_BASE}{gov_path.strip('/')}"
    attachments: list[str] = []

    try:
        res = session.get(api_url, timeout=10)
    except requests.RequestException as exc:
        logger.info("Could not fetch attachments for %s: %s", gov_path, exc)
        return attachments

    if res.status_code != 200:
        return attachments

    try:
        data = res.json()
    except ValueError:
        logger.info("Non-JSON content response for %s", gov_path)
        return attachments

    details = data.get("details", {})
    links = data.get("links", {})
    self_path = f"{SITE_BASE}/{gov_path.strip('/')}"

    def _add(candidate: str) -> None:
        if candidate and candidate not in attachments and candidate != self_path:
            attachments.append(candidate)

    for att in details.get("attachments", []):
        u = att.get("url", "")
        if u:
            _add(u if u.startswith("http") else f"{SITE_BASE}{u}")

    for part in details.get("parts", []):
        slug = part.get("slug", "")
        if slug:
            _add(f"{SITE_BASE}/{gov_path.strip('/')}/{slug}")

    for item_list in links.values():
        if not isinstance(item_list, list):
            continue
        for item in item_list:
            if not isinstance(item, dict):
                continue
            bp = item.get("base_path") or item.get("web_url") or ""
            if bp:
                _add(f"{SITE_BASE}{bp}" if bp.startswith("/") else bp)

    # Some attachments only appear as raw hrefs embedded in body HTML,
    # which the structured fields above don't cover. This is a best-effort
    # scrape and deliberately conservative about what it accepts.
    for u in re.findall(r'href=["\']([^"\'#\s]+)["\']', str(details)):
        if not (u.startswith("/") or u.startswith("http")):
            continue
        if any(frag in u.lower() for frag in IGNORED_URL_FRAGMENTS):
            continue
        full_u = f"{SITE_BASE}{u}" if u.startswith("/") else u
        _add(full_u)

    return attachments
