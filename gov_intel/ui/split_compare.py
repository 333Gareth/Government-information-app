"""Side-by-side PDF comparator window."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, ttk
from typing import Callable

from .pdf_viewer import PDFViewerWidget


class SplitPDFComparatorWindow(tk.Toplevel):
    def __init__(self, parent: tk.Widget, get_kw_rules_cb: Callable[[], dict]):
        super().__init__(parent)
        self.title("⚔️ Split-Screen Policy PDF Comparator")
        self.geometry("1300x800")
        self.get_kw_rules_cb = get_kw_rules_cb

        paned = ttk.Panedwindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=5, pady=5)

        left_f = ttk.LabelFrame(paned, text=" Left Document (Primary) ", padding=4)
        paned.add(left_f, weight=1)
        self.left_viewer = PDFViewerWidget(left_f, get_kw_rules_cb)
        self.left_viewer.pack(fill="both", expand=True)

        right_f = ttk.LabelFrame(paned, text=" Right Document (Comparison) ", padding=4)
        paned.add(right_f, weight=1)
        self.right_viewer = PDFViewerWidget(right_f, get_kw_rules_cb)
        self.right_viewer.pack(fill="both", expand=True)

        top_bar = ttk.Frame(self, padding=4)
        top_bar.pack(fill="x", side="top")
        ttk.Button(top_bar, text="📁 Load Left PDF", command=lambda: self._browse_and_load(self.left_viewer)).pack(side="left", padx=5)
        ttk.Button(top_bar, text="📁 Load Right PDF", command=lambda: self._browse_and_load(self.right_viewer)).pack(side="right", padx=5)

    def _browse_and_load(self, viewer: PDFViewerWidget) -> None:
        p = filedialog.askopenfilename(filetypes=[("PDF Documents", "*.pdf")])
        if p:
            viewer.load_pdf(p)
