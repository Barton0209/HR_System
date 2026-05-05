Файл: OCR_PASS_UP.md
Улучшенный пайплайн распознавания паспортов v3.5
Страны СНГ, Балкан и дружественные государства
Production-ready | Async | VRAM-safe | Graceful Shutdown | MRZ-First Routing

0. Установка зависимостей
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install transformers accelerate bitsandbytes
pip install paddleocr paddlepaddle
pip install python-mrz
pip install opencv-python-headless numpy scikit-image Pillow scipy
pip install qwen-vl-utils pydantic
pip install rapidfuzz unidecode transliterate
pip install uvicorn fastapi python-multipart prometheus-client
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

1. Pydantic модели, конфигурация стран и ModelRegistry
```python
"""
Базовые модели, конфигурация стран и потокобезопасный реестр моделей.
"""
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import threading
import torch
import logging

logger = logging.getLogger(__name__)


class Script(Enum):
    CYRILLIC = "cyrillic"
    LATIN = "latin"
    CHINESE = "chinese"
    ARABIC = "arabic"


class MRZType(Enum):
    TD3 = "TD3"
    TD1 = "TD1"


@dataclass
class CountryConfig:
    iso2: str
    iso3: str
    name_ru: str
    name_en: str
    mrz_code: str
    script: Script
    mrz_country_code: str
    mrz_type: MRZType
    has_hologram: bool
    languages: List[str]
    ocr_lang: str
    features: Dict = field(default_factory=dict)


SUPPORTED_COUNTRIES: Dict[str, CountryConfig] = {
    "RUS": CountryConfig(
        iso2="RU", iso3="RUS", name_ru="Россия", name_en="Russia",
        mrz_code="RUS", script=Script.CYRILLIC, mrz_country_code="RUS",
        mrz_type=MRZType.TD3, has_hologram=True, languages=["ru"],
        ocr_lang="russian", features={"patronymic_required": True}
    ),
    "UKR": CountryConfig(
        iso2="UA", iso3="UKR", name_ru="Украина", name_en="Ukraine",
        mrz_code="UKR", script=Script.CYRILLIC, mrz_country_code="UKR",
        mrz_type=MRZType.TD3, has_hologram=True, languages=["uk", "en"],
        ocr_lang="russian", features={"patronymic_required": False}
    ),
    "BLR": CountryConfig(
        iso2="BY", iso3="BLR", name_ru="Беларусь", name_en="Belarus",
        mrz_code="BLR", script=Script.CYRILLIC, mrz_country_code="BLR",
        mrz_type=MRZType.TD3, has_hologram=True, languages=["be", "ru", "en"],
        ocr_lang="russian", features={"patronymic_required": True}
    ),
    "KAZ": CountryConfig(
        iso2="KZ", iso3="KAZ", name_ru="Казахстан", name_en="Kazakhstan",
        mrz_code="KAZ", script=Script.CYRILLIC, mrz_country_code="KAZ",
        mrz_type=MRZType.TD1, has_hologram=True, languages=["kk", "ru"],
        ocr_lang="russian", features={"patronymic_required": True}
    ),
    "UZB": CountryConfig(
        iso2="UZ", iso3="UZB", name_ru="Узбекистан", name_en="Uzbekistan",
        mrz_code="UZB", script=Script.CYRILLIC, mrz_country_code="UZB",
        mrz_type=MRZType.TD1, has_hologram=False, languages=["uz", "ru"],
        ocr_lang="russian", features={"patronymic_required": True}
    ),
}


def get_country_by_mrz_code(mrz_code: str) -> Optional[CountryConfig]:
    return SUPPORTED_COUNTRIES.get(mrz_code.upper())


class ModelRegistry:
    _cache = {}
    _locks = {}

    @classmethod
    def _get_lock(cls, key: str) -> threading.Lock:
        if key not in cls._locks:
            cls._locks[key] = threading.Lock()
        return cls._locks[key]

    @classmethod
    def get_clip(cls) -> Tuple[Any, Any]:
        lock = cls._get_lock("clip")
        with lock:
            if "clip_model" not in cls._cache:
                logger.info("Loading CLIP model...")
                from transformers import CLIPProcessor, CLIPModel
                device = "cuda" if torch.cuda.is_available() else "cpu"
                model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
                processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
                cls._cache["clip_model"] = model
                cls._cache["clip_processor"] = processor
                cls._cache["clip_device"] = device
        return cls._cache["clip_model"], cls._cache["clip_processor"]

    @classmethod
    def get_vlm(cls) -> Tuple[Any, Any]:
        lock = cls._get_lock("vlm")
        with lock:
            if "vlm" not in cls._cache:
                logger.info("Loading VLM model...")
                from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
                device = "cuda" if torch.cuda.is_available() else "cpu"
                model_name = "Qwen/Qwen2-VL-2B-Instruct"
                model = Qwen2VLForConditionalGeneration.from_pretrained(
                    model_name,
                    torch_dtype=torch.float16 if device == "cuda" else torch.float32,
                    device_map="auto",
                    trust_remote_code=True
                )
                processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True)
                cls._cache["vlm"] = model
                cls._cache["vlm_proc"] = processor
        return cls._cache["vlm"], cls._cache["vlm_proc"]

    @classmethod
    def clear_cache(cls):
        with threading.Lock():
            cls._cache.clear()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()


class MRZDataModel(BaseModel):
    country_code: str
    surname: str
    given_names: str
    document_number: str
    nationality: Optional[str] = None
    date_of_birth: Optional[str] = None
    expiry_date: Optional[str] = None
    is_valid: bool = False
    confidence: float = 1.0


class VIZDataModel(BaseModel):
    surname: Optional[str] = None
    given_names: Optional[str] = None
    patronymic: Optional[str] = None
    document_number: Optional[str] = None
    date_of_birth: Optional[str] = None
    source: str = "unknown"


class CrossValidationResult(BaseModel):
    status: str
    checks: Dict[str, Any] = {}
    requires_manual_review: bool = False


class PassportResult(BaseModel):
    success: bool
    country_code: str
    mrz: Optional[MRZDataModel] = None
    viz: Optional[VIZDataModel] = None
    cross_validation: CrossValidationResult = CrossValidationResult(status="incomplete")
    processing_time: float = 0.0
    errors: List[str] = []
```

