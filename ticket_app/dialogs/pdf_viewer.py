# ticket_app/dialogs/pdf_viewer.py
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import fitz


class PDFViewer:
    def __init__(self, parent, on_page_changed=None):
        self.parent = parent
        self.current_page = 0
        self.total_pages = 0
        self.zoom_level = 1.0
        self.doc = None
        self.photo_images = []
        self.on_page_changed = on_page_changed
        self._build_ui()

    def _build_ui(self):
        toolbar = ttk.Frame(self.parent)
        toolbar.pack(fill='x', pady=2)

        ttk.Label(toolbar, text="Страница:").pack(side='left', padx=5)
        self.page_label = ttk.Label(toolbar, text="0 / 0")
        self.page_label.pack(side='left', padx=5)

        ttk.Button(toolbar, text="◀", width=3, command=self.prev_page).pack(side='left', padx=2)
        ttk.Button(toolbar, text="▶", width=3, command=self.next_page).pack(side='left', padx=2)
        ttk.Separator(toolbar, orient='vertical').pack(side='left', fill='y', padx=10)
        ttk.Button(toolbar, text="🔍+", width=3, command=self.zoom_in).pack(side='left', padx=2)
        ttk.Button(toolbar, text="🔍-", width=3, command=self.zoom_out).pack(side='left', padx=2)
        self.zoom_label = ttk.Label(toolbar, text="100%")
        self.zoom_label.pack(side='left', padx=5)
        ttk.Button(toolbar, text="↺", width=3, command=self.fit_width).pack(side='left', padx=2)

        frame = tk.Frame(self.parent)
        frame.pack(fill='both', expand=True)

        self.canvas = tk.Canvas(frame, bg='#333', highlightthickness=0)
        v_scroll = tk.Scrollbar(frame, orient='vertical', command=self.canvas.yview)
        h_scroll = tk.Scrollbar(frame, orient='horizontal', command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        v_scroll.pack(side='right', fill='y')
        h_scroll.pack(side='bottom', fill='x')
        self.canvas.pack(fill='both', expand=True)

        self.canvas.bind('<MouseWheel>', lambda e: self.canvas.yview_scroll(
            int(-1 * (e.delta / 120)), "units"))
        self.canvas.bind('<Shift-MouseWheel>', lambda e: self.canvas.xview_scroll(
            int(-1 * (e.delta / 120)), "units"))
        self.canvas.bind('<ButtonPress-1>', lambda e: self.canvas.scan_mark(e.x, e.y))
        self.canvas.bind('<B1-Motion>', lambda e: self.canvas.scan_dragto(e.x, e.y, gain=1))

    def load_pdf(self, pdf_path: str) -> bool:
        try:
            self.close()
            self.doc = fitz.open(pdf_path)
            self.total_pages = len(self.doc)
            self.current_page = 0
            self.zoom_level = 1.0
            self._render()
            return True
        except Exception as e:
            print(f"Ошибка загрузки PDF: {e}")
            return False

    def _render(self):
        if not self.doc:
            return
        self.canvas.delete('all')
        self.photo_images.clear()
        page = self.doc[self.current_page]
        mat = fitz.Matrix(2, 2) * self.zoom_level
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        self.photo_image = ImageTk.PhotoImage(img)
        self.photo_images.append(self.photo_image)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo_image)
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))
        self.page_label.config(text=f"{self.current_page + 1} / {self.total_pages}")
        self.zoom_label.config(text=f"{int(self.zoom_level * 100)}%")

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self._render()
            if self.on_page_changed:
                self.on_page_changed()

    def next_page(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self._render()
            if self.on_page_changed:
                self.on_page_changed()

    def go_to_page(self, page_num: int):
        if 0 <= page_num < self.total_pages:
            self.current_page = page_num
            self._render()

    def zoom_in(self):
        self.zoom_level = min(self.zoom_level + 0.25, 4.0)
        self._render()

    def zoom_out(self):
        self.zoom_level = max(self.zoom_level - 0.25, 0.25)
        self._render()

    def fit_width(self):
        self.zoom_level = 1.0
        self._render()

    def close(self):
        if self.doc:
            self.doc.close()
            self.doc = None
        self.photo_images.clear()
