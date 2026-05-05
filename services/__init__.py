"""
Services module initialization.
"""

from services.passport_service import (
    PassportService,
    PassportResult,
)

from services.universal_ocr_service import (
    UniversalOCRService,
    OCRDocumentResult,
    OCRPageResult,
    ProcessingMode,
)

__all__ = [
    # Passport
    'PassportService',
    'PassportResult',

    # Universal OCR
    'UniversalOCRService',
    'OCRDocumentResult',
    'OCRPageResult',
    'ProcessingMode',
]