2. Умный классификатор (MRZ-First + CLIP Lazy Fallback)
```python
"""
Классификатор страны: MRZ-полоса имеет приоритет 100%.
CLIP — только fallback при отсутствии MRZ.
"""
from PIL import Image
import torch
import numpy as np
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class DocumentClassifier:
    def __init__(self):
        self._text_embeds = None
        self._country_codes = []
        self._prompts = []

    def classify(self, image: Image.Image, mrz_country_code: Optional[str] = None) -> Dict[str, Any]:
        if mrz_country_code:
            config = get_country_by_mrz_code(mrz_country_code)
            if config:
                return {
                    "country_code": config.iso3,
                    "config": config,
                    "confidence": 1.0,
                    "source": "mrz"
                }

        logger.warning("MRZ not found. Falling back to CLIP.")
        return self._classify_by_clip(image)

    def _classify_by_clip(self, image: Image.Image) -> Dict[str, Any]:
        clip_model, clip_processor = ModelRegistry.get_clip()
        device = ModelRegistry._cache.get("clip_device", "cpu")

        if self._text_embeds is None:
            self._prompts = []
            self._country_codes = []
            for code, config in SUPPORTED_COUNTRIES.items():
                self._prompts.extend([
                    f"{config.name_ru} passport",
                    f"{config.name_en} passport"
                ])
                self._country_codes.extend([code, code])

            with torch.no_grad():
                text_inputs = clip_processor(text=self._prompts, return_tensors="pt", padding=True).to(device)
                self._text_embeds = clip_model.get_text_features(**text_inputs)
                self._text_embeds = self._text_embeds / self._text_embeds.norm(dim=-1, keepdim=True)

        img_inputs = clip_processor(images=image, return_tensors="pt").to(device)
        with torch.no_grad():
            img_embeds = clip_model.get_image_features(**img_inputs)
            img_embeds = img_embeds / img_embeds.norm(dim=-1, keepdim=True)

        similarities = (img_embeds @ self._text_embeds.T)[0]
        probs = similarities.softmax(dim=-1).cpu().numpy()

        scores = {}
        counts = {}
        for i, code in enumerate(self._country_codes):
            scores[code] = scores.get(code, 0.0) + float(probs[i])
            counts[code] = counts.get(code, 0) + 1

        for code in scores:
            scores[code] /= counts[code]

        best_code = max(scores, key=scores.get)
        best_score = scores[best_code]

        return {
            "country_code": best_code,
            "config": SUPPORTED_COUNTRIES[best_code],
            "confidence": best_score,
            "source": "clip"
        }
```

