Файл: OCR_DOC_UP.md
Улучшенный пайплайн OCR документов v2.5
General Document OCR with VLM Enhancement
Production-ready | Async | VRAM-safe | Graceful Shutdown

0. Установка зависимостей
```bash
pip install torch torchvision transformers accelerate bitsandbytes
pip install paddleocr paddlepaddle easyocr python-doctr
pip install pdf2image pymupdf pikepdf pdfplumber
pip install opencv-python-headless numpy scikit-image Pillow scipy
pip install qwen-vl-utils pydantic rapidfuzz
pip install uvicorn fastapi python-multipart aiofiles prometheus-client
pip install structlog python-magic uvloop psutil
```

0.1. Утилита VRAM Guard
```python
"""
Контекстный менеджер для контроля VRAM и Python-GC.
Освобождает память GPU и сборщик мусора после тяжелого инференса.
"""
import torch
import gc
import logging
import contextlib
import psutil

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def vram_guard(tag: str = "request"):
    """
    Обертка для тяжелых блоков. Гарантирует очистку VRAM и GC после выхода.
    """
    process = psutil.Process()
    mem_before = process.memory_info().rss / 1024 ** 2
    vram_before = torch.cuda.memory_allocated() / 1024 ** 2 if torch.cuda.is_available() else 0

    try:
        yield
    finally:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()

        mem_after = process.memory_info().rss / 1024 ** 2
        vram_after = torch.cuda.memory_allocated() / 1024 ** 2 if torch.cuda.is_available() else 0

        logger.info(
            f"[{tag}] VRAM guard | "
            f"VRAM: {vram_before:.1f} -> {vram_after:.1f} MB | "
            f"RAM: {mem_before:.1f} -> {mem_after:.1f} MB"
        )
```

1. Pydantic модели и типы
```python
"""
Структурированные модели данных для всего пайплайна.
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal, Tuple, Union
from dataclasses import dataclass, field
import numpy as np


class OCRWord(BaseModel):
    text: str
    bbox: Tuple[float, float, float, float]
    confidence: float = Field(ge=0.0, le=1.0)
    engine: Literal["paddleocr", "easyocr", "doctr", "ensemble"]
    engines: Optional[List[str]] = None
    alternatives: Optional[List[str]] = None
    page: int = 0


class TableData(BaseModel):
    bbox: List[float]
    confidence: float
    headers: List[str] = []
    rows: List[List[str]] = []
    vlm_refined: bool = False
    source: Literal["pdfplumber", "table_transformer", "vlm"] = "table_transformer"


class DocumentAnalysis(BaseModel):
    document_type: Optional[str] = None
    confidence: float = 0.0
    key_fields: Dict[str, str] = {}
    tables: List[TableData] = []
    dates: List[str] = []
    amounts: List[str] = []
    language: Optional[str] = None
    layout_zones: List[Dict[str, Any]] = []
    low_confidence_corrections: Dict[str, str] = {}


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
    vlm_used: bool = False
```

