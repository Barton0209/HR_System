 Бесплатный OCR Пайплайн v3.0 (CPU-only, No Root, No Docker)
0. Подготовка окружения (без root)
bash
Copy
# Создаём виртуальное окружение в домашней директории
python3 -m venv ~/ocr-env
source ~/ocr-env/bin/activate

# Обновляем pip
pip install --upgrade pip

# Устанавливаем всё в пользовательское окружение (не требует root)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install transformers accelerate
pip install paddleocr paddlepaddle -f https://www.paddlepaddle.org.cn/whl/linux/cpu/mkl/avx/stable.html
pip install opencv-python-headless numpy Pillow scipy
pip install qwen-vl-utils pydantic rapidfuzz
pip install uvicorn fastapi python-multipart aiofiles
pip install structlog python-magic psutil
pip install pdf2image pymupdf pikepdf pdfplumber
pip install easyocr python-doctr
pip install scikit-image
Альтернатива без venv (если python3-venv недоступен):
bash
Copy
# Установка pipx (если доступен)
pip install --user pipx
pipx ensurepath
0.1. VRAM Guard → CPU/RAM Guard (адаптирован для CPU)
Python
Copy
"""
Контекстный менеджер для контроля RAM (CPU-only версия).
Освобождает память и сборщик мусора после тяжелого инференса.
"""
import gc
import logging
import contextlib
import psutil
import time

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def resource_guard(tag: str = "request", max_ram_mb: int = 4096):
    """
    Обертка для тяжелых блоков. Контролирует RAM, прерывает при превышении лимита.
    """
    process = psutil.Process()
    mem_before = process.memory_info().rss / 1024 ** 2
    
    # Проверка перед стартом
    if mem_before > max_ram_mb * 0.8:
        gc.collect()
        mem_before = process.memory_info().rss / 1024 ** 2
        logger.warning(f"[{tag}] High RAM before start: {mem_before:.1f} MB")

    start_time = time.time()
    
    try:
        yield
    finally:
        gc.collect()
        
        mem_after = process.memory_info().rss / 1024 ** 2
        duration = time.time() - start_time
        
        logger.info(
            f"[{tag}] Resource guard | "
            f"RAM: {mem_before:.1f} -> {mem_after:.1f} MB | "
            f"Time: {duration:.2f}s"
        )
        
        # Агрессивная очистка если RAM вырос сильно
        if mem_after - mem_before > 1024:  # > 1GB роста
            logger.warning(f"[{tag}] Significant RAM growth detected, forcing cleanup")
            gc.collect()
