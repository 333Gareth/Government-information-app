# GOV.UK Policy Intelligence Workstation

A desktop tool (Tkinter) for harvesting GOV.UK publications on a topic, reading
and annotating them (including PDFs), tracking favorites/tags, and running
simple keyword analytics across a batch of documents.

This is a restructured version of the original single-file `fetch_assets.py`.
The functionality is the same; the code is split into testable modules so the
core logic can be verified without launching the GUI.

## Project layout

```
main.py                     entry point (python main.py)
gov_intel/
  config.py                 paths, defaults - no import-time side effects
  storage.py                 atomic JSON load/save
  models.py                  Document dataclass, stable doc IDs, keyword-rule migration
  gov_api.py                 GOV.UK search/content API client (pure functions, mockable)
  archive.py                 turns search results into a saved topic archive (JSON)
  app_state.py                favorites / tags / history / keyword rules (no Tkinter)
  ui/
    app.py                   main window: Control Panel, Reader, Favorites, Keyword Brain, Analytics
    pdf_viewer.py             reusable PDF viewer widget (highlight, search, notes)
    data_grid.py              CSV/dataset grid viewer window
    split_compare.py          side-by-side PDF comparator window
tests/                       unit tests for everything except the Tkinter widgets
```

The dependency direction is one-way: `gov_api` / `archive` / `app_state` /
`models` / `storage` know nothing about Tkinter, so they're imported and
tested directly. `ui/` depends on them, not the other way round.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

`python-docx` is only needed for the "Export Word Brief" button; everything
else works without it (the button just shows a friendly warning if it's missing,
same as before).

## Running

```bash
python main.py
```

## Running the tests

```bash
pip install pytest
pytest
```

The test suite covers `storage`, `models`, `gov_api` (with `requests` mocked --
no real network calls), `archive`, and `app_state`. The Tkinter widgets
(`ui/`) aren't unit-tested here since they need a real display, but they're
intentionally thin wrappers around the tested logic above, and every method
that talks to the network or the filesystem now goes through the tested
functions rather than reimplementing that logic inline.

## What changed vs. the original `fetch_assets.py`

**Correctness / thread-safety**
- Background threads no longer touch Tkinter widgets or `messagebox` directly
  (`self.log()` and the CSV/PDF download workers now marshal all UI updates
  through `root.after(...)`). The original called `self.log_box.insert(...)`
  and `messagebox.showerror(...)` straight from worker threads, which is
  undefined behavior in Tkinter and a likely source of intermittent crashes.
- Downloading a PDF attachment now happens on a background thread instead of
  blocking the UI on `requests.get()`.
- Fixed literal backtick characters that were showing up in the notebook tab
  titles (`` `🛰️ Control Panel` `` → `🛰️ Control Panel`).
- Filenames derived from remote URLs are sanitized before being used as local
  paths (`sanitize_filename`), instead of a raw `url.split("/")[-1]`.
- File extension checks (`classify_attachment_url`) now ignore query strings,
  so `report.pdf?download=true` is correctly classified as a PDF.

**Data model**
- Documents are stored as structured JSON (`documents.json` per topic)
  instead of hand-formatted `.txt` files that were re-parsed with
  `startswith("TITLE:")` / `startswith("URL:")` string matching throughout
  the UI. A title or description containing a newline could silently break
  the old format.
- Favorites/tags are now keyed by a stable id derived from the document URL
  (`make_doc_id`), rather than by a filesystem path that had to be
  reconstructed with `"gov_intelligence" in path` heuristics in four separate
  places in the original code.
- `save_json` writes atomically (temp file + `os.replace`), so a crash
  mid-write can't corrupt `favorites.json`, `keywords.json`, etc.

**Robustness**
- No more bare `except Exception: pass`. Failures are logged
  (`logging.getLogger(__name__)`) even where the UI still degrades
  gracefully, so problems are visible instead of silently swallowed.
- Removed the unused `pyttsx3` and `zipfile` imports (dead code -- neither
  was actually referenced anywhere in the original file).

**Structure / style**
- Split one 1075-line file into focused modules (see layout above).
- One import per line; added type hints and docstrings throughout.
- `config.py` no longer creates directories as an import-time side effect
  (call `ensure_data_dirs()` explicitly, which `main.py` / `GovApp` do).

## Known limitations carried over from the original design

- `PyMuPDF` (`fitz`) is AGPL-licensed -- fine for personal/internal use, but
  worth checking your organization's policy if this is ever distributed.
- The keyword "auto-highlight" sentence splitter is a simple regex, not a
  real sentence tokenizer, so it will occasionally mis-split on abbreviations
  or decimals. Same behavior as the original.