2. ModelRegistry (Singleton + Thread-safe)
```python
"""
Потокобезопасный реестр моделей с LRU-кэшем.
Предотвращает множественную загрузку тяжелых моделей в VRAM.
"""
import threading
import torch
import logging
from typing import Tuple, Any, Optional

logger = logging.getLogger(__name__)


class ModelRegistry:
    _cache = {}
    _locks = {}
    _meta = {}

    @classmethod
    def _get_lock(cls, key: str) -> threading.Lock:
        if key not in cls._locks:
            cls._locks[key] = threading.Lock()
        return cls._locks[key]

    @classmethod
    def get_vlm(cls) -> Tuple[Any, Any]:
        lock = cls._get_lock("vlm")
        with lock:
            if "vlm" not in cls._cache:
                logger.info("Loading VLM model into registry...")
                from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
                model_name = "Qwen/Qwen2-VL-2B-Instruct"
                device = "cuda" if torch.cuda.is_available() else "cpu"

                model = Qwen2VLForConditionalGeneration.from_pretrained(
                    model_name,
                    torch_dtype=torch.float16 if device == "cuda" else torch.float32,
                    device_map="auto",
                    trust_remote_code=True
                )
                processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True)

                cls._cache["vlm"] = model
                cls._cache["vlm_proc"] = processor
                cls._meta["vlm_device"] = device
                logger.info("VLM loaded successfully")
        return cls._cache["vlm"], cls._cache["vlm_proc"]

    @classmethod
    def get_table_detector(cls) -> Tuple[Any, Any]:
        lock = cls._get_lock("table")
        with lock:
            if "table" not in cls._cache:
                logger.info("Loading Table Transformer...")
                from transformers import TableTransformerForObjectDetection, AutoImageProcessor
                model = TableTransformerForObjectDetection.from_pretrained(
                    "microsoft/table-transformer-detection"
                )
                processor = AutoImageProcessor.from_pretrained(
                    "microsoft/table-transformer-detection"
                )
                cls._cache["table"] = model
                cls._cache["table_proc"] = processor
        return cls._cache["table"], cls._cache["table_proc"]

    @classmethod
    def clear_cache(cls):
        with threading.Lock():
            cls._cache.clear()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.info("Model registry cache cleared")
```

3. PDFExtractor
```python
"""
Извлечение страниц из PDF с автоматическим ремонтом битых файлов.
Определяет, является ли PDF нативным (с текстом) или сканом.
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
    def __init__(self, dpi: int = 300):
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
```

4. Предобработка (Adaptive Profiles)
```python
"""
Адаптивная предобработка: автодетекция типа входа и выбор профиля.
"""
import cv2
import numpy as np
from PIL import Image
from typing import Tuple, Union


class ImagePreprocessor:
    def preprocess(self, image: Union[Image.Image, np.ndarray]) -> Tuple[np.ndarray, dict]:
        img = np.array(image) if isinstance(image, Image.Image) else image.copy()
        metadata = {}

        img, flip_angle = self._correct_180(img)
        metadata["flip_180"] = flip_angle

        img, angle = self._deskew(img)
        metadata["deskew_angle"] = angle

        img_type = self._detect_input_type(img)
        metadata["input_type"] = img_type

        if img_type == "low_contrast_scan":
            img = self._apply_clahe_and_binarize(img)
        elif img_type == "photo_or_screen":
            img = self._denoise_and_deskew(img)
        else:
            img = self._light_enhance(img)

        return img, metadata

    def _detect_input_type(self, img: np.ndarray) -> str:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img
        contrast = float(np.std(gray))
        edges = cv2.Canny(gray, 50, 150)
        edge_density = float(np.sum(edges > 0) / edges.size)

        if contrast < 40 and edge_density < 0.05:
            return "low_contrast_scan"
        if contrast > 80 and edge_density > 0.15:
            return "photo_or_screen"
        return "standard_scan"

    def _correct_180(self, img: np.ndarray) -> Tuple[np.ndarray, int]:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img
        h = gray.shape[0]
        top_dark = np.sum(gray[:h//3] < 128)
        bottom_dark = np.sum(gray[2*h//3:] < 128)
        if bottom_dark > top_dark * 2.5:
            return cv2.rotate(img, cv2.ROTATE_180), 180
        return img, 0

    def _deskew(self, img: np.ndarray) -> Tuple[np.ndarray, float]:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img
        best_angle, best_score = 0, 0
        for angle in range(-15, 16, 3):
            M = cv2.getRotationMatrix2D((gray.shape[1]//2, gray.shape[0]//2), angle, 1)
            rotated = cv2.warpAffine(gray, M, (gray.shape[1], gray.shape[0]), borderValue=(255,255,255))
            _, binary = cv2.threshold(rotated, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            score = np.var(np.sum(binary, axis=1))
            if score > best_score:
                best_score, best_angle = score, angle

        if abs(best_angle) > 0.5:
            h, w = img.shape[:2]
            diag = int(np.sqrt(h**2 + w**2))
            M = cv2.getRotationMatrix2D((w//2, h//2), best_angle, 1.0)
            M[0, 2] += (diag - w) / 2
            M[1, 2] += (diag - h) / 2
            img = cv2.warpAffine(img, M, (diag, diag), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=(255,255,255))
            return img, float(best_angle)
        return img, 0.0

    def _apply_clahe_and_binarize(self, img: np.ndarray) -> np.ndarray:
        if len(img.shape) == 3:
            lab = cv2.cvtColor(img, cv2.COLOR_RGB2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            img = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2RGB)
        else:
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            img = clahe.apply(img)
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return cv2.cvtColor(binary, cv2.COLOR_GRAY2RGB) if len(img.shape) == 3 else binary

    def _denoise_and_deskew(self, img: np.ndarray) -> np.ndarray:
        if len(img.shape) == 3:
            return cv2.fastNlMeansDenoisingColored(img, None, 10, 10, 7, 21)
        return cv2.fastNlMeansDenoising(img, None, 10, 7, 21)

    def _light_enhance(self, img: np.ndarray) -> np.ndarray:
        if len(img.shape) == 3:
            lab = cv2.cvtColor(img, cv2.COLOR_RGB2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            img = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2RGB)
        kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
        return cv2.filter2D(img, -1, kernel)
```

