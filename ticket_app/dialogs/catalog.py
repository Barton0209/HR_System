# ticket_app/dialogs/catalog.py
import tkinter as tk
from tkinter import ttk
from database import get_all_employees


class EmployeeCatalogDialog:
    """Каталог сотрудников — Excel-подобная таблица."""

    CLR_HEADER_BG = '#217346'
    CLR_HEADER_FG = '#ffffff'
    CLR_ODD       = '#ffffff'
    CLR_EVEN      = '#EEF4EE'
    CLR_ADDED     = '#C6EFCE'   # уже добавлен
    CLR_SELECTED  = '#FFEB9C'   # отмечен чекбоксом
    CLR_SEL_FG    = '#000000'
    FONT_HEADER   = ('Calibri', 10, 'bold')
    FONT_CELL     = ('Calibri', 10)
    ROW_HEIGHT    = 22

    COLUMNS = ('#', '✓', 'ФИО', 'Подразделение', 'Должность',
               'Таб. №', 'Гражданство', 'Паспорт')
    COL_WIDTHS = {
        '#': 40, '✓': 45, 'ФИО': 220, 'Подразделение': 160,
        'Должность': 160, 'Таб. №': 75, 'Гражданство': 95, 'Паспорт': 130,
    }

    def __init__(self, parent, on_select_callback):
        self.on_select = on_select_callback
        self.selected_tab_nums: set[str] = set()   # отмечены чекбоксом
        self.added_tab_nums: set[str] = set()       # уже добавлены в заявку
        self.all_employees = get_all_employees()
        self.filtered: list[dict] = self.all_employees[:]
        self._sort_col: str | None = None
        self._sort_asc = True

        self.window = tk.Toplevel(parent)
        self.window.title("Каталог сотрудников")
        self.window.geometry("1150x720")
        self.window.transient(parent)
        self.window.grab_set()
        self._build_ui()
        self._apply_style()
        self._reload()
        self.search_entry.focus()

    # ------------------------------------------------------------------
    # Стиль
    # ------------------------------------------------------------------

    def _apply_style(self):
        style = ttk.Style()
        style.configure('Catalog.Treeview',
                        font=self.FONT_CELL,
                        rowheight=self.ROW_HEIGHT,
                        background=self.CLR_ODD,
                        fieldbackground=self.CLR_ODD,
                        foreground='#000000',
                        borderwidth=0)
        style.configure('Catalog.Treeview.Heading',
                        font=self.FONT_HEADER,
                        background=self.CLR_HEADER_BG,
                        foreground=self.CLR_HEADER_FG,
                        relief='flat', padding=(4, 4))
        style.map('Catalog.Treeview',
                  background=[('selected', self.CLR_SELECTED)],
                  foreground=[('selected', self.CLR_SEL_FG)])
        style.map('Catalog.Treeview.Heading',
                  background=[('active', '#1a5c38')])

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        # ── Панель поиска ──────────────────────────────────────────────
        sf = tk.Frame(self.window, bg='#f5f5f5', pady=6)
        sf.pack(fill='x', padx=10)

        tk.Label(sf, text="🔍 Поиск:", font=('Calibri', 10, 'bold'),
                 bg='#f5f5f5').pack(side='left', padx=(0, 4))
        self.search_entry = tk.Entry(sf, font=('Calibri', 11), width=36,
                                     relief='solid', bd=1)
        self.search_entry.pack(side='left', padx=4, ipady=3)
        self.search_entry.bind('<KeyRelease>', self._on_search)
        self.search_entry.bind('<Return>', self._on_enter)

        tk.Label(sf, text="Подразделение:", font=('Calibri', 10),
                 bg='#f5f5f5').pack(side='left', padx=(14, 4))
        self.dept_combo = ttk.Combobox(sf, values=['Все'], width=22,
                                       font=('Calibri', 10), state='readonly')
        self.dept_combo.set('Все')
        self.dept_combo.pack(side='left', padx=4)
        self.dept_combo.bind('<<ComboboxSelected>>', self._on_search)

        # счётчик результатов
        self.count_lbl = tk.Label(sf, text='', font=('Calibri', 9, 'italic'),
                                  bg='#f5f5f5', fg='#555')
        self.count_lbl.pack(side='left', padx=12)

        # ── Таблица ────────────────────────────────────────────────────
        tf = tk.Frame(self.window)
        tf.pack(fill='both', expand=True, padx=10, pady=(0, 4))

        vsb = ttk.Scrollbar(tf, orient='vertical')
        hsb = ttk.Scrollbar(tf, orient='horizontal')
        vsb.pack(side='right', fill='y')
        hsb.pack(side='bottom', fill='x')

        self.tree = ttk.Treeview(
            tf, columns=self.COLUMNS, show='headings',
            style='Catalog.Treeview',
            yscrollcommand=vsb.set, xscrollcommand=hsb.set,
            selectmode='extended',
        )
        vsb.config(command=self.tree.yview)
        hsb.config(command=self.tree.xview)
        self.tree.pack(fill='both', expand=True)

        for col in self.COLUMNS:
            w = self.COL_WIDTHS.get(col, 100)
            self.tree.heading(col, text=col,
                              command=lambda c=col: self._sort_by(c))
            self.tree.column(col, width=w, minwidth=30,
                             anchor='center' if col in ('#', '✓') else 'w',
                             stretch=(col == 'ФИО'))

        self.tree.tag_configure('odd',     background=self.CLR_ODD)
        self.tree.tag_configure('even',    background=self.CLR_EVEN)
        self.tree.tag_configure('added',   background=self.CLR_ADDED)
        self.tree.tag_configure('checked', background=self.CLR_SELECTED)

        self.tree.bind('<ButtonRelease-1>', self._on_click)
        self.tree.bind('<Double-1>',        self._on_double_click)
        self.tree.bind('<space>',           self._toggle_selected)

        # ── Строка итогов ──────────────────────────────────────────────
        footer = tk.Frame(self.window, bg='#D8E4BC', height=22)
        footer.pack(fill='x', padx=10)
        self.footer_lbl = tk.Label(footer, text='', font=('Calibri', 9, 'italic'),
                                   bg='#D8E4BC', fg='#333', anchor='w')
        self.footer_lbl.pack(fill='x', padx=6)

        # ── Кнопки ─────────────────────────────────────────────────────
        bf = tk.Frame(self.window, pady=8)
        bf.pack()
        self.sel_count_lbl = tk.Label(bf, text='Отмечено: 0',
                                      font=('Calibri', 10, 'bold'))
        self.sel_count_lbl.pack(side='left', padx=16)

        btn_cfg = dict(font=('Calibri', 10), padx=18, pady=6)
        tk.Button(bf, text='☑ Добавить отмеченных',
                  command=self._add_checked,
                  bg='#217346', fg='white', **btn_cfg).pack(side='left', padx=5)
        tk.Button(bf, text='✓ Готово',
                  command=self.window.destroy,
                  bg='#0070C0', fg='white', **btn_cfg).pack(side='left', padx=5)
        tk.Button(bf, text='✕ Отмена',
                  command=self.window.destroy,
                  bg='#C00000', fg='white', **btn_cfg).pack(side='left', padx=5)

    # ------------------------------------------------------------------
    # Данные
    # ------------------------------------------------------------------

    def _reload(self):
        """Перезаполняет таблицу из self.filtered."""
        self.tree.delete(*self.tree.get_children())

        # Обновляем список подразделений
        depts = {'Все'} | {e.get('department', '') for e in self.all_employees
                           if e.get('department')}
        self.dept_combo['values'] = ['Все'] + sorted(depts - {'Все'})

        for idx, emp in enumerate(self.filtered, 1):
            tn = emp.get('tab_num', '')
            ps = f"{emp.get('doc_series', '')} {emp.get('doc_num', '')}".strip()

            if tn and tn in self.added_tab_nums:
                ch, tag = '✓', 'added'
            elif tn and tn in self.selected_tab_nums:
                ch, tag = '☑', 'checked'
            else:
                ch = '☐'
                tag = 'odd' if idx % 2 == 1 else 'even'

            self.tree.insert('', 'end', iid=str(idx), values=(
                idx, ch,
                emp.get('fio', ''),
                emp.get('department', ''),
                emp.get('position', ''),
                tn,
                emp.get('citizenship', ''),
                ps,
            ), tags=(tag,))

        total = len(self.filtered)
        added = sum(1 for e in self.filtered
                    if e.get('tab_num', '') in self.added_tab_nums)
        self.footer_lbl.config(
            text=f'  Показано: {total}  |  Всего в базе: {len(self.all_employees)}'
                 f'  |  Добавлено в заявку: {added}')
        self.count_lbl.config(text=f'Найдено: {total}')

    # ------------------------------------------------------------------
    # Поиск и фильтр
    # ------------------------------------------------------------------

    def _on_search(self, event=None):
        query = self.search_entry.get().lower().strip()
        dept  = self.dept_combo.get()
        self.filtered = [
            e for e in self.all_employees
            if (not query or any(
                query in str(e.get(f, '')).lower()
                for f in ('fio', 'position', 'tab_num', 'doc_series', 'doc_num', 'citizenship')
            ))
            and (dept == 'Все' or dept in e.get('department', ''))
        ]
        # Сброс выделения при новом поиске
        if event and hasattr(event, 'widget') and event.widget == self.search_entry:
            self.selected_tab_nums.clear()
            self.sel_count_lbl.config(text='Отмечено: 0')
        self._reload()

    def _on_enter(self, event=None):
        self._on_search()
        children = self.tree.get_children()
        if children:
            self._quick_add(children[0])

    # ------------------------------------------------------------------
    # Сортировка
    # ------------------------------------------------------------------

    def _sort_by(self, col: str):
        col_map = {
            '#': None, '✓': None,
            'ФИО': 'fio', 'Подразделение': 'department',
            'Должность': 'position', 'Таб. №': 'tab_num',
            'Гражданство': 'citizenship', 'Паспорт': None,
        }
        key = col_map.get(col)
        if not key:
            return
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True
        self.filtered.sort(key=lambda e: str(e.get(key, '')).lower(),
                           reverse=not self._sort_asc)
        arrow = ' ▲' if self._sort_asc else ' ▼'
        for c in self.COLUMNS:
            self.tree.heading(c, text=c)
        self.tree.heading(col, text=col + arrow)
        self._reload()

    # ------------------------------------------------------------------
    # Клики
    # ------------------------------------------------------------------

    def _on_click(self, event):
        """Клик по колонке '✓' — переключает чекбокс."""
        col_id = self.tree.identify_column(event.x)
        iid    = self.tree.identify_row(event.y)
        if not iid:
            return
        # Колонка '✓' — вторая (#2)
        if col_id == '#2':
            self._toggle_item(iid)

    def _on_double_click(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            self._quick_add(iid)

    def _toggle_selected(self, event=None):
        """Пробел — переключить чекбокс у выделенных строк."""
        for iid in self.tree.selection():
            self._toggle_item(iid)

    def _toggle_item(self, iid: str):
        try:
            idx = int(iid) - 1
            emp = self.filtered[idx]
        except (ValueError, IndexError):
            return
        tn = emp.get('tab_num', '')
        if tn and tn in self.added_tab_nums:
            return   # уже добавлен — не трогаем
        vals = list(self.tree.item(iid, 'values'))
        if tn in self.selected_tab_nums:
            self.selected_tab_nums.discard(tn)
            vals[1] = '☐'
            tag = 'odd' if int(iid) % 2 == 1 else 'even'
        else:
            self.selected_tab_nums.add(tn)
            vals[1] = '☑'
            tag = 'checked'
        self.tree.item(iid, values=tuple(vals), tags=(tag,))
        self.sel_count_lbl.config(text=f'Отмечено: {len(self.selected_tab_nums)}')

    # ------------------------------------------------------------------
    # Добавление
    # ------------------------------------------------------------------

    def _quick_add(self, iid: str):
        """Двойной клик / Enter — добавить одного сотрудника."""
        try:
            idx = int(iid) - 1
            emp = self.filtered[idx]
        except (ValueError, IndexError):
            return
        tn = emp.get('tab_num', '')
        if tn and tn in self.added_tab_nums:
            return
        if tn:
            self.added_tab_nums.add(tn)
        self.selected_tab_nums.discard(tn)
        self.on_select([emp])
        self._reload()

    def _add_checked(self):
        """Добавить всех отмеченных."""
        to_add = []
        for emp in self.filtered:
            tn = emp.get('tab_num', '')
            if tn in self.selected_tab_nums and tn not in self.added_tab_nums:
                to_add.append(emp)
                if tn:
                    self.added_tab_nums.add(tn)
        if to_add:
            self.on_select(to_add)
            self.selected_tab_nums.clear()
            self.sel_count_lbl.config(text='Отмечено: 0')
            self._reload()
