"""A window that downloads a CSV dataset and displays it in a grid.

The original version called ``messagebox.showerror`` directly from the
background download thread, which is unsafe with Tkinter (all widget
and dialog calls must happen on the main thread). Errors are now
reported via ``self.after(0, ...)`` instead.
"""

from __future__ import annotations

import csv
import io
import logging
import tkinter as tk
from tkinter import messagebox, ttk

import requests

from ..config import CSV_PREVIEW_ROW_LIMIT

logger = logging.getLogger(__name__)


class DataGridViewerWindow(tk.Toplevel):
    def __init__(self, parent: tk.Widget, csv_url: str, title: str = "Dataset Viewer"):
        super().__init__(parent)
        self.title(f"📊 Dataset Grid: {title}")
        self.geometry("900x600")

        ttk.Label(self, text=f"Source URL: {csv_url}", font=("Segoe UI", 9, "italic")).pack(fill="x", padx=10, pady=5)
        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.tree = ttk.Treeview(frame, show="headings")
        sb_y = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        sb_x = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)

        sb_y.pack(side="right", fill="y")
        sb_x.pack(side="bottom", fill="x")
        self.tree.pack(side="left", fill="both", expand=True)

        import threading
        threading.Thread(target=self._load_csv_data, args=(csv_url,), daemon=True).start()

    def _load_csv_data(self, url: str) -> None:
        try:
            res = requests.get(url, timeout=15)
        except requests.RequestException as exc:
            logger.warning("Failed to download CSV %s: %s", url, exc)
            self.after(0, lambda: messagebox.showerror("Error Loading Data", f"Could not download dataset: {exc}"))
            return

        if res.status_code != 200:
            self.after(0, lambda: messagebox.showerror(
                "Error Loading Data", f"Server returned status {res.status_code}."))
            return

        try:
            reader = csv.reader(io.StringIO(res.text))
            header = next(reader, None)
            rows = list(reader)
        except csv.Error as exc:
            logger.warning("Failed to parse CSV %s: %s", url, exc)
            self.after(0, lambda: messagebox.showerror("Error Loading Data", f"Could not parse CSV dataset: {exc}"))
            return

        if header:
            self.after(0, lambda: self._populate_grid(header, rows))

    def _populate_grid(self, headers: list[str], rows: list[list[str]]) -> None:
        self.tree["columns"] = headers
        for h in headers:
            self.tree.heading(h, text=h)
            self.tree.column(h, width=120, anchor="w")
        for row in rows[:CSV_PREVIEW_ROW_LIMIT]:
            self.tree.insert("", "end", values=row)
        if len(rows) > CSV_PREVIEW_ROW_LIMIT:
            ttk.Label(
                self, text=f"Showing first {CSV_PREVIEW_ROW_LIMIT} of {len(rows)} rows.", foreground="#a00"
            ).pack(fill="x", padx=10, pady=(0, 5))