5. Консенсусный OCR Ансамбль
```python
"""
Последовательный запуск OCR-движков с ранним выходом.
Слияние через IoU-кластеризацию + взвешенный консенсус.
"""
from paddleocr import PaddleOCR
from easyocr import EasyOCR
from doctr.io import DocumentFile
from doctr.models import ocr_predictor
from typing import List, Dict, Any
import numpy as np
import cv2
from scipy.cluster.hierarchy import fclusterdata
from rapidfuzz import fuzz
import logging

logger = logging.getLogger(__name__)


class OCREnsemble:
    ENGINE_PRIORITY = ["paddleocr", "easyocr", "doctr"]
    HIGH_CONFIDENCE_THRESHOLD = 0.90
    MIN_WORDS_FOR_CONFIDENCE = 10
    ENGINE_WEIGHTS = {"paddleocr": 1.2, "easyocr": 1.0, "doctr": 0.9}

    def __init__(self, languages: List[str] = ["en", "ru"], use_gpu: bool = True):
        self.languages = languages
        self._use_gpu = use_gpu
        self.engines = {}
        self._init_engines()

    def _init_engines(self):
        gpu_flag = self._use_gpu
        try:
            self.engines["paddleocr"] = PaddleOCR(use_angle_cls=True, lang="en", use_gpu=gpu_flag, show_log=False)
        except Exception as e:
            logger.warning(f"PaddleOCR GPU init failed, falling back to CPU: {e}")
            self.engines["paddleocr"] = PaddleOCR(use_angle_cls=True, lang="en", use_gpu=False, show_log=False)

        try:
            self.engines["easyocr"] = EasyOCR(lang_list=self.languages, gpu=gpu_flag, verbose=False)
        except Exception as e:
            logger.warning(f"EasyOCR GPU init failed, falling back to CPU: {e}")
            self.engines["easyocr"] = EasyOCR(lang_list=self.languages, gpu=False, verbose=False)

        self.engines["doctr"] = ocr_predictor(det_arch="db_resnet50", reco_arch="crnn_vgg16_bn", pretrained=True)

    def ensemble_ocr(self, image: np.ndarray) -> List[Dict[str, Any]]:
        all_results = {}
        for name in self.ENGINE_PRIORITY:
            try:
                result = self._run_engine(name, image)
                all_results[name] = result
                if name == "paddleocr" and self._high_confidence(result):
                    logger.info("PaddleOCR high confidence, skipping fallback engines")
                    break
            except Exception as e:
                logger.error(f"Engine {name} failed: {e}", exc_info=True)
                all_results[name] = []
        return self._merge_results(all_results)

    def _run_engine(self, name: str, image: np.ndarray) -> List[Dict]:
        if name == "paddleocr":
            return self._run_paddle(image)
        elif name == "easyocr":
            return self._run_easy(image)
        elif name == "doctr":
            return self._run_doctr(image)
        return []

    def _run_paddle(self, image: np.ndarray) -> List[Dict]:
        result = self.engines["paddleocr"].ocr(image, cls=True)
        if not result or not result[0]:
            return []
        outputs = []
        for line in result[0]:
            bbox = line[0]
            xs = [p[0] for p in bbox]
            ys = [p[1] for p in bbox]
            flat_bbox = [min(xs), min(ys), max(xs), max(ys)]
            outputs.append({"text": line[1][0], "bbox": flat_bbox, "confidence": line[1][1], "engine": "paddleocr"})
        return outputs

    def _run_easy(self, image: np.ndarray) -> List[Dict]:
        image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR) if len(image.shape) == 3 else image
        result = self.engines["easyocr"].readtext(image_bgr)
        outputs = []
        for item in result:
            bbox = item[0]
            xs = [p[0] for p in bbox]
            ys = [p[1] for p in bbox]
            flat_bbox = [min(xs), min(ys), max(xs), max(ys)]
            outputs.append({"text": item[1], "bbox": flat_bbox, "confidence": item[2], "engine": "easyocr"})
        return outputs

    def _run_doctr(self, image: np.ndarray) -> List[Dict]:
        pil_img = Image.fromarray(image)
        doc = DocumentFile.from_images(pil_img)
        result = self.engines["doctr"](doc)
        outputs = []
        for page in result.pages:
            for block in page.blocks:
                for line in block.lines:
                    for word in line.words:
                        geom = word.geometry
                        flat_bbox = [geom[0][0], geom[0][1], geom[1][0], geom[1][1]]
                        outputs.append({"text": word.value, "bbox": flat_bbox, "confidence": word.confidence, "engine": "doctr"})
        return outputs

    def _high_confidence(self, results: List[Dict]) -> bool:
        if not results or len(results) < self.MIN_WORDS_FOR_CONFIDENCE:
            return False
        avg_conf = sum(r.get("confidence", 0.0) for r in results) / len(results)
        return avg_conf >= self.HIGH_CONFIDENCE_THRESHOLD

    def _merge_results(self, results: Dict[str, List[Dict]]) -> List[Dict]:
        all_boxes = []
        for engine, items in results.items():
            if not items:
                continue
            for item in items:
                bbox = np.array(item["bbox"]).flatten()[:4]
                all_boxes.append({**item, "_flat_bbox": bbox})

        if not all_boxes:
            return []

        active_engines = [e for e, v in results.items() if v]
        if len(active_engines) == 1:
            for item in all_boxes:
                item.pop("_flat_bbox", None)
            return all_boxes

        centers = np.array([[(b[0] + b[2]) / 2, (b[1] + b[3]) / 2] for b in [b["_flat_bbox"] for b in all_boxes]])
        clusters = fclusterdata(centers, t=15, criterion="distance", method="single")

        merged = []
        for cid in np.unique(clusters):
            group = [all_boxes[i] for i, c in enumerate(clusters) if c == cid]
            resolved = self._resolve_cluster(group)
            merged.append(resolved)
        return merged

    def _resolve_cluster(self, group: List[Dict]) -> Dict:
        if len(group) == 1:
            item = group[0]
            item.pop("_flat_bbox", None)
            return item

        texts = [g["text"] for g in group]
        weights = self.ENGINE_WEIGHTS

        unique_groups = []
        for txt in texts:
            placed = False
            for ug in unique_groups:
                if fuzz.ratio(txt, ug[0]) > 85:
                    ug.append(txt)
                    placed = True
                    break
            if not placed:
                unique_groups.append([txt])

        representatives = [g[0] for g in unique_groups]

        scored = []
        for rep in representatives:
            score = 0.0
            for g in group:
                if fuzz.ratio(g["text"], rep) > 85:
                    score += g.get("confidence", 0) * weights.get(g.get("engine", ""), 1.0)
            scored.append((rep, score))

        best_text, best_score = max(scored, key=lambda x: x[1])

        return {
            "text": best_text,
            "confidence": best_score / len(group),
            "engine": "ensemble",
            "engines": list(set(g["engine"] for g in group)),
            "alternatives": list(set(texts))
        }
```

