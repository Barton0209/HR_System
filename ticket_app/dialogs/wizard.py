# ticket_app/dialogs/wizard.py
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Dict, Callable, Optional

from config import ROUTES, REASONS
from database import get_all_employees, find_employee_by_fio
from dialogs.pdf_viewer import PDFViewer
from dialogs.catalog import EmployeeCatalogDialog

# Обратный маршрут: «А - Б» → «Б - А»
_REVERSE_ROUTES: dict[str, str] = {}
for _r in ROUTES:
    if " - " in _r:
        a, b = _r.split(" - ", 1)
        _REVERSE_ROUTES[_r] = f"{b.strip()} - {a.strip()}"


class FillFromBaseWizard:
    """
    Визард ручной корректировки данных заявок.
    Каждая запись pdf_results = одна страница-заявка.
    """

    def __init__(self, parent, pdf_results: List[Dict], pdf_files: Dict[str, str],
                 department: str, on_complete: Callable):
        self.parent = parent
        self.pdf_results = pdf_results
        self.pdf_files = pdf_files          # {filename: full_path}
        self.department = department
        self.on_complete = on_complete

        self.current_index = 0
        self.saved_edits: List[Dict] = []   # подтверждённые записи
        self.draft_data: Dict[int, Dict] = {}  # черновики (не сохранённые)
        self.current_employee: Optional[Dict] = None
        self.employees_list: List[Dict] = []

        self.window = tk.Toplevel(parent)
        self.window.title("Ручное форматирование заявок")
        self.window.geometry("1500x850")
        self.window.transient(parent)
        self.window.grab_set()

        self._build_ui()
        self.employees_list = get_all_employees()
        self._process_current()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        # Навигационная панель
        nav = tk.Frame(self.window, bg='#1a1a2e', height=50)
        nav.pack(fill='x')
        self.nav_label = tk.Label(nav, text="", font=('Arial', 12),
                                  bg='#1a1a2e', fg='white')
        self.nav_label.pack(side='left', padx=20)
        tk.Button(nav, text="⏭ ДАЛЕЕ", command=self._go_next,
                  bg='#007bff', fg='white', font=('Arial', 12, 'bold'),
                  padx=30, pady=8).pack(side='right', padx=20)

        # Основная область
        paned = ttk.PanedWindow(self.window, orient='horizontal')
        paned.pack(fill='both', expand=True)

        # Левая панель — PDF
        left = ttk.LabelFrame(paned, text="Документ PDF", padding=5)
        paned.add(left, weight=3)
        self.pdf_viewer = PDFViewer(left)

        # Центральная панель — форма
        center = ttk.LabelFrame(paned, text="Данные заявки", padding=10)
        paned.add(center, weight=2)
        self._build_center(center)

        # Правая панель — сохранённые
        right = ttk.LabelFrame(paned, text="Сохранённые записи", padding=10)
        paned.add(right, weight=1)
        self._build_right(right)

    def _build_center(self, parent):
        # Список файлов
        ff = tk.LabelFrame(parent, text="Файлы", padx=5, pady=5)
        ff.pack(fill='x', pady=5)
        self.files_listbox = tk.Listbox(ff, height=3, font=('Arial', 10))
        self.files_listbox.pack(fill='x')
        self.files_listbox.bind('<<ListboxSelect>>', self._on_file_select)

        seen: set[str] = set()
        for r in self.pdf_results:
            fn = r.get('source_file', '')
            if fn and fn not in seen:
                seen.add(fn)
                self.files_listbox.insert('end', fn)

        # Поля формы
        ef = tk.LabelFrame(parent, text="Редактирование полей", padx=5, pady=5)
        ef.pack(fill='x', pady=10)
        ef.columnconfigure(1, weight=1)

        fields = [
            ("ФИО:", None),
            ("Маршрут 1:", ROUTES),
            ("Дата вылета 1:", None),
            ("Маршрут 2:", ROUTES),
            ("Дата вылета 2:", None),
            ("Обоснование:", REASONS),
        ]
        self._form_widgets = {}
        for row_idx, (label, values) in enumerate(fields):
            tk.Label(ef, text=label, font=('Arial', 10, 'bold')).grid(
                row=row_idx, column=0, sticky='w', pady=4)
            if values is not None:
                w = ttk.Combobox(ef, font=('Arial', 11), width=33, values=values)
                w.set('')
            else:
                w = tk.Entry(ef, font=('Arial', 11), width=35)
            w.grid(row=row_idx, column=1, sticky='ew', padx=5, pady=4)
            self._form_widgets[row_idx] = w

        self.fio_entry    = self._form_widgets[0]
        self.route1_combo = self._form_widgets[1]
        self.date1_entry  = self._form_widgets[2]
        self.route2_combo = self._form_widgets[3]
        self.date2_entry  = self._form_widgets[4]
        self.reason_combo = self._form_widgets[5]

        self.fio_entry.bind('<KeyRelease>', self._on_fio_change)
        self.fio_entry.bind('<FocusOut>', self._on_fio_change)
        self.route1_combo.bind('<<ComboboxSelected>>', self._on_route1_select)
        if REASONS:
            self.reason_combo.set(REASONS[0])

        self.emp_info_label = tk.Label(ef, text="", font=('Arial', 9),
                                       fg='gray', wraplength=300)
        self.emp_info_label.grid(row=len(fields), column=0, columnspan=2,
                                 sticky='w', pady=5)

        tk.Button(parent, text="💾 Сохранить и перейти далее",
                  command=self._save_edits,
                  bg='#ffc107', fg='black', font=('Arial', 10)).pack(fill='x', pady=5)

        # Поиск в базе
        sf = tk.Frame(parent)
        sf.pack(fill='x', pady=5)
        tk.Label(sf, text="Поиск в базе:").pack(side='left')
        self.search_entry = tk.Entry(sf, font=('Arial', 11), width=20)
        self.search_entry.pack(side='left', padx=5)
        self.search_entry.bind('<Return>', lambda e: self._search_employees())
        self.search_entry.bind('<Control-v>', self._paste_and_search)
        tk.Button(sf, text="Найти", command=self._search_employees).pack(side='left', padx=2)
        self.btn_add_to_form = tk.Button(sf, text="Добавить в анкету",
                                         command=self._add_selected_to_form,
                                         bg='#17a2b8', fg='white', font=('Arial', 10),
                                         state='disabled')
        self.btn_add_to_form.pack(side='left', padx=5)

        # Таблица результатов поиска
        tf = tk.Frame(parent)
        tf.pack(fill='both', expand=True, pady=5)
        cols = ('ФИО', 'Отдел', 'Должность', 'Таб. №')
        self.search_tree = ttk.Treeview(tf, columns=cols, show='headings', height=6)
        for c in cols:
            self.search_tree.heading(c, text=c)
            self.search_tree.column(c, width=120)
        vsb = ttk.Scrollbar(tf, orient='vertical', command=self.search_tree.yview)
        self.search_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y')
        self.search_tree.pack(fill='both', expand=True)
        self.search_tree.bind('<Double-1>', self._on_tree_double_click)
        self.search_tree.bind('<<TreeviewSelect>>', self._on_tree_select)

        bf = tk.Frame(parent)
        bf.pack(pady=5)
        tk.Button(bf, text="Выбрать сотрудника", command=self._select_from_tree,
                  bg='#28a745', fg='white', font=('Arial', 10), padx=15).pack(side='left', padx=5)
        tk.Button(bf, text="Открыть каталог", command=self._open_catalog,
                  bg='#17a2b8', fg='white', font=('Arial', 10), padx=15).pack(side='left', padx=5)

    def _build_right(self, parent):
        self.saved_listbox = tk.Listbox(parent, font=('Arial', 10), bg='#f8f9fa')
        self.saved_listbox.pack(fill='both', expand=True, pady=(0, 10))
        tk.Button(parent, text="✓ СОХРАНИТЬ И ДОБАВИТЬ ВСЕХ В ЗАЯВКУ",
                  command=self._finish_and_add_all,
                  bg='#28a745', fg='white', font=('Arial', 11, 'bold'),
                  pady=15).pack(fill='x')

    # ------------------------------------------------------------------
    # Навигация
    # ------------------------------------------------------------------

    def _process_current(self):
        if self.current_index >= len(self.pdf_results):
            self.nav_label.config(text="Все листы обработаны")
            return

        res = self.pdf_results[self.current_index]
        fn = res.get('source_file', '')

        # Загружаем PDF если нужно
        if fn in self.pdf_files:
            current_doc = getattr(self.pdf_viewer.doc, 'name', '') if self.pdf_viewer.doc else ''
            if current_doc != self.pdf_files[fn]:
                self.pdf_viewer.load_pdf(self.pdf_files[fn])

            # Переходим на нужную страницу
            page_num = res.get('page_num', 1) - 1
            self.pdf_viewer.go_to_page(page_num)

        # Подсвечиваем файл в списке
        for i in range(self.files_listbox.size()):
            if self.files_listbox.get(i) == fn:
                self.files_listbox.selection_clear(0, tk.END)
                self.files_listbox.selection_set(i)
                self.files_listbox.see(i)
                break

        total = len(self.pdf_results)
        page_info = f"стр. {res.get('page_num', '?')}"
        self.nav_label.config(
            text=f"Запись {self.current_index + 1} из {total} | {fn} ({page_info})")
        self._load_data_to_form()

    def _go_next(self):
        self.draft_data[self.current_index] = self._get_form_data()
        if self.current_index < len(self.pdf_results) - 1:
            self.current_index += 1
            self._process_current()
        else:
            messagebox.showinfo("Инфо", "Это последняя запись.")

    def _on_file_select(self, event):
        sel = self.files_listbox.curselection()
        if not sel:
            return
        fn = self.files_listbox.get(sel[0])
        if fn in self.pdf_files:
            self.pdf_viewer.load_pdf(self.pdf_files[fn])
        for i, r in enumerate(self.pdf_results):
            if r.get('source_file') == fn:
                self.draft_data[self.current_index] = self._get_form_data()
                self.current_index = i
                self._load_data_to_form()
                break

    # ------------------------------------------------------------------
    # Форма
    # ------------------------------------------------------------------

    def _get_form_data(self) -> Dict:
        return {
            'fio':      self.fio_entry.get().strip(),
            'route':    self.route1_combo.get(),
            'date':     self.date1_entry.get().strip(),
            'route2':   self.route2_combo.get(),
            'date2':    self.date2_entry.get().strip(),
            'reason':   self.reason_combo.get(),
            'employee': self.current_employee,
        }

    def _set_form_data(self, data: Dict):
        self.fio_entry.delete(0, 'end')
        self.fio_entry.insert(0, data.get('fio', ''))
        self.route1_combo.set(data.get('route', ''))
        self.date1_entry.delete(0, 'end')
        self.date1_entry.insert(0, data.get('date', ''))
        self.route2_combo.set(data.get('route2', ''))
        self.date2_entry.delete(0, 'end')
        self.date2_entry.insert(0, data.get('date2', ''))
        self.reason_combo.set(data.get('reason', REASONS[0] if REASONS else ''))
        self.current_employee = data.get('employee')

    def _load_data_to_form(self):
        # Приоритет: сохранённое → черновик → исходные данные PDF
        saved = next((s for s in self.saved_edits
                      if s.get('original_index') == self.current_index), None)
        if saved:
            self._set_form_data(saved)
            emp = saved.get('employee')
            self.emp_info_label.config(
                text=f"✓ Сохранено: {emp.get('fio', '') if emp else 'Нет в базе'}",
                fg='green' if emp else 'orange')
            return

        if self.current_index in self.draft_data:
            self._set_form_data(self.draft_data[self.current_index])
            self._on_fio_change(silent=True)
            return

        r = self.pdf_results[self.current_index]
        self._set_form_data({**r, 'employee': None})
        self.emp_info_label.config(text="Ожидание...", fg='gray')
        self._on_fio_change(silent=True)

    def _on_route1_select(self, event=None):
        r1 = self.route1_combo.get()
        rev = _REVERSE_ROUTES.get(r1)
        if rev:
            self.route2_combo.set(rev)
        elif " - " in r1:
            a, b = r1.split(" - ", 1)
            candidate = f"{b.strip()} - {a.strip()}"
            self.route2_combo.set(candidate if candidate in ROUTES else '')

    def _on_fio_change(self, event=None, silent=False):
        fio = self.fio_entry.get().strip()
        self.draft_data[self.current_index] = self._get_form_data()

        if len(fio) < 3:
            if not silent:
                self.emp_info_label.config(text="Введите минимум 3 символа", fg='orange')
            self.current_employee = None
            return

        emp, status = find_employee_by_fio(fio, None)
        if status == 'found':
            self.current_employee = emp
            self.draft_data[self.current_index]['employee'] = emp
            if not silent:
                self.emp_info_label.config(
                    text=f"✓ Найден: {emp.get('fio', '')}", fg='green')
            self._search_employees(fio)
        elif status == 'multiple':
            self.current_employee = None
            if not silent:
                self.emp_info_label.config(
                    text=f"Найдено {len(emp)} совпадений", fg='orange')
            self._show_in_tree(emp)
        else:
            self.current_employee = None
            if not silent:
                self.emp_info_label.config(text="Не найден в базе", fg='red')

    # ------------------------------------------------------------------
    # Поиск / дерево
    # ------------------------------------------------------------------

    def _paste_and_search(self, event):
        try:
            self.search_entry.delete(0, 'end')
            self.search_entry.insert(0, self.window.clipboard_get())
            self._search_employees()
        except tk.TclError:
            pass
        return "break"

    def _search_employees(self, query: str = None):
        if query is None:
            query = self.search_entry.get().strip()
        self.search_tree.delete(*self.search_tree.get_children())
        source = self.employees_list if query else self.employees_list[:20]
        count = 0
        for emp in source:
            if query and query.lower() not in emp.get('fio', '').lower():
                continue
            self.search_tree.insert('', 'end',
                                    values=(emp.get('fio', ''), emp.get('department', ''),
                                            emp.get('position', ''), emp.get('tab_num', '')),
                                    tags=(str(id(emp)),))
            count += 1
            if count >= 50:
                break

    def _show_in_tree(self, emps: List[Dict]):
        self.search_tree.delete(*self.search_tree.get_children())
        for emp in emps:
            self.search_tree.insert('', 'end',
                                    values=(emp.get('fio', ''), emp.get('department', ''),
                                            emp.get('position', ''), emp.get('tab_num', '')),
                                    tags=(str(id(emp)),))

    def _on_tree_select(self, event):
        self.btn_add_to_form.config(
            state='normal' if self.search_tree.selection() else 'disabled')

    def _on_tree_double_click(self, event):
        self._select_from_tree()

    def _get_emp_from_tree_item(self, iid: str) -> Optional[Dict]:
        """Находит объект сотрудника по iid строки дерева через tab_num."""
        vals = self.search_tree.item(iid, 'values')
        tab_num = vals[3] if len(vals) > 3 else ""
        fio = vals[0] if vals else ""
        for emp in self.employees_list:
            if tab_num and emp.get('tab_num') == tab_num:
                return emp
            if not tab_num and emp.get('fio') == fio:
                return emp
        return None

    def _select_from_tree(self):
        sel = self.search_tree.selection()
        if not sel:
            return
        emp = self._get_emp_from_tree_item(sel[0])
        if emp:
            self._apply_employee(emp)

    def _add_selected_to_form(self):
        self._select_from_tree()

    def _apply_employee(self, emp: Dict):
        self.current_employee = emp
        self.fio_entry.delete(0, 'end')
        self.fio_entry.insert(0, emp.get('fio', ''))
        self.emp_info_label.config(
            text=f"✓ Добавлен: {emp.get('fio', '')}", fg='green')

    def _open_catalog(self):
        def on_sel(emps):
            if emps:
                self._apply_employee(emps[0])
        EmployeeCatalogDialog(self.window, on_sel)

    # ------------------------------------------------------------------
    # Сохранение
    # ------------------------------------------------------------------

    def _save_edits(self):
        fio = self.fio_entry.get().strip()
        if not fio:
            messagebox.showwarning("Внимание", "Заполните ФИО!")
            return

        record = {
            'original_index': self.current_index,
            **self._get_form_data(),
        }

        # Обновляем если уже есть
        for i, existing in enumerate(self.saved_edits):
            if existing.get('original_index') == self.current_index:
                self.saved_edits[i] = record
                self.draft_data.pop(self.current_index, None)
                self._update_saved_listbox()
                self._advance()
                return

        self.saved_edits.append(record)
        self.draft_data.pop(self.current_index, None)
        self._update_saved_listbox()
        self._advance()

    def _advance(self):
        if self.current_index < len(self.pdf_results) - 1:
            self.current_index += 1
            self._process_current()
        else:
            messagebox.showinfo("Инфо", "Сохранено! Это последняя запись.")

    def _update_saved_listbox(self):
        self.saved_listbox.delete(0, 'end')
        for i, rec in enumerate(self.saved_edits):
            status = "✓ База" if rec.get('employee') else "⚠ Нет в базе"
            self.saved_listbox.insert('end', f"{i + 1}. {rec.get('fio', '')} ({status})")

    def _finish_and_add_all(self):
        if not self.saved_edits:
            messagebox.showwarning("Внимание", "Нет сохранённых записей!")
            return

        final = []
        for rec in self.saved_edits:
            fio = rec.get('fio', '')
            emp = rec.get('employee')
            if not emp and fio:
                found, status = find_employee_by_fio(fio, None)
                emp = found if status == 'found' else None
            final.append({
                "fio":      fio,
                "route":    rec.get('route', ''),
                "date":     rec.get('date', ''),
                "route2":   rec.get('route2', ''),
                "date2":    rec.get('date2', ''),
                "reason":   rec.get('reason', ''),
                "employee": emp,
                "status":   'selected' if emp else 'manual',
            })

        self.on_complete(final)
        self.window.destroy()
