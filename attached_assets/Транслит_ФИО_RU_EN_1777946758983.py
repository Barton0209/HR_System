#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Транслитератор ФИО (RU → EN) с поддержкой конкретных стран:

    Азербайджан, Армения, Беларусь, Босния и Герцеговина,
    Гана, Индия, Казахстан, Киргизия, Китай, Молдова,
    Пакистан, Россия, Северная Корея, Северная Македония,
    Сербия, Сирийская Арабская Республика, Таджикистан,
    Туркмения, Турция, Узбекистан, Украина, Хорватия,
    Чёрногория

Особенности:
 • Для каждой страны – отдельная карта транслитерации.
 • Вывод «Capitalize Each Word» (Vasic Zoran, Volkov Ihar …)
   (можно переключить в полностью‑ЗАГЛАВНЫЙ режим).
 • Таблица‑виджет почти как Excel (контекстное меню, Ctrl+C/V/X,
   Delete, Ctrl+A, переход Enter/Tab, двойной клик, выделение мышью).
"""

import sys
import os
import re
import pandas as pd
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QFileDialog, QMessageBox, QLabel, QGroupBox, QMenu,
    QAbstractItemView, QLineEdit, QComboBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QAction, QKeySequence, QShortcut, QClipboard

# -------------------------------------------------------------------------
#  ТРАНСЛИТЕРАЦИОННЫЕ КАРТЫ ДЛЯ ОТДЕЛЬНЫХ СТРАН
# -------------------------------------------------------------------------

# ---------- 1. Общая карта (Казахстан, Киргизия, Таджикистан,
#                       Узбекистан, Туркмения, Россия,
#                       Индия, Гана, Китай, Пакистан, США и т.п.) ----------
CIS_MAP = {
    # Верхний регистр
    'А': 'A',  'Б': 'B',  'В': 'V',  'Г': 'G',  'Д': 'D',
    'Е': 'E',  'Ё': 'Yo','Ж': 'Zh','З': 'Z',  'И': 'I',
    'Й': 'Y',  'К': 'K',  'Л': 'L',  'М': 'M',  'Н': 'N',
    'О': 'O',  'П': 'P',  'Р': 'R',  'С': 'S',  'Т': 'T',
    'У': 'U',  'Ф': 'F',  'Х': 'Kh','Ц': 'Ts','Ч': 'Ch',
    'Ш': 'Sh','Щ': 'Shch','Ъ': '','Ы': 'Y','Ь': '',
    'Э': 'E',  'Ю': 'Yu','Я': 'Ya',
    # Нижний регистр
    'а': 'a','б': 'b','в': 'v','г': 'g','д': 'd',
    'е': 'e','ё': 'yo','ж': 'zh','з': 'z','и': 'i',
    'й': 'y','к': 'k','л': 'l','м': 'm','н': 'n',
    'о': 'o','п': 'p','р': 'r','с': 's','т': 't',
    'у': 'u','ф': 'f','х': 'kh','ц': 'ts','ч': 'ch',
    'ш': 'sh','щ': 'shch','ъ':'','ы':'y','ь':'',
    'э': 'e','ю': 'yu','я': 'ya',
}

# ---------- 2. Беларусь (офиц. латиница) ----------
BELARUS_MAP = {
    # Верхний регистр
    'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'H', 'Д': 'D',
    'Е': 'E', 'Ё': 'Yo','Ж': 'Zh','З': 'Z', 'І': 'I',
    'Й': 'J', 'К': 'K', 'Л': 'L', 'М': 'M', 'Н': 'N',
    'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T',
    'У': 'U', 'Ў': 'U', 'Ф': 'F', 'Х': 'Kh','Ц': 'Ts',
    'Ч': 'C', 'Ш': 'S', 'Щ': 'S', 'Ь': '',
    'Ы': 'Y', 'Э': 'E', 'Ю': 'Ju','Я': 'Ja',
    'И': 'I',
    # Нижний регистр
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'h', 'д': 'd',
    'е': 'e', 'ё': 'yo','ж': 'zh','з': 'z','і': 'i',
    'й': 'j', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n',
    'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't',
    'у': 'u', 'ў': 'u', 'ф': 'f', 'х': 'kh','ц': 'ts',
    'ч': 'c', 'ш': 's', 'щ': 's', 'ь': '',
    'ы': 'y', 'э': 'e', 'ю': 'ju','я': 'ja',
    'и': 'i',
}

# ---------- 3. Сербия (упрощённая карта без диакритики) ----------
SERBIAN_MAP = {
    'А':'A','Б':'B','В':'V','Г':'G','Д':'D','Е':'E','Ё':'E',
    'Ж':'Z','З':'Z','И':'I','Й':'J','К':'K','Л':'L','М':'M',
    'Н':'N','О':'O','П':'P','Р':'R','С':'S','Т':'T','У':'U',
    'Ф':'F','Х':'H','Ц':'C','Ч':'C','Ш':'S','Щ':'S',
    'Ъ':'','Ы':'Y','Ь':'','Э':'E','Ю':'Ju','Я':'Ja',
    'а':'a','б':'b','в':'v','г':'h','д':'d','е':'e','ё':'e',
    'ж':'z','з':'z','и':'i','й':'j','к':'k','л':'l','м':'m',
    'н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u',
    'ф':'f','х':'h','ц':'c','ч':'c','ш':'s','щ':'s',
    'ъ':'','ы':'y','ь':'','э':'e','ю':'ju','я':'ja',
    'И':'I','и':'i',               # И сохраняется
}

# ---------- 4. Босния‑Херцеговина, Хорватия, Черногория (латиница с диакритикой) ----------
BOSNIAN_CROATIAN_MAP = {
    # Верхний регистр
    'А':'A','Б':'B','В':'V','Г':'G','Д':'D','Ђ':'Đ','Е':'E','Ж':'Ž',
    'З':'Z','И':'I','Ј':'J','К':'K','Л':'L','Љ':'Lj','М':'M','Н':'N',
    'Њ':'Nj','О':'O','П':'P','Р':'R','С':'S','Т':'T','Ћ':'Ć','У':'U',
    'Ф':'F','Х':'H','Ц':'C','Ч':'Č','Џ':'Dž','Ш':'Š',
    # Нижний регистр
    'а':'a','б':'b','в':'v','г':'g','д':'d','ђ':'đ','е':'e','ж':'ž',
    'з':'z','и':'i','ј':'j','к':'k','л':'l','љ':'lj','м':'m','н':'n',
    'њ':'nj','о':'o','п':'p','р':'r','с':'s','т':'t','ћ':'ć','у':'u',
    'ф':'f','х':'h','ц':'c','ч':'č','џ':'dž','ш':'š',
    # Остальные буквы обычные
    'Ё':'Yo','ё':'yo','Й':'J','й':'j','Ы':'Y','ы':'y','Ь':'','ь':'',
    'Ъ':'','ъ':'','Э':'E','э':'e','Ю':'Yu','ю':'yu','Я':'Ya','я':'ya',
}

# ---------- 5. Азербайджан (латиница) ----------
AZERBAIJAN_MAP = {
    'А':'A','а':'a','Б':'B','б':'b','В':'V','в':'v','Г':'G','г':'g','Д':'D','д':'d',
    'Е':'E','е':'e','Ё':'Yo','ё':'yo','Ж':'J','ж':'j','З':'Z','з':'z','И':'I','и':'i',
    'Й':'Y','й':'y','К':'K','к':'k','Қ':'Q','қ':'q','Л':'L','л':'l','М':'M','м':'m',
    'Н':'N','н':'n','О':'O','о':'o','П':'P','п':'p','Р':'R','р':'r','С':'S','с':'s',
    'Т':'T','т':'t','У':'U','у':'u','Ү':'Ü','ү':'ü','Ф':'F','ф':'f','Х':'X','х':'x',
    'Һ':'H','һ':'h','Ц':'Ts','ц':'ts','Ч':'Ç','ч':'ç','Ш':'Ş','ш':'ş','Щ':'Şç','щ':'şç',
    'Ы':'I','ы':'i','Ь':'','ь':'','Э':'E','э':'e','Ю':'Yu','ю':'yu','Я':'Ya','я':'ya',
    'Ә':'Ä','ә':'ä','İ':'İ','ı':'i','Ğ':'Ğ','ğ':'ğ','Ö':'Ö','ö':'ö','Ş':'Ş','ş':'ş','Ç':'Ç','ç':'ç',
    'Ъ':'','ъ':'',
}

# ---------- 6. Армения (обычная русская карта) ----------
ARMENIA_MAP = CIS_MAP

# ---------- 7. Северная Македония ----------
MACEDONIA_MAP = {
    # Верхний регистр
    'А':'A','Б':'B','В':'V','Г':'G','Д':'D','Ѓ':'Gj','Е':'E','Ж':'Zh',
    'З':'Z','И':'I','Ј':'J','К':'K','Л':'L','Љ':'Lj','М':'M','Н':'N',
    'Њ':'Nj','О':'O','П':'P','Р':'R','С':'S','Т':'T','Ќ':'Kj','У':'U',
    'Ф':'F','Х':'H','Ц':'C','Ч':'Ch','Џ':'Dzh','Ш':'Sh',
    # Нижний регистр
    'а':'a','б':'b','в':'v','г':'g','д':'d','ѓ':'gj','е':'e','ж':'zh',
    'з':'z','и':'i','ј':'j','к':'k','л':'l','љ':'lj','м':'m','н':'n',
    'њ':'nj','о':'o','п':'p','р':'r','с':'s','т':'t','ќ':'kj','у':'u',
    'ф':'f','х':'h','ц':'c','ч':'ch','џ':'dzh','ш':'sh',
    # Оставшиеся обычные
    'Ё':'Yo','ё':'yo','Й':'Y','й':'y','Ы':'Y','ы':'y','Ь':'','ь':'',
    'Ъ':'','ъ':'','Э':'E','э':'e','Ю':'Yu','ю':'yu','Я':'Ya','я':'ya',
}

# ---------- 8. Украина ----------
UKRAINE_MAP = {
    # Верхний регистр
    'А':'A','Б':'B','В':'V','Г':'H','Ґ':'G','Д':'D','Е':'E','Є':'Ye',
    'Ж':'Zh','З':'Z','И':'Y','І':'I','Ї':'Yi','Й':'Y','К':'K','Л':'L',
    'М':'M','Н':'N','О':'O','П':'P','Р':'R','С':'S','Т':'T','У':'U',
    'Ф':'F','Х':'Kh','Ц':'Ts','Ч':'Ch','Ш':'Sh','Щ':'Shch','Ю':'Yu','Я':'Ya',
    'Ы':'Y','Э':'E','Ь':'','Ъ':'',
    # Нижний регистр
    'а':'a','б':'b','в':'v','г':'h','ґ':'g','д':'d','е':'e','є':'ye',
    'ж':'zh','з':'z','и':'y','і':'i','ї':'yi','й':'y','к':'k','л':'l',
    'м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u',
    'ф':'f','х':'kh','ц':'ts','ч':'ch','ш':'sh','щ':'shch','ю':'yu','я':'ya',
    'ы':'y','э':'e','ь':'','ъ':'',
}

# -------------------------------------------------------------------------
#  Выбор карты в зависимости от гражданства (по имени страны)
# -------------------------------------------------------------------------
def get_translit_map(citizenship: str):
    """
    Возвращает нужную карту транслитерации в зависимости от названия страны.
    Сравнение – регистронезависимое, без учёта пробелов/запятых.
    """
    low = citizenship.lower().replace(',', '').replace(' ', '')

    # страна → карта
    if any(s in low for s in ('azerbaij', 'azerbaij', 'azerbaij')):
        return AZERBAIJAN_MAP
    if any(s in low for s in ('armeni',)):
        return ARMENIA_MAP
    if any(s in low for s in ('belarus', 'беларус')):
        return BELARUS_MAP
    if any(s in low for s in ('bosni', 'bosnia', 'herzegovina')):
        return BOSNIAN_CROATIAN_MAP
    if any(s in low for s in ('croati',)):
        return BOSNIAN_CROATIAN_MAP
    if any(s in low for s in ('montenegro', 'черногори')):
        return BOSNIAN_CROATIAN_MAP
    if any(s in low for s in ('gana',)):
        return CIS_MAP                      # латиница уже в нужном виде
    if any(s in low for s in ('india',)):
        return CIS_MAP
    if any(s in low for s in ('kazakhstan', 'kazakstan')):
        return CIS_MAP
    if any(s in low for s in ('kyrgyzstan', 'kirgiz')):
        return CIS_MAP
    if any(s in low for s in ('china',)):
        return CIS_MAP
    if any(s in low for s in ('moldova',)):
        return CIS_MAP
    if any(s in low for s in ('pakistan',)):
        return CIS_MAP
    if any(s in low for s in ('russia', 'россия')):
        return CIS_MAP
    if any(s in low for s in ('northkorea', 'severnakore')):
        return CIS_MAP
    if any(s in low for s in ('macedonia', 'northmaced')):
        return MACEDONIA_MAP
    if any(s in low for s in ('serbia',)):
        return SERBIAN_MAP
    if any(s in low for s in ('syria',)):
        return CIS_MAP
    if any(s in low for s in ('tajikistan',)):
        return CIS_MAP
    if any(s in low for s in ('turkmenistan',)):
        return CIS_MAP
    if any(s in low for s in ('turkey',)):
        return CIS_MAP
    if any(s in low for s in ('uzbekistan',)):
        return CIS_MAP
    if any(s in low for s in ('ukraine',)):
        return UKRAINE_MAP
    # По‑умолчанию – обычная CIS‑карта
    return CIS_MAP

# -------------------------------------------------------------------------
#  Основная функция транслитерации
# -------------------------------------------------------------------------
UPPERCASE = False      # True → полностью заглавные (VOLKOV IHAR …)

def transliterate_text(text: str, citizenship: str) -> str:
    """Транслитерирует строку `text` согласно правилам страны `citizenship`."""
    if not text:
        return ""

    trans_map = get_translit_map(citizenship)

    # 1️⃣ Транслитерация символов
    result = []
    for ch in text:
        if ch in trans_map:
            result.append(trans_map[ch])
        else:
            # оставляем латиницу, цифры, пробелы, дефисы
            if re.match(r'[A-Za-z0-9\s\-]', ch):
                result.append(ch)
    translit = ''.join(result)

    # 2️⃣ Приведение к формату «Capitalize Each Word» (или все‑заглавные)
    translit = translit.title()
    if UPPERCASE:
        translit = translit.upper()
    return translit

# -------------------------------------------------------------------------
#  Excel‑подобная таблица (минимум кода, максимум удобства)
# -------------------------------------------------------------------------
class ExcelLikeTable(QTableWidget):
    """Таблица‑виджет, почти как настоящий Excel."""
    def __init__(self, rows: int, columns: int):
        super().__init__(rows, columns)
        self._setup_behavior()

    # ----------------------------------------------------- Поведение
    def _setup_behavior(self):
        self.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.setSelectionMode(QAbstractItemView.ContiguousSelection)
        self.setEditTriggers(QAbstractItemView.DoubleClicked |
                             QAbstractItemView.EditKeyPressed)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setDefaultSectionSize(25)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)

        # контекстное меню по правому клику
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # горячие клавиши
        self._setup_shortcuts()

    def _setup_shortcuts(self):
        QShortcut(QKeySequence.Copy,   self, self.copy_selection)
        QShortcut(QKeySequence.Paste,  self, self.paste_selection)
        QShortcut(QKeySequence.Cut,    self, self.cut_selection)
        QShortcut(QKeySequence.Delete, self, self.clear_selection)
        QShortcut(QKeySequence.SelectAll, self, self.selectAll)

    # ----------------------------------------------------- Контекст‑меню
    def _show_context_menu(self, pos):
        menu = QMenu(self)
        menu.addAction(QAction("Копировать (Ctrl+C)", self,
                              triggered=self.copy_selection))
        menu.addAction(QAction("Вставить (Ctrl+V)", self,
                              triggered=self.paste_selection))
        menu.addAction(QAction("Вырезать (Ctrl+X)", self,
                              triggered=self.cut_selection))
        menu.addAction(QAction("Очистить (Delete)", self,
                              triggered=self.clear_selection))
        menu.addSeparator()
        menu.addAction(QAction("Выделить всё (Ctrl+A)", self,
                              triggered=self.selectAll))
        menu.exec_(self.mapToGlobal(pos))

    # ----------------------------------------------------- Буфер обмена
    def copy_selection(self):
        ranges = self.selectedRanges()
        if not ranges:
            return
        txt = ""
        for r in ranges:
            for row in range(r.topRow(), r.bottomRow() + 1):
                line = []
                for col in range(r.leftColumn(), r.rightColumn() + 1):
                    it = self.item(row, col)
                    line.append(it.text() if it else "")
                txt += "\t".join(line) + "\n"
        QApplication.clipboard().setText(txt.strip())

    def paste_selection(self):
        txt = QApplication.clipboard().text()
        if not txt:
            return
        cur_r, cur_c = self.currentRow(), self.currentColumn()
        rows = txt.split("\n")
        for i, line in enumerate(rows):
            if not line:
                continue
            cells = line.split("\t")
            for j, cell in enumerate(cells):
                r = cur_r + i
                c = cur_c + j
                if r < self.rowCount() and c < self.columnCount():
                    it = self.item(r, c)
                    if not it:
                        it = QTableWidgetItem("")
                        self.setItem(r, c, it)
                    it.setText(cell)

    def cut_selection(self):
        self.copy_selection()
        self.clear_selection()

    def clear_selection(self):
        for it in self.selectedItems():
            it.setText("")

    # ----------------------------------------------------- Навигация клавиатурой
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Enter, Qt.Key_Return):
            r = self.currentRow()
            c = self.currentColumn()
            if event.modifiers() & Qt.ShiftModifier:
                r = max(0, r - 1)
            else:
                r = min(self.rowCount() - 1, r + 1)
            self.setCurrentCell(r, c)
            event.accept()
        elif event.key() == Qt.Key_Tab:
            r = self.currentRow()
            c = self.currentColumn()
            c = min(self.columnCount() - 1, c + 1)
            self.setCurrentCell(r, c)
            event.accept()
        elif event.key() == Qt.Key_Backtab:
            r = self.currentRow()
            c = self.currentColumn()
            c = max(0, c - 1)
            self.setCurrentCell(r, c)
            event.accept()
        else:
            super().keyPressEvent(event)


# -------------------------------------------------------------------------
#  Основное окно программы (современный дизайн)
# -------------------------------------------------------------------------
class ModernTranslitApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🚀 Транслитератор ФИО – Excel‑режим")
        self.setGeometry(50, 50, 1400, 900)

        # --------------------- палитра цветов
        self.colors = {
            'primary':        '#2563eb',
            'primary_hover':  '#1d4ed8',
            'bg':             '#f8fafc',
            'card':           '#ffffff',
            'text':           '#1e293b',
            'text_secondary': '#64748b',
            'border':         '#e2e8f0'
        }
        self._apply_styles()
        self._build_ui()

    # -----------------------------------------------------------------
    #  Стиль (CSS)
    # -----------------------------------------------------------------
    def _apply_styles(self):
        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {self.colors['bg']}; }}
            QWidget {{ font-family: 'Segoe UI', Arial, sans-serif; }}
            QPushButton {{
                background-color: {self.colors['primary']};
                color: white; border: none;
                padding: 8px 12px; border-radius: 6px;
                font-weight: 600; font-size: 11px;
            }}
            QPushButton:hover {{ background-color: {self.colors['primary_hover']}; }}
            QPushButton:disabled {{ background-color: #cbd5e1; color:#94a3b8; }}
            QGroupBox {{
                font-weight: bold; font-size: 12px;
                color: {self.colors['text']};
                border: 1px solid {self.colors['border']};
                border-radius: 8px; margin-top: 8px;
                padding-top: 12px; background-color: {self.colors['card']};
            }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 12px;
                               padding: 0 6px; color: {self.colors['primary']}; }}
            QTableWidget {{
                background-color: white; border: 1px solid #d1d5db;
                gridline-color: #e5e7eb; font-size: 11px;
                selection-background-color: #dbeafe;
                selection-color: black;
            }}
            QHeaderView::section {{
                background-color: {self.colors['primary']};
                color: white; padding: 6px 8px; border: none;
                font-weight: 600; font-size: 10px;
            }}
            QLabel {{ color: {self.colors['text']}; font-size: 11px; }}
        """)

    # -----------------------------------------------------------------
    #  Построение UI
    # -----------------------------------------------------------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        lo = QVBoxLayout(central)
        lo.setSpacing(10)
        lo.setContentsMargins(15, 15, 15, 15)

        # --------------------- заголовок
        hdr = QLabel("🌍 Транслитератор ФИО (RU → EN) – Excel‑режим")
        hdr.setFont(QFont("Segoe UI", 16, QFont.Bold))
        hdr.setStyleSheet(f"color:{self.colors['primary']}; margin-bottom:8px;")
        hdr.setAlignment(Qt.AlignCenter)
        lo.addWidget(hdr)

        # --------------------- панель инструментов
        toolbar = QHBoxLayout()
        self.btn_load   = QPushButton("📁 Загрузить Excel")
        self.btn_save   = QPushButton("💾 Сохранить")
        self.btn_clear  = QPushButton("🗑️ Очистить")
        self.btn_transl = QPushButton("🔄 Транслит")
        self.btn_copy_all = QPushButton("📋 Копировать всё")
        self.btn_copy_en  = QPushButton("🔤 Копировать EN")
        for b in (self.btn_load, self.btn_save, self.btn_clear,
                  self.btn_transl, self.btn_copy_all, self.btn_copy_en):
            b.setMaximumWidth(120)
            toolbar.addWidget(b)
        toolbar.addStretch()
        lo.addLayout(toolbar)

        # --------------------- таблица
        self.table = ExcelLikeTable(500, 3)            # 500 строк стартом
        self.table.setHorizontalHeaderLabels(
            ["Гражданство", "ФИО (RU)", "ФИО (EN)"])
        self.table.setColumnWidth(0, 150)   # гражданство
        self.table.setColumnWidth(1, 400)   # ФИО RU
        self.table.setColumnWidth(2, 400)   # ФИО EN
        # делаем колонку EN только для чтения
        for r in range(500):
            it = QTableWidgetItem("")
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(r, 2, it)
        lo.addWidget(self.table)

        # --------------------- статус‑панель (как в Excel)
        status = QHBoxLayout()
        self.lbl_status = QLabel("Готов")
        self.lbl_status.setStyleSheet(
            f"color:{self.colors['text_secondary']}; font-size:10px; "
            f"border:1px solid {self.colors['border']}; padding:2px 8px;")
        self.lbl_cell = QLabel("A1")
        self.lbl_cell.setStyleSheet(
            f"color:{self.colors['text']}; font-size:10px; "
            f"border:1px solid {self.colors['border']}; padding:2px 8px;")
        self.lbl_cell.setMinimumWidth(50)
        status.addWidget(self.lbl_status)
        status.addStretch()
        status.addWidget(self.lbl_cell)
        lo.addLayout(status)

        # --------------------- сигналы/слоты
        self.btn_load.clicked.connect(self.load_excel)
        self.btn_save.clicked.connect(self.save_excel)
        self.btn_clear.clicked.connect(self.clear_table)
        self.btn_transl.clicked.connect(self.transliterate_all)
        self.btn_copy_all.clicked.connect(self.copy_all)
        self.btn_copy_en.clicked.connect(self.copy_en)

        self.table.currentCellChanged.connect(self._update_status_cell)
        self.table.cellChanged.connect(self._update_status_cell)

    # -----------------------------------------------------------------
    #  Обновление индикатора текущей ячейки
    # -----------------------------------------------------------------
    def _update_status_cell(self, row=None, col=None, *_):
        if row is None:
            row = self.table.currentRow()
        if col is None:
            col = self.table.currentColumn()
        self.lbl_cell.setText(f"{chr(65 + col)}{row + 1}")

    # -----------------------------------------------------------------
    #  Очистка таблицы
    # -----------------------------------------------------------------
    def clear_table(self):
        for r in range(self.table.rowCount()):
            for c in range(self.table.columnCount()):
                it = self.table.item(r, c)
                if it:
                    it.setText("")
        self.lbl_status.setText("Таблица очищена")

    # -----------------------------------------------------------------
    #  Загрузка из Excel‑файла
    # -----------------------------------------------------------------
    def load_excel(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Открыть Excel", "",
            "Excel Files (*.xlsx *.xls);;All Files (*)")
        if not path:
            return
        try:
            df = pd.read_excel(
                path, usecols=[0, 1], header=None,
                names=['Citizenship', 'FIO_RU'])
            self.clear_table()
            for i, row in df.iterrows():
                if i >= self.table.rowCount():
                    break
                self.table.setItem(i, 0,
                                   QTableWidgetItem(str(row['Citizenship'])))
                self.table.setItem(i, 1,
                                   QTableWidgetItem(str(row['FIO_RU'])))
            self.lbl_status.setText(
                f"Загружено {min(len(df), self.table.rowCount())} строк")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка",
                                 f"Не удалось загрузить файл:\n{e}")

    # -----------------------------------------------------------------
    #  Транслитерация всех заполненных строк
    # -----------------------------------------------------------------
    def transliterate_all(self):
        processed = 0
        for r in range(self.table.rowCount()):
            cit_it = self.table.item(r, 0)
            fio_it = self.table.item(r, 1)
            if cit_it and fio_it and fio_it.text().strip():
                result = transliterate_text(fio_it.text(),
                                           cit_it.text())
                en_it = self.table.item(r, 2)
                en_it.setText(result)
                processed += 1
        self.lbl_status.setText(f"Транслитерировано {processed} записей")

    # -----------------------------------------------------------------
    #  Сохранение в Excel‑файл
    # -----------------------------------------------------------------
    def save_excel(self):
        rows = []
        for r in range(self.table.rowCount()):
            cit = self.table.item(r, 0).text() if self.table.item(r, 0) else ""
            ru  = self.table.item(r, 1).text() if self.table.item(r, 1) else ""
            en  = self.table.item(r, 2).text() if self.table.item(r, 2) else ""
            if any([cit.strip(), ru.strip(), en.strip()]):
                rows.append([cit, ru, en])
        if not rows:
            QMessageBox.warning(self, "Внимание",
                                "Нет данных для сохранения")
            return
        df = pd.DataFrame(rows,
                          columns=["Гражданство", "ФИО (RU)", "ФИО (EN)"])
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить результат", "EN_результат.xlsx",
            "Excel Files (*.xlsx)")
        if not path:
            return
        try:
            df.to_excel(path, index=False)
            self.lbl_status.setText(
                f"Файл сохранён: {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка",
                                 f"Не удалось сохранить файл:\n{e}")

    # -----------------------------------------------------------------
    #  Копировать всё / только EN‑колонку
    # -----------------------------------------------------------------
    def copy_all(self):
        self.table.selectAll()
        self.table.copy_selection()
        self.lbl_status.setText("Все данные скопированы в буфер")

    def copy_en(self):
        txt = ""
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 2)
            if it and it.text().strip():
                txt += it.text() + "\n"
        if txt:
            QApplication.clipboard().setText(txt.strip())
            self.lbl_status.setText("EN‑колонка скопирована")
        else:
            QMessageBox.warning(self, "Внимание",
                                "В колонке EN нет данных")

# -------------------------------------------------------------------------
#  Точка входа
# -------------------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")          # современный набор стилей
    win = ModernTranslitApp()
    win.show()
    sys.exit(app.exec())