3. Предобработка
```python
"""
Предобработка паспортов: deskew, удаление голограмм, адаптивный контраст.
"""
import cv2
import numpy as np
from PIL import Image
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class PassportPreprocessor:
    def preprocess(self, image: Image.Image, country_config: Optional[CountryConfig] = None) -> Tuple[Image.Image, dict]:
        img_array = np.array(image)
        metadata = {"had_hologram": False, "had_skew": 0.0}

        img_array, angle = self._deskew(img_array)
        metadata["had_skew"] = angle

        if country_config and country_config.has_hologram:
            if self._detect_hologram_gradient(img_array):
                metadata["had_hologram"] = True
                img_array = self._remove_hologram(img_array)

        img_array = self._adaptive_contrast(img_array, country_config)

        return Image.fromarray(img_array), metadata

    def _deskew(self, img: np.ndarray) -> Tuple[np.ndarray, float]:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img
        angle = self._detect_angle_by_projection(gray)

        if abs(angle) > 0.5:
            h, w = img.shape[:2]
            diag = int(np.sqrt(h**2 + w**2))
            M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
            M[0, 2] += (diag - w) / 2
            M[1, 2] += (diag - h) / 2
            img = cv2.warpAffine(
                img, M, (diag, diag),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(255, 255, 255)
            )
            return img, float(angle)
        return img, 0.0

    def _detect_angle_by_projection(self, gray: np.ndarray) -> float:
        best_angle, best_score = 0, 0
        for angle in range(-15, 16, 3):
            M = cv2.getRotationMatrix2D((gray.shape[1] // 2, gray.shape[0] // 2), angle, 1)
            rotated = cv2.warpAffine(gray, M, (gray.shape[1], gray.shape[0]), borderValue=(255, 255, 255))
            _, binary = cv2.threshold(rotated, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            score = np.var(np.sum(binary, axis=1))
            if score > best_score:
                best_score, best_angle = score, angle
        return float(best_angle)

    def _detect_hologram_gradient(self, img: np.ndarray) -> bool:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img
        if len(img.shape) == 3:
            hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
            saturation = hsv[:, :, 1].mean()
            lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            if saturation > 60 and lap_var < 500:
                return True
        return False

    def _remove_hologram(self, img: np.ndarray) -> np.ndarray:
        return cv2.bilateralFilter(img, d=9, sigmaColor=75, sigmaSpace=75)

    def _adaptive_contrast(self, img: np.ndarray, country_config: Optional[CountryConfig]) -> np.ndarray:
        if len(img.shape) == 3:
            lab = cv2.cvtColor(img, cv2.COLOR_RGB2LAB)
            l, a, b = cv2.split(lab)
            clip_limit = 1.5 if (country_config and country_config.script.value == "chinese") else 2.0
            l = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8)).apply(l)
            return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2RGB)
        return img
```

