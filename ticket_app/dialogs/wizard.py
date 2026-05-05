# ticket_app/dialogs/wizard.py
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Dict, Callable, Optional

from config import ROUTES, REASONS
from database import (
    get_all_employees, find_employee_by_fio,
    get_routes_for_department, get_transfer_city_for_route,
    get_responsible_for_department,
)
from dialogs.pdf_viewer import PDFViewer
from dialogs.catalog import EmployeeCatalogDialog

# Логика автозаполнения Обоснование 2 по Обоснованию 1
_REASON2_AUTO = {
    "Командировка":      "Командировка",
    "Межвахтовый отдых": "Возвращение из отпуска",
}
# При этих обоснованиях Маршрут 2 и Обоснование 2 не заполняются
_REASON_NO_ROUTE2 = {"Увольнение", "Перевод в др. ОП"}


def _reverse_route(route: str, available: List[str]) -> str:
    if " - " not in route:
        return ""
    a, b = route.split(" - ", 1)
    candidate = f"{b.strip()} - {a.strip()}"
    return candidate if candidate in available else ""


class FillFromBaseWizard:
    """
    Визард ручной корректировки данных заявок.
    Каждая запись pdf_results = одна страница-заявка.
    """

    def __init__(self, parent, pdf_results: List[Dict], pdf_files: Dict[str, str],
                 department: str, on_complete: Callable):
        self.parent = parent
        self.pdf_results = pdf_results
        self.pdf_files = pdf_files
        self.department = department
        self.on_complete = on_complete

        self.current_index = 0
        self.saved_edits: List[Dict] = []
        self.draft_data: Dict[int, Dict] = {}
        self.current_employee: Optional[Dict] = None
        self.employees_list: List[Dict] = []

        # Маршруты для текущего подразделения
        self.dept_routes = get_routes_for_department(department) or ROUTES
        # Ответственные для текущего подразделения
        self.dept_responsible = get_responsible_for_department(department)

        self.window = tk.Toplevel(parent)
        self.window.title("Ручное форматирование заявок")
        self.window.geometry("1600x900")
        self.window.transient(parent)
        self.window.grab_set()

        self._build_ui()
        self.employees_list = get_all_employees()
        self._process_current()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        nav = tk.Frame(self.window, bg='#1a1a2e', height=50)
        nav.pack(fill='x')
        self.nav_label = tk.Label(nav, text="", font=('Arial', 12),
                                  bg='#1a1a2e', fg='white')
        self.nav_label.pack(side='left', padx=20)
        tk.Button(nav, text="⏭ ДАЛЕЕ", command=self._go_next,
                  bg='#007bff', fg='white', font=('Arial', 12, 'bold'),
                  padx=30, pady=8).pack(side='right', padx=20)

        paned = ttk.PanedWindow(self.window, orient='horizontal')
        paned.pack(fill='both', expand=True)

        left = ttk.LabelFrame(paned, text="Документ PDF", padding=5)
        paned.add(left, weight=3)
        self.pdf_viewer = PDFViewer(left)

        center = ttk.LabelFrame(paned, text="Данные заявки", padding=10)
        paned.add(center, weight=2)
        self._build_center(center)

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

        # Форма
        ef = tk.LabelFrame(parent, text="Редактирование полей", padx=5, pady=5)
        ef.pack(fill='x', pady=5)
        ef.columnconfigure(1, weight=1)
        ef.columnconfigure(3, weight=1)

        # ФИО — строка 0, colspan 4
        tk.Label(ef, text="ФИО:", font=('Arial', 10, 'bold')).grid(
            row=0, column=0, sticky='w', pady=3)
        self.fio_entry = tk.Entry(ef, font=('Arial', 11), width=50)
        self.fio_entry.grid(row=0, column=1, columnspan=3, sticky='ew', padx=5, pady=3)
        self.fio_entry.bind('<KeyRelease>', self._on_fio_change)
        self.fio_entry.bind('<FocusOut>', self._on_fio_change)

        # Маршрут 1 | Обоснование 1
        tk.Label(ef, text="Маршрут 1:", font=('Arial', 10, 'bold')).grid(
            row=1, column=0, sticky='w', pady=3)
        self.route1_combo = ttk.Combobox(ef, font=('Arial', 10), width=28,
                                         values=self.dept_routes)
        self.route1_combo.grid(row=1, column=1, sticky='ew', padx=5, pady=3)
        self.route1_combo.bind('<<ComboboxSelected>>', self._on_route1_select)

        tk.Label(ef, text="Обоснование 1:", font=('Arial', 10, 'bold')).grid(
            row=1, column=2, sticky='w', pady=3, padx=(10, 0))
        self.reason1_combo = ttk.Combobox(ef, font=('Arial', 10), width=25,
                                          values=REASONS)
        self.reason1_combo.grid(row=1, column=3, sticky='ew', padx=5, pady=3)
        self.reason1_combo.bind('<<ComboboxSelected>>', self._on_reason1_select)
        if REASONS:
            self.reason1_combo.set(REASONS[0])

        # Дата вылета 1
        tk.Label(ef, text="Дата вылета 1:", font=('Arial', 10, 'bold')).grid(
            row=2, column=0, sticky='w', pady=3)
        self.date1_entry = tk.Entry(ef, font=('Arial', 11), width=15)
        self.date1_entry.grid(row=2, column=1, sticky='w', padx=5, pady=3)

        # Маршрут 2 | Обоснование 2
        tk.Label(ef, text="Маршрут 2:", font=('Arial', 10, 'bold')).grid(
            row=3, column=0, sticky='w', pady=3)
        self.route2_combo = ttk.Combobox(ef, font=('Arial', 10), width=28,
                                         values=self.dept_routes)
        self.route2_combo.grid(row=3, column=1, sticky='ew', padx=5, pady=3)

        tk.Label(ef, text="Обоснование 2:", font=('Arial', 10, 'bold')).grid(
            row=3, column=2, sticky='w', pady=3, padx=(10, 0))
        self.reason2_combo = ttk.Combobox(ef, font=('Arial', 10), width=25,
                                          values=REASONS)
        self.reason2_combo.grid(row=3, column=3, sticky='ew', padx=5, pady=3)

        # Дата вылета 2
        tk.Label(ef, text="Дата вылета 2:", font=('Arial', 10, 'bold')).grid(
            row=4, column=0, sticky='w', pady=3)
        self.date2_entry = tk.Entry(ef, font=('Arial', 11), width=15)
        self.date2_entry.grid(row=4, column=1, sticky='w', padx=5, pady=3)

        # Ответственный
        tk.Label(ef, text="Ответственный:", font=('Arial', 10, 'bold')).grid(
            row=5, column=0, sticky='w', pady=3)
        self.responsible_combo = ttk.Combobox(ef, font=('Arial', 10), width=28,
                                              values=self.dept_responsible)
        self.responsible_combo.grid(row=5, column=1, sticky='ew', padx=5, pady=3)
        if self.dept_responsible:
            self.responsible_combo.set(self.dept_responsible[0])

        # Метка сложного маршрута
        self.transfer_label = tk.Label(ef, text="", font=('Arial', 9, 'italic'),
                                       fg='#e94560')
        self.transfer_label.grid(row=6, column=0, columnspan=4, sticky='w', pady=2)

        # Инфо о сотруднике
        self.emp_info_label = tk.Label(ef, text="", font=('Arial', 9),
                                       fg='gray', wraplength=400)
        self.emp_info_label.grid(row=7, column=0, columnspan=4, sticky='w', pady=3)

        tk.Button(parent, text="💾 Сохранить и перейти далее",
                  command=self._save_edits,
                  bg='#ffc107', fg='black', font=('Arial', 10)).pack(fill='x', pady=5)

        # Поиск в базе
        sf = tk.Frame(parent)
        sf.pack(fill='x', pady=3)
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

        tf = tk.Frame(parent)
        tf.pack(fill='both', expand=True, pady=3)
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
        bf.pack(pady=3)
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
        if fn in self.pdf_files:
            current_doc = getattr(self.pdf_viewer.doc, 'name', '') if self.pdf_viewer.doc else ''
            if current_doc != self.pdf_files[fn]:
                self.pdf_viewer.load_pdf(self.pdf_files[fn])
            self.pdf_viewer.go_to_page(res.get('page_num', 1) - 1)
        for i in range(self.files_listbox.size()):
            if self.files_listbox.get(i) == fn:
                self.files_listbox.selection_clear(0, tk.END)
                self.files_listbox.selection_set(i)
                self.files_listbox.see(i)
                break
        total = len(self.pdf_results)
        self.nav_label.config(
            text=f"Запись {self.current_index + 1} из {total} | {fn} (стр. {res.get('page_num', '?')})")
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
            'fio':         self.fio_entry.get().strip(),
            'route':       self.route1_combo.get(),
            'date':        self.date1_entry.get().strip(),
            'reason':      self.reason1_combo.get(),
            'route2':      self.route2_combo.get(),
            'date2':       self.date2_entry.get().strip(),
            'reason2':     self.reason2_combo.get(),
            'responsible': self.responsible_combo.get(),
            'employee':    self.current_employee,
        }

    def _set_form_data(self, data: Dict):
        self.fio_entry.delete(0, 'end')
        self.fio_entry.insert(0, data.get('fio', ''))
        self.route1_combo.set(data.get('route', ''))
        self.date1_entry.delete(0, 'end')
        self.date1_entry.insert(0, data.get('date', ''))
        self.reason1_combo.set(data.get('reason', REASONS[0] if REASONS else ''))
        self.route2_combo.set(data.get('route2', ''))
        self.date2_entry.delete(0, 'end')
        self.date2_entry.insert(0, data.get('date2', ''))
        self.reason2_combo.set(data.get('reason2', ''))
        resp = data.get('responsible', '')
        self.responsible_combo.set(resp or (self.dept_responsible[0] if self.dept_responsible else ''))
        self.current_employee = data.get('employee')
        self._update_transfer_label(data.get('route', ''))

    def _load_data_to_form(self):
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
        reason1 = self.reason1_combo.get()
        # Обратный маршрут
        if reason1 not in _REASON_NO_ROUTE2:
            rev = _reverse_route(r1, self.dept_routes)
            if rev:
                self.route2_combo.set(rev)
        self._update_transfer_label(r1)

    def _on_reason1_select(self, event=None):
        reason1 = self.reason1_combo.get()
        if reason1 in _REASON_NO_ROUTE2:
            self.route2_combo.set('')
            self.reason2_combo.set('')
            self.date2_entry.delete(0, 'end')
        elif reason1 in _REASON2_AUTO:
            self.reason2_combo.set(_REASON2_AUTO[reason1])
            # Обратный маршрут если ещё не заполнен
            if not self.route2_combo.get():
                rev = _reverse_route(self.route1_combo.get(), self.dept_routes)
                if rev:
                    self.route2_combo.set(rev)

    def _update_transfer_label(self, route: str):
        """Проверяет сложный маршрут и показывает метку с городом пересадки."""
        if not route:
            self.transfer_label.config(text="")
            return
        transfer = get_transfer_city_for_route(route, self.department)
        if transfer:
            self.transfer_label.config(
                text=f"⚠ Сложный маршрут — пересадка через {transfer}")
        else:
            self.transfer_label.config(text="")

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
                                            emp.get('position', ''), emp.get('tab_num', '')))
            count += 1
            if count >= 50:
                break

    def _show_in_tree(self, emps: List[Dict]):
        self.search_tree.delete(*self.search_tree.get_children())
        for emp in emps:
            self.search_tree.insert('', 'end',
                                    values=(emp.get('fio', ''), emp.get('department', ''),
                                            emp.get('position', ''), emp.get('tab_num', '')))

    def _on_tree_select(self, event):
        self.btn_add_to_form.config(
            state='normal' if self.search_tree.selection() else 'disabled')

    def _on_tree_double_click(self, event):
        self._select_from_tree()

    def _get_emp_from_tree_item(self, iid: str) -> Optional[Dict]:
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
        record = {'original_index': self.current_index, **self._get_form_data()}
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
            transfer = get_transfer_city_for_route(rec.get('route', ''), self.department)
            mark = f" [пересадка {transfer}]" if transfer else ""
            self.saved_listbox.insert(
                'end', f"{i + 1}. {rec.get('fio', '')} ({status}){mark}")

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

            route1  = rec.get('route', '')
            route2  = rec.get('route2', '')
            reason1 = rec.get('reason', '')
            reason2 = rec.get('reason2', '')
            date1   = rec.get('date', '')
            date2   = rec.get('date2', '')
            responsible = rec.get('responsible', '')

            transfer1 = get_transfer_city_for_route(route1, self.department)
            transfer2 = get_transfer_city_for_route(route2, self.department) if route2 else ''

            def split_route(route, transfer, date, reason):
                """Разбивает маршрут через пересадку на две строки."""
                if not transfer or " - " not in route:
                    return [{'route': route, 'date': date, 'reason': reason}]
                city_from, city_to = route.split(" - ", 1)
                return [
                    {'route': f"{city_from.strip()} - {transfer}", 'date': date,  'reason': reason},
                    {'route': f"{transfer} - {city_to.strip()}",   'date': date,  'reason': reason},
                ]

            legs = split_route(route1, transfer1, date1, reason1)
            if route2:
                legs += split_route(route2, transfer2, date2, reason2)

            final.append({
                "fio":         fio,
                "legs":        legs,       # список сегментов маршрута
                "employee":    emp,
                "responsible": responsible,
                "status":      'selected' if emp else 'manual',
            })

        self.on_complete(final)
        self.window.destroy()
