"""
Core preprocessing module — общая предобработка изображений.
"""

import cv2
import numpy as np
from typing import Tuple, Optional


def deskew(img: np.ndarray) -> Tuple[np.ndarray, float]:
    """
    Коррекция перекоса через преобразование Хафа.

    Returns:
        (изображение, угол поворота)
    """
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    else:
        gray = img

    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=100)

    if lines is not None and len(lines) > 3:
        angles = []
        for line in lines[:20]:
            rho, theta = line[0]
            angle = np.degrees(theta) - 90
            if -45 < angle < 45:
                angles.append(angle)

        if angles:
            median_angle = float(np.median(angles))
            if abs(median_angle) > 0.5:
                h, w = img.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
                rotated = cv2.warpAffine(
                    img, M, (w, h),
                    flags=cv2.INTER_CUBIC,
                    borderMode=cv2.BORDER_REPLICATE
                )
                return rotated, median_angle

    return img, 0.0


def remove_moire(img: np.ndarray) -> np.ndarray:
    """
    Подавление муара через FFT-фильтрацию.
    """
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    else:
        gray = img

    # FFT
    dft = np.fft.fftshift(np.fft.fft2(gray))
    magnitude = np.log(np.abs(dft) + 1)

    h, w = magnitude.shape
    cy, cx = h // 2, w // 2
    y, x = np.ogrid[:h, :w]
    dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)

    # Полоса муара
    lo, hi = int(min(h, w) * 0.05), int(min(h, w) * 0.15)
    moire_band = (dist > lo) & (dist < hi)

    if magnitude[moire_band].mean() > magnitude.mean() * 2.5:
        mask = np.ones_like(dft, dtype=np.float32)
        mask[moire_band] = 0.3
        result = np.real(np.fft.ifft2(np.fft.ifftshift(dft * mask))).astype(np.uint8)
        result = cv2.bilateralFilter(result, 5, 30, 30)

        if len(img.shape) == 3:
            return cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)
        return result

    return img


def apply_clahe(img: np.ndarray, clip_limit: float = 2.0) -> np.ndarray:
    """
    Применение CLAHE (Contrast Limited Adaptive Histogram Equalization).
    Работает в LAB цветовом пространстве для цветных изображений.
    """
    if len(img.shape) == 3:
        lab = cv2.cvtColor(img, cv2.COLOR_RGB2LAB)
        l, a, b = cv2.split(lab)

        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
        l = clahe.apply(l)

        lab = cv2.merge([l, a, b])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
    else:
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
        return clahe.apply(img)


def sharpen_text(img: np.ndarray, strength: float = 0.3) -> np.ndarray:
    """
    Избирательное повышение резкости текстовых областей.
    """
    kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])

    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    else:
        gray = img

    # Маска текстовых областей
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, text_mask = cv2.threshold(cv2.subtract(gray, blur), 15, 255, cv2.THRESH_BINARY)
    text_mask = cv2.dilate(text_mask, np.ones((2, 2), np.uint8)) / 255.0

    # Повышение резкости
    sharpened = cv2.filter2D(img, -1, kernel)

    # Применяем только к текстовым областям
    if len(img.shape) == 3:
        m = cv2.cvtColor(text_mask.astype(np.float32), cv2.COLOR_GRAY2RGB) * strength
        result = np.clip(img * (1 - m) + sharpened * m, 0, 255).astype(np.uint8)
    else:
        result = np.clip(img * (1 - text_mask * strength) + sharpened * (text_mask * strength), 0, 255).astype(np.uint8)

    return result


def binarize(img: np.ndarray, method: str = "otsu") -> np.ndarray:
    """
    Бинаризация изображения.

    Args:
        img: Входное изображение (RGB или grayscale)
        method: "otsu" или "adaptive"

    Returns:
        Бинаризованное изображение (grayscale)
    """
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    else:
        gray = img

    # Удаление шума
    gray = cv2.medianBlur(gray, 3)

    if method == "otsu":
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    elif method == "adaptive":
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )
    else:
        raise ValueError(f"Unknown method: {method}")

    return binary


def preprocess_for_ocr(
    img: np.ndarray,
    deskew_image: bool = True,
    remove_moire_pattern: bool = True,
    apply_clahe_filter: bool = True,
    sharpen: bool = True,
    binarize_image: bool = True,
) -> np.ndarray:
    """
    Полный пайплайн предобработки для OCR.

    Args:
        img: Входное изображение (RGB)
        deskew_image: Коррекция перекоса
        remove_moire_pattern: Удаление муара
        apply_clahe_filter: Применение CLAHE
        sharpen: Повышение резкости
        binarize_image: Бинаризация

    Returns:
        Обработанное изображение
    """
    result = img.copy()

    if deskew_image:
        result, _ = deskew(result)

    if remove_moire_pattern:
        result = remove_moire(result)

    if apply_clahe_filter:
        result = apply_clahe(result)

    if sharpen:
        result = sharpen_text(result)

    if binarize_image:
        result = binarize(result)

    return result


def resize_if_needed(img: np.ndarray, max_size: int = 4096) -> np.ndarray:
    """
    Изменение размера изображения если оно слишком большое.
    """
    h, w = img.shape[:2]
    max_dim = max(h, w)

    if max_dim > max_size:
        scale = max_size / max_dim
        new_w = int(w * scale)
        new_h = int(h * scale)
        return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

    return img


def normalize_for_vlm(img: np.ndarray, target_size: Optional[Tuple[int, int]] = None) -> np.ndarray:
    """
    Нормализация изображения для VLM модели.
    """
    # Убедимся что RGB
    if len(img.shape) == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)

    # Изменение размера если нужно
    if target_size:
        img = cv2.resize(img, target_size, interpolation=cv2.INTER_LANCZOS4)

    # Нормализация значений
    img = img.astype(np.float32) / 255.0

    return img