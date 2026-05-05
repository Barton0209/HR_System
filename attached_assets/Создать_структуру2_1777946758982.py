import os
import sys
from pathlib import Path

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget,
                               QVBoxLayout, QHBoxLayout, QPushButton,
                               QFileDialog, QLabel, QTextEdit, QMessageBox)


class ProjectGenerator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Генератор Структуры Проекта")
        self.setGeometry(100, 100, 800, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        # --- Выбор папки для проекта ---
        path_layout = QHBoxLayout()
        self.path_label = QLabel("1. Папка для создания проекта:")
        self.path_display = QLabel("Не выбрана")
        self.path_display.setStyleSheet("color: gray; font-style: italic;")
        path_layout.addWidget(self.path_label)
        path_layout.addWidget(self.path_display, 1)
        layout.addLayout(path_layout)

        self.select_folder_btn = QPushButton("Выбрать папку...")
        self.select_folder_btn.clicked.connect(self.select_folder)
        layout.addWidget(self.select_folder_btn)

        # --- Выбор файла шаблона ---
        template_layout = QHBoxLayout()
        self.template_label = QLabel("2. Файл шаблона (.txt):")
        self.template_display = QLabel("Не выбран")
        self.template_display.setStyleSheet("color: gray; font-style: italic;")
        template_layout.addWidget(self.template_label)
        template_layout.addWidget(self.template_display, 1)
        layout.addLayout(template_layout)

        self.select_template_btn = QPushButton("Выбрать файл шаблона...")
        self.select_template_btn.clicked.connect(self.select_template)
        layout.addWidget(self.select_template_btn)

        # --- Кнопка генерации ---
        self.generate_btn = QPushButton("3. Создать структуру проекта")
        self.generate_btn.setStyleSheet("font-weight: bold; background-color: #4CAF50; color: white; padding: 10px;")
        self.generate_btn.clicked.connect(self.generate_project)
        layout.addWidget(self.generate_btn)

        # --- Лог ---
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("background-color: #f0f0f0; font-family: monospace;")
        layout.addWidget(self.log_text)

        self.selected_path = None
        self.selected_template_path = None
        self.parsed_structure = []
        self.project_root_name = ""

    def select_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Выберите родительскую папку")
        if folder_path:
            self.selected_path = Path(folder_path)
            self.path_display.setText(str(self.selected_path))
            self.path_display.setStyleSheet("")

    def select_template(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите файл шаблона", "", "Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            self.selected_template_path = Path(file_path)
            self.template_display.setText(str(self.selected_template_path.name))
            self.template_display.setStyleSheet("")
            self.parse_template_file()

    def parse_template_file(self):
        """Парсит файл tree в список путей относительно корня."""
        if not self.selected_template_path or not self.selected_template_path.exists():
            return

        try:
            with self.selected_template_path.open('r', encoding='utf-8') as f:
                lines = f.readlines()

            structure_list = []
            path_stack = [] # Стек имен папок для построения пути
            root_name_found = False

            for line in lines:
                raw_line = line.rstrip('\n\r')
                
                # 1. Определяем корень (первая строка, не содержащая ├──/└── и заканчивающаяся на /)
                if not root_name_found:
                    if raw_line.endswith('/') and '├──' not in raw_line and '└──' not in raw_line:
                        self.project_root_name = raw_line.strip().rstrip('/')
                        root_name_found = True
                        continue # Переходим к следующей строке

                # Если корень еще не найден, пропускаем пустые строки или заголовки
                if not root_name_found:
                    continue

                # 2. Обрабатываем элементы дерева
                if '├──' in raw_line or '└──' in raw_line:
                    # Находим позицию маркера ветвления
                    marker_pos = -1
                    if '├──' in raw_line:
                        marker_pos = raw_line.find('├──')
                    else:
                        marker_pos = raw_line.find('└──')
                    
                    if marker_pos == -1:
                        continue

                    # Извлекаем имя элемента после маркера
                    item_part = raw_line[marker_pos:]
                    # Убираем сам маркер и пробелы после него
                    item_name_raw = item_part.replace('├── ', '').replace('└── ', '')
                    # Берем только первое слово (имя), игнорируя комментарии
                    item_name = item_name_raw.split()[0] if item_name_raw.split() else ""
                    
                    if not item_name:
                        continue

                    # Вычисляем уровень вложенности
                    # Отступ до маркера содержит символы │ и пробелы.
                    # Каждый уровень обычно добавляет 4 символа (например "│   " или "    ")
                    indent_str = raw_line[:marker_pos]
                    # Заменяем сложные символы на простые пробелы для подсчета длины
                    # │ занимает 1 символ, но визуально соответствует отступу. 
                    # Стандартный вывод tree использует 4 символа на уровень.
                    # Просто посчитаем длину строки отступа.
                    level = len(indent_str) // 4
                    
                    # Корректируем стек
                    if level < len(path_stack):
                        path_stack = path_stack[:level]
                    elif level > len(path_stack):
                        # Это возможно, если есть пропущенные уровни, но обычно level <= len(stack) + 1
                        pass

                    # Формируем относительный путь
                    current_parts = path_stack + [item_name]
                    relative_path = "/".join(current_parts)

                    # Добавляем в список
                    structure_list.append(relative_path)

                    # Если это папка, добавляем в стек для следующих уровней
                    if item_name.endswith('/'):
                        path_stack.append(item_name)

            self.parsed_structure = structure_list
            self.log_text.append(f"[INFO] Шаблон '{self.selected_template_path.name}' прочитан.")
            self.log_text.append(f"[INFO] Найден корень: {self.project_root_name}")
            self.log_text.append(f"[INFO] Элементов структуры: {len(self.parsed_structure)}")

        except Exception as e:
            QMessageBox.critical(self, "Ошибка парсинга", str(e))
            self.log_text.append(f"[ERROR] Ошибка при чтении шаблона: {e}")

    def generate_project(self):
        if not self.selected_path:
            QMessageBox.warning(self, "Внимание", "Сначала выберите папку для проекта!")
            return
        if not self.selected_template_path:
            QMessageBox.warning(self, "Внимание", "Сначала выберите файл шаблона!")
            return
        if not self.parsed_structure:
            QMessageBox.warning(self, "Внимание", "Шаблон пуст или не распознан!")
            return

        root_name = self.project_root_name
        project_root = self.selected_path / root_name

        self.log_text.append("\n--- Начало создания структуры ---")
        
        try:
            # Создаем корень
            project_root.mkdir(parents=True, exist_ok=True)
            self.log_text.append(f"[OK] Создана папка: {project_root}")

            for rel_path in self.parsed_structure:
                # Проверяем, является ли элемент папкой (заканчивается на /)
                is_dir = rel_path.endswith('/')
                
                # Чистое имя для работы с Path
                clean_path_str = rel_path.rstrip('/')
                
                full_path = project_root / clean_path_str

                if is_dir:
                    full_path.mkdir(parents=True, exist_ok=True)
                    self.log_text.append(f"[OK] Папка: {full_path}")
                else:
                    # Для файла создаем родителя, если нет
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    # Создаем пустой файл
                    full_path.touch(exist_ok=True)
                    self.log_text.append(f"[OK] Файл: {full_path}")

            self.log_text.append("\n--- Готово! ---")
            QMessageBox.information(self, "Успех", f"Структура проекта '{root_name}' успешно создана в:\n{project_root}")

        except PermissionError:
            QMessageBox.critical(self, "Ошибка прав", "Нет доступа к записи в выбранную папку. Попробуйте запустить от администратора или выбрать другую папку.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка создания", f"Произошла ошибка: {e}")
            self.log_text.append(f"[ERROR] {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ProjectGenerator()
    window.show()
    sys.exit(app.exec())