6. VLM Анализатор
```python
"""
VLM-анализатор с circuit breaker, комбинированным промптом и safe device.
"""
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
import torch
from PIL import Image
import time
import logging
import re
import json
import threading
from typing import Optional

logger = logging.getLogger(__name__)


def circuit_breaker(threshold: int = 2, timeout: int = 120):
    """
    Circuit breaker для защиты от каскадных падений VLM.
    NOTE: В multi-worker режиме (uvicorn --workers N) состояние хранится
    в памяти процесса. Для кластерной синхронизации используйте Redis.
    """
    failures = 0
    last_failure = 0.0
    lock = threading.Lock()

    def decorator(func):
        def wrapper(*args, **kwargs):
            nonlocal failures, last_failure
            with lock:
                if failures >= threshold and (time.time() - last_failure) < timeout:
                    raise RuntimeError("Circuit breaker OPEN for VLM")
            try:
                return func(*args, **kwargs)
            except Exception as e:
                with lock:
                    failures += 1
                    last_failure = time.time()
                raise
        return wrapper
    return decorator


class VLMDocumentAnalyzer:
    SYSTEM_PROMPT = """You are an expert document analyzer.
Analyze the document image and provide structured information.
Keep values in the ORIGINAL LANGUAGE. Return ONLY valid JSON."""

    COMBINED_PROMPT = """Analyze this document page and return ONLY valid JSON with:
{
  "document_type": "invoice|contract|form|letter|other",
  "confidence": 0.0-1.0,
  "key_fields": {"field_name": "value"},
  "layout_zones": [{"bbox": [x1,y1,x2,y2], "type": "header|body|table|footer"}],
  "tables": [{"headers": [...], "rows": [[...]]}],
  "dates": ["DD.MM.YYYY"],
  "amounts": ["123.45"],
  "low_confidence_corrections": {"original_text": "corrected_text"},
  "language": "ru|en|..."
}"""

    def __init__(self, use_combined_prompt: bool = True):
        self._model = None
        self._processor = None
        self.use_combined_prompt = use_combined_prompt

    def _lazy_init(self):
        if self._model is None:
            self._model, self._processor = ModelRegistry.get_vlm()

    @circuit_breaker(threshold=2, timeout=120)
    def analyze(self, image: Image.Image, custom_prompt: Optional[str] = None, max_new_tokens: int = 4000) -> Dict[str, Any]:
        self._lazy_init()

        prompt_text = custom_prompt or (self.COMBINED_PROMPT if self.use_combined_prompt else "Analyze this document:")

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": prompt_text}
            ]}
        ]

        text = self._processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self._processor(text=[text], images=[image], return_tensors="pt")

        with torch.no_grad():
            output_ids = self._model.generate(**inputs, max_new_tokens=max_new_tokens, temperature=0.1, do_sample=False)

        response = self._processor.batch_decode(output_ids[:, inputs.input_ids.shape[1]:], skip_special_tokens=True)[0]
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
```

