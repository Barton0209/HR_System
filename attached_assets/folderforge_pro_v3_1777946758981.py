#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FolderForge Pro - Advanced Folder Creation Tool
PyQt6 Edition with Responsive UI Design
"""

import sys
import os
import re
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

import pandas as pd
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QComboBox, QTableWidget, QTableWidgetItem,
    QFileDialog, QMessageBox, QProgressBar, QTextEdit, QGroupBox,
    QSplitter, QHeaderView, QMenuBar, QMenu, QToolBar, QStatusBar,
    QDialog, QDialogButtonBox, QCheckBox, QSpinBox, QDoubleSpinBox,
    QGridLayout, QFrame, QSizePolicy, QSpacerItem, QTabWidget,
    QListWidget, QListWidgetItem, QAbstractItemView, QScrollArea
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QSize, QSettings, QTimer, QPoint
)
from PyQt6.QtGui import (
    QIcon, QFont, QFontDatabase, QPalette, QColor, QDragEnterEvent, QDropEvent,
    QAction, QKeySequence, QFontMetrics
)

import ctypes  # Для Windows API (опционально)
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StructureType(Enum):
    FLAT = "flat"
    ALPHABETICAL = "alphabetical"
    BY_DATE = "by_date"
    BY_FIRST_WORD = "by_first_word"


@dataclass
class FolderConfig:
    structure_type: StructureType = StructureType.FLAT
    remove_duplicates: bool = True
    validate_names: bool = True
    create_log: bool = True
    open_after_creation: bool = True
    date_format: str = "%Y-%m-%d"
    prefix: str = ""
    suffix: str = ""


class ModernStyle:
    """Modern Catppuccin Mocha Theme with Responsive Typography"""

    # Colors
    BASE = "#1e1e2e"
    MANTLE = "#181825"
    CRUST = "#11111b"
    SURFACE0 = "#313244"
    SURFACE1 = "#45475a"
    SURFACE2 = "#585b70"
    OVERLAY0 = "#6c7086"
    OVERLAY1 = "#7f849c"
    OVERLAY2 = "#9399b2"
    TEXT = "#cdd6f4"
    SUBTEXT0 = "#a6adc8"
    SUBTEXT1 = "#bac2de"
    BLUE = "#89b4fa"
    LAVENDER = "#b4befe"
    SAPPHIRE = "#74c7ec"
    SKY = "#89dceb"
    TEAL = "#94e2d5"
    GREEN = "#a6e3a1"
    YELLOW = "#f9e2af"
    PEACH = "#fab387"
    MAROON = "#eba0ac"
    RED = "#f38ba8"
    MAUVE = "#cba6f7"
    PINK = "#f5c2e7"
    FLAMINGO = "#f2cdcd"
    ROSEWATER = "#f5e0dc"

    # Typography Scale (responsive)
    FONT_FAMILY = "Segoe UI", "SF Pro Display", "Helvetica Neue", "Arial", "sans-serif"

    @classmethod
    def get_font_sizes(cls, base_size: int = 10) -> Dict[str, int]:
        """Calculate font sizes based on base size"""
        return {
            'tiny': int(base_size * 0.75),      # 7.5pt
            'small': int(base_size * 0.875),    # 8.75pt
            'normal': base_size,                 # 10pt
            'medium': int(base_size * 1.125),   # 11.25pt
            'large': int(base_size * 1.25),     # 12.5pt
            'xlarge': int(base_size * 1.5),     # 15pt
            'xxlarge': int(base_size * 1.75),   # 17.5pt
            'huge': int(base_size * 2),         # 20pt
            'title': int(base_size * 2.5),      # 25pt
        }

    @classmethod
    def get_stylesheet(cls, base_font_size: int = 10) -> str:
        fonts = cls.get_font_sizes(base_font_size)

        return f"""
        QMainWindow, QDialog {{
            background-color: {cls.BASE};
            color: {cls.TEXT};
            font-family: "Segoe UI", "SF Pro Display", "Helvetica Neue", Arial, sans-serif;
            font-size: {fonts['normal']}pt;
        }}

        QWidget {{
            background-color: {cls.BASE};
            color: {cls.TEXT};
            font-size: {fonts['normal']}pt;
        }}

        /* === TYPOGRAPHY === */
        QLabel {{
            color: {cls.TEXT};
            font-size: {fonts['normal']}pt;
            padding: 4px 0px;
        }}

        QLabel[class="title"] {{
            font-size: {fonts['title']}pt;
            font-weight: 700;
            color: {cls.LAVENDER};
            padding: 16px 0px 8px 0px;
        }}

        QLabel[class="subtitle"] {{
            font-size: {fonts['xlarge']}pt;
            font-weight: 600;
            color: {cls.BLUE};
            padding: 12px 0px 6px 0px;
        }}

        QLabel[class="heading"] {{
            font-size: {fonts['large']}pt;
            font-weight: 600;
            color: {cls.TEXT};
            padding: 8px 0px 4px 0px;
        }}

        QLabel[class="caption"] {{
            font-size: {fonts['small']}pt;
            color: {cls.SUBTEXT0};
            padding: 2px 0px;
        }}

        /* === BUTTONS === */
        QPushButton {{
            background-color: {cls.SURFACE0};
            color: {cls.TEXT};
            border: 1px solid {cls.SURFACE1};
            border-radius: 8px;
            padding: 10px 20px;
            font-size: {fonts['normal']}pt;
            font-weight: 500;
            min-width: 100px;
            min-height: 20px;
        }}

        QPushButton:hover {{
            background-color: {cls.SURFACE1};
            border-color: {cls.SURFACE2};
        }}

        QPushButton:pressed {{
            background-color: {cls.SURFACE2};
        }}

        QPushButton:disabled {{
            background-color: {cls.CRUST};
            color: {cls.OVERLAY0};
            border-color: {cls.SURFACE0};
        }}

        QPushButton[class="primary"] {{
            background-color: {cls.BLUE};
            color: {cls.CRUST};
            border: none;
            font-weight: 600;
            padding: 12px 24px;
        }}

        QPushButton[class="primary"]:hover {{
            background-color: {cls.SAPPHIRE};
        }}

        QPushButton[class="success"] {{
            background-color: {cls.GREEN};
            color: {cls.CRUST};
            border: none;
            font-weight: 600;
        }}

        QPushButton[class="danger"] {{
            background-color: {cls.RED};
            color: {cls.CRUST};
            border: none;
            font-weight: 600;
        }}

        QPushButton[class="icon-button"] {{
            min-width: 36px;
            min-height: 36px;
            max-width: 36px;
            max-height: 36px;
            padding: 0px;
            border-radius: 6px;
            font-size: {fonts['large']}pt;
        }}

        /* === INPUT FIELDS === */
        QLineEdit, QTextEdit, QComboBox {{
            background-color: {cls.SURFACE0};
            color: {cls.TEXT};
            border: 2px solid {cls.SURFACE1};
            border-radius: 6px;
            padding: 8px 12px;
            font-size: {fonts['normal']}pt;
            min-height: 20px;
        }}

        QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
            border-color: {cls.BLUE};
        }}

        QLineEdit:disabled, QTextEdit:disabled, QComboBox:disabled {{
            background-color: {cls.CRUST};
            color: {cls.OVERLAY0};
        }}

        QComboBox::drop-down {{
            border: none;
            width: 30px;
        }}

        QComboBox QAbstractItemView {{
            background-color: {cls.SURFACE0};
            color: {cls.TEXT};
            selection-background-color: {cls.BLUE};
            selection-color: {cls.CRUST};
            border: 1px solid {cls.SURFACE1};
        }}

        /* === TABLES === */
        QTableWidget {{
            background-color: {cls.MANTLE};
            color: {cls.TEXT};
            border: 1px solid {cls.SURFACE0};
            border-radius: 8px;
            gridline-color: {cls.SURFACE0};
            font-size: {fonts['normal']}pt;
        }}

        QTableWidget::item {{
            padding: 8px 12px;
            border-bottom: 1px solid {cls.SURFACE0};
        }}

        QTableWidget::item:selected {{
            background-color: {cls.BLUE};
            color: {cls.CRUST};
        }}

        QHeaderView::section {{
            background-color: {cls.SURFACE0};
            color: {cls.TEXT};
            padding: 10px 12px;
            border: none;
            border-bottom: 2px solid {cls.SURFACE1};
            font-weight: 600;
            font-size: {fonts['small']}pt;
        }}

        QHeaderView::section:hover {{
            background-color: {cls.SURFACE1};
        }}

        /* === GROUP BOXES === */
        QGroupBox {{
            background-color: {cls.MANTLE};
            border: 1px solid {cls.SURFACE0};
            border-radius: 12px;
            margin-top: 16px;
            padding-top: 16px;
            font-size: {fonts['medium']}pt;
            font-weight: 600;
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 16px;
            padding: 0px 12px;
            color: {cls.LAVENDER};
        }}

        /* === PROGRESS BAR === */
        QProgressBar {{
            background-color: {cls.SURFACE0};
            border: none;
            border-radius: 6px;
            height: 8px;
            text-align: center;
            font-size: {fonts['small']}pt;
        }}

        QProgressBar::chunk {{
            background-color: {cls.BLUE};
            border-radius: 6px;
        }}

        /* === SCROLL BARS === */
        QScrollBar:vertical {{
            background-color: {cls.CRUST};
            width: 12px;
            border-radius: 6px;
        }}

        QScrollBar::handle:vertical {{
            background-color: {cls.SURFACE0};
            border-radius: 6px;
            min-height: 30px;
        }}

        QScrollBar::handle:vertical:hover {{
            background-color: {cls.SURFACE1};
        }}

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}

        /* === TABS === */
        QTabWidget::pane {{
            border: 1px solid {cls.SURFACE0};
            border-radius: 8px;
            background-color: {cls.MANTLE};
        }}

        QTabBar::tab {{
            background-color: {cls.SURFACE0};
            color: {cls.SUBTEXT0};
            padding: 10px 20px;
            margin-right: 4px;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            font-size: {fonts['normal']}pt;
        }}

        QTabBar::tab:selected {{
            background-color: {cls.BLUE};
            color: {cls.CRUST};
        }}

        QTabBar::tab:hover:!selected {{
            background-color: {cls.SURFACE1};
            color: {cls.TEXT};
        }}

        /* === MENU === */
        QMenuBar {{
            background-color: {cls.MANTLE};
            color: {cls.TEXT};
            padding: 4px;
            font-size: {fonts['normal']}pt;
        }}

        QMenuBar::item:selected {{
            background-color: {cls.SURFACE0};
            border-radius: 4px;
        }}

        QMenu {{
            background-color: {cls.SURFACE0};
            color: {cls.TEXT};
            border: 1px solid {cls.SURFACE1};
            padding: 8px;
            font-size: {fonts['normal']}pt;
        }}

        QMenu::item {{
            padding: 8px 24px;
            border-radius: 4px;
        }}

        QMenu::item:selected {{
            background-color: {cls.BLUE};
            color: {cls.CRUST};
        }}

        /* === STATUS BAR === */
        QStatusBar {{
            background-color: {cls.MANTLE};
            color: {cls.SUBTEXT0};
            border-top: 1px solid {cls.SURFACE0};
            font-size: {fonts['small']}pt;
            padding: 4px 16px;
        }}

        /* === TOOL BAR === */
        QToolBar {{
            background-color: {cls.MANTLE};
            border: none;
            spacing: 8px;
            padding: 8px;
        }}

        QToolButton {{
            background-color: transparent;
            border: none;
            border-radius: 6px;
            padding: 8px;
            font-size: {fonts['normal']}pt;
        }}

        QToolButton:hover {{
            background-color: {cls.SURFACE0};
        }}

        /* === LIST WIDGET === */
        QListWidget {{
            background-color: {cls.MANTLE};
            border: 1px solid {cls.SURFACE0};
            border-radius: 8px;
            padding: 8px;
            font-size: {fonts['normal']}pt;
        }}

        QListWidget::item {{
            padding: 10px 12px;
            border-radius: 6px;
            margin: 2px 0px;
        }}

        QListWidget::item:selected {{
            background-color: {cls.BLUE};
            color: {cls.CRUST};
        }}

        QListWidget::item:hover:!selected {{
            background-color: {cls.SURFACE0};
        }}

        /* === CHECKBOX === */
        QCheckBox {{
            font-size: {fonts['normal']}pt;
            spacing: 8px;
        }}

        QCheckBox::indicator {{
            width: 20px;
            height: 20px;
            border-radius: 4px;
            border: 2px solid {cls.SURFACE1};
            background-color: {cls.SURFACE0};
        }}

        QCheckBox::indicator:checked {{
            background-color: {cls.BLUE};
            border-color: {cls.BLUE};
        }}

        /* === FRAME === */
        QFrame[class="card"] {{
            background-color: {cls.MANTLE};
            border: 1px solid {cls.SURFACE0};
            border-radius: 12px;
            padding: 16px;
        }}

        QFrame[class="divider"] {{
            background-color: {cls.SURFACE0};
            max-height: 1px;
            margin: 16px 0px;
        }}

        /* === SPLITTER === */
        QSplitter::handle {{
            background-color: {cls.SURFACE0};
        }}

        QSplitter::handle:horizontal {{
            width: 2px;
        }}

        QSplitter::handle:vertical {{
            height: 2px;
        }}
        """


class FolderWorker(QThread):
    """Worker thread for folder creation"""
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(bool, list)

    def __init__(self, folder_names: List[str], base_path: str, config: FolderConfig):
        super().__init__()
        self.folder_names = folder_names
        self.base_path = base_path
        self.config = config
        self.created_folders = []
        self._is_running = True

    def run(self):
        try:
            total = len(self.folder_names)

            for i, name in enumerate(self.folder_names):
                if not self._is_running:
                    break

                # Create folder based on structure type
                folder_path = self._create_folder_structure(name)
                if folder_path:
                    self.created_folders.append(folder_path)

                progress = int((i + 1) / total * 100)
                self.progress.emit(progress)
                self.status.emit(f"Создание: {name}")

            self.finished.emit(True, self.created_folders)
        except Exception as e:
            logger.error(f"Worker error: {e}")
            self.finished.emit(False, [str(e)])

    def _create_folder_structure(self, name: str) -> Optional[str]:
        """Create folder with selected structure"""
        try:
            base = Path(self.base_path)

            if self.config.structure_type == StructureType.FLAT:
                folder_path = base / f"{self.config.prefix}{name}{self.config.suffix}"
            elif self.config.structure_type == StructureType.ALPHABETICAL:
                first_char = name[0].upper() if name else "_"
                folder_path = base / first_char / f"{self.config.prefix}{name}{self.config.suffix}"
            elif self.config.structure_type == StructureType.BY_DATE:
                today = datetime.now().strftime(self.config.date_format)
                folder_path = base / today / f"{self.config.prefix}{name}{self.config.suffix}"
            elif self.config.structure_type == StructureType.BY_FIRST_WORD:
                first_word = name.split()[0] if name.split() else "_"
                folder_path = base / first_word / f"{self.config.prefix}{name}{self.config.suffix}"
            else:
                folder_path = base / name

            folder_path.mkdir(parents=True, exist_ok=True)
            return str(folder_path)
        except Exception as e:
            logger.error(f"Error creating folder {name}: {e}")
            return None

    def stop(self):
        self._is_running = False


class ResponsiveLayout:
    """Helper class for responsive layout calculations"""

    @staticmethod
    def get_spacing(scale: float = 1.0) -> Dict[str, int]:
        """Get consistent spacing values"""
        base = 8
        return {
            'xs': int(base * 0.5 * scale),      # 4px
            'sm': int(base * 0.75 * scale),     # 6px
            'md': int(base * scale),            # 8px
            'lg': int(base * 1.5 * scale),      # 12px
            'xl': int(base * 2 * scale),        # 16px
            'xxl': int(base * 3 * scale),       # 24px
            'xxxl': int(base * 4 * scale),      # 32px
        }

    @staticmethod
    def setup_margins(layout, spacing: str = 'md', scale: float = 1.0):
        """Setup consistent margins for layout"""
        sp = ResponsiveLayout.get_spacing(scale)
        value = sp.get(spacing, sp['md'])
        layout.setContentsMargins(value, value, value, value)
        layout.setSpacing(sp['md'])


class MainWindow(QMainWindow):
    """Main application window with responsive design"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("FolderForge Pro")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

        # Detect screen DPI for scaling
        self.scale_factor = self._detect_scale_factor()

        # Apply modern theme
        self.apply_theme()

        # Initialize data
        self.folder_names: List[str] = []
        self.config = FolderConfig()
        self.current_file: Optional[str] = None

        # Setup UI
        self.setup_ui()
        self.setup_menu()
        self.setup_toolbar()
        self.setup_statusbar()

        # Enable drag and drop
        self.setAcceptDrops(True)

        logger.info("FolderForge Pro initialized")

    def _detect_scale_factor(self) -> float:
        """Detect screen scale factor for responsive design"""
        screen = QApplication.primaryScreen()
        if screen:
            dpi = screen.logicalDotsPerInch()
            # Base DPI is 96, scale accordingly
            factor = dpi / 96.0
            # Clamp between 1.0 and 2.0 for reasonable scaling
            return max(1.0, min(2.0, factor))
        return 1.0

    def apply_theme(self):
        """Apply modern stylesheet"""
        base_font_size = int(10 * self.scale_factor)
        stylesheet = ModernStyle.get_stylesheet(base_font_size)
        self.setStyleSheet(stylesheet)

        # Set application font
        font = QFont("Segoe UI", base_font_size)
        font.setStyleHint(QFont.StyleHint.SansSerif)
        QApplication.setFont(font)

    def setup_ui(self):
        """Setup main UI with responsive layout"""
        central = QWidget()
        self.setCentralWidget(central)

        # Main horizontal layout with splitter
        main_layout = QHBoxLayout(central)
        sp = ResponsiveLayout.get_spacing(self.scale_factor)
        main_layout.setContentsMargins(sp['xl'], sp['xl'], sp['xl'], sp['xl'])
        main_layout.setSpacing(sp['xl'])

        # Create splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel - Input
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)

        # Right panel - Preview and Settings
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)

        # Set splitter proportions (40% / 60%)
        splitter.setSizes([400, 600])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)

    def create_left_panel(self) -> QWidget:
        """Create left panel with input controls"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        sp = ResponsiveLayout.get_spacing(self.scale_factor)
        ResponsiveLayout.setup_margins(layout, 'lg', self.scale_factor)

        # Header
        header = QLabel("📂 FolderForge Pro")
        header.setProperty("class", "title")
        layout.addWidget(header)

        subtitle = QLabel("Массовое создание папок из Excel/CSV/TXT")
        subtitle.setProperty("class", "caption")
        layout.addWidget(subtitle)

        # Divider
        divider = QFrame()
        divider.setProperty("class", "divider")
        divider.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(divider)

        # File Group
        file_group = QGroupBox("📁 Источник данных")
        file_layout = QVBoxLayout(file_group)
        file_layout.setSpacing(sp['md'])

        # File path input with button
        file_input_layout = QHBoxLayout()
        self.file_path_input = QLineEdit()
        self.file_path_input.setPlaceholderText("Перетащите файл или нажмите 'Открыть'...")
        self.file_path_input.setMinimumHeight(int(36 * self.scale_factor))
        file_input_layout.addWidget(self.file_path_input)

        browse_btn = QPushButton("📂 Открыть")
        browse_btn.setProperty("class", "primary")
        browse_btn.setMinimumWidth(int(120 * self.scale_factor))
        browse_btn.clicked.connect(self.browse_file)
        file_input_layout.addWidget(browse_btn)

        file_layout.addLayout(file_input_layout)

        # Quick paste area
        paste_label = QLabel("⚡ Быстрый ввод (вставьте список через запятую или с новой строки):")
        paste_label.setProperty("class", "heading")
        file_layout.addWidget(paste_label)

        self.quick_input = QTextEdit()
        self.quick_input.setPlaceholderText("Например: Проект A, Проект B, Проект C...")
        self.quick_input.setMaximumHeight(int(120 * self.scale_factor))
        self.quick_input.textChanged.connect(self.on_quick_input_changed)
        file_layout.addWidget(self.quick_input)

        layout.addWidget(file_group)

        # Preview Group
        preview_group = QGroupBox("👁 Предпросмотр")
        preview_layout = QVBoxLayout(preview_group)

        # Stats label
        self.stats_label = QLabel("Загружено: 0 папок")
        self.stats_label.setProperty("class", "caption")
        preview_layout.addWidget(self.stats_label)

        # Table
        self.preview_table = QTableWidget()
        self.preview_table.setColumnCount(3)
        self.preview_table.setHorizontalHeaderLabels(["№", "Имя папки", "Статус"])
        self.preview_table.horizontalHeader().setStretchLastSection(True)
        self.preview_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.preview_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.setMinimumHeight(int(300 * self.scale_factor))

        # Set row height based on scale
        self.preview_table.verticalHeader().setDefaultSectionSize(int(28 * self.scale_factor))

        preview_layout.addWidget(self.preview_table)

        # Action buttons
        btn_layout = QHBoxLayout()

        self.validate_btn = QPushButton("✓ Проверить имена")
        self.validate_btn.clicked.connect(self.validate_names)
        self.validate_btn.setEnabled(False)
        btn_layout.addWidget(self.validate_btn)

        self.remove_duplicates_btn = QPushButton("🗑 Удалить дубликаты")
        self.remove_duplicates_btn.clicked.connect(self.remove_duplicates)
        self.remove_duplicates_btn.setEnabled(False)
        btn_layout.addWidget(self.remove_duplicates_btn)

        self.sort_btn = QPushButton("⇅ Сортировать")
        self.sort_btn.clicked.connect(self.sort_names)
        self.sort_btn.setEnabled(False)
        btn_layout.addWidget(self.sort_btn)

        preview_layout.addLayout(btn_layout)

        layout.addWidget(preview_group, 1)

        return panel

    def create_right_panel(self) -> QWidget:
        """Create right panel with settings and actions"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        sp = ResponsiveLayout.get_spacing(self.scale_factor)
        ResponsiveLayout.setup_margins(layout, 'lg', self.scale_factor)

        # Settings Group
        settings_group = QGroupBox("⚙ Настройки структуры")
        settings_layout = QVBoxLayout(settings_group)
        settings_layout.setSpacing(sp['lg'])

        # Structure type
        structure_label = QLabel("Тип организации:")
        structure_label.setProperty("class", "heading")
        settings_layout.addWidget(structure_label)

        self.structure_combo = QComboBox()
        self.structure_combo.addItems([
            "📂 Плоская (все в одной папке)",
            "🔤 По алфавиту (А/Б/В/...)",
            "📅 По дате (2024-03-02/)",
            "📝 По первому слову"
        ])
        self.structure_combo.setMinimumHeight(int(36 * self.scale_factor))
        self.structure_combo.currentIndexChanged.connect(self.on_structure_changed)
        settings_layout.addWidget(self.structure_combo)

        # Prefix/Suffix
        prefix_layout = QHBoxLayout()

        prefix_label = QLabel("Префикс:")
        prefix_layout.addWidget(prefix_label)

        self.prefix_input = QLineEdit()
        self.prefix_input.setPlaceholderText("например: [2024] ")
        prefix_layout.addWidget(self.prefix_input)

        suffix_label = QLabel("Суффикс:")
        prefix_layout.addWidget(suffix_label)

        self.suffix_input = QLineEdit()
        self.suffix_input.setPlaceholderText("например: _backup")
        prefix_layout.addWidget(self.suffix_input)

        settings_layout.addLayout(prefix_layout)

        # Options
        options_label = QLabel("Опции:")
        options_label.setProperty("class", "heading")
        settings_layout.addWidget(options_label)

        self.validate_check = QCheckBox("Проверять недопустимые символы Windows")
        self.validate_check.setChecked(True)
        settings_layout.addWidget(self.validate_check)

        self.remove_dup_check = QCheckBox("Удалять дубликаты автоматически")
        self.remove_dup_check.setChecked(True)
        settings_layout.addWidget(self.remove_dup_check)

        self.open_after_check = QCheckBox("Открыть папку после создания")
        self.open_after_check.setChecked(True)
        settings_layout.addWidget(self.open_after_check)

        layout.addWidget(settings_group)

        # Export Group
        export_group = QGroupBox("📤 Экспорт скриптов")
        export_layout = QVBoxLayout(export_group)

        export_btn_layout = QHBoxLayout()

        self.export_bat_btn = QPushButton("🪟 BAT скрипт")
        self.export_bat_btn.clicked.connect(lambda: self.export_script("bat"))
        self.export_bat_btn.setEnabled(False)
        export_btn_layout.addWidget(self.export_bat_btn)

        self.export_ps_btn = QPushButton("💻 PowerShell")
        self.export_ps_btn.clicked.connect(lambda: self.export_script("ps1"))
        self.export_ps_btn.setEnabled(False)
        export_btn_layout.addWidget(self.export_ps_btn)

        self.export_py_btn = QPushButton("🐍 Python")
        self.export_py_btn.clicked.connect(lambda: self.export_script("py"))
        self.export_py_btn.setEnabled(False)
        export_btn_layout.addWidget(self.export_py_btn)

        export_layout.addLayout(export_btn_layout)
        layout.addWidget(export_group)

        # Output Group
        output_group = QGroupBox("📂 Выходная директория")
        output_layout = QVBoxLayout(output_group)

        output_input_layout = QHBoxLayout()
        self.output_path_input = QLineEdit()
        self.output_path_input.setText(str(Path.home() / "Documents" / "CreatedFolders"))
        self.output_path_input.setMinimumHeight(int(36 * self.scale_factor))
        output_input_layout.addWidget(self.output_path_input)

        output_browse_btn = QPushButton("📁")
        output_browse_btn.setProperty("class", "icon-button")
        output_browse_btn.clicked.connect(self.browse_output)
        output_input_layout.addWidget(output_browse_btn)

        output_layout.addLayout(output_input_layout)
        layout.addWidget(output_group)

        # Progress
        progress_label = QLabel("Прогресс:")
        progress_label.setProperty("class", "heading")
        layout.addWidget(progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setMinimumHeight(int(24 * self.scale_factor))
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Готов к работе")
        self.status_label.setProperty("class", "caption")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # Spacer
        layout.addStretch()

        # Create Button (Big)
        self.create_btn = QPushButton("🚀 СОЗДАТЬ ПАПКИ")
        self.create_btn.setProperty("class", "success")
        self.create_btn.setMinimumHeight(int(56 * self.scale_factor))
        font = self.create_btn.font()
        font.setPointSize(int(14 * self.scale_factor))
        font.setBold(True)
        self.create_btn.setFont(font)
        self.create_btn.clicked.connect(self.create_folders)
        self.create_btn.setEnabled(False)
        layout.addWidget(self.create_btn)

        return panel

    def setup_menu(self):
        """Setup menu bar"""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("📁 Файл")

        open_action = QAction("Открыть...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.browse_file)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        export_template_action = QAction("Экспорт шаблона Excel", self)
        export_template_action.triggered.connect(self.export_template)
        file_menu.addAction(export_template_action)

        file_menu.addSeparator()

        exit_action = QAction("Выход", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("✏️ Правка")

        clear_action = QAction("Очистить список", self)
        clear_action.triggered.connect(self.clear_list)
        edit_menu.addAction(clear_action)

                # Tools menu
        tools_menu = menubar.addMenu("🛠 Инструменты")

        scan_folder_action = QAction("📂 Сканировать папку → Excel", self)
        scan_folder_action.triggered.connect(self.scan_folder_to_excel)
        tools_menu.addAction(scan_folder_action)

# Help menu
        help_menu = menubar.addMenu("❓ Помощь")

        about_action = QAction("О программе", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def setup_toolbar(self):
        """Setup toolbar"""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Add toolbar actions if needed
        toolbar.setVisible(False)  # Hide for cleaner look

    def setup_statusbar(self):
        """Setup status bar"""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("Готов")

    # === FILE OPERATIONS ===

    def browse_file(self):
        """Open file dialog"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл",
            "",
            "Excel files (*.xlsx *.xls *.xlsm *.xlsb);;CSV files (*.csv);;Text files (*.txt);;All files (*.*)"
        )

        if file_path:
            self.load_file(file_path)

    def load_file(self, file_path: str):
        """Load and parse file"""
        try:
            self.current_file = file_path
            self.file_path_input.setText(file_path)

            ext = Path(file_path).suffix.lower()

            if ext in ['.xlsx', '.xls', '.xlsm', '.xlsb']:
                df = pd.read_excel(file_path, header=None)
            elif ext == '.csv':
                df = pd.read_csv(file_path, header=None)
            elif ext == '.txt':
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                self.folder_names = [line.strip() for line in lines if line.strip()]
                self.update_preview()
                return
            else:
                raise ValueError(f"Unsupported file format: {ext}")

            # Extract first column
            self.folder_names = df.iloc[:, 0].dropna().astype(str).tolist()

            if self.remove_dup_check.isChecked():
                self.remove_duplicates()

            self.update_preview()
            self.statusbar.showMessage(f"Загружено {len(self.folder_names)} папок из {file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить файл: {str(e)}")
            logger.error(f"File load error: {e}")

    def on_quick_input_changed(self):
        """Handle quick input changes"""
        text = self.quick_input.toPlainText()
        if text:
            # Split by comma or newline
            names = re.split(r'[,\n]', text)
            self.folder_names = [name.strip() for name in names if name.strip()]
            self.update_preview()

    def update_preview(self):
        """Update preview table"""
        self.preview_table.setRowCount(len(self.folder_names))

        for i, name in enumerate(self.folder_names):
            # Number
            num_item = QTableWidgetItem(str(i + 1))
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.preview_table.setItem(i, 0, num_item)

            # Name
            name_item = QTableWidgetItem(name)
            self.preview_table.setItem(i, 1, name_item)

            # Status
            status = "✓" if self.is_valid_name(name) else "⚠ Недопустимые символы"
            status_item = QTableWidgetItem(status)
            self.preview_table.setItem(i, 2, status_item)

        self.stats_label.setText(f"Загружено: {len(self.folder_names)} папок")

        # Enable/disable buttons
        has_data = len(self.folder_names) > 0
        self.create_btn.setEnabled(has_data)
        self.validate_btn.setEnabled(has_data)
        self.remove_duplicates_btn.setEnabled(has_data)
        self.sort_btn.setEnabled(has_data)
        self.export_bat_btn.setEnabled(has_data)
        self.export_ps_btn.setEnabled(has_data)
        self.export_py_btn.setEnabled(has_data)

    def is_valid_name(self, name: str) -> bool:
        """Check if folder name is valid for Windows"""
        invalid_chars = r'[<>:"/\\|?*]'
        return not re.search(invalid_chars, name) and name not in ['CON', 'PRN', 'AUX', 'NUL']

    def validate_names(self):
        """Validate and clean folder names"""
        cleaned = []
        invalid_found = []

        for name in self.folder_names:
            # Remove invalid characters
            clean = re.sub(r'[<>:"/\\|?*]', '_', name)
            if clean != name:
                invalid_found.append(f"{name} → {clean}")
            cleaned.append(clean)

        self.folder_names = cleaned
        self.update_preview()

        if invalid_found:
            msg = "\n".join(invalid_found[:10])
            if len(invalid_found) > 10:
                msg += f"\n... и еще {len(invalid_found) - 10}"
            QMessageBox.information(self, "Исправлены имена", f"Очищены имена:\n{msg}")

    def remove_duplicates(self):
        """Remove duplicate names"""
        original_count = len(self.folder_names)
        self.folder_names = list(dict.fromkeys(self.folder_names))
        removed = original_count - len(self.folder_names)

        self.update_preview()

        if removed > 0:
            self.statusbar.showMessage(f"Удалено {removed} дубликатов")

    def sort_names(self):
        """Sort folder names alphabetically"""
        self.folder_names.sort(key=str.lower)
        self.update_preview()

    def clear_list(self):
        """Clear all folder names"""
        self.folder_names = []
        self.preview_table.setRowCount(0)
        self.quick_input.clear()
        self.update_preview()

    # === EXPORT ===

    def export_script(self, format_type: str):
        """Export to script format"""
        if not self.folder_names:
            return

        file_filters = {
            "bat": "Batch files (*.bat)",
            "ps1": "PowerShell files (*.ps1)",
            "py": "Python files (*.py)"
        }

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить скрипт",
            f"create_folders.{format_type}",
            file_filters.get(format_type, "All files (*.*)")
        )

        if not file_path:
            return

        try:
            if format_type == "bat":
                content = self.generate_bat()
            elif format_type == "ps1":
                content = self.generate_ps1()
            elif format_type == "py":
                content = self.generate_py()
            else:
                return

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            self.statusbar.showMessage(f"Скрипт сохранен: {file_path}")
            QMessageBox.information(self, "Успех", f"Скрипт сохранен:\n{file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить: {str(e)}")

    def generate_bat(self) -> str:
        """Generate batch script"""
        lines = ["@echo off", "chcp 65001 >nul", f'cd /d "{self.output_path_input.text()}"', ""]

        for name in self.folder_names:
            safe_name = name.replace('"', '\"')
            lines.append(f'mkdir "{safe_name}" 2>nul')

        lines.extend(["", "echo Папки созданы!", "pause"])
        return "\n".join(lines)

    def generate_ps1(self) -> str:
        """Generate PowerShell script"""
        output_path = self.output_path_input.text().replace("'", "''")

        lines = [
            "# Create folders script",
            f"$basePath = '{output_path}'",
            "New-Item -ItemType Directory -Force -Path $basePath | Out-Null",
            "Set-Location $basePath",
            "",
            "$folders = @("
        ]

        for name in self.folder_names:
            safe_name = name.replace("'", "''")
            lines.append(f"    '{safe_name}'")

        lines.extend([
            ")",
            "",
            "foreach ($folder in $folders) {",
            "    $path = Join-Path $basePath $folder",
            "    New-Item -ItemType Directory -Force -Path $path | Out-Null",
            r'    Write-Host "Created: $folder" -ForegroundColor Green',
            "}",
            "",
            r'Write-Host "Done!" -ForegroundColor Cyan'
        ])

        return "\n".join(lines)

    def generate_py(self) -> str:
        """Generate Python script"""
        output_path = self.output_path_input.text().replace("'", "\'")
        lines = [
            "#!/usr/bin/env python3",
            "# -*- coding: utf-8 -*-",
            "",
            "import os",
            "from pathlib import Path",
            "",
            f"BASE_PATH = Path(r'{output_path}')",
            "",
            "FOLDERS = ["
        ]

        for name in self.folder_names:
            safe_name = name.replace("'", "\'")
            lines.append(f"    '{safe_name}',")

        lines.extend([
            "]",
            "",
            "def create_folders():",
            "    BASE_PATH.mkdir(parents=True, exist_ok=True)",
            "    ",
            "    for name in FOLDERS:",
            "        folder_path = BASE_PATH / name",
            "        folder_path.mkdir(exist_ok=True)",
            r'        print(f"Created: {name}")',
            "    ",
            r'    print("Done!")',
            "",
            "if __name__ == '__main__':",
            "    create_folders()"
        ])

        return "\n".join(lines)

    def export_template(self):
        """Export Excel template with formulas"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить шаблон",
            "template.xlsx",
            "Excel files (*.xlsx)"
        )

        if file_path:
            try:
                # Create template with formulas
                data = {
                    'A': ['Имя папки 1', 'Имя папки 2', 'Имя папки 3'],
                    'B': ['=\"MD \"\"&A1&\"\"\"', '=\"MD \"\"&A2&\"\"\"', '=\"MD \"\"&A3&\"\"\"']
                }
                df = pd.DataFrame(data)
                df.to_excel(file_path, index=False, header=False)

                self.statusbar.showMessage(f"Шаблон сохранен: {file_path}")
                QMessageBox.information(self, "Успех", "Шаблон Excel сохранен!")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить: {str(e)}")


    def scan_folder_to_excel(self):
        """Scan folder and create Excel with file names"""
        # Select folder to scan
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Выберите папку для сканирования",
            str(Path.home())
        )

        if not folder_path:
            return

        # Options dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Настройки сканирования")
        dialog.setMinimumWidth(400)

        layout = QVBoxLayout(dialog)

        # Include subfolders
        subfolders_check = QCheckBox("Включить подпапки (рекурсивно)")
        subfolders_check.setChecked(False)
        layout.addWidget(subfolders_check)

        # Include file extensions
        extensions_check = QCheckBox("Включить расширения файлов")
        extensions_check.setChecked(True)
        layout.addWidget(extensions_check)

        # Include full paths
        fullpath_check = QCheckBox("Включить полные пути")
        fullpath_check.setChecked(False)
        layout.addWidget(fullpath_check)

        # Include file sizes
        size_check = QCheckBox("Включить размер файлов")
        size_check.setChecked(True)
        layout.addWidget(size_check)

        # Include modified date
        date_check = QCheckBox("Включить дату изменения")
        date_check.setChecked(True)
        layout.addWidget(date_check)

        # Buttons
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        layout.addWidget(btn_box)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        # Get options
        include_subfolders = subfolders_check.isChecked()
        include_extensions = extensions_check.isChecked()
        include_fullpath = fullpath_check.isChecked()
        include_size = size_check.isChecked()
        include_date = date_check.isChecked()

        # Scan folder
        self.statusbar.showMessage(f"Сканирование: {folder_path}...")

        try:
            file_data = []
            base_path = Path(folder_path)

            if include_subfolders:
                pattern = "**/*"
            else:
                pattern = "*"

            for item in base_path.glob(pattern):
                if item.is_file():
                    row = {}

                    # File name (with or without extension)
                    if include_extensions:
                        row['Имя файла'] = item.name
                    else:
                        row['Имя файла'] = item.stem

                    # Full path (relative or absolute)
                    if include_fullpath:
                        row['Полный путь'] = str(item.absolute())
                    else:
                        try:
                            row['Относительный путь'] = str(item.relative_to(base_path.parent))
                        except:
                            row['Относительный путь'] = str(item.relative_to(base_path))

                    # File size
                    if include_size:
                        size = item.stat().st_size
                        # Convert to human readable
                        if size < 1024:
                            row['Размер'] = f"{size} B"
                        elif size < 1024 * 1024:
                            row['Размер'] = f"{size / 1024:.2f} KB"
                        elif size < 1024 * 1024 * 1024:
                            row['Размер'] = f"{size / (1024 * 1024):.2f} MB"
                        else:
                            row['Размер'] = f"{size / (1024 * 1024 * 1024):.2f} GB"
                        row['Размер (байт)'] = size

                    # Modified date
                    if include_date:
                        mtime = datetime.fromtimestamp(item.stat().st_mtime)
                        row['Дата изменения'] = mtime.strftime("%Y-%m-%d %H:%M:%S")

                    # Extension separate column
                    row['Расширение'] = item.suffix.lower()

                    file_data.append(row)

            if not file_data:
                QMessageBox.information(self, "Информация", "В выбранной папке нет файлов.")
                return

            # Create DataFrame
            df = pd.DataFrame(file_data)

            # Reorder columns
            column_order = ['Имя файла']
            if include_fullpath:
                column_order.append('Полный путь')
            else:
                column_order.append('Относительный путь')
            column_order.append('Расширение')
            if include_size:
                column_order.extend(['Размер', 'Размер (байт)'])
            if include_date:
                column_order.append('Дата изменения')

            df = df[column_order]

            # Save dialog
            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "Сохранить список файлов",
                str(base_path / "file_list.xlsx"),
                "Excel files (*.xlsx);;CSV files (*.csv)"
            )

            if save_path:
                if save_path.endswith('.csv'):
                    df.to_csv(save_path, index=False, encoding='utf-8-sig')
                else:
                    df.to_excel(save_path, index=False, engine='openpyxl')

                self.statusbar.showMessage(f"Сохранено {len(file_data)} файлов в {save_path}")

                # Ask to open the file
                reply = QMessageBox.question(
                    self,
                    "Успех",
                    f"Найдено и сохранено {len(file_data)} файлов.\n\nОткрыть файл?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )

                if reply == QMessageBox.StandardButton.Yes:
                    import subprocess
                    subprocess.Popen(f'explorer "{save_path}"')

                # Also load into the app
                load_reply = QMessageBox.question(
                    self,
                    "Загрузить имена?",
                    "Загрузить имена файлов в программу для создания папок?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )

                if load_reply == QMessageBox.StandardButton.Yes:
                    self.folder_names = df['Имя файла'].tolist()
                    self.update_preview()

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка сканирования: {str(e)}")
            logger.error(f"Scan folder error: {e}")

    # === FOLDER CREATION ===

    def browse_output(self):
        """Browse for output directory"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Выберите директорию",
            self.output_path_input.text()
        )

        if dir_path:
            self.output_path_input.setText(dir_path)

    def on_structure_changed(self, index: int):
        """Handle structure type change"""
        structures = [
            StructureType.FLAT,
            StructureType.ALPHABETICAL,
            StructureType.BY_DATE,
            StructureType.BY_FIRST_WORD
        ]

        if 0 <= index < len(structures):
            self.config.structure_type = structures[index]

    def create_folders(self):
        """Start folder creation process"""
        if not self.folder_names:
            QMessageBox.warning(self, "Внимание", "Список папок пуст!")
            return

        output_path = self.output_path_input.text()
        if not output_path:
            QMessageBox.warning(self, "Внимание", "Укажите выходную директорию!")
            return

        # Update config
        self.config.prefix = self.prefix_input.text()
        self.config.suffix = self.suffix_input.text()
        self.config.validate_names = self.validate_check.isChecked()
        self.config.remove_duplicates = self.remove_dup_check.isChecked()
        self.config.open_after_creation = self.open_after_check.isChecked()

        # Validate names if needed
        if self.config.validate_names:
            self.validate_names()

        # Create output directory
        Path(output_path).mkdir(parents=True, exist_ok=True)

        # Start worker thread
        self.worker = FolderWorker(self.folder_names, output_path, self.config)
        self.worker.progress.connect(self.on_progress)
        self.worker.status.connect(self.on_status)
        self.worker.finished.connect(self.on_finished)

        self.create_btn.setEnabled(False)
        self.create_btn.setText("⏳ Создание...")

        self.worker.start()

    def on_progress(self, value: int):
        """Update progress bar"""
        self.progress_bar.setValue(value)

    def on_status(self, message: str):
        """Update status label"""
        self.status_label.setText(message)

    def on_finished(self, success: bool, results: list):
        """Handle completion"""
        self.create_btn.setEnabled(True)
        self.create_btn.setText("🚀 СОЗДАТЬ ПАПКИ")

        if success:
            self.progress_bar.setValue(100)
            self.status_label.setText(f"✓ Создано {len(results)} папок")
            self.statusbar.showMessage(f"Успешно создано {len(results)} папок")

            if self.config.open_after_creation and results:
                import subprocess
                subprocess.Popen(f'explorer "{self.output_path_input.text()}"')

            QMessageBox.information(
                self,
                "Успех",
                f"Создано {len(results)} папок!\n\nРасположение:\n{self.output_path_input.text()}"
            )
        else:
            self.status_label.setText("✗ Ошибка создания")
            QMessageBox.critical(self, "Ошибка", f"Произошла ошибка:\n{results[0] if results else 'Unknown'}")

    # === DRAG AND DROP ===

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        """Handle file drop"""
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path:
                self.load_file(file_path)

    # === ABOUT ===

    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "О FolderForge Pro",
            """<h2>FolderForge Pro</h2>
            <p>Версия 2.0</p>
            <p>Инструмент для массового создания папок из Excel/CSV/TXT файлов.</p>
            <p>Создано на Python + PyQt6</p>
            <p>Тема: Catppuccin Mocha</p>
            """
        )

    def closeEvent(self, event):
        """Handle application close"""
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(2000)
        event.accept()


def main():
    """Application entry point"""
    # Enable high DPI scaling
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("FolderForge Pro")
    app.setApplicationVersion("2.0")

    # Set application font
    font = QFont("Segoe UI", 10)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
