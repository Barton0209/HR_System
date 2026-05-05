"""
PDF Service — извлечение данных из PDF билетов
"""
import re
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


def extract_ticket_data(pdf_path: str) -> List[Dict]:
    """Извлекает данные пассажиров из PDF билета."""
    results = []
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            full_text = "\n".join(
                page.extract_text() or "" for page in pdf.pages
            )
        results = _parse_ticket_text(full_text)
    except ImportError:
        logger.warning("pdfplumber not installed, trying pypdf2")
        try:
            import PyPDF2
            with open(pdf_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                full_text = "\n".join(
                    page.extract_text() or "" for page in reader.pages
                )
            results = _parse_ticket_text(full_text)
        except ImportError:
            logger.error("No PDF library available")
    except Exception as e:
        logger.exception("Error reading PDF %s", pdf_path)

    return results


def _parse_ticket_text(text: str) -> List[Dict]:
    """Парсит текст билета и извлекает данные пассажиров."""
    results = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # Pattern: ФИО (usually all caps)
    fio_pattern = re.compile(r'^([А-ЯЁ][А-ЯЁ\s\-]+[А-ЯЁ])$')
    # Pattern: date DD.MM.YYYY or DD/MM/YYYY
    date_pattern = re.compile(r'\b(\d{2}[./]\d{2}[./]\d{4})\b')
    # Pattern: route like "МСК-ТАШ" or "Москва – Ташкент"
    route_pattern = re.compile(r'([А-Яа-я]+)\s*[–—-]\s*([А-Яа-я]+)')

    current = {}
    for line in lines:
        if fio_pattern.match(line) and len(line) > 5:
            if current.get("fio"):
                results.append(current)
                current = {}
            current["fio"] = line.title()

        dates = date_pattern.findall(line)
        if dates and not current.get("date"):
            current["date"] = dates[0]

        route_m = route_pattern.search(line)
        if route_m and not current.get("route"):
            current["route"] = f"{route_m.group(1)} - {route_m.group(2)}"

        # Phone
        phone_m = re.search(r'(\+?7[\s-]?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2})', line)
        if phone_m:
            current["phone"] = phone_m.group(1)

    if current.get("fio"):
        results.append(current)

    return results
