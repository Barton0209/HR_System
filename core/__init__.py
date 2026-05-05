"""
Core module initialization.
"""

from core.preprocessing import (
    deskew,
    remove_moire,
    apply_clahe,
    sharpen_text,
    binarize,
    preprocess_for_ocr,
    resize_if_needed,
)

from core.mrz import (
    MRZData,
    MRZType,
    extract_mrz_from_text,
    parse_td3,
    parse_td1,
    mrz_to_dict,
)

from core.vlm import (
    VLMManager,
    VLMResult,
    get_vlm_manager,
    is_vlm_available,
)

from core.ocr_engines import (
    OCResult,
    TesseractEngine,
    EasyOCREngine,
    OCREnsemble,
    quick_ocr,
    accurate_ocr,
)

from core.countries_config import (
    CountryConfig,
    Script,
    MRZType as CountryMRZType,
    SUPPORTED_COUNTRIES,
    get_country_by_iso3,
    get_country_by_iso2,
    get_country_by_mrz_code,
    get_countries_by_script,
    get_all_countries,
    get_country_names,
)

__all__ = [
    # Preprocessing
    'deskew',
    'remove_moire',
    'apply_clahe',
    'sharpen_text',
    'binarize',
    'preprocess_for_ocr',
    'resize_if_needed',

    # MRZ
    'MRZData',
    'MRZType',
    'extract_mrz_from_text',
    'parse_td3',
    'parse_td1',
    'mrz_to_dict',

    # VLM
    'VLMManager',
    'VLMResult',
    'get_vlm_manager',
    'is_vlm_available',

    # OCR Engines
    'OCResult',
    'TesseractEngine',
    'EasyOCREngine',
    'OCREnsemble',
    'quick_ocr',
    'accurate_ocr',

    # Countries
    'CountryConfig',
    'Script',
    'CountryMRZType',
    'SUPPORTED_COUNTRIES',
    'get_country_by_iso3',
    'get_country_by_iso2',
    'get_country_by_mrz_code',
    'get_countries_by_script',
    'get_all_countries',
    'get_country_names',
]