# ticket_app/main.py
"""
Система обработки заявок на билеты v2.0
Запуск: python ticket_app/main.py  (из корня проекта idps/)
"""

import sys
import os
import logging

# Добавляем ticket_app в путь поиска модулей
sys.path.insert(0, os.path.dirname(__file__))

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import pandas as pd

from auth import AuthManager, LoginWindow
from config import ALL_COLUMNS, ROUTES, REASONS
from database import (
    load_employees_base, get_employees_db, set_employees_db,
    find_employee_by_fio, get_all_employees,
)
from excel_handler import save_as_excel, create_application_row, create_empty_row, format_date_ddmmyyyy
from pdf_processor import process_pdf_file
from storage import save_database_to_file, load_database_from_file
from dialogs.pdf_viewer import PDFViewer
from dialogs.catalog import EmployeeCatalogDialog
from dialogs.wizard import FillFromBaseWizard

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('ticket_app.log', encoding='utf-8'),
    ]
)
logger = logging.getLogger(__name__)


class EmployeeDetailDialog:
    """Диалог просмотра и редактирования данных сотрудника."""

    def __init__(self, parent, employee: dict, on_save=None):
        self.employee = employee
        self.on_save = on_save

        self.window = tk.Toplevel(parent)
        self.window.title(f"Сотрудник: {employee.get('fio', '')}")
        self.window.geometry("600x520")
        self.window.transient(parent)
        self.window.grab_set()

        frame = tk.LabelFrame(self.window, text="Данные сотрудника", padx=10, pady=10)
        frame.pack(fill='x', padx=10, pady=10)

        fields = [
            ('ФИО', 'fio'), ('Подразделение', 'department'), ('Должность', 'position'),
            ('Табельный номер', 'tab_num'), ('Гражданство', 'citizenship'),
            ('Дата рождения', 'birth_date'), ('Серия паспорта', 'doc_series'),
            ('Номер паспорта', 'doc_num'), ('Дата выдачи', 'doc_date'),
            ('Дата окончания', 'doc_expiry'), ('Адрес', 'address'), ('Телефон', 'phone'),
        ]
        self.entries: dict[str, tk.Entry] = {}
        for label, key in fields:
            row = tk.Frame(frame)
            row.pack(fill='x', pady=2)
            tk.Label(row, text=f"{label}:", width=16, anchor='w').pack(side='left')
            entry = tk.Entry(row, font=('Arial', 10))
            entry.pack(side='left', fill='x', expand=True)
            entry.insert(0, employee.get(key, ''))
            entry.config(state='readonly')
            self.entries[key] = entry

        bf = tk.Frame(self.window)
        bf.pack(pady=15)
        self.edit_btn = tk.Button(bf, text="Редактировать", command=self._enable_edit,
                                  bg='#ffc107', fg='black', font=('Arial', 11), padx=20)
        self.edit_btn.pack(side='left', padx=5)
        tk.Button(bf, text="Закрыть", command=self.window.destroy,
                  bg='#6c757d', fg='white', font=('Arial', 11), padx=20).pack(side='left', padx=5)

    def _enable_edit(self):
        for entry in self.entries.values():
            entry.config(state='normal')
        self.edit_btn.config(text="Сохранить", command=self._save, bg='#28a745', fg='white')

    def _save(self):
        for key, entry in self.entries.items():
            self.employee[key] = entry.get()
        if self.on_save:
            self.on_save(self.employee)
        messagebox.showinfo("Успех", "Изменения сохранены")
        self.window.destroy()


class MainApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Система обработки заявок на билеты v2.0")
        self.root.geometry("1800x1000")
        self.root.state('zoomed')

        self.auth = AuthManager()
        self.current_department: str | None = None
        self.is_admin = False

        self.pdf_results: list[dict] = []
        self.pdf_files: dict[str, str] = {}   # {filename: full_path}
        self.applications_df: pd.DataFrame | None = None
        self.existing_tab_nums: set[str] = set()

        self._build_ui()
        self._auto_load_database()
        self._show_login()
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    # ------------------------------------------------------------------
    # Инициализация
    # ------------------------------------------------------------------

    def _auto_load_database(self):
        df = load_database_from_file()
        if df is not None and not df.empty:
            set_employees_db(df)
            self.status_label.config(
                text=f"Автозагрузка: {len(df)} сотрудников из локальной базы")
            self.btn_catalog.config(state='normal')

    def _on_closing(self):
        self._save_current_database()
        self.root.quit()
        self.root.destroy()

    def _save_current_database(self):
        db = get_employees_db()
        if db is not None and not db.empty:
            save_database_to_file(db)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        # Шапка
        top = tk.Frame(self.root, bg='#1a1a2e', height=60)
        top.pack(fill='x')
        tk.Label(top, text="СИСТЕМА ЗАЯВОК НА БИЛЕТЫ v2.0",
                 font=('Arial', 18, 'bold'), bg='#1a1a2e', fg='white').pack(
            side='left', padx=20, pady=15)
        self.user_label = tk.Label(top, text="Не авторизован",
                                   font=('Arial', 11), bg='#1a1a2e', fg='#e94560')
        self.user_label.pack(side='right', padx=20)

        # Тулбар
        toolbar = tk.Frame(self.root, bg='#16213e', height=50)
        toolbar.pack(fill='x')
        toolbar.pack_propagate(False)

        btn_cfg = dict(fg='white', font=('Arial', 10), padx=15, pady=8)

        self.btn_load_base = tk.Button(
            toolbar, text="Загрузить Базу", command=self._load_base,
            bg='#0f3460', state='disabled', **btn_cfg)
        self.btn_load_base.pack(side='left', padx=5, pady=10)

        self.btn_catalog = tk.Button(
            toolbar, text="Каталог сотрудников", command=self._open_catalog,
            bg='#17a2b8', state='disabled', **btn_cfg)
        self.btn_catalog.pack(side='left', padx=5, pady=10)

        tk.Button(toolbar, text="Выбрать файл", command=self._select_single_file,
                  bg='#0f3460', **btn_cfg).pack(side='left', padx=5, pady=10)

        tk.Button(toolbar, text="Выбрать папку", command=self._select_folder,
                  bg='#0f3460', **btn_cfg).pack(side='left', padx=5, pady=10)

        self.btn_fill = tk.Button(
            toolbar, text="Заполнить из Базы", command=self._fill_from_database,
            bg='#0f3460', state='disabled', **btn_cfg)
        self.btn_fill.pack(side='left', padx=5, pady=10)

        self.btn_export = tk.Button(
            toolbar, text="Экспорт в Excel", command=self._export_to_excel,
            bg='#e94560', state='disabled', **btn_cfg)
        self.btn_export.pack(side='left', padx=5, pady=10)

        self.btn_clear = tk.Button(
            toolbar, text="Очистить заявку", command=self._clear_all,
            bg='#dc3545', state='disabled', **btn_cfg)
        self.btn_clear.pack(side='left', padx=5, pady=10)

        tk.Button(toolbar, text="Выход", command=self._logout,
                  bg='#333', **btn_cfg).pack(side='right', padx=10, pady=10)

        # Основная область
        main_paned = ttk.PanedWindow(self.root, orient='horizontal')
        main_paned.pack(fill='both', expand=True)

        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=2)

        # Список PDF
        pdf_list_frame = ttk.LabelFrame(left_frame, text="Обработанные PDF", padding=5)
        pdf_list_frame.pack(fill='x', padx=5, pady=5)
        scrollbar = ttk.Scrollbar(pdf_list_frame)
        self.pdf_listbox = tk.Listbox(pdf_list_frame, height=4, font=('Arial', 10),
                                      yscrollcommand=scrollbar.set)
        self.pdf_listbox.pack(side='left', fill='x', expand=True)
        scrollbar.config(command=self.pdf_listbox.yview)
        scrollbar.pack(side='right', fill='y')
        self.pdf_listbox.bind('<<ListboxSelect>>', self._on_pdf_select)

        # Таблица заявок
        table_frame = ttk.Frame(left_frame)
        table_frame.pack(fill='both', expand=True, padx=5, pady=5)
        y_scroll = ttk.Scrollbar(table_frame, orient='vertical')
        y_scroll.pack(side='right', fill='y')
        x_scroll = ttk.Scrollbar(table_frame, orient='horizontal')
        x_scroll.pack(side='bottom', fill='x')

        self.table = ttk.Treeview(
            table_frame, yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.table['columns'] = ALL_COLUMNS
        self.table['show'] = 'headings'

        col_widths = {
            "№": 40, "Подразделение": 100, "Отдел": 70, "Операция": 70,
            "Классификация": 80, "Дата заказа": 90, "Организация": 80,
            "Ф.И.О.": 150, "Ф.И.О лат": 150, "Табельный номер": 70,
            "Гражданство": 90, "Дата рождения": 90, "Вид документа": 130,
            "Серия": 50, "Номер": 70, "Дата выдачи": 90, "Дата окончания": 90,
            "Кем выдан": 120, "Адрес": 120, "Маршрут": 150, "Обоснование": 120,
            "ПС": 40, "АВИА/ЖД": 60, "Дата вылета": 90, "Примечание": 100,
            "Ответственный": 100, "Дата выписки": 80, "Билет": 70, "Сумма": 60,
            "Оплата": 70, "Причина возврата": 80, "Последний перелет": 80,
            "Телефон": 100, "Трансфер": 60,
        }
        for col in ALL_COLUMNS:
            self.table.heading(col, text=col)
            self.table.column(col, width=col_widths.get(col, 80), anchor='w')

        y_scroll.config(command=self.table.yview)
        x_scroll.config(command=self.table.xview)
        self.table.pack(fill='both', expand=True)
        self.table.bind('<Double-1>', self._on_table_double_click)

        # Правая панель — просмотр PDF
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=3)
        self.pdf_viewer = PDFViewer(right_frame)

        # Статус бар
        self.status_label = tk.Label(
            self.root, text="Готов к работе", bd=1, relief='sunken',
            anchor='w', font=('Arial', 9), bg='#f0f0f0')
        self.status_label.pack(side='bottom', fill='x')

        # Прогресс бар
        self.progress_frame = tk.Frame(self.root)
        self.progress_label = tk.Label(self.progress_frame, text="", font=('Arial', 10))
        self.progress_label.pack(side='left', padx=10)
        self.progress_bar = ttk.Progressbar(
            self.progress_frame, mode='determinate', length=300)
        self.progress_bar.pack(side='left', padx=10)

    # ------------------------------------------------------------------
    # Авторизация
    # ------------------------------------------------------------------

    def _show_login(self):
        login = LoginWindow(self.root, self.auth)
        self.root.wait_window(login.window)
        if self.auth.current_user:
            self.current_department = self.auth.current_user
            self.is_admin = self.auth.is_admin
            self._update_ui()
            self.status_label.config(text=f"Вход: {self.current_department}")
        else:
            self.root.quit()

    def _update_ui(self):
        if not self.current_department:
            return
        label = f"{self.current_department} (Admin)" if self.is_admin else self.current_department
        self.user_label.config(text=label)
        self.btn_load_base.config(state='normal' if self.is_admin else 'disabled')
        if get_employees_db() is not None:
            self.btn_catalog.config(state='normal')

    def _logout(self):
        if messagebox.askyesno("Выход", "Выйти из системы?"):
            self._on_closing()

    # ------------------------------------------------------------------
    # База сотрудников
    # ------------------------------------------------------------------

    def _load_base(self):
        fp = filedialog.askopenfilename(
            title="Выберите файл базы", filetypes=[("Excel", "*.xlsx *.xls")])
        if not fp:
            return
        success, msg, count = load_employees_base(fp)
        if success:
            messagebox.showinfo("Успех", msg)
            self.status_label.config(text=f"База: {count} сотрудников")
            self.btn_catalog.config(state='normal')
            self._save_current_database()
        else:
            messagebox.showerror("Ошибка", msg)
        self._update_ui()

    def _open_catalog(self):
        def on_sel(emps: list[dict]):
            if not emps:
                return
            rows = []
            start_num = (len(self.applications_df) + 1
                         if self.applications_df is not None and not self.applications_df.empty
                         else 1)
            skipped = 0
            for i, emp in enumerate(emps):
                tn = emp.get('tab_num', '')
                if tn and tn in self.existing_tab_nums:
                    skipped += 1
                    continue
                if tn:
                    self.existing_tab_nums.add(tn)
                pdf_data = {
                    'source_file': 'Каталог', 'fio': emp.get('fio', ''),
                    'route': '', 'date': '', 'reason': '', 'phone': emp.get('phone', ''),
                }
                rows.append(create_application_row(start_num + i - skipped,
                                                   self.current_department, pdf_data, emp))
            if rows:
                df = pd.DataFrame(rows, columns=ALL_COLUMNS)
                self._append_to_table(df)

        EmployeeCatalogDialog(self.root, on_sel)

    # ------------------------------------------------------------------
    # Обработка PDF
    # ------------------------------------------------------------------

    def _select_single_file(self):
        if get_employees_db() is None:
            messagebox.showwarning("Внимание", "Сначала загрузите базу сотрудников!")
            return
        fp = filedialog.askopenfilename(title="Выберите PDF", filetypes=[("PDF", "*.pdf")])
        if fp:
            self._process_single_pdf(fp)

    def _select_folder(self):
        if get_employees_db() is None:
            messagebox.showwarning("Внимание", "Сначала загрузите базу сотрудников!")
            return
        fd = filedialog.askdirectory(title="Выберите папку с PDF")
        if fd:
            self._process_pdfs_folder(fd)

    def _process_single_pdf(self, fp: str):
        import os
        fn = os.path.basename(fp)
        self.pdf_files[fn] = fp
        self._show_progress("Обработка...")
        try:
            results = process_pdf_file(fp)
            self.pdf_results.extend(results)
            self._update_pdf_list()
            self.btn_fill.config(state='normal')
            if results:
                self.pdf_viewer.load_pdf(fp)
                self._fill_from_database()
            else:
                messagebox.showwarning("Внимание", "Не удалось извлечь данные из PDF")
        except Exception as e:
            logger.exception("Ошибка обработки PDF")
            messagebox.showerror("Ошибка", str(e))
        finally:
            self._hide_progress()

    def _process_pdfs_folder(self, folder: str):
        from pathlib import Path
        pdf_files = list(Path(folder).glob("*.pdf"))
        if not pdf_files:
            messagebox.showwarning("Внимание", "PDF-файлы не найдены в папке")
            return

        self.progress_frame.pack(side='bottom', fill='x', padx=10, pady=5)
        self.progress_bar['maximum'] = len(pdf_files)
        self.progress_bar['value'] = 0
        self.root.update()

        try:
            for i, pf in enumerate(pdf_files):
                self.progress_bar['value'] = i
                self.progress_label.config(text=f"Обработка: {pf.name}")
                self.root.update_idletasks()
                results = process_pdf_file(str(pf))
                self.pdf_results.extend(results)
                self.pdf_files[pf.name] = str(pf)
            self._update_pdf_list()
            self.btn_fill.config(state='normal')
        except Exception as e:
            logger.exception("Ошибка обработки папки")
            messagebox.showerror("Ошибка", str(e))
        finally:
            self._hide_progress()

    def _update_pdf_list(self):
        self.pdf_listbox.delete(0, 'end')
        for r in self.pdf_results:
            self.pdf_listbox.insert('end', f"{r.get('source_file', '')} — {r.get('fio', '')}")

    def _on_pdf_select(self, event):
        sel = self.pdf_listbox.curselection()
        if sel and sel[0] < len(self.pdf_results):
            fn = self.pdf_results[sel[0]].get('source_file', '')
            if fn in self.pdf_files:
                self.pdf_viewer.load_pdf(self.pdf_files[fn])

    # ------------------------------------------------------------------
    # Заполнение из базы
    # ------------------------------------------------------------------

    def _fill_from_database(self):
        if not self.pdf_results:
            return

        def on_complete(final_results: list[dict]):
            start_num = (len(self.applications_df) + 1
                         if self.applications_df is not None and not self.applications_df.empty
                         else 1)
            rows = []
            for i, res in enumerate(final_results):
                emp = res.get('employee')
                num = start_num + i
                if res.get('status') == 'skipped':
                    row = create_empty_row(num, self.current_department, res)
                else:
                    row = create_application_row(num, self.current_department, res, emp)
                rows.append(row)
                tn = emp.get('tab_num', '') if emp else ''
                if tn:
                    self.existing_tab_nums.add(tn)

            if rows:
                df = pd.DataFrame(rows, columns=ALL_COLUMNS)
                self._append_to_table(df)

        FillFromBaseWizard(
            self.root, self.pdf_results, self.pdf_files,
            self.current_department, on_complete
        )

    # ------------------------------------------------------------------
    # Таблица
    # ------------------------------------------------------------------

    def _append_to_table(self, df: pd.DataFrame):
        if self.applications_df is not None and not self.applications_df.empty:
            self.applications_df = pd.concat(
                [self.applications_df, df], ignore_index=True)
        else:
            self.applications_df = df
        self.applications_df['№'] = range(1, len(self.applications_df) + 1)
        self._display_table()
        self.btn_export.config(state='normal')
        self.btn_clear.config(state='normal')

    def _display_table(self):
        self.table.delete(*self.table.get_children())
        if self.applications_df is None or self.applications_df.empty:
            return
        for _, row in self.applications_df.iterrows():
            self.table.insert('', 'end', values=list(row))

    def _on_table_double_click(self, event):
        sel = self.table.selection()
        if not sel:
            return
        vals = self.table.item(sel[0])['values']
        if len(vals) > 7:
            emp, status = find_employee_by_fio(str(vals[7]), self.current_department)
            if status == 'found':
                EmployeeDetailDialog(self.root, emp)
            elif status == 'multiple':
                EmployeeCatalogDialog(self.root, lambda x: None)
            else:
                messagebox.showinfo("Информация", "Сотрудник не найден в базе")

    def _clear_all(self):
        if not messagebox.askyesno("Подтверждение", "Очистить все заявки?"):
            return
        self.applications_df = None
        self.pdf_results = []
        self.pdf_files = {}
        self.existing_tab_nums.clear()
        self.table.delete(*self.table.get_children())
        self.pdf_listbox.delete(0, 'end')
        self.pdf_viewer.close()
        self.btn_fill.config(state='disabled')
        self.btn_export.config(state='disabled')
        self.btn_clear.config(state='disabled')

    # ------------------------------------------------------------------
    # Экспорт
    # ------------------------------------------------------------------

    def _export_to_excel(self):
        if self.applications_df is None or self.applications_df.empty:
            messagebox.showwarning("Внимание", "Нет данных для экспорта!")
            return

        default_name = f"НОВАЯ-{self.current_department}. Заказ билетов.xlsx"
        fp = filedialog.asksaveasfilename(
            title="Сохранить как", defaultextension=".xlsx",
            initialfile=default_name, filetypes=[("Excel", "*.xlsx")])
        if not fp:
            return

        try:
            from openpyxl import Workbook, load_workbook
            wb = load_workbook(fp) if os.path.exists(fp) else Workbook()

            for sheet_name in ("Заявка", "Sheet"):
                if sheet_name in wb.sheetnames:
                    del wb[sheet_name]

            ws = wb.create_sheet("Заявка")
            for col_idx, col_name in enumerate(self.applications_df.columns, 1):
                ws.cell(row=1, column=col_idx, value=col_name)
            for row_idx, row_data in enumerate(
                    self.applications_df.itertuples(index=False, name=None), 2):
                for col_idx, value in enumerate(row_data, 1):
                    val = value if pd.notna(value) else ""
                    if hasattr(val, 'strftime'):
                        val = val.strftime("%d.%m.%Y")
                    ws.cell(row=row_idx, column=col_idx, value=val)

            wb.save(fp)
            messagebox.showinfo("Успех", f"Данные сохранены:\n{fp}")
            logger.info("Экспорт в Excel: %s", fp)
        except Exception as e:
            logger.exception("Ошибка экспорта")
            messagebox.showerror("Ошибка", f"Ошибка сохранения:\n{e}")

    # ------------------------------------------------------------------
    # Вспомогательные
    # ------------------------------------------------------------------

    def _show_progress(self, text: str = ""):
        self.progress_frame.pack(side='bottom', fill='x', padx=10, pady=5)
        self.progress_bar['value'] = 30
        self.progress_label.config(text=text)
        self.root.update()

    def _hide_progress(self):
        self.progress_frame.pack_forget()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = MainApp()
    app.run()