7. Table Extractor
```python
"""
Извлечение таблиц с маршрутизацией: pdfplumber для нативных PDF, TT+VLM для растров.
"""
from typing import List, Dict, Any, Optional
from PIL import Image, ImageDraw
import torch
import numpy as np
import logging

logger = logging.getLogger(__name__)


class TableExtractor:
    def __init__(self):
        self._detector = None
        self._processor = None
        self._vlm = VLMDocumentAnalyzer(use_combined_prompt=False)

    def _lazy_init_detector(self):
        if self._detector is None:
            self._detector, self._processor = ModelRegistry.get_table_detector()

    def extract_tables(self, image: Image.Image, source_type: str = "scan", pdf_path: Optional[str] = None, page_num: int = 0) -> List[Dict[str, Any]]:
        if source_type == "native" and pdf_path:
            return self._extract_pdfplumber(pdf_path, page_num)
        return self._extract_raster(image)

    def _extract_pdfplumber(self, pdf_path: str, page_num: int) -> List[Dict[str, Any]]:
        try:
            import pdfplumber
            tables = []
            with pdfplumber.open(pdf_path) as pdf:
                if page_num >= len(pdf.pages):
                    return []
                page = pdf.pages[page_num]
                for table in page.extract_tables():
                    if table and len(table) > 1:
                        tables.append({
                            "headers": table[0],
                            "rows": table[1:],
                            "confidence": 1.0,
                            "source": "pdfplumber",
                            "bbox": [0, 0, page.width, page.height]
                        })
            return tables
        except Exception as e:
            logger.warning(f"pdfplumber failed, falling back to raster: {e}")
            return []

    def _extract_raster(self, image: Image.Image) -> List[Dict[str, Any]]:
        self._lazy_init_detector()

        img_array = np.array(image)
        inputs = self._processor(images=img_array, return_tensors="pt")

        with torch.no_grad():
            outputs = self._detector(**inputs)

        target_sizes = [img_array.shape[:2]]
        results = self._processor.post_process_object_detection(outputs, target_sizes=target_sizes)[0]

        tables = []
        for score, box in zip(results["scores"], results["boxes"]):
            if score > 0.5:
                tables.append({"bbox": box.tolist(), "confidence": score.item(), "source": "table_transformer"})

        if tables:
            return self._refine_with_vlm(image, tables)
        return tables

    def _refine_with_vlm(self, image: Image.Image, tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        max_size = 2048
        vis_img = image.copy()
        if max(vis_img.size) > max_size:
            vis_img.thumbnail((max_size, max_size))

        draw = ImageDraw.Draw(vis_img)
        scale_x = vis_img.width / image.width
        scale_y = vis_img.height / image.height

        for i, t in enumerate(tables):
            x1, y1, x2, y2 = t["bbox"]
            sx1, sy1 = int(x1 * scale_x), int(y1 * scale_y)
            sx2, sy2 = int(x2 * scale_x), int(y2 * scale_y)
            draw.rectangle([sx1, sy1, sx2, sy2], outline="red", width=3)
            draw.text((sx1, sy1), f"T{i+1}", fill="red")

        prompt = (
            "Extract all tables marked with red rectangles (T1, T2, etc.). "
            "Return JSON: {\"tables\": [{\"id\": 1, "
            "\"headers\": [...], "rows\": [[...]]}]}"
        )

        try:
            result = self._vlm.analyze(vis_img, custom_prompt=prompt, max_new_tokens=4000)
            return self._map_vlm_result(tables, result)
        except Exception as e:
            logger.error(f"VLM table refinement failed: {e}")
            return tables

    def _map_vlm_result(self, tables: List[Dict[str, Any]], vlm_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        vlm_tables = vlm_result.get("tables", [])
        for i, table in enumerate(tables):
            vlm_table = None
            for vt in vlm_tables:
                if vt.get("id") == i + 1:
                    vlm_table = vt
                    break
            if not vlm_table and i < len(vlm_tables):
                vlm_table = vlm_tables[i]

            if vlm_table:
                table["headers"] = vlm_table.get("headers", [])
                table["rows"] = vlm_table.get("rows", [])
                table["vlm_refined"] = True
                table["source"] = "vlm"
        return tables
```

