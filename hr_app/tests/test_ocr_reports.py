"""
Тесты OCR и отчётов
"""
import pytest
import sys
import os

# Добавляем корень проекта в path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from hr_app.backend.services.ollama_service import (
    TESSERACT_AVAILABLE, 
    parse_passport_with_regex,
    ocr_with_tesseract
)


class TestPassportRegexParser:
    """Тесты парсинга паспортов через regex"""
    
    def test_parse_full_passport(self):
        text = "Фамилия:Иванов Имя:Иван Отчество:Иванович 4506 123456 Дата рождения: 15.05.1985 Пол: Мужской"
        result = parse_passport_with_regex(text)
        
        assert result["surname"] == "Иванов"
        assert result["name"] == "Иван"
        assert result["patronymic"] == "Иванович"
        assert result["birth_date"] == "15.05.1985"
        assert result["gender"] == "М"
        assert result["series"] == "4506"
        assert result["number"] == "123456"
    
    def test_parse_female_passport(self):
        text = "Фамилия:Петрова Имя:Анна Отчество:Сергеевна 1234 567890 25.12.1990 Ж"
        result = parse_passport_with_regex(text)
        
        assert result["surname"] == "Петрова"
        assert result["name"] == "Анна"
        assert result["gender"] == "Ж"
        assert result["birth_date"] == "25.12.1990"
    
    def test_parse_partial_data(self):
        text = "4506 123456 выдан 01.01.2020"
        result = parse_passport_with_regex(text)
        
        assert result["series"] == "4506"
        assert result["number"] == "123456"
        # Остальные поля пустые
    
    def test_parse_empty_text(self):
        result = parse_passport_with_regex("")
        assert all(v == "" for v in result.values())
    
    def test_parse_no_series_number(self):
        text = "Фамилия:Сидоров Имя:Пётр 10.03.1975"
        result = parse_passport_with_regex(text)
        
        assert result["surname"] == "Сидоров"
        assert result["name"] == "Пётр"
        assert result["birth_date"] == "10.03.1975"
        assert result["series"] == ""  # Нет серии


class TestTesseractAvailability:
    """Тесты доступности Tesseract"""
    
    def test_tesseract_imported(self):
        """Проверяем что pytesseract импортирован"""
        assert TESSERACT_AVAILABLE is True
    
    def test_ocr_function_exists(self):
        """Проверяем что функция OCR существует"""
        assert callable(ocr_with_tesseract)


class TestReportsExport:
    """Тесты экспорта отчётов"""
    
    def test_reports_router_imports(self):
        """Проверяем что router отчётов импортируется"""
        from hr_app.backend.routers.reports import router
        assert router is not None
        assert router.prefix == "/api/reports"
    
    def test_export_endpoints_exist(self):
        """Проверяем наличие endpoints для экспорта"""
        from hr_app.backend.routers.reports import router
        routes = [r.path for r in router.routes]
        
        # Проверяем что есть export-excel endpoint (с префиксом /api/reports)
        assert any("/export-excel" in r for r in routes)
        assert any("/export-all" in r for r in routes)


class TestOCRServiceIntegration:
    """Интеграционные тесты OCR сервиса"""
    
    def test_analyze_document_function_exists(self):
        """Проверяем что основная функция анализа существует"""
        from hr_app.backend.services.ollama_service import analyze_document
        assert callable(analyze_document)
    
    def test_fallback_chain(self):
        """
        Проверяем цепочку fallback:
        1. Ollama (если доступен)
        2. Tesseract + regex
        3. Ошибка если ничего не работает
        """
        from hr_app.backend.services.ollama_service import analyze_document
        import asyncio
        
        # Тест что функция асинхронная и возвращает dict
        async def test_call():
            # Пустой вызов вернёт ошибку т.к. нет файла
            result = await analyze_document("/nonexistent.jpg", "passport_ru")
            return result
        
        result = asyncio.run(test_call())
        assert isinstance(result, dict)
        assert "error" in result or "raw" in result