4. Извлечение MRZ (TD1/TD3 + Positional Safe Clean + Crop Optimization)
```python
"""
Извлечение MRZ с оптимизированным кропом нижней зоны.
Поддержка TD1 и TD3 с позиционной очисткой.
"""
from mrz.checker.td3 import TD3CodeChecker
from mrz.checker.td1 import TD1CodeChecker
from paddleocr import PaddleOCR
import cv2
import numpy as np
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class MRZExtractor:
    MRZ_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<"
    TD3_LINE2_DIGITS = set(range(0, 9)) | set(range(13, 19)) | set(range(21, 27))
    TD1_LINE2_DIGITS = set(range(0, 9)) | set(range(13, 19)) | set(range(21, 27))

    def __init__(self, use_gpu: bool = True):
        try:
            self.ocr = PaddleOCR(use_angle_cls=False, lang="en", use_gpu=use_gpu, show_log=False)
        except Exception as e:
            logger.warning(f"PaddleOCR GPU init failed, falling back to CPU: {e}")
            self.ocr = PaddleOCR(use_angle_cls=False, lang="en", use_gpu=False, show_log=False)

    def crop_mrz_zone(self, image: np.ndarray) -> np.ndarray:
        """Оптимизированный кроп: MRZ в нижних 15%, центральные 90% ширины."""
        h, w = image.shape[:2]
        y_start = int(h * 0.85)
        x_start = int(w * 0.05)
        x_end = int(w * 0.95)
        return image[y_start:h, x_start:x_end, :]

    def extract(self, image, mrz_type: MRZType = MRZType.TD3) -> Optional[MRZDataModel]:
        img_array = np.array(image) if not isinstance(image, np.ndarray) else image

        mrz_region = self.crop_mrz_zone(img_array)

        gray = cv2.cvtColor(mrz_region, cv2.COLOR_RGB2GRAY)
        result = self.ocr.ocr(gray, cls=False)

        if not result or not result[0]:
            return None

        mrz_lines = []
        for line in result[0]:
            text = line[1][0].strip()
            if self._looks_like_mrz(text):
                cleaned = self._safe_clean_mrz_line(text, len(mrz_lines) + 1, mrz_type)
                if len(cleaned) >= 20:
                    mrz_lines.append(cleaned)

        if len(mrz_lines) >= 2:
            line_len = 44 if mrz_type == MRZType.TD3 else 30
            mrz_string = (
                mrz_lines[0][:line_len].ljust(line_len, "<") + "\n" +
                mrz_lines[1][:line_len].ljust(line_len, "<")
            )
            if mrz_type == MRZType.TD1 and len(mrz_lines) >= 3:
                mrz_string += "\n" + mrz_lines[2][:line_len].ljust(line_len, "<")
            return self._validate_mrz(mrz_string, mrz_type)
        return None

    def _looks_like_mrz(self, text: str) -> bool:
        ratio = sum(1 for c in text if c.isupper() or c.isdigit()) / max(len(text), 1)
        return ratio > 0.8 and len(text) > 15

    def _safe_clean_mrz_line(self, text: str, line_num: int, mrz_type: MRZType) -> str:
        result = list(text.upper())
        digit_positions = self.TD3_LINE2_DIGITS if mrz_type == MRZType.TD3 else self.TD1_LINE2_DIGITS

        for i, c in enumerate(result):
            if c in self.MRZ_CHARS:
                continue
            if c == " ":
                result[i] = "<"
                continue

            if line_num == 2 and i in digit_positions:
                if c == "О":
                    result[i] = "0"
                elif c == "В":
                    result[i] = "8"
                elif c == "З":
                    result[i] = "3"
                elif c == "Ч":
                    result[i] = "4"
                elif c == "Б":
                    result[i] = "6"
                else:
                    result[i] = "<"
            else:
                result[i] = "<"

        return "".join(result)

    def _validate_mrz(self, mrz_string: str, mrz_type: MRZType) -> Optional[MRZDataModel]:
        try:
            if mrz_type == MRZType.TD1:
                checker = TD1CodeChecker(mrz_string)
            else:
                checker = TD3CodeChecker(mrz_string)

            if checker.result:
                f = checker.fields()
                return MRZDataModel(
                    country_code=f.country_code,
                    surname=f.surname,
                    given_names=f.name,
                    document_number=f.number,
                    nationality=getattr(f, "nationality", None),
                    date_of_birth=getattr(f, "date_of_birth", None),
                    expiry_date=getattr(f, "expiry_date", None),
                    is_valid=True,
                    confidence=1.0
                )
        except Exception as e:
            logger.debug(f"MRZ validation failed: {e}")
        return None
```