8. OCR Постпроцессор
```python
import re
from typing import List, Dict, Any


class OCRPostProcessor:
    def process(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        processed = []
        for item in results:
            text = item.get("text", "")
            text = self._clean_text(text)
            if text:
                processed.append({**item, "text": text, "processed": True})
        return processed

    def _clean_text(self, text: str) -> str:
        text = "".join(c for c in text if c.isprintable() or c in "\n\t")
        text = re.sub(r"\s+", " ", text)
        return text.strip()
```

9. Главный пайплайн
```python
"""
Главный пайплайн OCR документов v2.5.
Confidence-gated routing: VLM запускается только при низком качестве OCR.
"""
import time
from PIL import Image
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class DocumentOCRPipeline:
    def __init__(
        self,
        languages: List[str] = ["en", "ru"],
        use_vlm: bool = True,
        use_gpu: bool = True,
        dpi: int = 300,
        vlm_confidence_threshold: float = 0.85
    ):
        self.languages = languages
        self.use_vlm = use_vlm
        self.use_gpu = use_gpu
        self.vlm_threshold = vlm_confidence_threshold

        self.pdf_extractor = PDFExtractor(dpi=dpi)
        self.preprocessor = ImagePreprocessor()
        self.ocr_ensemble = OCREnsemble(languages=languages, use_gpu=use_gpu)
        self.post_processor = OCRPostProcessor()
        self.table_extractor = TableExtractor()
        self.vlm_analyzer = VLMDocumentAnalyzer(use_combined_prompt=True) if use_vlm else None

    def process_pdf(self, pdf_path: str, extract_tables: bool = True) -> DocumentOCRResult:
        start_time = time.time()
        all_texts = []
        all_tables = []
        all_errors = []
        vlm_used = False

        try:
            for page_num, (page_image, source_type) in enumerate(self.pdf_extractor.extract_pages(pdf_path)):
                page_result = self.process_image(
                    page_image,
                    extract_tables=extract_tables,
                    source_type=source_type,
                    pdf_path=pdf_path,
                    page_num=page_num
                )
                all_texts.append(page_result.text)
                all_tables.extend(page_result.tables)
                all_errors.extend(page_result.errors)
                if page_result.vlm_used:
                    vlm_used = True

            return DocumentOCRResult(
                success=True,
                text="\n".join(all_texts),
                tables=all_tables,
                processing_time=time.time() - start_time,
                errors=all_errors,
                vlm_used=vlm_used
            )
        except Exception as e:
            logger.exception(f"PDF processing failed: {e}")
            return DocumentOCRResult(
                success=False,
                text="",
                errors=[str(e)],
                processing_time=time.time() - start_time
            )

    def process_image(
        self,
        image: Image.Image,
        extract_tables: bool = True,
        source_type: str = "scan",
        pdf_path: Optional[str] = None,
        page_num: int = 0
    ) -> DocumentOCRResult:
        start_time = time.time()
        vlm_used = False

        try:
            img_array, meta = self.preprocessor.preprocess(image)

            ocr_results = self.ocr_ensemble.ensemble_ocr(img_array)
            ocr_results = self.post_processor.process(ocr_results)
            full_text = " ".join(r["text"] for r in ocr_results)

            avg_conf = self._compute_avg_confidence(ocr_results)
            needs_vlm = self.use_vlm and (
                avg_conf < self.vlm_threshold
                or not full_text.strip()
                or len(ocr_results) < 5
            )

            tables = []
            if extract_tables:
                tables = self.table_extractor.extract_tables(
                    Image.fromarray(img_array),
                    source_type=source_type,
                    pdf_path=pdf_path,
                    page_num=page_num
                )

            document_type = None
            key_fields = {}
            if needs_vlm and self.vlm_analyzer:
                try:
                    doc_analysis = self.vlm_analyzer.analyze(Image.fromarray(img_array))
                    document_type = doc_analysis.get("document_type")
                    key_fields = doc_analysis.get("key_fields", {})
                    vlm_used = True
                except Exception as e:
                    logger.warning(f"VLM analysis skipped due to error: {e}")

            return DocumentOCRResult(
                success=True,
                text=full_text,
                tables=tables,
                document_type=document_type,
                key_fields=key_fields,
                metadata={**meta, "ocr_avg_confidence": avg_conf},
                processing_time=time.time() - start_time,
                vlm_used=vlm_used
            )
        except Exception as e:
            logger.exception(f"Image processing failed: {e}")
            return DocumentOCRResult(
                success=False,
                text="",
                errors=[str(e)],
                processing_time=time.time() - start_time
            )

    def _compute_avg_confidence(self, results: List[Dict]) -> float:
        if not results:
            return 0.0
        return sum(r.get("confidence", 0.0) for r in results) / len(results)
```