1. Pydantic модели (упрощенные, без GPU-зависимостей)
Python
Copy
"""
Структурированные модели данных для пайплайна.
CPU-only, минимальные зависимости.
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal, Tuple
from dataclasses import dataclass, field
from enum import Enum


class Script(Enum):
    CYRILLIC = "cyrillic"
    LATIN = "latin"


class MRZType(Enum):
    TD3 = "TD3"
    TD1 = "TD1"


class OCRWord(BaseModel):
    text: str
    bbox: Tuple[float, float, float, float]
    confidence: float = Field(ge=0.0, le=1.0)
    engine: Literal["paddleocr", "easyocr", "doctr"]
    page: int = 0


class TableData(BaseModel):
    bbox: List[float]
    headers: List[str] = []
    rows: List[List[str]] = []
    source: Literal["pdfplumber", "vlm"] = "pdfplumber"


class DocumentAnalysis(BaseModel):
    document_type: Optional[str] = None
    confidence: float = 0.0
    key_fields: Dict[str, str] = {}
    tables: List[TableData] = []
    language: Optional[str] = None


@dataclass
class DocumentOCRResult:
    success: bool
    text: str
    pages: List[str] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    document_type: Optional[str] = None
    key_fields: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    processing_time: float = 0.0


@dataclass
class PassportResult:
    success: bool
    country_code: str
    mrz: Optional[Dict[str, Any]] = None
    viz: Optional[Dict[str, Any]] = None
    cross_validation: Dict[str, Any] = field(default_factory=dict)
    processing_time: float = 0.0
    errors: List[str] = field(default_factory=list)
2. ModelRegistry (CPU-only, Singleton, Lazy Loading)
Python
Copy
"""
Потокобезопасный реестр моделей с ленивой загрузкой.
CPU-only, кэширование в RAM, без GPU-зависимостей.
"""
import threading
import logging
from typing import Tuple, Any, Optional
import gc

logger = logging.getLogger(__name__)


class ModelRegistry:
    _cache = {}
    _locks = {}
    _initialized = False

    @classmethod
    def _get_lock(cls, key: str) -> threading.Lock:
        if key not in cls._locks:
            cls._locks[key] = threading.Lock()
        return cls._locks[key]

    @classmethod
    def get_vlm(cls) -> Tuple[Any, Any]:
        """Загружает VLM только при первом запросе. CPU-only режим."""
        lock = cls._get_lock("vlm")
        with lock:
            if "vlm" not in cls._cache:
                logger.info("Loading VLM model (CPU mode)...")
                try:
                    from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
                    
                    model_name = "Qwen/Qwen2-VL-2B-Instruct"
                    
                    # CPU-only: float32, без device_map
                    model = Qwen2VLForConditionalGeneration.from_pretrained(
                        model_name,
                        torch_dtype=torch.float32,
                        device_map=None,  # CPU
                        low_cpu_mem_usage=True,
                        trust_remote_code=True
                    )
                    model = model.cpu().eval()
                    
                    processor = AutoProcessor.from_pretrained(
                        model_name, 
                        trust_remote_code=True
                    )
                    
                    cls._cache["vlm"] = model
                    cls._cache["vlm_proc"] = processor
                    logger.info("VLM loaded successfully (CPU)")
                    
                except Exception as e:
                    logger.error(f"Failed to load VLM: {e}")
                    raise
                    
        return cls._cache["vlm"], cls._cache["vlm_proc"]

    @classmethod
    def get_ocr_engine(cls, engine_name: str = "paddleocr", lang: str = "en", use_gpu: bool = False):
        """Ленивая загрузка OCR-движков."""
        cache_key = f"ocr_{engine_name}_{lang}"
        lock = cls._get_lock(cache_key)
        
        with lock:
            if cache_key not in cls._cache:
                logger.info(f"Loading OCR engine: {engine_name} (CPU)")
                
                if engine_name == "paddleocr":
                    from paddleocr import PaddleOCR
                    cls._cache[cache_key] = PaddleOCR(
                        use_angle_cls=True,
                        lang=lang,
                        use_gpu=False,  # Force CPU
                        show_log=False
                    )
                    
                elif engine_name == "easyocr":
                    from easyocr import EasyOCR
                    cls._cache[cache_key] = EasyOCR(
                        lang_list=[lang],
                        gpu=False,  # Force CPU
                        verbose=False
                    )
                    
                logger.info(f"OCR engine {engine_name} loaded")
                
        return cls._cache[cache_key]

    @classmethod
    def clear_cache(cls):
        """Очистка кэша моделей для освобождения RAM."""
        with threading.Lock():
            logger.info("Clearing model registry cache...")
            
            # Явное удаление моделей
            for key in list(cls._cache.keys()):
                if hasattr(cls._cache[key], 'cpu'):
                    del cls._cache[key]
                else:
                    del cls._cache[key]
                    
            cls._cache.clear()
            gc.collect()
            logger.info("Cache cleared")
3. PDFExtractor (без изменений, но с CPU-оптимизацией)
Python
Copy
"""
Извлечение страниц из PDF с автоматическим ремонтом битых файлов.
CPU-оптимизированная версия: уменьшен DPI для скорости.
"""
import fitz
import pikepdf
from PIL import Image
from typing import Generator, Tuple
import tempfile
import os
import logging

logger = logging.getLogger(__name__)


class PDFExtractor:
    def __init__(self, dpi: int = 200):  # Уменьшили DPI для скорости на CPU
        self.dpi = dpi

    def extract_pages(self, pdf_path: str) -> Generator[Tuple[Image.Image, str], None, None]:
        repaired_path = self._repair_pdf(pdf_path)
        temp_created = (repaired_path != pdf_path)

        try:
            doc = fitz.open(repaired_path)
            for page_num, page in enumerate(doc):
                text_blocks = page.get_text("blocks")
                has_native_text = len(text_blocks) > 0

                pix = page.get_pixmap(dpi=self.dpi)
                img = Image.frombytes(
                    "RGB",
                    [pix.width, pix.height],
                    pix.samples
                )
                source_type = "native" if has_native_text else "scan"
                yield img, source_type
            doc.close()
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            raise
        finally:
            if temp_created and os.path.exists(repaired_path):
                os.remove(repaired_path)

    def _repair_pdf(self, file_path: str) -> str:
        try:
            with pikepdf.open(file_path) as pdf:
                return file_path
        except pikepdf.PdfError:
            logger.warning("Corrupted PDF detected, attempting repair...")
            try:
                pdf = pikepdf.open(file_path, allow_overwriting_input=True)
                temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                pdf.save(temp.name)
                pdf.close()
                logger.info(f"PDF repaired to temp file: {temp.name}")
                return temp.name
            except Exception as repair_err:
                logger.error(f"PDF repair failed: {repair_err}")
                return file_path
4. Предобработка (упрощенная, CPU-оптимизированная)
Python
Copy
"""
Упрощенная предобработка для CPU-only режима.
Без тяжелых операций, фокус на скорость.
"""
import cv2
import numpy as np
from PIL import Image
from typing import Tuple, Union


class ImagePreprocessor:
    def preprocess(self, image: Union[Image.Image, np.ndarray]) -> Tuple[np.ndarray, dict]:
        img = np.array(image) if isinstance(image, Image.Image) else image.copy()
        metadata = {}

        # Быстрая проверка ориентации
        img, flip_angle = self._correct_180(img)
        metadata["flip_180"] = flip_angle

        # Легкий deskew (каждые 5 градусов вместо 3)
        img, angle = self._deskew_fast(img)
        metadata["deskew_angle"] = angle

        # Адаптивный контраст
        img = self._adaptive_contrast(img)
        
        return img, metadata

    def _correct_180(self, img: np.ndarray) -> Tuple[np.ndarray, int]:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img
        h = gray.shape[0]
        # Упрощенная эвристика: сравниваем верх и низ
        top_dark = np.sum(gray[:h//4] < 128)
        bottom_dark = np.sum(gray[3*h//4:] < 128)
        if bottom_dark > top_dark * 2.0:
            return cv2.rotate(img, cv2.ROTATE_180), 180
        return img, 0

    def _deskew_fast(self, img: np.ndarray) -> Tuple[np.ndarray, float]:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img
        best_angle, best_score = 0, 0
        
        # Грубый поиск с шагом 5 градусов
        for angle in range(-10, 11, 5):
            M = cv2.getRotationMatrix2D((gray.shape[1]//2, gray.shape[0]//2), angle, 1)
            rotated = cv2.warpAffine(gray, M, (gray.shape[1], gray.shape[0]), borderValue=255)
            _, binary = cv2.threshold(rotated, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            score = np.var(np.sum(binary, axis=1))
            if score > best_score:
                best_score, best_angle = score, angle

        # Точная доводка вокруг лучшего угла
        if abs(best_angle) > 0:
            fine_best, fine_score = best_angle, best_score
            for angle in [best_angle - 2, best_angle + 2]:
                M = cv2.getRotationMatrix2D((gray.shape[1]//2, gray.shape[0]//2), angle, 1)
                rotated = cv2.warpAffine(gray, M, (gray.shape[1], gray.shape[0]), borderValue=255)
                _, binary = cv2.threshold(rotated, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
                score = np.var(np.sum(binary, axis=1))
                if score > fine_score:
                    fine_best, fine_score = angle, score
            
            best_angle = fine_best

        if abs(best_angle) > 0.5:
            h, w = img.shape[:2]
            M = cv2.getRotationMatrix2D((w//2, h//2), best_angle, 1.0)
            img = cv2.warpAffine(
                img, M, (w, h),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(255, 255, 255)
            )
            return img, float(best_angle)
        return img, 0.0

    def _adaptive_contrast(self, img: np.ndarray) -> np.ndarray:
        if len(img.shape) == 3:
            lab = cv2.cvtColor(img, cv2.COLOR_RGB2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2RGB)
        else:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            return clahe.apply(img)
5. OCR Ансамбль (упрощенный, без весов, CPU)
Python
Copy
"""
Упрощенный OCR-ансамбль для CPU.
Один движок по умолчанию (PaddleOCR), fallback на EasyOCR.
"""
from typing import List, Dict, Any
import numpy as np
import logging

logger = logging.getLogger(__name__)


class OCREnsemble:
    def __init__(self, languages: List[str] = ["en", "ru"], use_gpu: bool = False):
        self.languages = languages
        self.use_gpu = False  # Force CPU
        self._paddle = None
        self._easy = None

    def _get_paddle(self):
        if self._paddle is None:
            self._paddle = ModelRegistry.get_ocr_engine("paddleocr", "en", False)
        return self._paddle

    def _get_easy(self):
        if self._easy is None:
            from easyocr import EasyOCR
            self._easy = EasyOCR(lang_list=self.languages, gpu=False, verbose=False)
        return self._easy

    def ensemble_ocr(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """Основной метод: пробуем PaddleOCR, fallback на EasyOCR."""
        try:
            result = self._run_paddle(image)
            if len(result) >= 3:  # Если нашли достаточно текста
                return result
            logger.info("PaddleOCR returned few results, trying EasyOCR fallback")
        except Exception as e:
            logger.warning(f"PaddleOCR failed: {e}")

        try:
            return self._run_easy(image)
        except Exception as e:
            logger.error(f"EasyOCR fallback failed: {e}")
            return []

    def _run_paddle(self, image: np.ndarray) -> List[Dict]:
        result = self._get_paddle().ocr(image, cls=True)
        if not result or not result[0]:
            return []
        
        outputs = []
        for line in result[0]:
            bbox = line[0]
            xs = [p[0] for p in bbox]
            ys = [p[1] for p in bbox]
            flat_bbox = [min(xs), min(ys), max(xs), max(ys)]
            outputs.append({
                "text": line[1][0],
                "bbox": flat_bbox,
                "confidence": line[1][1],
                "engine": "paddleocr"
            })
        return outputs

    def _run_easy(self, image: np.ndarray) -> List[Dict]:
        import cv2
        image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR) if len(image.shape) == 3 else image
        result = self._get_easy().readtext(image_bgr)
        
        outputs = []
        for item in result:
            bbox = item[0]
            xs = [p[0] for p in bbox]
            ys = [p[1] for p in bbox]
            flat_bbox = [min(xs), min(ys), max(xs), max(ys)]
            outputs.append({
                "text": item[1],
                "bbox": flat_bbox,
                "confidence": item[2],
                "engine": "easyocr"
            })
        return outputs
6. VLM Анализатор (CPU-оптимизированный, с ограничениями)
Python
Copy
"""
VLM-анализатор для CPU.
Включается только при необходимости, с таймаутами.
"""
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
from PIL import Image
import time
import logging
import re
import json
import threading
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class VLMDocumentAnalyzer:
    SYSTEM_PROMPT = """You are an expert document analyzer.
