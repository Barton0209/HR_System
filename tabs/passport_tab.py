"""
Passport Tab — UI для обработки паспортов.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from typing import List
import threading
import logging

from PIL import Image, ImageTk

from services import PassportService, PassportResult
from core import get_country_names

logger = logging.getLogger(__name__)


class PassportTab(ttk.Frame):
    """Вкладка обработки паспортов 23 стран."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.service: PassportService = None
        self.results: List[PassportResult] = []
        self.files: List[str] = []

        self._build_ui()

    def _build_ui(self):
        # Левая панель
        left_frame = ttk.Frame(self, width=350)
        left_frame.pack(side='left', fill='y', padx=5, pady=5)
        left_frame.pack_propagate(False)

        # Кнопки
        btn_frame = ttk.LabelFrame(left_frame, text="Действия", padding=10)
        btn_frame.pack(fill='x', pady=5)

        ttk.Button(
            btn_frame,
            text="📁 Выбрать файлы",
            command=self._select_files
        ).pack(fill='x', pady=2)

        ttk.Button(
            btn_frame,
            text="📂 Выбрать папку",
            command=self._select_folder
        ).pack(fill='x', pady=2)

        # Настройки
        settings_frame = ttk.LabelFrame(left_frame, text="Настройки", padding=10)
        settings_frame.pack(fill='x', pady=5)

        ttk.Label(settings_frame, text="Страна (опционально):").pack(anchor='w')
        self.country_var = tk.StringVar(value="AUTO")
        country_combo = ttk.Combobox(
            settings_frame,
            textvariable=self.country_var,
            values=["AUTO - Автоопределение"] + get_country_names()
        )
        country_combo.pack(fill='x', pady=2)

        self.vlm_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            settings_frame,
            text="Использовать VLM (точнее, медленнее)",
            variable=self.vlm_var
        ).pack(anchor='w', pady=5)

        # Список файлов
        files_frame = ttk.LabelFrame(left_frame, text="Файлы", padding=5)
        files_frame.pack(fill='both', expand=True, pady=5)

        scrollbar = ttk.Scrollbar(files_frame)
        scrollbar.pack(side='right', fill='y')

        self.files_listbox = tk.Listbox(
            files_frame,
            yscrollcommand=scrollbar.set,
            selectmode='single'
        )
        self.files_listbox.pack(fill='both', expand=True)
        scrollbar.config(command=self.files_listbox.yview)

        self.files_listbox.bind('<<ListboxSelect>>', self._on_file_select)

        # Правая панель
        right_frame = ttk.Frame(self)
        right_frame.pack(side='left', fill='both', expand=True, padx=5, pady=5)

        # Просмотр изображения
        img_frame = ttk.LabelFrame(right_frame, text="Просмотр", padding=5)
        img_frame.pack(fill='both', expand=True, pady=5)

        self.img_label = ttk.Label(img_frame, text="Выберите файл для просмотра")
        self.img_label.pack(expand=True)

        # Результаты
        result_frame = ttk.LabelFrame(right_frame, text="Результаты", padding=5)
        result_frame.pack(fill='x', pady=5)

        self.result_text = tk.Text(result_frame, height=12, wrap='word', font=('Consolas', 10))
        self.result_text.pack(fill='both', expand=True)

        # Кнопки экспорта
        export_frame = ttk.Frame(right_frame)
        export_frame.pack(fill='x', pady=5)

        ttk.Button(
            export_frame,
            text="📊 Экспорт в Excel",
            command=self._export_excel
        ).pack(side='left', padx=5)

        ttk.Button(
            export_frame,
            text="🗑 Очистить",
            command=self._clear
        ).pack(side='left', padx=5)

        # Прогресс
        self.progress_var = tk.DoubleVar(value=0)
        self.progress = ttk.Progressbar(
            right_frame,
            variable=self.progress_var,
            maximum=100
        )
        self.progress.pack(fill='x', pady=5)

        self.status_label = ttk.Label(right_frame, text="Готов")
        self.status_label.pack(anchor='w')

    def _select_files(self):
        files = filedialog.askopenfilenames(
            title="Выберите изображения паспортов",
            filetypes=[
                ("Все поддерживаемые", "*.png *.jpg *.jpeg *.pdf"),
                ("Изображения", "*.png *.jpg *.jpeg"),
                ("PDF", "*.pdf"),
            ]
        )
        if files:
            self.files = list(files)
            self._update_files_list()
            self._process_files()

    def _select_folder(self):
        folder = filedialog.askdirectory(title="Выберите папку с паспортами")
        if folder:
            path = Path(folder)
            self.files = [
                str(f) for f in path.glob("*")
                if f.suffix.lower() in ('.png', '.jpg', '.jpeg', '.pdf')
            ]
            self._update_files_list()
            self._process_files()

    def _update_files_list(self):
        self.files_listbox.delete(0, 'end')
        for f in self.files:
            self.files_listbox.insert('end', Path(f).name)

    def _process_files(self):
        if not self.files:
            return

        thread = threading.Thread(target=self._process_thread)
        thread.daemon = True
        thread.start()

    def _process_thread(self):
        try:
            self.service = PassportService(use_vlm=self.vlm_var.get())
            self.results = []

            # Определяем подсказку о стране
            country_hint = None
            country_val = self.country_var.get()
            if country_val != "AUTO - Автоопределение":
                country_hint = country_val.split(" ")[0]  # ISO3 код

            for i, file_path in enumerate(self.files):
                self._update_progress(i, len(self.files), f"Обработка: {Path(file_path).name}")

                if file_path.lower().endswith('.pdf'):
                    page_results = self.service.process_pdf(file_path, country_hint)
                    self.results.extend(page_results)
                else:
                    result = self.service.process_image(file_path, country_hint)
                    self.results.append(result)

            self._update_progress(len(self.files), len(self.files), "Готово!")

            if self.results:
                self.after(0, lambda: self._show_result(0))

        except Exception as e:
            logger.error("Ошибка обработки: %s", e)
            self.after(0, lambda: messagebox.showerror("Ошибка", str(e)))

    def _update_progress(self, current: int, total: int, message: str):
        def update():
            self.progress_var.set((current / total) * 100)
            self.status_label.config(text=message)
        self.after(0, update)

    def _on_file_select(self, event):
        selection = self.files_listbox.curselection()
        if selection:
            idx = selection[0]
            self._show_image(idx)
            # Находим соответствующий результат
            if idx < len(self.results):
                self._display_result(self.results[idx])

    def _show_image(self, idx: int):
        """Показать изображение файла."""
        if idx >= len(self.files):
            return

        file_path = self.files[idx]

        try:
            if file_path.lower().endswith('.pdf'):
                # Для PDF — первая страница
                import fitz
                doc = fitz.open(file_path)
                page = doc[0]
                pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                doc.close()
            else:
                img = Image.open(file_path)

            # Масштабирование
            img.thumbnail((600, 450))
            photo = ImageTk.PhotoImage(img)

            self.img_label.config(image=photo, text="")
            self.img_label.image = photo  # Сохраняем ссылку

        except Exception as e:
            logger.error("Ошибка загрузки изображения: %s", e)
            self.img_label.config(image='', text="Ошибка загрузки")

    def _show_result(self, idx: int):
        """Показать результат по индексу."""
        if idx < len(self.results):
            self._display_result(self.results[idx])

    def _display_result(self, result: PassportResult):
        """Отобразить результат в текстовом поле."""
        self.result_text.delete('1.0', 'end')

        text = f"""📄 Файл: {result.source_file}
{"="*50}

🌍 Страна: {result.country_name or result.country_iso3 or "Не определена"}

👤 ФИО:
  Фамилия: {result.surname or "N/A"}
  Имена: {result.given_names or "N/A"}

📝 Документ:
  Номер: {result.doc_number or "N/A"}
  Гражданство: {result.nationality or "N/A"}

📅 Даты:
  Дата рождения: {result.dob or "N/A"}
  Срок действия: {result.expiry or "N/A"}
  Пол: {result.sex or "N/A"}

🏛 Кем выдан: {result.issuing_authority or "N/A"}

✅ MRZ валиден: {"Да" if result.mrz_valid else "Нет"}
🤖 VLM использован: {"Да" if result.vlm_used else "Нет"}
📊 Уверенность: {result.confidence:.0%}
⏱ Время обработки: {result.processing_time:.2f}с
"""

        if result.error:
            text += f"\n❌ Ошибка: {result.error}\n"

        self.result_text.insert('1.0', text)

    def _export_excel(self):
        if not self.results:
            messagebox.showwarning("Внимание", "Нет данных для экспорта")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialfile="passports_export.xlsx"
        )
        if file_path:
            try:
                self.service.export_to_excel(self.results, file_path)
                messagebox.showinfo("Успех", f"Экспортировано в:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))

    def _clear(self):
        self.files = []
        self.results = []
        self.files_listbox.delete(0, 'end')
        self.result_text.delete('1.0', 'end')
        self.img_label.config(image='', text="Выберите файл для просмотра")
        self.progress_var.set(0)
        self.status_label.config(text="Готов")