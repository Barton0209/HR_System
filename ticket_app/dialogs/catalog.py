# ticket_app/dialogs/catalog.py
import tkinter as tk
from tkinter import ttk
from database import get_all_employees


class EmployeeCatalogDialog:
    """Диалог выбора сотрудников из базы."""

    def __init__(self, parent, on_select_callback):
        self.on_select = on_select_callback
        self.selected_items: set[str] = set()
        self.added_tab_nums: set[str] = set()
        self.all_employees = get_all_employees()
        self.filtered_employees = self.all_employees[:]

        self.window = tk.Toplevel(parent)
        self.window.title("Каталог сотрудников")
        self.window.geometry("1100x700")
        self.window.transient(parent)
        self.window.grab_set()
        self._build_ui()
        self._load_table()
        self.search_entry.focus()

    def _build_ui(self):
        # --- Поиск ---
        sf = tk.Frame(self.window)
        sf.pack(fill='x', padx=10, pady=5)

        tk.Label(sf, text="Поиск (ФИО / Паспорт):").pack(side='left', padx=5)
        self.search_entry = tk.Entry(sf, font=('Arial', 11), width=38)
        self.search_entry.pack(side='left', padx=5)
        self.search_entry.bind('<KeyRelease>', self._filter)
        self.search_entry.bind('<Return>', self._on_enter)

        tk.Label(sf, text="Подразделение:").pack(side='left', padx=(10, 5))
        self.dept_filter = ttk.Combobox(sf, values=['Все'], width=20)
        self.dept_filter.set('Все')
        self.dept_filter.pack(side='left', padx=5)
        self.dept_filter.bind('<<ComboboxSelected>>', self._filter)

        # --- Таблица ---
        tf = tk.Frame(self.window)
        tf.pack(fill='both', expand=True, padx=10, pady=5)

        cols = ('#', 'Выбрать', 'ФИО', 'Подразделение', 'Должность', 'Таб. №',
                'Паспорт', 'Гражданство')
        self.tree = ttk.Treeview(tf, columns=cols, show='headings')
        for col in cols:
            self.tree.heading(col, text=col)
        self.tree.column('#', width=40, anchor='center')
        self.tree.column('Выбрать', width=60, anchor='center')
        self.tree.column('ФИО', width=200)
        self.tree.column('Подразделение', width=140)
        self.tree.column('Должность', width=140)
        self.tree.column('Таб. №', width=70)
        self.tree.column('Паспорт', width=130)
        self.tree.column('Гражданство', width=90)

        vsb = ttk.Scrollbar(tf, orient='vertical', command=self.tree.yview)
        hsb = ttk.Scrollbar(tf, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side='right', fill='y')
        hsb.pack(side='bottom', fill='x')
        self.tree.pack(fill='both', expand=True)

        self.tree.bind('<ButtonRelease-1>', self._on_click)
        self.tree.bind('<Double-1>', self._on_double_click)

        # --- Кнопки ---
        bf = tk.Frame(self.window)
        bf.pack(pady=10)
        self.count_label = tk.Label(bf, text="Выбрано: 0", font=('Arial', 10, 'bold'))
        self.count_label.pack(side='left', padx=20)
        tk.Button(bf, text="Добавить выбранных", command=self._add_selected,
                  bg='#28a745', fg='white', font=('Arial', 11), padx=20).pack(side='left', padx=5)
        tk.Button(bf, text="Готово", command=self.window.destroy,
                  bg='#007bff', fg='white', font=('Arial', 11), padx=20).pack(side='left', padx=5)
        tk.Button(bf, text="Отмена", command=self.window.destroy,
                  bg='#dc3545', fg='white', font=('Arial', 11), padx=20).pack(side='left', padx=5)

    def _load_table(self):
        self.tree.delete(*self.tree.get_children())
        depts = {'Все'} | {e.get('department', '') for e in self.all_employees if e.get('department')}
        self.dept_filter['values'] = sorted(depts)

        for idx, emp in enumerate(self.filtered_employees, 1):
            tn = emp.get('tab_num', '')
            ps = f"{emp.get('doc_series', '')} {emp.get('doc_num', '')}".strip()
            if tn and tn in self.added_tab_nums:
                ch = '✓'
            elif str(idx) in self.selected_items:
                ch = '☑'
            else:
                ch = '☐'
            self.tree.insert('', 'end', iid=str(idx), values=(
                idx, ch, emp.get('fio', ''), emp.get('department', ''),
                emp.get('position', ''), tn, ps, emp.get('citizenship', '')
            ))

    def _filter(self, event=None):
        query = self.search_entry.get().lower().strip()
        dept = self.dept_filter.get()
        self.filtered_employees = [
            e for e in self.all_employees
            if (not query or any(query in str(e.get(f, '')).lower()
                                 for f in ('fio', 'position', 'tab_num', 'doc_series', 'doc_num')))
            and (dept == 'Все' or dept in e.get('department', ''))
        ]
        if event and hasattr(event, 'widget') and event.widget == self.search_entry:
            self.selected_items.clear()
            self.count_label.config(text="Выбрано: 0")
        self._load_table()

    def _on_enter(self, event=None):
        self._filter()
        children = self.tree.get_children()
        if children:
            self._quick_add(children[0])

    def _on_double_click(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self._quick_add(item)

    def _quick_add(self, iid: str):
        try:
            idx = int(iid) - 1
            if 0 <= idx < len(self.filtered_employees):
                emp = self.filtered_employees[idx]
                tn = emp.get('tab_num', '')
                if tn and tn in self.added_tab_nums:
                    return
                if tn:
                    self.added_tab_nums.add(tn)
                self.on_select([emp])
                self._load_table()
        except (ValueError, IndexError):
            pass

    def _on_click(self, event):
        if self.tree.identify_column(event.x) != '#2':
            return
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        vals = list(self.tree.item(iid, 'values'))
        tn = vals[5] if len(vals) > 5 else ""
        if tn and tn in self.added_tab_nums:
            return
        if iid in self.selected_items:
            self.selected_items.discard(iid)
            vals[1] = '☐'
        else:
            self.selected_items.add(iid)
            vals[1] = '☑'
        self.tree.item(iid, values=tuple(vals))
        self.count_label.config(text=f"Выбрано: {len(self.selected_items)}")

    def _add_selected(self):
        added = []
        for iid in list(self.selected_items):
            try:
                idx = int(iid) - 1
                if 0 <= idx < len(self.filtered_employees):
                    emp = self.filtered_employees[idx]
                    tn = emp.get('tab_num', '')
                    if tn and tn in self.added_tab_nums:
                        continue
                    if tn:
                        self.added_tab_nums.add(tn)
                    added.append(emp)
            except (ValueError, IndexError):
                continue
        if added:
            self.on_select(added)
            self.selected_items.clear()
            self.count_label.config(text="Выбрано: 0")
            self._load_table()
