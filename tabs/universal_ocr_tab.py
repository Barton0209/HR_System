"""
Universal OCR Tab — UI для универсального OCR.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from typing import List
import threading
import logging

from services import UniversalOCRService, OCRDocumentResult, ProcessingMode

logger = logging.getLogger(__name__)


class UniversalOCRTab(ttk.Frame):
    """Вкладка универсального OCR."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.service: UniversalOCRService = None
        self.results: List[OCRDocumentResult] = []

        self._build_ui()

    def _build_ui(self):
        # Верхняя панель
        top_frame = ttk.Frame(self)
        top_frame.pack(fill='x', padx=10, pady=10)

        # Кнопки выбора
        ttk.Button(
            top_frame,
            text="📁 Выбрать файл",
            command=self._select_file
        ).pack(side='left', padx=5)

        ttk.Button(
            top_frame,
            text="📂 Выбрать папку",
            command=self._select_folder
        ).pack(side='left', padx=5)

        # Режим
        ttk.Label(top_frame, text="Режим:").pack(side='left', padx=(30, 5))
        self.mode_var = tk.StringVar(value="standard")

        modes_frame = ttk.Frame(top_frame)
        modes_frame.pack(side='left')

        ttk.Radiobutton(
            modes_frame,
            text="Быстрый",
            variable=self.mode_var,
            value="fast"
        ).pack(side='left', padx=5)

        ttk.Radiobutton(
            modes_frame,
            text="Стандарт",
            variable=self.mode_var,
            value="standard"
        ).pack(side='left', padx=5)

        ttk.Radiobutton(
            modes_frame,
            text="Точный (VLM)",
            variable=self.mode_var,
            value="accurate"
        ).pack(side='left', padx=5)

        # Кнопка экспорта
        ttk.Button(
            top_frame,
            text="📊 Экспорт Excel",
            command=self._export_excel
        ).pack(side='right', padx=5)

        ttk.Button(
            top_frame,
            text="🗑 Очистить",
            command=self._clear
        ).pack(side='right', padx=5)

        # Область результатов
        result_frame = ttk.LabelFrame(self, text="Результаты", padding=10)
        result_frame.pack(fill='both', expand=True, padx=10, pady=5)

        # Treeview для результатов
        columns = ("file", "pages", "mode", "confidence", "preview")
        self.tree = ttk.Treeview(
            result_frame,
            columns=columns,
            show='headings',
            selectmode='browse'
        )

        self.tree.heading("file", text="Файл")
        self.tree.heading("pages", text="Страниц")
        self.tree.heading("mode", text="Режим")
        self.tree.heading("confidence", text="Уверенность")
        self.tree.heading("preview", text="Превью текста")

        self.tree.column("file", width=200)
        self.tree.column("pages", width=60, anchor='center')
        self.tree.column("mode", width=80, anchor='center')
        self.tree.column("confidence", width=80, anchor='center')
        self.tree.column("preview", width=400)

        # Скроллбары
        vsb = ttk.Scrollbar(result_frame, orient='vertical', command=self.tree.yview)
        hsb = ttk.Scrollbar(result_frame, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        result_frame.grid_rowconfigure(0, weight=1)
        result_frame.grid_columnconfigure(0, weight=1)

        # Привязка выбора
        self.tree.bind('<<TreeviewSelect>>', self._on_select)

        # Текстовое поле для полного текста
        text_frame = ttk.LabelFrame(self, text="Полный текст", padding=5)
        text_frame.pack(fill='both', expand=True, padx=10, pady=5)

        self.text_widget = tk.Text(
            text_frame,
            wrap='word',
            font=('Consolas', 10),
            height=10
        )
        self.text_widget.pack(fill='both', expand=True)

        # Прогресс
        self.progress_var = tk.DoubleVar(value=0)
        self.progress = ttk.Progressbar(
            self,
            variable=self.progress_var,
            maximum=100
        )
        self.progress.pack(fill='x', padx=10, pady=5)

        self.status_label = ttk.Label(self, text="Готов")
        self.status_label.pack(anchor='w', padx=10)

    def _select_file(self):
        file_path = filedialog.askopenfilename(
            title="Выберите документ",
            filetypes=[
                ("Все файлы", "*.*"),
                ("PDF", "*.pdf"),
                ("Изображения", "*.png *.jpg *.jpeg *.tiff *.bmp"),
            ]
        )
        if file_path:
            self._process_files([file_path])

    def _select_folder(self):
        folder = filedialog.askdirectory(title="Выберите папку")
        if folder:
            path = Path(folder)
            files = [
                str(f) for f in path.iterdir()
                if f.suffix.lower() in ('.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.bmp')
            ]
            if files:
                self._process_files(files)

    def _process_files(self, files: List[str]):
        if not files:
            return

        # Очищаем предыдущие результаты
        self._clear_results()

        thread = threading.Thread(target=self._process_thread, args=(files,))
        thread.daemon = True
        thread.start()

    def _process_thread(self, files: List[str]):
        try:
            mode_map = {
                "fast": ProcessingMode.FAST,
                "standard": ProcessingMode.STANDARD,
                "accurate": ProcessingMode.ACCURATE,
            }
            mode = mode_map.get(self.mode_var.get(), ProcessingMode.STANDARD)

            self.service = UniversalOCRService(default_mode=mode)

            total = len(files)
            self.results = []

            for i, file_path in enumerate(files):
                self._update_progress(i, total, f"Обработка: {Path(file_path).name}")

                result = self.service.process_file(file_path, mode)
                self.results.append(result)

                # Добавляем в treeview
                self.after(0, lambda r=result: self._add_result_to_tree(r))

            self._update_progress(total, total, "Готово!")

        except Exception as e:
            logger.error("Ошибка OCR: %s", e)
            self.after(0, lambda: messagebox.showerror("Ошибка", str(e)))

    def _update_progress(self, current: int, total: int, message: str):
        def update():
            self.progress_var.set((current / total) * 100)
            self.status_label.config(text=message)
        self.after(0, update)

    def _add_result_to_tree(self, result: OCRDocumentResult):
        """Добавить результат в treeview."""
        preview = result.full_text[:100].replace('\n', ' ') + "..."

        self.tree.insert(
            '',
            'end',
            values=(
                result.source_file,
                len(result.pages),
                result.mode,
                f"{result.avg_confidence:.0%}",
                preview
            )
        )

    def _on_select(self, event):
        """При выборе строки показываем полный текст."""
        selection = self.tree.selection()
        if not selection:
            return

        idx = self.tree.index(selection[0])
        if idx < len(self.results):
            result = self.results[idx]
            self.text_widget.delete('1.0', 'end')
            self.text_widget.insert('1.0', result.full_text)

    def _export_excel(self):
        if not self.results:
            messagebox.showwarning("Внимание", "Нет данных для экспорта")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialfile="ocr_results.xlsx"
        )
        if file_path:
            try:
                self.service.export_to_excel(self.results, file_path)
                messagebox.showinfo("Успех", f"Экспортировано в:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))

    def _clear_results(self):
        """Очистить только результаты."""
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.results = []
        self.text_widget.delete('1.0', 'end')

    def _clear(self):
        """Полная очистка."""
        self._clear_results()
        self.progress_var.set(0)
        self.status_label.config(text="Готов")