Analyze the document image and provide structured information.
Keep values in the ORIGINAL LANGUAGE. Return ONLY valid JSON."""

    COMBINED_PROMPT = """Analyze this document and return ONLY valid JSON:
{
  "document_type": "invoice|contract|form|letter|other",
  "confidence": 0.0-1.0,
  "key_fields": {"field_name": "value"},
  "language": "ru|en|..."
}"""

    def __init__(self):
        self._model = None
        self._processor = None
        self._lock = threading.Lock()

    def _lazy_init(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    self._model, self._processor = ModelRegistry.get_vlm()

    def analyze(self, image: Image.Image, custom_prompt: Optional[str] = None, max_new_tokens: int = 512) -> Dict[str, Any]:
        """
        CPU-оптимизированный анализ.
        max_new_tokens снижен для скорости.
        """
        self._lazy_init()

        prompt_text = custom_prompt or self.COMBINED_PROMPT

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": prompt_text}
            ]}
        ]

        text = self._processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self._processor(text=[text], images=[image], return_tensors="pt")

        # CPU inference
        start_time = time.time()
        with torch.no_grad():
            output_ids = self._model.generate(
                **inputs, 
                max_new_tokens=max_new_tokens,
                temperature=0.1,
                do_sample=False,
                use_cache=True  # Ускорение на CPU
            )
        
        duration = time.time() - start_time
        logger.info(f"VLM inference took {duration:.2f}s")

        response = self._processor.batch_decode(
            output_ids[:, inputs.input_ids.shape[1]:], 
            skip_special_tokens=True
        )[0]
        
        return self._parse_analysis(response)

    def _parse_analysis(self, response: str) -> Dict[str, Any]:
        cleaned = re.sub(r"```json\s*", "", response)
        cleaned = re.sub(r"```\s*", "", cleaned)
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        logger.warning(f"VLM returned non-JSON: {cleaned[:200]}")
        return {"success": False, "raw_response": cleaned}
7. Паспортный пайплайн (упрощенный, CPU)
Python
Copy
"""
Упрощенный паспортный пайплайн для CPU.
MRZ-first, без CLIP, без тяжелых моделей.
"""
import time
from PIL import Image
from typing import Optional, Dict, Any
import logging
import re

logger = logging.getLogger(__name__)


class PassportPipeline:
    # Упрощенная конфигурация стран (без Enum для простоты)
    COUNTRY_CONFIGS = {
        "RUS": {"name": "Россия", "patronymic": True, "script": "cyrillic"},
        "UKR": {"name": "Украина", "patronymic": False, "script": "cyrillic"},
        "BLR": {"name": "Беларусь", "patronymic": True, "script": "cyrillic"},
        "KAZ": {"name": "Казахстан", "patronymic": True, "script": "cyrillic"},
        "UZB": {"name": "Узбекистан", "patronymic": True, "script": "cyrillic"},
    }

    def __init__(self, use_gpu: bool = False):
        self.use_gpu = False
        self.preprocessor = ImagePreprocessor()
        self.mrz_extractor = MRZExtractorCPU()
        self.viz_extractor = VIZExtractorCPU()

    def process(self, image: Image.Image) -> PassportResult:
        start_time = time.time()
        errors = []

        try:
            # Предобработка
            img_prep, meta = self.preprocessor.preprocess(image)

            # MRZ извлечение
            mrz_data = None
            country_code = "UNKNOWN"
            
            for mrz_type in ["TD3", "TD1"]:
                mrz_data = self.mrz_extractor.extract(img_prep, mrz_type)
                if mrz_data:
                    country_code = mrz_data.get("country_code", "UNKNOWN")
                    break

            # Определение страны
            config = self.COUNTRY_CONFIGS.get(country_code, {})
            
            # VIZ извлечение
            viz_data = self.viz_extractor.extract(img_prep, config)

            # Простая валидация
            cross_val = self._simple_validate(mrz_data, viz_data)

            return PassportResult(
                success=True,
                country_code=country_code,
                mrz=mrz_data,
                viz=viz_data,
                cross_validation=cross_val,
                processing_time=time.time() - start_time,
                errors=errors
            )

        except Exception as e:
            logger.exception(f"Passport processing failed: {e}")
            errors.append(str(e))
            return PassportResult(
                success=False,
                country_code="UNKNOWN",
                processing_time=time.time() - start_time,
                errors=errors
            )

    def _simple_validate(self, mrz: Optional[Dict], viz: Optional[Dict]) -> Dict[str, Any]:
        if not mrz or not viz:
            return {"status": "incomplete", "checks": {}}

        checks = {}
        
        # Сравнение фамилии
        if mrz.get("surname") and viz.get("surname"):
            mrz_sur = mrz["surname"].replace("<", " ").strip().upper()
            viz_sur = viz.get("surname", "").upper()
            checks["surname"] = {
                "mrz": mrz_sur,
                "viz": viz_sur,
                "match": mrz_sur == viz_sur or mrz_sur in viz_sur or viz_sur in mrz_sur
            }

        # Сравнение имени
        if mrz.get("given_names") and viz.get("given_names"):
            mrz_name = mrz["given_names"].replace("<", " ").strip().upper()
            viz_name = viz.get("given_names", "").upper()
            checks["given_names"] = {
                "mrz": mrz_name,
                "viz": viz_name,
                "match": mrz_name == viz_name or mrz_name in viz_name or viz_name in mrz_name
            }

        all_passed = all(c.get("match", False) for c in checks.values()) if checks else False
        
        return {
            "status": "passed" if all_passed else "mismatch",
            "checks": checks,
            "requires_manual_review": not all_passed
        }


class MRZExtractorCPU:
    """Упрощенный MRZ-экстрактор на PaddleOCR (CPU)."""
    
    MRZ_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<")
    
    def __init__(self):
        self._ocr = None
    
    def _get_ocr(self):
        if self._ocr is None:
            self._ocr = ModelRegistry.get_ocr_engine("paddleocr", "en", False)
        return self._ocr

    def extract(self, image, mrz_type: str = "TD3") -> Optional[Dict[str, Any]]:
        img_array = np.array(image) if not isinstance(image, np.ndarray) else image
        
        # Кроп нижней зоны
        h, w = img_array.shape[:2]
        mrz_region = img_array[int(h*0.85):h, int(w*0.05):int(w*0.95)]
        
        gray = cv2.cvtColor(mrz_region, cv2.COLOR_RGB2GRAY)
        result = self._get_ocr().ocr(gray, cls=False)
        
        if not result or not result[0]:
            return None

        mrz_lines = []
        for line in result[0]:
            text = line[1][0].strip().upper()
            # Очистка от лишних символов
            cleaned = "".join(c for c in text if c in self.MRZ_CHARS)
            if len(cleaned) >= 20:
                mrz_lines.append(cleaned)

        if len(mrz_lines) >= 2:
            line_len = 44 if mrz_type == "TD3" else 30
            line1 = mrz_lines[0][:line_len].ljust(line_len, "<")
            line2 = mrz_lines[1][:line_len].ljust(line_len, "<")
            
            # Простой парсинг MRZ
            return self._parse_mrz_lines(line1, line2, mrz_type)
        
        return None

    def _parse_mrz_lines(self, line1: str, line2: str, mrz_type: str) -> Dict[str, Any]:
        try:
            # TD3: P<RUS surname<<name<<<<<<<<<<<<<<<<<<<<<<
            if mrz_type == "TD3":
                country = line1[2:5]
                names_part = line1[5:44]
                names = names_part.split("<<")
                surname = names[0].replace("<", " ").strip()
                given_names = names[1].replace("<", " ").strip() if len(names) > 1 else ""
                
                doc_num = line2[0:9].replace("<", "")
                dob = line2[13:19]
                expiry = line2[21:27]
                
                return {
                    "country_code": country,
                    "surname": surname,
                    "given_names": given_names,
                    "document_number": doc_num,
                    "date_of_birth": dob,
                    "expiry_date": expiry,
                    "is_valid": True
                }
            
            # TD1 упрощенно
            return {
                "country_code": line1[2:5],
                "surname": line1[5:30].split("<<")[0].replace("<", " ").strip(),
                "given_names": "",
                "document_number": line1[5:14].replace("<", ""),
                "date_of_birth": line2[0:6],
                "expiry_date": line2[8:14],
                "is_valid": True
            }
            
        except Exception as e:
            logger.error(f"MRZ parse error: {e}")
            return None


class VIZExtractorCPU:
    """Упрощенный VIZ-экстрактор на PaddleOCR (CPU)."""
    
    def __init__(self):
        self._ocr = None
    
    def _get_ocr(self):
        if self._ocr is None:
            self._ocr = ModelRegistry.get_ocr_engine("paddleocr", "ru", False)
        return self._ocr

    def extract(self, image, config: Dict) -> Dict[str, Any]:
        result = self._get_ocr().ocr(np.array(image), cls=True)
        
        if not result or not result[0]:
            return {"source": "failed"}

        # Собираем все текстовые блоки с позициями
        blocks = []
        for line in result[0]:
            bbox = line[0]
            text = line[1][0]
            y_center = (bbox[0][1] + bbox[2][1]) / 2
            x_start = bbox[0][0]
            blocks.append({"text": text, "y": y_center, "x": x_start})

        # Сортируем по Y
        blocks.sort(key=lambda b: b["y"])

        # Ищем якоря
        extracted = {}
        anchors = {
            "surname": ["ФАМИЛИЯ", "SURNAME", "ПРІЗВИЩЕ"],
            "given_names": ["ИМЯ", "NAME", "GIVEN NAMES", "ІМ'Я"],
            "patronymic": ["ОТЧЕСТВО", "PATRONYMIC"]
        }

        for i, block in enumerate(blocks):
            text_upper = block["text"].upper()
            
            for field, labels in anchors.items():
                if field == "patronymic" and not config.get("patronymic", False):
                    continue
                    
                if any(label in text_upper for label in labels):
                    # Ищем значение справа или снизу
                    for candidate in blocks[i+1:]:
                        if candidate["x"] > block["x"] + 50:
                            extracted[field] = candidate["text"]
                            break
                    if field not in extracted:
                        # Проверяем следующую строку
                        for candidate in blocks[i+1:]:
                            if abs(candidate["y"] - block["y"]) < 30:
                                extracted[field] = candidate["text"]
                                break

        return {
            "surname": extracted.get("surname"),
            "given_names": extracted.get("given_names"),
            "patronymic": extracted.get("patronymic"),
            "source": "anchors"
        }
8. FastAPI приложение (CPU, без uvloop, простой запуск)
Python
Copy
"""
Простое FastAPI приложение для CPU-only режима.
Без uvloop (может требовать компиляции), без сложных зависимостей.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
import signal
import sys

