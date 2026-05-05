# make_ocr_pdfs.py
"""
Создаёт OCR-версии PDF для всех файлов из Download/Pass/ФСБ/
которых ещё нет в Download/Pass/OCR/

Алгоритм:
  1. Рендерим каждую страницу PDF в изображение (300 DPI)
  2. Предобрабатываем (CLAHE + Sauvola)
  3. Tesseract → hOCR (содержит координаты слов)
  4. Накладываем невидимый текстовый слой поверх оригинального изображения
  5. Сохраняем как PDF с текстовым слоем в папку OCR

Запуск: python make_ocr_pdfs.py
"""

import os
import sys
import gc
import logging
import subprocess
import tempfile
from pathlib import Path

import fitz
import numpy as np
import cv2
from PIL import Image as PILImage

sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# ── Пути ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
FSB_DIR  = BASE_DIR / "Download" / "Pass" / "ФСБ"
OCR_DIR  = BASE_DIR / "Download" / "Pass" / "OCR"
OCR_DIR.mkdir(exist_ok=True)

TESSERACT = os.getenv(
    "TESSERACT_PATH",
    r"C:\Users\DerevyankoGA\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
)
LANG = "rus+eng"
DPI  = 300   # разрешение рендеринга страницы
SCALE = DPI / 72.0  # fitz использует 72 DPI по умолчанию


# ── Предобработка ─────────────────────────────────────────────────────────────

def _preprocess(img: np.ndarray) -> np.ndarray:
    """CLAHE + Sauvola бинаризация."""
    if img.ndim == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    else:
        gray = img.copy()
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    gray = cv2.fastNlMeansDenoising(gray, h=10)
    try:
        from skimage.filters import threshold_sauvola
        thresh = threshold_sauvola(gray, window_size=25, k=0.2)
        return (gray > thresh).astype(np.uint8) * 255
    except ImportError:
        return cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 31, 10
        )


# ── Tesseract → PDF с текстовым слоем ────────────────────────────────────────

def _page_to_ocr_pdf(page: fitz.Page, tmp_dir: str) -> bytes:
    """
    Рендерит одну страницу → OCR → возвращает bytes однострочного PDF
    с текстовым слоем поверх изображения.
    """
    # 1. Рендерим страницу в изображение
    mat = fitz.Matrix(SCALE, SCALE)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width, pix.n).copy()
    del pix

    # 2. Предобрабатываем для OCR
    binary = _preprocess(arr)

    # 3. Сохраняем предобработанное изображение во временный файл
    img_path = os.path.join(tmp_dir, "page.png")
    PILImage.fromarray(binary).save(img_path, dpi=(DPI, DPI))

    # 4. Tesseract → PDF (создаёт файл с текстовым слоем)
    out_base = os.path.join(tmp_dir, "out")
    result = subprocess.run(
        [TESSERACT, img_path, out_base, "-l", LANG, "--dpi", str(DPI), "pdf"],
        capture_output=True, timeout=120
    )
    if result.returncode != 0:
        logger.warning("Tesseract error: %s", result.stderr.decode('utf-8', errors='replace'))
        return None

    out_pdf = out_base + ".pdf"
    if not os.path.exists(out_pdf):
        return None

    with open(out_pdf, "rb") as f:
        pdf_bytes = f.read()

    # Удаляем временные файлы
    for p in [img_path, out_pdf]:
        try:
            os.remove(p)
        except Exception:
            pass

    return pdf_bytes


# ── Сборка многостраничного PDF ───────────────────────────────────────────────

def make_ocr_pdf(src_path: Path, dst_path: Path) -> bool:
    """
    Создаёт OCR-версию PDF: каждая страница рендерится,
    распознаётся Tesseract, результат объединяется в один PDF.
    """
    try:
        src_doc = fitz.open(str(src_path))
        page_count = len(src_doc)
    except Exception as e:
        logger.error("Не удалось открыть %s: %s", src_path.name, e)
        return False

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Собираем PDF из отдельных страниц
        result_doc = fitz.open()

        for i, page in enumerate(src_doc):
            logger.debug("  Страница %d/%d", i + 1, page_count)
            page_pdf_bytes = _page_to_ocr_pdf(page, tmp_dir)

            if page_pdf_bytes:
                # Вставляем OCR-страницу
                tmp_page_doc = fitz.open("pdf", page_pdf_bytes)
                result_doc.insert_pdf(tmp_page_doc)
                tmp_page_doc.close()
            else:
                # Если OCR не удался — вставляем оригинальную страницу
                tmp_orig = fitz.open()
                tmp_orig.insert_pdf(src_doc, from_page=i, to_page=i)
                result_doc.insert_pdf(tmp_orig)
                tmp_orig.close()

            gc.collect()

        src_doc.close()

        if len(result_doc) == 0:
            result_doc.close()
            return False

        result_doc.save(str(dst_path), garbage=4, deflate=True)
        result_doc.close()

    return True


# ── Сбор файлов для обработки ─────────────────────────────────────────────────

def collect_pending() -> list:
    """
    Возвращает список PDF которых ещё нет в папке OCR.
    """
    pending = []
    if not FSB_DIR.exists():
        logger.error("Папка ФСБ не найдена: %s", FSB_DIR)
        return pending

    for person_dir in sorted(FSB_DIR.iterdir()):
        if not person_dir.is_dir():
            continue
        fio = person_dir.name
        for pdf in sorted(person_dir.glob("*.pdf")):
            # Имя OCR-файла: ИМЯ_001-ocr.pdf
            stem = pdf.stem  # напр. "Александров Евгений Михайлович_001"
            ocr_name = f"{stem}-ocr.pdf"
            ocr_path = OCR_DIR / ocr_name
            if not ocr_path.exists():
                pending.append({"src": pdf, "dst": ocr_path, "fio": fio})

    return pending


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    pending = collect_pending()
    total = len(pending)

    if total == 0:
        print("✅ Все файлы уже имеют OCR-версии.")
        return

    logger.info("Файлов для OCR: %d", total)
    ok, fail = 0, 0

    for i, item in enumerate(pending, 1):
        src: Path = item["src"]
        dst: Path = item["dst"]
        logger.info("[%d/%d] %s", i, total, src.name)

        success = make_ocr_pdf(src, dst)
        if success:
            size_kb = dst.stat().st_size // 1024
            logger.info("  ✓ Сохранён: %s (%d KB)", dst.name, size_kb)
            ok += 1
        else:
            logger.warning("  ✗ Ошибка: %s", src.name)
            fail += 1

        gc.collect()

    print(f"\n✅ Готово! Создано: {ok}  |  Ошибок: {fail}")
    print(f"   Папка: {OCR_DIR}")


if __name__ == "__main__":
    main()
