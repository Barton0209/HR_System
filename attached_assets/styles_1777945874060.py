# core/styles.py
def apply_stylesheet(app):
    qss = """
    QMainWindow {
        background-color: #1e1e2e;
        color: #cdd6f4;
    }
    QWidget {
        background-color: #1e1e2e;
        color: #cdd6f4;
    }
    QListWidget {
        background-color: #181825;
        border: none;
    }
    QListWidget::item {
        color: #cdd6f4;
        padding: 10px 15px;
    }
    QListWidget::item:selected {
        background-color: #313244;
        color: #89b4fa;
    }
    QPushButton {
        background-color: #313244;
        color: #cdd6f4;
        border: 1px solid #45475a;
        border-radius: 6px;
        padding: 8px 16px;
    }
    QPushButton:hover {
        background-color: #45475a;
    }
    QLineEdit, QComboBox {
        background-color: #313244;
        color: #cdd6f4;
        border: 1px solid #45475a;
        border-radius: 4px;
        padding: 6px;
    }
    QTabWidget::pane {
        border: 1px solid #45475a;
    }
    QTabBar::tab {
        background: #313244;
        color: #cdd6f4;
        padding: 8px;
    }
    QTabBar::tab:selected {
        background: #89b4fa;
        color: #1e1e2e;
    }
    QTableWidget {
        background-color: #181825;
        gridline-color: #313244;
    }
    QHeaderView::section {
        background-color: #313244;
        color: #cdd6f4;
        padding: 6px;
        border: none;
    }
    QScrollBar:vertical {
        background: #181825;
        width: 10px;
    }
    QScrollBar::handle:vertical {
        background: #585b70;
        border-radius: 5px;
    }
    """
    app.setStyleSheet(qss)