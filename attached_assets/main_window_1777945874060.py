# ui/main_window.py
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QStackedWidget, QLabel
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

# Эти импорты будут работать после переноса виджетов в modules/...
from modules.hr.views.hr_tab import HRTab
from modules.daily_accounting.views.daily_tab import DailyTab
from modules.tickets.views.tickets_tab import TicketsTab
from modules.passports.views.passport_tab import PassportTab
from modules.ocr_documents.views.universal_ocr_tab import UniversalOCRTab

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EnterpriseToolkit — HR & Document Processing")
        self.setMinimumSize(1400, 800)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Боковая навигация
        self.nav_list = QListWidget()
        self.nav_list.setFixedWidth(220)
        items = [
            ("📊 HR-аналитика", 0),
            ("📅 Ежедневный учёт", 1),
            ("🎫 Заявки на билеты", 2),
            ("🛂 Паспорта", 3),
            ("🔍 Универсальный OCR", 4),
        ]
        for text, idx in items:
            item = QListWidgetItem(text)
            item.setFont(QFont("Segoe UI", 11))
            self.nav_list.addItem(item)

        self.stack = QStackedWidget()
        self.stack.addWidget(HRTab(self))
        self.stack.addWidget(DailyTab(self))
        self.stack.addWidget(TicketsTab(self))
        self.stack.addWidget(PassportTab(self))
        self.stack.addWidget(UniversalOCRTab(self))

        main_layout.addWidget(self.nav_list)
        main_layout.addWidget(self.stack)

        self.nav_list.currentRowChanged.connect(self.stack.setCurrentIndex)