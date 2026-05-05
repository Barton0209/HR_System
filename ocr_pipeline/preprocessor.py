# ocr_pipeline/preprocessor.py
"""
Предобработка изображений — общий модуль для Passport и Document режимов.

Цепочка (применяется последовательно):
  1. Deskew          — исправление наклона (проекционный профиль)
  2. CLAHE           — выравнивание освещённости
  3. Denoising       — удаление шума (fastNlMeans)
  4. Inpaint бликов  — восстановление пересвеченных областей
  5. Бинаризация     — Sauvola (адаптивная, устойчива к теням)

Для паспортов дополнительно:
  6. Edge-preserving — размытие фоновой сетки с сохранением текста
"""

import numpy as np
import cv2
from PIL import Image as PILImage


# ── Deskew ────────────────────────────────────────────────────────────────────

def _deskew(gray: np.ndarray) -> np.ndarray:
    """Исправляет наклон через проекционный профиль."""
    try:
        from deskew import determine_skew
        angle = determine_skew(gray)
        if angle is None or abs(angle) < 0.3:
            return gray
        h, w = gray.shape
        M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        return cv2.warpAffine(gray, M, (w, h),
                              flags=cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_REPLICATE)
    except ImportError:
        # Fallback: Hough-based deskew
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 100,
                                minLineLength=100, maxLineGap=10)
        if lines is None:
            return gray
        angles = []
        for x1, y1, x2, y2 in lines[:, 0]:
            if x2 != x1:
                angles.append(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
        if not angles:
            return gray
        median_angle = np.median(angles)
        if abs(median_angle) < 0.3 or abs(median_angle) > 45:
            return gray
        h, w = gray.shape
        M = cv2.getRotationMatrix2D((w / 2, h / 2), median_angle, 1.0)
        return cv2.warpAffine(gray, M, (w, h),
                              flags=cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_REPLICATE)


# ── Inpaint бликов ────────────────────────────────────────────────────────────

def _remove_glare(gray: np.ndarray) -> np.ndarray:
    """Восстанавливает пересвеченные области через inpaint."""
    _, glare_mask = cv2.threshold(gray, 245, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    glare_mask = cv2.dilate(glare_mask, kernel, iterations=1)
    if glare_mask.sum() == 0:
        return gray
    return cv2.inpaint(gray, glare_mask, inpaintRadius=3,
                       flags=cv2.INPAINT_TELEA)


# ── Sauvola бинаризация ───────────────────────────────────────────────────────

def _sauvola(gray: np.ndarray, window: int = 25, k: float = 0.2) -> np.ndarray:
    """Адаптивная бинаризация Sauvola — устойчива к теням и неравномерному фону."""
    try:
        from skimage.filters import threshold_sauvola
        thresh = threshold_sauvola(gray, window_size=window, k=k)
        binary = (gray > thresh).astype(np.uint8) * 255
        return binary
    except ImportError:
        # Fallback: OpenCV адаптивный порог
        return cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 31, 10
        )


# ── Публичные функции ─────────────────────────────────────────────────────────

def preprocess_for_ocr(img: np.ndarray, deskew: bool = True) -> np.ndarray:
    """
    Стандартная предобработка для Document режима.
    Возвращает бинаризованное изображение (uint8, 0/255).
    """
    # RGB → Gray
    if img.ndim == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    else:
        gray = img.copy()

    if deskew:
        gray = _deskew(gray)

    # CLAHE — выравнивание освещённости
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    # Denoising
    gray = cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7,
                                    searchWindowSize=21)

    # Sauvola бинаризация
    return _sauvola(gray)


def preprocess_for_passport(img: np.ndarray, deskew: bool = True) -> np.ndarray:
    """
    Предобработка для Passport режима.
    Дополнительно: удаление бликов + edge-preserving фильтр (убирает фоновую сетку).
    Возвращает бинаризованное изображение.
    """
    if img.ndim == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    else:
        gray = img.copy()

    if deskew:
        gray = _deskew(gray)

    # CLAHE
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    # Удаление бликов (голограммы, ламинация)
    gray = _remove_glare(gray)

    # Edge-preserving — размывает фоновую гильоширную сетку, сохраняет текст
    # Работает на цветном изображении, поэтому конвертируем туда-обратно
    color = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    color = cv2.edgePreservingFilter(color, flags=1, sigma_s=30, sigma_r=0.3)
    gray = cv2.cvtColor(color, cv2.COLOR_BGR2GRAY)

    # Denoising
    gray = cv2.fastNlMeansDenoising(gray, h=8)

    # Sauvola
    return _sauvola(gray, window=21, k=0.15)


def pil_to_numpy(pil_img: PILImage.Image) -> np.ndarray:
    """PIL Image → numpy RGB array."""
    return np.array(pil_img.convert("RGB"))


def numpy_to_pil(arr: np.ndarray) -> PILImage.Image:
    """numpy array → PIL Image."""
    if arr.ndim == 2:
        return PILImage.fromarray(arr, mode="L")
    return PILImage.fromarray(arr)