5. Извлечение VIZ (Fuzzy Anchors + VLM Fallback)
```python
"""
Извлечение VIZ: Label-Guided Search с fuzzy matching + VLM fallback.
"""
from paddleocr import PaddleOCR
from PIL import Image
import torch
from typing import Dict, List, Optional
from rapidfuzz import fuzz
import numpy as np
import logging

logger = logging.getLogger(__name__)


class VIZExtractor:
    def __init__(self, use_gpu: bool = True):
        self._use_gpu = use_gpu
        self._ocr = None

    def _init_ocr(self, country_config: CountryConfig):
        if self._ocr is None:
            lang_map = {"russian": "ru", "english": "en", "ukrainian": "uk"}
            ocr_lang = lang_map.get(country_config.ocr_lang, "ru")
            try:
                self._ocr = PaddleOCR(use_angle_cls=True, lang=ocr_lang, use_gpu=self._use_gpu, show_log=False)
            except Exception as e:
                logger.warning(f"PaddleOCR GPU init failed, CPU fallback: {e}")
                self._ocr = PaddleOCR(use_angle_cls=True, lang=ocr_lang, use_gpu=False, show_log=False)

    def extract(self, image: Image.Image, country_config: CountryConfig) -> VIZDataModel:
        self._init_ocr(country_config)
        ocr_results = self._get_ocr_results(image)
        anchor_data = self._extract_by_anchors(ocr_results, country_config)

        required = ["surname", "given_names"]
        if country_config.features.get("patronymic_required"):
            required.append("patronymic")

        if not all(anchor_data.get(f) for f in required):
            logger.info("Anchor extraction incomplete, falling back to VLM")
            return self._extract_by_vlm(image, country_config)

        return VIZDataModel(
            surname=anchor_data.get("surname"),
            given_names=anchor_data.get("given_names"),
            patronymic=anchor_data.get("patronymic"),
            source="anchors"
        )

    def _get_ocr_results(self, image: Image.Image) -> List[Dict]:
        result = self._ocr.ocr(np.array(image), cls=True)
        if not result or not result[0]:
            return []
        outputs = []
        for line in result[0]:
            bbox, text = line[0], line[1][0]
            y_center = (bbox[0][1] + bbox[2][1]) / 2
            x_start = bbox[0][0]
            outputs.append({"text": text, "y": y_center, "x": x_start, "bbox": bbox})
        return outputs

    def _extract_by_anchors(self, ocr_results: List[Dict], country_config: CountryConfig) -> Dict[str, str]:
        extracted = {}
        anchor_map = {
            "surname": ["ФАМИЛИЯ", "SURNAME", "ПРІЗВИЩЕ", "ТЕГІ"],
            "given_names": ["ИМЯ", "NAME", "GIVEN NAMES", "ІМ'Я", "АТЫ"],
            "patronymic": ["ОТЧЕСТВО", "PATRONYMIC", "ІМЯ ПА БАТКУ", "ӘТ-ЖӨНІ"]
        }

        for field, labels in anchor_map.items():
            if field == "patronymic" and not country_config.features.get("patronymic_required"):
                continue

            best_match = None
            best_score = 0

            for res in ocr_results:
                for lbl in labels:
                    score = fuzz.ratio(res["text"].upper(), lbl)
                    if score > 80 and score > best_score:
                        best_score = score
                        best_match = res

            if best_match:
                y_center = best_match["y"]
                y_thresh = max(y_center * 0.02, 10)
                candidates = [
                    r for r in ocr_results
                    if abs(r["y"] - y_center) < y_thresh
                    and r["x"] > best_match["x"] + 20
                    and not any(fuzz.ratio(r["text"].upper(), lbl) > 80 for lbl in labels)
                ]
                if candidates:
                    candidates.sort(key=lambda x: x["x"])
                    extracted[field] = candidates[0]["text"]

        return extracted

    def _extract_by_vlm(self, image: Image.Image, country_config: CountryConfig) -> VIZDataModel:
        vlm_model, vlm_processor = ModelRegistry.get_vlm()

        fields_prompt = "surname, given_names"
        if country_config.features.get("patronymic_required"):
            fields_prompt += ", patronymic"

        prompt = (
            f"Extract fields from passport: {fields_prompt}. "
            "Return ONLY valid JSON with these exact keys. "
            "Keep values in original language (Cyrillic/Latin). Do not translate."
        )

        messages = [{
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": prompt}
            ]
        }]

        text = vlm_processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = vlm_processor(text=[text], images=[image], return_tensors="pt")

        with torch.no_grad():
            output_ids = vlm_model.generate(**inputs, max_new_tokens=200, temperature=0.1, do_sample=False)

        response = vlm_processor.batch_decode(output_ids[:, inputs.input_ids.shape[1]:], skip_special_tokens=True)[0]

        parsed = self._parse_vlm_response(response)
        return VIZDataModel(
            surname=parsed.get("surname"),
            given_names=parsed.get("given_names"),
            patronymic=parsed.get("patronymic"),
            source="vlm"
        )

    def _parse_vlm_response(self, response: str) -> Dict[str, str]:
        import re, json
        cleaned = re.sub(r"```json\s*", "", response)
        cleaned = re.sub(r"```\s*", "", cleaned)
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        logger.warning(f"VLM VIZ parse failed: {cleaned[:200]}")
        return {"raw_vlm": cleaned}
