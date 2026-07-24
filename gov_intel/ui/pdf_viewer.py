"""A reusable, embeddable PDF viewer widget with highlighting, annotations, and advanced search."""

from __future__ import annotations

import fnmatch
import io
import re
import tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog, ttk
from typing import Callable

import fitz  # PyMuPDF
from PIL import Image, ImageTk

KeywordRulesCallback = Callable[[], dict]

_COLOR_BY_LABEL = {
    "Red 🟥": (1, 0.2, 0.2),
    "Green 🟩": (0.2, 0.9, 0.2),
    "Blue 🟦": (0.3, 0.6, 1),
}
_DEFAULT_COLOR = (1, 1, 0)  # Yellow


class PDFViewerWidget(ttk.Frame):
    """Scrollable, zoomable PDF renderer with interactive canvas overlay, search highlighting, and TOC."""

    def __init__(self, parent: tk.Widget, get_kw_rules_cb: KeywordRulesCallback):
        super().__init__(parent)
        self.get_kw_rules_cb = get_kw_rules_cb
        self.doc_obj: fitz.Document | None = None
        self.pdf_path = ""
        self.zoom = 1.3
        self.highlight_color = _DEFAULT_COLOR
        self.pen_active = tk.BooleanVar(value=False)
        self.images: list[ImageTk.PhotoImage] = []
        self.page_offsets: list[dict] = []
        self.selected_text = ""
        self.selected_page_num = 0
        self.search_matches: list[dict] = []
        self.current_match_idx = -1
        self.drag_start: tuple[float, float] | None = None
        self.auto_highlights_index: list[dict] = []

        # Search Modifiers
        self.use_regex = tk.BooleanVar(value=False)
        self.match_case = tk.BooleanVar(value=False)

        self._build_toolbar_row1()
        self._build_toolbar_row2()
        self._build_canvas_area()
        self._bind_keyboard_shortcuts()

    def _build_toolbar_row1(self) -> None:
        tb1 = ttk.Frame(self, padding=4)
        tb1.pack(fill="x", side="top")
        ttk.Checkbutton(tb1, text="🖍️ Pen", variable=self.pen_active).pack(side="left", padx=4)

        self.color_cb = ttk.Combobox(
            tb1,
            values=list(_COLOR_BY_LABEL.keys()) + ["Yellow 🟨"],
            state="readonly",
            width=10,
        )
        self.color_cb.pack(side="left", padx=2)
        self.color_cb.set("Yellow 🟨")
        self.color_cb.bind("<<ComboboxSelected>>", self._change_color)

        ttk.Button(tb1, text="💾 Save", command=self.save_pdf).pack(side="left", padx=4)
        ttk.Button(tb1, text="✨ Auto Highlight", command=self.auto_highlight).pack(side="left", padx=4)
        ttk.Button(tb1, text="📤 Export Notes", command=self.export_annotations_report).pack(side="left", padx=4)

        z_frame = ttk.Frame(tb1)
        z_frame.pack(side="right", padx=4)
        ttk.Button(z_frame, text="🔍 +", width=3, command=lambda: self._set_zoom(0.2)).pack(side="left")
        ttk.Button(z_frame, text="🔍 -", width=3, command=lambda: self._set_zoom(-0.2)).pack(side="left")
        self.z_lbl = ttk.Label(z_frame, text="130%", font=("Segoe UI", 9, "bold"))
        self.z_lbl.pack(side="left", padx=4)

    def _build_toolbar_row2(self) -> None:
        tb2 = ttk.Frame(self, padding=4)
        tb2.pack(fill="x", side="top")
        ttk.Label(tb2, text="Find in PDF:").pack(side="left", padx=(4, 2))
        self.e_find = ttk.Entry(tb2, width=16)
        self.e_find.pack(side="left", padx=2)
        self.e_find.bind("<Return>", lambda e: self.perform_in_doc_search(forward=True))

        ttk.Checkbutton(tb2, text="Regex", variable=self.use_regex).pack(side="left", padx=2)
        ttk.Checkbutton(tb2, text="Aa", variable=self.match_case).pack(side="left", padx=2)

        ttk.Button(tb2, text="Search", command=lambda: self.perform_in_doc_search(True)).pack(side="left", padx=2)
        ttk.Button(tb2, text="◀", width=2, command=lambda: self.navigate_search_match(-1)).pack(side="left")
        ttk.Button(tb2, text="▶", width=2, command=lambda: self.navigate_search_match(1)).pack(side="left")
        self.lbl_search_count = ttk.Label(tb2, text="")
        self.lbl_search_count.pack(side="left", padx=6)

        ttk.Button(tb2, text="📌 Copy w/ Ref", command=self.copy_selected_text_with_ref).pack(side="right", padx=2)
        ttk.Button(tb2, text="📋 Copy", command=self.copy_selected_text_to_clipboard).pack(side="right", padx=2)
        self.lbl_selection_status = ttk.Label(tb2, text="", font=("Segoe UI", 8, "italic"))
        self.lbl_selection_status.pack(side="right", padx=6)

    def _build_canvas_area(self) -> None:
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)

        # 3-Tab Sidebar: Pages, Outline, Highlights
        self.sidebar_nb = ttk.Notebook(body, width=190)
        self.sidebar_nb.pack(side="left", fill="y")

        # Tab 1: Pages
        f_pages = ttk.Frame(self.sidebar_nb)
        self.sidebar_nb.add(f_pages, text="Pages")
        self.lb_page_index = tk.Listbox(f_pages, bg="#ffffff", exportselection=False)
        self.lb_page_index.pack(fill="both", expand=True)
        self.lb_page_index.bind("<<ListboxSelect>>", self._on_sidebar_page_select)

        # Tab 2: Outlines / TOC
        f_toc = ttk.Frame(self.sidebar_nb)
        self.sidebar_nb.add(f_toc, text="Outline")
        self.toc_tree = ttk.Treeview(f_toc, show="tree", selectmode="browse")
        self.toc_tree.pack(fill="both", expand=True)
        self.toc_tree.bind("<<TreeviewSelect>>", self._on_toc_select)

        # Tab 3: Highlights Navigation
        f_hl = ttk.Frame(self.sidebar_nb)
        self.sidebar_nb.add(f_hl, text="Highlights")
        self.lb_highlights = tk.Listbox(f_hl, bg="#fef08a", exportselection=False, font=("Segoe UI", 9))
        self.lb_highlights.pack(fill="both", expand=True)
        self.lb_highlights.bind("<<ListboxSelect>>", self._on_highlight_item_select)

        canvas_frame = ttk.Frame(body)
        canvas_frame.pack(side="left", fill="both", expand=True)

        self.canvas = tk.Canvas(canvas_frame, bg="#525659")
        sb_y = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        sb_x = ttk.Scrollbar(canvas_frame, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)

        sb_x.pack(side="bottom", fill="x")
        sb_y.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Control-MouseWheel>", self._on_ctrl_mousewheel)
        self.canvas.bind("<Button-4>", self._on_mousewheel)
        self.canvas.bind("<Button-5>", self._on_mousewheel)
        self.canvas.bind("<ButtonPress-1>", self._on_drag_start)
        self.canvas.bind("<B1-Motion>", self._on_drag_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_drag_end)
        self.canvas.bind("<Button-3>", self._on_right_click)

    def _bind_keyboard_shortcuts(self) -> None:
        self.bind_all("<Control-f>", lambda e: self.e_find.focus_set())

    def _on_mousewheel(self, event: tk.Event) -> None:
        if event.delta:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        elif event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")

    def _on_ctrl_mousewheel(self, event: tk.Event) -> None:
        if event.delta > 0:
            self._set_zoom(0.1)
        elif event.delta < 0:
            self._set_zoom(-0.1)

    def load_pdf(self, path: str) -> None:
        self.pdf_path = path
        self.doc_obj = fitz.open(path)
        self.search_matches = []
        self.current_match_idx = -1
        self.auto_highlights_index = []
        self.lb_highlights.delete(0, tk.END)

        self.lb_page_index.delete(0, tk.END)
        for i in range(len(self.doc_obj)):
            self.lb_page_index.insert(tk.END, f"Page {i + 1}")

        for item in self.toc_tree.get_children():
            self.toc_tree.delete(item)
        toc = self.doc_obj.get_toc()
        for _lvl, title, page_no in toc:
            self.toc_tree.insert("", "end", iid=f"page_{page_no}", text=f"{title} (p.{page_no})")

        self.render()

    def render(self) -> None:
        if not self.doc_obj:
            return

        self.canvas.delete("all")
        self.images.clear()
        self.page_offsets.clear()

        mat = fitz.Matrix(self.zoom, self.zoom)
        y_offset, max_width = 15, 100

        for page_num in range(len(self.doc_obj)):
            page = self.doc_obj[page_num]
            pix = page.get_pixmap(matrix=mat)
            img = ImageTk.PhotoImage(Image.open(io.BytesIO(pix.tobytes("ppm"))))
            self.images.append(img)

            self.canvas.create_image(15, y_offset, anchor="nw", image=img, tags=("pdf_page", f"p_{page_num}"))
            p_w, p_h = pix.width, pix.height
            max_width = max(max_width, p_w)
            self.page_offsets.append({
                "page_num": page_num,
                "y_start": y_offset,
                "y_end": y_offset + p_h,
                "width": p_w,
                "height": p_h,
            })
            y_offset += p_h + 15

        self.canvas.configure(scrollregion=(0, 0, max_width + 30, y_offset + 30))

    def _on_sidebar_page_select(self, _event: tk.Event) -> None:
        sel = self.lb_page_index.curselection()
        if sel and self.page_offsets:
            self.scroll_to_page(sel[0])

    def _on_toc_select(self, _event: tk.Event) -> None:
        sel = self.toc_tree.selection()
        if sel:
            p_str = sel[0].replace("page_", "")
            if p_str.isdigit():
                self.scroll_to_page(int(p_str) - 1)

    def _on_highlight_item_select(self, _event: tk.Event) -> None:
        sel = self.lb_highlights.curselection()
        if sel and self.auto_highlights_index:
            idx = sel[0]
            item = self.auto_highlights_index[idx]
            self.scroll_to_page(item["page_num"], item["y_offset"] * self.zoom)

    def scroll_to_page(self, page_num: int, y_offset_within_page: float = 0) -> None:
        if not (0 <= page_num < len(self.page_offsets)):
            return
        y_pos = self.page_offsets[page_num]["y_start"] + y_offset_within_page
        total_h = float(self.canvas.cget("scrollregion").split()[3])
        if total_h > 0:
            self.canvas.yview_moveto(y_pos / total_h)

    def perform_in_doc_search(self, forward: bool = True) -> None:
        term = self.e_find.get().strip()
        if not term or not self.doc_obj:
            return
        self.search_matches = []
        flags = 0 if self.match_case.get() else fitz.TEXT_DECASE

        for p_num in range(len(self.doc_obj)):
            page = self.doc_obj[p_num]
            if self.use_regex.get():
                try:
                    p_text = page.get_text("text")
                    for m in re.finditer(term, p_text, flags=0 if self.match_case.get() else re.IGNORECASE):
                        for rect in page.search_for(m.group(0)):
                            self.search_matches.append({"page_num": p_num, "rect": rect})
                except re.error:
                    self.lbl_search_count.config(text="Invalid Regex")
                    return
            else:
                for rect in page.search_for(term, flags=flags):
                    self.search_matches.append({"page_num": p_num, "rect": rect})

        if self.search_matches:
            self.current_match_idx = 0
            self.lbl_search_count.config(text=f"Match 1 of {len(self.search_matches)}")
            self._jump_to_current_search_match()
        else:
            self.lbl_search_count.config(text="No matches found")

    def navigate_search_match(self, delta: int) -> None:
        if not self.search_matches:
            return
        self.current_match_idx = (self.current_match_idx + delta) % len(self.search_matches)
        self.lbl_search_count.config(text=f"Match {self.current_match_idx + 1} of {len(self.search_matches)}")
        self._jump_to_current_search_match()

    def _jump_to_current_search_match(self) -> None:
        m = self.search_matches[self.current_match_idx]
        p_num = m["page_num"]
        rect = m["rect"]

        self.scroll_to_page(p_num, rect.y0 * self.zoom)

        self.canvas.delete("search_match_box")
        p_info = self.page_offsets[p_num]
        box_x0 = 15 + (rect.x0 * self.zoom)
        box_y0 = p_info["y_start"] + (rect.y0 * self.zoom)
        box_x1 = 15 + (rect.x1 * self.zoom)
        box_y1 = p_info["y_start"] + (rect.y1 * self.zoom)

        self.canvas.create_rectangle(
            box_x0, box_y0, box_x1, box_y1,
            outline="#f59e0b", width=3, fill="#fef08a", tags="search_match_box"
        )

    def _on_drag_start(self, event: tk.Event) -> None:
        self.canvas.delete("selection_box")
        self.drag_start = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))

    def _on_drag_motion(self, event: tk.Event) -> None:
        if not self.drag_start or self.pen_active.get():
            return
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        sx, sy = self.drag_start
        self.canvas.delete("selection_box")
        self.canvas.create_rectangle(sx, sy, cx, cy, outline="#3b82f6", width=1, dash=(3, 3), tags="selection_box")

    def _on_drag_end(self, event: tk.Event) -> None:
        self.canvas.delete("selection_box")
        if self.drag_start is None or not self.doc_obj:
            return
        canvas_ex, canvas_ey = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        sx, sy = self.drag_start

        for p_info in self.page_offsets:
            if not (p_info["y_start"] <= sy <= p_info["y_end"]):
                continue
            page_num = p_info["page_num"]

            x0 = (min(sx, canvas_ex) - 15) / self.zoom
            y0 = (min(sy, canvas_ey) - p_info["y_start"]) / self.zoom
            x1 = (max(sx, canvas_ex) - 15) / self.zoom
            y1 = (max(sy, canvas_ey) - p_info["y_start"]) / self.zoom

            rect = fitz.Rect(x0, y0, x1, y1)
            page = self.doc_obj[page_num]

            if self.pen_active.get():
                quads = page.search_for(page.get_text("text", clip=rect), quads=True)
                for q in quads:
                    annot = page.add_highlight_annot(q)
                    annot.set_colors(stroke=self.highlight_color)
                    annot.update()
                if quads:
                    self.render()
            else:
                extracted = page.get_text("text", clip=rect).strip()
                if extracted:
                    self.selected_text = extracted
                    self.selected_page_num = page_num + 1
                    self.lbl_selection_status.config(text=f"Selected {len(extracted)} chars (p. {self.selected_page_num})")
            break

    def copy_selected_text_to_clipboard(self) -> None:
        if self.selected_text:
            self.clipboard_clear()
            self.clipboard_append(self.selected_text)
            self.lbl_selection_status.config(text="Copied to clipboard!")
        else:
            messagebox.showwarning("No Text Selected", "Click and drag over text on any page first.")

    def copy_selected_text_with_ref(self) -> None:
        if self.selected_text:
            ref_str = f'"{self.selected_text}"\n\n— Source: {self.pdf_path.rsplit("/", 1)[-1]}, Page {self.selected_page_num}'
            self.clipboard_clear()
            self.clipboard_append(ref_str)
            self.lbl_selection_status.config(text="Copied citation!")

    def _on_right_click(self, event: tk.Event) -> None:
        if not self.doc_obj:
            return
        cx, cy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        for p_info in self.page_offsets:
            if not (p_info["y_start"] <= cy <= p_info["y_end"]):
                continue
            note = simpledialog.askstring("Add Sticky Note", f"Enter note for Page {p_info['page_num'] + 1}:")
            if note:
                point = fitz.Point((cx - 15) / self.zoom, (cy - p_info["y_start"]) / self.zoom)
                annot = self.doc_obj[p_info["page_num"]].add_text_annot(point, note)
                annot.update()
                self.render()
            break

    def export_annotations_report(self) -> None:
        if not self.doc_obj:
            return
        report = [f"📋 ANNOTATION REPORT: {self.pdf_path.rsplit('/', 1)[-1]}\n{'=' * 50}"]
        for p_num in range(len(self.doc_obj)):
            annots = self.doc_obj[p_num].annots()
            if not annots:
                continue
            report.append(f"\n📌 PAGE {p_num + 1}:")
            for a in annots:
                report.append(f"  ↳ [{a.type[1].upper()}] {a.info.get('content', '').strip() or 'Highlight'}")
        pop = tk.Toplevel(self)
        pop.title("📤 Annotations Export")
        pop.geometry("600x450")
        txt = scrolledtext.ScrolledText(pop, wrap="word")
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        txt.insert(tk.END, "\n".join(report))

    def _set_zoom(self, delta: float) -> None:
        self.zoom = round(max(0.5, min(3.0, self.zoom + delta)), 1)
        self.z_lbl.config(text=f"{int(self.zoom * 100)}%")
        self.render()

    def _change_color(self, _event: tk.Event) -> None:
        self.highlight_color = _COLOR_BY_LABEL.get(self.color_cb.get(), _DEFAULT_COLOR)

    def auto_highlight(self) -> None:
        if not self.doc_obj:
            return
        rules = self.get_kw_rules_cb()
        count = 0
        self.auto_highlights_index = []
        self.lb_highlights.delete(0, tk.END)

        for p_num in range(len(self.doc_obj)):
            page = self.doc_obj[p_num]
            sentences = re.split(r"(?<!\w\.\w.)(?<=\.|\?)\s", page.get_text("text"))
            for s in sentences:
                clean_s = s.strip().replace("\n", " ")
                if len(clean_s) < 15:
                    continue
                lower_s = clean_s.lower()

                for cat, data in rules.items():
                    active_terms = [t for t, enabled in data.get("terms", {}).items() if enabled]
                    if not active_terms:
                        continue

                    # Check for wildcard patterns or direct substrings
                    matched_term = None
                    for t in active_terms:
                        if "*" in t or "?" in t:
                            words = lower_s.split()
                            if any(fnmatch.fnmatch(w, t) for w in words):
                                matched_term = t
                                break
                        elif t in lower_s:
                            matched_term = t
                            break

                    if not matched_term:
                        continue

                    rects = page.search_for(s.strip())
                    for inst in rects:
                        annot = page.add_highlight_annot(inst)
                        annot.set_colors(stroke=tuple(data["color"]))
                        annot.update()
                        count += 1

                    if rects:
                        snippet_label = f"P.{p_num + 1} [{cat[:10]}] {clean_s[:30]}..."
                        self.lb_highlights.insert(tk.END, snippet_label)
                        self.auto_highlights_index.append({
                            "page_num": p_num,
                            "y_offset": rects[0].y0,
                            "text": clean_s,
                        })

        if count > 0:
            self.render()
            self.sidebar_nb.select(2)  # Switch sidebar tab to "Highlights"
        messagebox.showinfo("Auto Highlight", f"Applied {count} highlights across the PDF!")

    def save_pdf(self) -> None:
        if not (self.doc_obj and self.pdf_path):
            return
        try:
            self.doc_obj.save(self.pdf_path, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
            messagebox.showinfo("Saved", "Highlights saved directly!")
        except (RuntimeError, OSError, ValueError) as exc:
            fallback_path = f"{self.pdf_path}_modified.pdf"
            self.doc_obj.save(fallback_path)
            messagebox.showwarning(
                "Saved to a New File",
                f"Could not save in place ({exc}). Saved a copy instead:\n{fallback_path}",
            )