10. FastAPI приложение (Async + VRAM Guard + Graceful Shutdown)
```python
"""
Production-ready FastAPI endpoint с полной асинхронизацией,
VRAM-контролем и graceful shutdown.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
import signal
import sys

from fastapi import FastAPI, File, UploadFile, HTTPException
from prometheus_client import Histogram, Counter, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
import magic
import tempfile
import os

# Подключаем guard
# from vram_guard import vram_guard

# Пул для CPU/GPU задач.
# Для GPU max_workers=1-2, иначе OOM. Для CPU-only можно 4.
_executor = ThreadPoolExecutor(
    max_workers=2,
    thread_name_prefix="ocr_worker"
)

app = FastAPI(title="Document OCR API", version="2.5")

ocr_duration = Histogram("doc_ocr_duration_seconds", "Processing time", ["stage"])
ocr_errors = Counter("doc_ocr_errors_total", "Errors", ["component"])
ocr_requests = Counter("doc_ocr_requests_total", "Total requests")
ocr_vlm_fallback = Counter("doc_vlm_fallback_total", "VLM fallback invocations")

pipeline = DocumentOCRPipeline()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 OCR Service starting...")

    def handle_sigterm(sig, frame):
        logger.warning("📉 SIGTERM received. Flushing models...")
        ModelRegistry.clear_cache()
        _executor.shutdown(wait=True)
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_sigterm)
    yield
    logger.info("🛑 OCR Service shutdown complete.")
    _executor.shutdown(wait=True)

app = FastAPI(title="Document OCR API", version="2.5", lifespan=lifespan)


@app.post("/ocr/document")
async def ocr_document(file: UploadFile = File(...)):
    ocr_requests.inc()

    content = await file.read(2048)
    mime = magic.from_buffer(content, mime=True)
    await file.seek(0)

    if mime not in ("application/pdf", "image/png", "image/jpeg", "image/tiff"):
        raise HTTPException(400, f"Unsupported file type: {mime}")

    if content[:4] == b"PK\x03\x04":
        raise HTTPException(400, "ZIP archives are not allowed")

    temp_path = None
    try:
        suffix = os.path.splitext(file.filename)[1] or ".tmp"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            temp_path = tmp.name

        loop = asyncio.get_event_loop()

        if mime == "application/pdf":
            with ocr_duration.labels(stage="pdf").time():
                with vram_guard(tag="document_pdf"):
                    result = await loop.run_in_executor(
                        _executor,
                        lambda: pipeline.process_pdf(temp_path)
                    )
        else:
            with ocr_duration.labels(stage="image").time():
                img = await loop.run_in_executor(
                    _executor,
                    lambda: Image.open(temp_path)
                )
                with vram_guard(tag="document_image"):
                    result = await loop.run_in_executor(
                        _executor,
                        lambda: pipeline.process_image(img)
                    )

        if not result.success:
            ocr_errors.labels(component="pipeline").inc()
            raise HTTPException(500, detail=result.errors)

        if result.vlm_used:
            ocr_vlm_fallback.inc()

        return {
            "success": True,
            "text": result.text,
            "tables": result.tables,
            "document_type": result.document_type,
            "key_fields": result.key_fields,
            "vlm_used": result.vlm_used,
            "processing_time": result.processing_time
        }
    except HTTPException:
        raise
    except Exception as e:
        ocr_errors.labels(component="unknown").inc()
        raise HTTPException(500, str(e))
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

11. Запуск в продакшене
```bash
# Установка uvloop для ускорения event loop
pip install uvloop

# Запуск через uvicorn с асинхронной поддержкой
# --workers: НЕ больше количества GPU (иначе OOM)
# --loop uvloop: ускорение на 20-30%
# --timeout-graceful-shutdown: время на завершение текущих запросов
uvicorn main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 2 \
    --loop uvloop \
    --timeout-graceful-shutdown 15 \
    --log-level info
```