```

6. Кросс-валидация MRZ ↔ VIZ
```python
"""
Кросс-валидация: сравнение MRZ и VIZ через транслитерацию + fuzzy matching.
"""
from rapidfuzz import fuzz
from transliterate import translit
from unidecode import unidecode
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class CrossValidator:
    def validate(self, mrz: Optional[MRZDataModel], viz: Optional[VIZDataModel]) -> CrossValidationResult:
        if not mrz or not viz:
            return CrossValidationResult(status="incomplete")

        checks = {}

        if mrz.surname and viz.surname:
            mrz_surname = mrz.surname.replace("<", " ").strip()
            viz_translit = self._transliterate_to_latin(viz.surname)
            score = fuzz.ratio(mrz_surname.upper(), viz_translit.upper())
            checks["surname"] = {
                "mrz": mrz_surname,
                "viz_original": viz.surname,
                "viz_translit": viz_translit,
                "score": score,
                "passed": score > 70
            }

        if mrz.given_names and viz.given_names:
            mrz_names = mrz.given_names.replace("<", " ").strip()
            viz_translit = self._transliterate_to_latin(viz.given_names)
            score = fuzz.ratio(mrz_names.upper(), viz_translit.upper())
            checks["given_names"] = {
                "mrz": mrz_names,
                "viz_original": viz.given_names,
                "viz_translit": viz_translit,
                "score": score,
                "passed": score > 70
            }

        if mrz.document_number and viz.document_number:
            score = fuzz.ratio(mrz.document_number, viz.document_number)
            checks["document_number"] = {
                "mrz": mrz.document_number,
                "viz": viz.document_number,
                "score": score,
                "passed": score > 85
            }

        if mrz.date_of_birth and viz.date_of_birth:
            score = fuzz.ratio(mrz.date_of_birth, viz.date_of_birth)
            checks["date_of_birth"] = {
                "mrz": mrz.date_of_birth,
                "viz": viz.date_of_birth,
                "score": score,
                "passed": score > 90
            }

        all_passed = all(c["passed"] for c in checks.values()) if checks else False
        mismatches = [k for k, v in checks.items() if not v["passed"]]

        return CrossValidationResult(
            status="passed" if all_passed else "mismatch",
            checks=checks,
            requires_manual_review=not all_passed and len(mismatches) > 0
        )

    def _transliterate_to_latin(self, text: str) -> str:
        try:
            result = translit(text, "ru", reversed=True)
        except Exception:
            result = unidecode(text)
        return result.upper()