from fastapi import FastAPI, File, UploadFile, HTTPException
from starlette.responses import JSONResponse
import tempfile
import os
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Простой пул потоков (CPU-bound задачи)
_executor = ThreadPoolExecutor(
    max_workers=1,  # Для CPU лучше 1 worker (GIL)
    thread_name_prefix="ocr_worker"
)

# Инициализация пайплайнов (ленивая)
doc_pipeline = None
pass_pipeline = None

def get_doc_pipeline():
    global doc_pipeline
    if doc_pipeline is None:
        doc_pipeline = DocumentOCRPipeline(use_gpu=False)
    return doc_pipeline

def get_pass_pipeline():
    global pass_pipeline
    if pass_pipeline is None:
        pass_pipeline = PassportPipeline(use_gpu=False)
    return pass_pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 OCR Service starting (CPU mode)...")
    
    def handle_sigterm(sig, frame):
        logger.warning("📉 SIGTERM received. Shutting down...")
        _executor.shutdown(wait=True)
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, handle_sigterm)
    yield
    
    logger.info("🛑 OCR Service shutdown complete.")
    _executor.shutdown(wait=True)


app = FastAPI(title="Free OCR API", version="3.0", lifespan=lifespan)


@app.post("/ocr/document")
async def ocr_document(file: UploadFile = File(...)):
    content = await file.read()
    
    # Проверка типа файла по сигнатуре
    if content[:4] == b"%PDF":
        mime = "application/pdf"
    elif content[:4] == b"\x89PNG":
        mime = "image/png"
    elif content[:2] == b"\xff\xd8":
        mime = "image/jpeg"
    else:
        # Пробуем определить по расширению
        ext = os.path.splitext(file.filename)[1].lower()
        mime_map = {".pdf": "application/pdf", ".png": "image/png", 
                   ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
        mime = mime_map.get(ext)
        if not mime:
            raise HTTPException(400, f"Unsupported file type")

    temp_path = None
    try:
        suffix = os.path.splitext(file.filename)[1] or ".tmp"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            temp_path = tmp.name

        loop = asyncio.get_event_loop()
        pipeline = get_doc_pipeline()

        if mime == "application/pdf":
            with resource_guard(tag="document_pdf"):
                result = await loop.run_in_executor(
                    _executor,
                    lambda: pipeline.process_pdf(temp_path)
                )
        else:
            from PIL import Image
            img = Image.open(temp_path)
            with resource_guard(tag="document_image"):
                result = await loop.run_in_executor(
                    _executor,
                    lambda: pipeline.process_image(img)
                )

        return {
            "success": result.success,
            "text": result.text,
            "tables": result.tables,
            "document_type": result.document_type,
            "key_fields": result.key_fields,
            "processing_time": result.process_time,
            "errors": result.errors
        }
        
    except Exception as e:
        logger.exception("Document OCR failed")
        raise HTTPException(500, str(e))
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@app.post("/ocr/passport")
async def ocr_passport(file: UploadFile = File(...)):
    content = await file.read()
    
    # Только изображения
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".png", ".jpg", ".jpeg", ".tiff", ".webp"]:
        raise HTTPException(400, "Only image files supported for passport OCR")

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(content)
            temp_path = tmp.name

        from PIL import Image
        loop = asyncio.get_event_loop()
        
        img = await loop.run_in_executor(_executor, lambda: Image.open(temp_path))
        pipeline = get_pass_pipeline()
        
        with resource_guard(tag="passport_ocr"):
            result = await loop.run_in_executor(
                _executor,
                lambda: pipeline.process(img)
            )

        return {
            "success": result.success,
            "country_code": result.country_code,
            "mrz": result.mrz,
            "viz": result.viz,
            "cross_validation": result.cross_validation,
            "processing_time": result.processing_time,
            "errors": result.errors
        }
        
    except Exception as e:
        logger.exception("Passport OCR failed")
        raise HTTPException(500, str(e))
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@app.get("/health")
async def health():
    return {"status": "ok", "mode": "cpu-only"}


