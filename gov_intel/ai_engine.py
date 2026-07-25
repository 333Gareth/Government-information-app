"""100% Free Local AI & NLP Engine using Ollama with Local Python Fallback."""

from __future__ import annotations

import logging
import re
import collections
import requests

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3.2"


def check_ollama_status() -> bool:
    """Checks if Ollama local server is active and reachable."""
    try:
        res = requests.get("http://localhost:11434/api/tags", timeout=1.5)
        return res.status_code == 200
    except requests.RequestException:
        return False


def get_available_ollama_models() -> list[str]:
    """Retrieves list of locally pulled Ollama models."""
    try:
        res = requests.get("http://localhost:11434/api/tags", timeout=2.0)
        if res.status_code == 200:
            data = res.json()
            return [m["name"] for m in data.get("models", [])]
    except requests.RequestException:
        pass
    return []


def _fallback_local_nlp_summary(text: str, top_n: int = 5) -> str:
    """Extractive frequency-based local NLP summarizer (100% offline fallback)."""
    clean_text = text.strip()
    if not clean_text:
        return "No text available to summarize."

    # Extract sentences
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', clean_text) if len(s.strip()) > 20]
    if not sentences:
        return clean_text[:500] + "..."

    # Frequency analysis of words
    words = re.findall(r'\b[a-zA-Z]{4,}\b', clean_text.lower())
    # Exclude common stop words
    stopwords = {
        "this", "that", "with", "from", "have", "were", "which", "their", "about", "other",
        "would", "these", "there", "government", "policy", "report", "public", "shall", "under"
    }
    filtered_words = [w for w in words if w not in stopwords]
    word_freq = collections.Counter(filtered_words)

    # Score sentences by term frequency
    sentence_scores = {}
    for i, sent in enumerate(sentences):
        score = 0
        sent_words = re.findall(r'\b[a-zA-Z]{4,}\b', sent.lower())
        for w in sent_words:
            score += word_freq.get(w, 0)
        # Normalize by length to avoid bias toward long sentences
        sentence_scores[i] = score / (len(sent_words) + 1)

    # Pick top N sentences preserving original narrative flow
    top_indices = sorted(sentence_scores, key=sentence_scores.get, reverse=True)[:top_n]
    top_indices.sort()

    bullet_points = "\n".join([f"• {sentences[idx]}" for idx in top_indices])

    return (
        "📌 EXECUTIVE BRIEFING (Local NLP Fallback)\n"
        "===========================================\n"
        "⚡ Ollama was not detected on localhost:11434. Showing key extractive insights:\n\n"
        f"{bullet_points}\n\n"
        "💡 Tip: Install Ollama (https://ollama.com) and run 'ollama run llama3.2' for full generative LLM summaries."
    )


def generate_document_briefing(text: str, model_name: str = DEFAULT_MODEL) -> str:
    """Generates an executive policy briefing via Ollama LLM, falling back to local NLP."""
    if not text or not text.strip():
        return "Cannot generate briefing: Document contains no text."

    # Cap prompt text length to ~12,000 characters to keep local inference fast
    truncated_text = text[:12000]

    prompt = (
        "You are an expert UK Government policy analyst. Provide a clear, concise Executive Briefing "
        "for the following policy document. Format your response with clear markdown headings:\n\n"
        "## 📑 Executive Summary\n"
        "[2-3 sentence core overview]\n\n"
        "## 🎯 Key Policy Objectives & Directives\n"
        "[3-5 key bullet points]\n\n"
        "## 💷 Financial, Regulatory & Legal Impacts\n"
        "[3-4 key bullet points]\n\n"
        "## ⏳ Target Dates & Implementation Timelines\n"
        "[List any specific dates or deadlines found]\n\n"
        f"DOCUMENT TEXT:\n{truncated_text}"
    )

    if check_ollama_status():
        try:
            payload = {
                "model": model_name,
                "prompt": prompt,
                "stream": False,
            }
            res = requests.post(OLLAMA_URL, json=payload, timeout=60)
            if res.status_code == 200:
                response_json = res.json()
                return response_json.get("response", "No response generated.")
        except requests.RequestException as exc:
            logger.warning("Ollama request failed (%s). Falling back to local NLP.", exc)

    return _fallback_local_nlp_summary(text)