```

7. Главный пайплайн
```python
"""
Главный пайплайн паспортов v3.5.
MRZ-first routing: сначала MRZ для определения страны,
затем адаптивная предобработка с учетом конфигурации.
"""
import time
from PIL import Image
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class PassportPipeline:
    def __init__(self, use_gpu: bool = True, dpi: int = 300):
        self.use_gpu = use_gpu
        self.dpi = dpi

        self.preprocessor = PassportPreprocessor()
        self.classifier = DocumentClassifier()
        self.mrz_extractor = MRZExtractor(use_gpu=use_gpu)
        self.viz_extractor = VIZExtractor(use_gpu=use_gpu)
        self.cross_validator = CrossValidator()

    def process(self, image: Image.Image) -> PassportResult:
        start_time = time.time()
        errors = []

        try:
            img_prep, meta = self.preprocessor.preprocess(image)

            mrz_data = None
            country_config = None
            for mrz_type in [MRZType.TD3, MRZType.TD1]:
                mrz_data = self.mrz_extractor.extract(img_prep, mrz_type=mrz_type)
                if mrz_data:
                    break

            if mrz_data:
                country_config = get_country_by_mrz_code(mrz_data.country_code)

            classification = self.classifier.classify(
                img_prep,
                mrz_country_code=mrz_data.country_code if mrz_data else None
            )

            if not country_config:
                country_config = classification["config"]

            img_final, meta2 = self.preprocessor.preprocess(image, country_config)

            viz_data = self.viz_extractor.extract(img_final, country_config)

            cross_val = self.cross_validator.validate(mrz_data, viz_data)

            return PassportResult(
                success=True,
                country_code=country_config.iso3,
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
```

8. FastAPI приложение (Async + VRAM Guard + Graceful Shutdown)
```python
"""
Production endpoint для распознавания паспортов.
Полностью асинхронный с контролем VRAM и graceful shutdown.
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

# from vram_guard import vram_guard

# Пул для CPU/GPU задач. Для GPU max_workers=1-2, иначе OOM.
_executor = ThreadPoolExecutor(
    max_workers=2,
    thread_name_prefix="passport_worker"
)

pass_duration = Histogram("pass_ocr_duration_seconds", "Processing time", ["stage"])
pass_errors = Counter("pass_ocr_errors_total", "Errors", ["component"])
pass_requests = Counter("pass_ocr_requests_total", "Total requests")
pass_mismatch = Counter("pass_mismatch_total", "Cross-validation mismatches")

pipeline = PassportPipeline()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Passport OCR Service starting...")

    def handle_sigterm(sig, frame):
        logger.warning("📉 SIGTERM received. Flushing models...")
        ModelRegistry.clear_cache()
        _executor.shutdown(wait=True)
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_sigterm)
    yield
    logger.info("🛑 Passport OCR Service shutdown complete.")
    _executor.shutdown(wait=True)

app = FastAPI(title="Passport OCR API", version="3.5", lifespan=lifespan)


@app.post("/ocr/passport")
async def ocr_passport(file: UploadFile = File(...)):
    pass_requests.inc()

    content = await file.read(2048)
    mime = magic.from_buffer(content, mime=True)
    await file.seek(0)

    if mime not in ("image/png", "image/jpeg", "image/tiff", "image/webp"):
        raise HTTPException(400, f"Unsupported image type: {mime}")

    temp_path = None
    try:
        suffix = os.path.splitext(file.filename)[1] or ".jpg"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            temp_path = tmp.name

        loop = asyncio.get_event_loop()

        img = await loop.run_in_executor(
            _executor,
            lambda: Image.open(temp_path)
        )

        with pass_duration.labels(stage="full").time():
            with vram_guard(tag="passport_ocr"):
                result = await loop.run_in_executor(
                    _executor,
                    lambda: pipeline.process(img)
                )

        if not result.success:
            pass_errors.labels(component="pipeline").inc()
            raise HTTPException(500, detail=result.errors)

        if result.cross_validation.requires_manual_review:
            pass_mismatch.inc()

        return result.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        pass_errors.labels(component="unknown").inc()
        raise HTTPException(500, str(e))
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

9. Запуск в продакшене
```bash
# Установка uvloop
pip install uvloop

# Запуск
# --workers: НЕ больше количества GPU (иначе OOM)
# --loop uvloop: ускорение event loop на 20-30%
# --timeout-graceful-shutdown: время на завершение текущих запросов
uvicorn main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 2 \
    --loop uvloop \
    --timeout-graceful-shutdown 15 \
    --log-level info
```