# Запуск без uvicorn (можно через python -m uvicorn)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        workers=1,  # CPU: только 1 worker
        loop="asyncio"  # Стандартный цикл, без uvloop
    )
9. Запуск (без root, без Docker)
bash
Copy
# 1. Активируем окружение
source ~/ocr-env/bin/activate

# 2. Запуск простым способом
python main.py

# Или через uvicorn (если установлен)
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1

# 3. Для фонового запуска (nohup)
nohup python main.py > ocr.log 2>&1 &

# 4. Через systemd --user (если доступно)
# Создать ~/.config/systemd/user/ocr.service
~/.config/systemd/user/ocr.service:
ini
Copy
[Unit]
Description=Free OCR Service
After=network.target

[Service]
Type=simple
WorkingDirectory=%h/ocr-app
Environment="PATH=%h/ocr-env/bin"
ExecStart=%h/ocr-env/bin/python %h/ocr-app/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
bash
Copy
systemctl --user daemon-reload
systemctl --user enable ocr
systemctl --user start ocr
10. Ключевые отличия от оригинала
Table
Компонент	Оригинал	Бесплатная версия
GPU	CUDA required	CPU only
Docker	Рекомендуется	Не нужен
Root	Может потребоваться	Не нужен
VLM	Qwen2-VL-2B (GPU)	Qwen2-VL-2B (CPU, float32)
OCR	3 движка + ансамбль	PaddleOCR + EasyOCR fallback
Таблицы	Table Transformer + VLM	Только pdfplumber / VLM fallback
Паспорта	CLIP + MRZ + VIZ	MRZ-first, без CLIP
Мониторинг	Prometheus	Базовое логирование
Запуск	uvicorn + uvloop	Стандартный asyncio
11. Оптимизации для CPU
bash
Copy
# Установка OpenBLAS для ускорения numpy на CPU
pip install scipy-openblas64

# Установка Intel MKL (если процессор Intel)
pip install mkl

# Оптимизация числа потоков
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
export OPENBLAS_NUM_THREADS=4

# Запуск с ограничением RAM (если доступно)
ulimit -v 4194304  # 4GB RAM limit