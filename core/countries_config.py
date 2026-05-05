"""
Countries Configuration — конфигурация 23 стран для паспортов.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum


class Script(Enum):
    """Алфавит страны."""
    CYRILLIC = "cyrillic"
    LATIN = "latin"
    CHINESE = "chinese"
    ARABIC = "arabic"


class MRZType(Enum):
    """Тип MRZ документа."""
    TD1 = "TD1"  # ID-карта
    TD3 = "TD3"  # Паспорт


@dataclass
class CountryConfig:
    """Конфигурация страны."""
    # ISO коды
    iso2: str
    iso3: str

    # Названия
    name_ru: str
    name_en: str

    # MRZ код страны (ICAO)
    mrz_code: str

    # Алфавит
    script: Script

    # MRZ параметры
    mrz_country_code: str
    mrz_type: MRZType

    # Особенности
    has_hologram: bool
    languages: List[str]
    ocr_lang: str

    # Шаблон
    template_id: Optional[str] = None

    # Дополнительные параметры
    features: Dict = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        """Отображаемое название."""
        return f"{self.name_ru} ({self.iso3})"


# ===== БАЗА ДАННЫХ СТРАН =====

SUPPORTED_COUNTRIES: Dict[str, CountryConfig] = {
    # ===== КИРИЛЛИЧЕСКИЕ СТРАНЫ (СНГ + Сирия) =====

    "RUS": CountryConfig(
        iso2="RU",
        iso3="RUS",
        name_ru="Россия",
        name_en="Russia",
        mrz_code="RUS",
        script=Script.CYRILLIC,
        mrz_country_code="RUS",
        mrz_type=MRZType.TD3,
        has_hologram=True,
        languages=["ru"],
        ocr_lang="rus",
        template_id="rus_passport",
        features={
            "patronymic_required": True,
            "authority_format": "код подразделения (XXX-XXX)",
            "series_format": "XX XX",
            "number_format": "XXXXXX",
            "validity_years": 10,
        }
    ),

    "UKR": CountryConfig(
        iso2="UA",
        iso3="UKR",
        name_ru="Украина",
        name_en="Ukraine",
        mrz_code="UKR",
        script=Script.CYRILLIC,
        mrz_country_code="UKR",
        mrz_type=MRZType.TD3,
        has_hologram=True,
        languages=["uk", "en"],
        ocr_lang="rus+eng",
        template_id="ukr_passport",
        features={
            "patronymic_required": False,
            "authority_format": "название органа",
            "number_format": "XXXXXXXXX",
            "validity_years": 10,
        }
    ),

    "BLR": CountryConfig(
        iso2="BY",
        iso3="BLR",
        name_ru="Беларусь",
        name_en="Belarus",
        mrz_code="BLR",
        script=Script.CYRILLIC,
        mrz_country_code="BLR",
        mrz_type=MRZType.TD3,
        has_hologram=True,
        languages=["be", "ru", "en"],
        ocr_lang="rus+eng",
        template_id="blr_passport",
        features={
            "patronymic_required": True,
            "authority_format": "название органа",
            "number_format": "ABXXXXXXX",
            "validity_years": 10,
        }
    ),

    "KAZ": CountryConfig(
        iso2="KZ",
        iso3="KAZ",
        name_ru="Казахстан",
        name_en="Kazakhstan",
        mrz_code="KAZ",
        script=Script.CYRILLIC,
        mrz_country_code="KAZ",
        mrz_type=MRZType.TD3,
        has_hologram=True,
        languages=["kk", "ru"],
        ocr_lang="rus",
        template_id="kaz_passport",
        features={
            "patronymic_required": True,
            "authority_format": "код (AY, AN, etc.)",
            "number_format": "NXXXXXXXX",
            "validity_years": 10,
        }
    ),

    "UZB": CountryConfig(
        iso2="UZ",
        iso3="UZB",
        name_ru="Узбекистан",
        name_en="Uzbekistan",
        mrz_code="UZB",
        script=Script.CYRILLIC,
        mrz_country_code="UZB",
        mrz_type=MRZType.TD3,
        has_hologram=True,
        languages=["uz", "ru"],
        ocr_lang="rus",
        template_id="uzb_passport",
        features={
            "patronymic_required": True,
            "authority_format": "код органа",
            "number_format": "AAXXXXXXXX",
            "validity_years": 10,
        }
    ),

    "KGZ": CountryConfig(
        iso2="KG",
        iso3="KGZ",
        name_ru="Кыргызстан",
        name_en="Kyrgyzstan",
        mrz_code="KGZ",
        script=Script.CYRILLIC,
        mrz_country_code="KGZ",
        mrz_type=MRZType.TD3,
        has_hologram=True,
        languages=["ky", "ru"],
        ocr_lang="rus",
        template_id="kgz_passport",
        features={
            "patronymic_required": True,
            "number_format": "XXXXXXXXX",
            "validity_years": 10,
        }
    ),

    "TJK": CountryConfig(
        iso2="TJ",
        iso3="TJK",
        name_ru="Таджикистан",
        name_en="Tajikistan",
        mrz_code="TJK",
        script=Script.CYRILLIC,
        mrz_country_code="TJK",
        mrz_type=MRZType.TD3,
        has_hologram=True,
        languages=["tg", "ru"],
        ocr_lang="rus",
        template_id="tjk_passport",
        features={
            "patronymic_required": True,
            "number_format": "XXXXXXXXX",
            "validity_years": 10,
        }
    ),

    "TKM": CountryConfig(
        iso2="TM",
        iso3="TKM",
        name_ru="Туркменистан",
        name_en="Turkmenistan",
        mrz_code="TKM",
        script=Script.CYRILLIC,
        mrz_country_code="TKM",
        mrz_type=MRZType.TD3,
        has_hologram=True,
        languages=["tk", "ru"],
        ocr_lang="rus",
        template_id="tkm_passport",
        features={
            "patronymic_required": True,
            "number_format": "XXXXXXXXX",
            "validity_years": 10,
        }
    ),

    "AZE": CountryConfig(
        iso2="AZ",
        iso3="AZE",
        name_ru="Азербайджан",
        name_en="Azerbaijan",
        mrz_code="AZE",
        script=Script.CYRILLIC,
        mrz_country_code="AZE",
        mrz_type=MRZType.TD3,
        has_hologram=True,
        languages=["az"],
        ocr_lang="rus+eng",
        template_id="aze_passport",
        features={
            "patronymic_required": False,
            "number_format": "XXXXXXXXX",
            "validity_years": 10,
        }
    ),

    "ARM": CountryConfig(
        iso2="AM",
        iso3="ARM",
        name_ru="Армения",
        name_en="Armenia",
        mrz_code="ARM",
        script=Script.CYRILLIC,
        mrz_country_code="ARM",
        mrz_type=MRZType.TD3,
        has_hologram=True,
        languages=["hy"],
        ocr_lang="rus+eng",
        template_id="arm_passport",
        features={
            "patronymic_required": False,
            "number_format": "XXXXXXXXX",
            "validity_years": 10,
        }
    ),

    "MDA": CountryConfig(
        iso2="MD",
        iso3="MDA",
        name_ru="Молдова",
        name_en="Moldova",
        mrz_code="MDA",
        script=Script.CYRILLIC,
        mrz_country_code="MDA",
        mrz_type=MRZType.TD3,
        has_hologram=True,
        languages=["ro", "ru"],
        ocr_lang="rus+eng",
        template_id="mda_passport",
        features={
            "patronymic_required": False,
            "number_format": "XXXXXXXXX",
            "validity_years": 10,
        }
    ),

    "SYR": CountryConfig(
        iso2="SY",
        iso3="SYR",
        name_ru="Сирия",
        name_en="Syria",
        mrz_code="SYR",
        script=Script.ARABIC,
        mrz_country_code="SYR",
        mrz_type=MRZType.TD3,
        has_hologram=True,
        languages=["ar"],
        ocr_lang="ara+eng",
        template_id="syr_passport",
        features={
            "patronymic_required": False,
            "number_format": "XXXXXXXX",
            "script_direction": "RTL",
            "validity_years": 6,
        }
    ),

    "PRK": CountryConfig(
        iso2="KP",
        iso3="PRK",
        name_ru="КНДР",
        name_en="North Korea",
        mrz_code="PRK",
        script=Script.CYRILLIC,
        mrz_country_code="PRK",
        mrz_type=MRZType.TD3,
        has_hologram=False,
        languages=["ko"],
        ocr_lang="rus+eng",
        template_id="prk_passport",
        features={
            "patronymic_required": False,
            "number_format": "XXXXXXX",
            "validity_years": 5,
        }
    ),

    # ===== ЛАТИНИЧЕСКИЕ СТРАНЫ =====

    "TUR": CountryConfig(
        iso2="TR",
        iso3="TUR",
        name_ru="Турция",
        name_en="Turkey",
        mrz_code="TUR",
        script=Script.LATIN,
        mrz_country_code="TUR",
        mrz_type=MRZType.TD3,
        has_hologram=True,
        languages=["tr", "en"],
        ocr_lang="tur+eng",
        template_id="tur_passport",
        features={
            "patronymic_required": False,
            "number_format": "XXXXXXXXX",
            "validity_years": 10,
        }
    ),

    "IND": CountryConfig(
        iso2="IN",
        iso3="IND",
        name_ru="Индия",
        name_en="India",
        mrz_code="IND",
        script=Script.LATIN,
        mrz_country_code="IND",
        mrz_type=MRZType.TD3,
        has_hologram=True,
        languages=["en", "hi"],
        ocr_lang="eng",
        template_id="ind_passport",
        features={
            "patronymic_required": False,
            "number_format": "XXXXXXXX",
            "has_online_ref": True,
            "validity_years": 10,
        }
    ),

    "PAK": CountryConfig(
        iso2="PK",
        iso3="PAK",
        name_ru="Пакистан",
        name_en="Pakistan",
        mrz_code="PAK",
        script=Script.LATIN,
        mrz_country_code="PAK",
        mrz_type=MRZType.TD3,
        has_hologram=True,
        languages=["en", "ur"],
        ocr_lang="eng",
        template_id="pak_passport",
        features={
            "patronymic_required": False,
            "number_format": "XXXXXXXXX",
            "validity_years": 10,
        }
    ),

    "GHA": CountryConfig(
        iso2="GH",
        iso3="GHA",
        name_ru="Гана",
        name_en="Ghana",
        mrz_code="GHA",
        script=Script.LATIN,
        mrz_country_code="GHA",
        mrz_type=MRZType.TD3,
        has_hologram=False,
        languages=["en"],
        ocr_lang="eng",
        template_id="gha_passport",
        features={
            "patronymic_required": False,
            "number_format": "XXXXXXXXX",
            "validity_years": 5,
        }
    ),

    # ===== БАЛКАНСКИЕ СТРАНЫ =====

    "BIH": CountryConfig(
        iso2="BA",
        iso3="BIH",
        name_ru="Босния и Герцеговина",
        name_en="Bosnia and Herzegovina",
        mrz_code="BIH",
        script=Script.LATIN,
        mrz_country_code="BIH",
        mrz_type=MRZType.TD3,
        has_hologram=True,
        languages=["bs", "hr", "sr"],
        ocr_lang="eng",
        template_id="bih_passport",
        features={
            "patronymic_required": False,
            "number_format": "XXXXXXXX",
            "validity_years": 10,
        }
    ),

    "HRV": CountryConfig(
        iso2="HR",
        iso3="HRV",
        name_ru="Хорватия",
        name_en="Croatia",
        mrz_code="HRV",
        script=Script.LATIN,
        mrz_country_code="HRV",
        mrz_type=MRZType.TD3,
        has_hologram=True,
        languages=["hr", "en"],
        ocr_lang="eng",
        template_id="hrv_passport",
        features={
            "patronymic_required": False,
            "number_format": "XXXXXXXX",
            "validity_years": 10,
        }
    ),

    "SRB": CountryConfig(
        iso2="RS",
        iso3="SRB",
        name_ru="Сербия",
        name_en="Serbia",
        mrz_code="SRB",
        script=Script.LATIN,
        mrz_country_code="SRB",
        mrz_type=MRZType.TD3,
        has_hologram=True,
        languages=["sr", "en"],
        ocr_lang="eng",
        template_id="srb_passport",
        features={
            "patronymic_required": False,
            "number_format": "XXXXXXXX",
            "validity_years": 10,
        }
    ),

    "MNE": CountryConfig(
        iso2="ME",
        iso3="MNE",
        name_ru="Черногория",
        name_en="Montenegro",
        mrz_code="MNE",
        script=Script.LATIN,
        mrz_country_code="MNE",
        mrz_type=MRZType.TD3,
        has_hologram=True,
        languages=["me", "en"],
        ocr_lang="eng",
        template_id="mne_passport",
        features={
            "patronymic_required": False,
            "number_format": "XXXXXXXX",
            "validity_years": 10,
        }
    ),

    "MKD": CountryConfig(
        iso2="MK",
        iso3="MKD",
        name_ru="Северная Македония",
        name_en="North Macedonia",
        mrz_code="MKD",
        script=Script.LATIN,
        mrz_country_code="MKD",
        mrz_type=MRZType.TD3,
        has_hologram=True,
        languages=["mk", "en"],
        ocr_lang="eng",
        template_id="mkd_passport",
        features={
            "patronymic_required": False,
            "number_format": "XXXXXXXX",
            "validity_years": 10,
        }
    ),

    # ===== АЗИЯ =====

    "CHN": CountryConfig(
        iso2="CN",
        iso3="CHN",
        name_ru="Китай",
        name_en="China",
        mrz_code="CHN",
        script=Script.CHINESE,
        mrz_country_code="CHN",
        mrz_type=MRZType.TD3,
        has_hologram=True,
        languages=["zh", "en"],
        ocr_lang="chi_sim+eng",
        template_id="chn_passport",
        features={
            "patronymic_required": False,
            "number_format": "GXXXXXXXX",
            "transliteration_required": True,
            "validity_years": 10,
        }
    ),
}


# ===== УТИЛИТЫ =====

def get_country_by_iso3(iso3: str) -> Optional[CountryConfig]:
    """Получить конфигурацию по ISO3 коду."""
    return SUPPORTED_COUNTRIES.get(iso3.upper())


def get_country_by_iso2(iso2: str) -> Optional[CountryConfig]:
    """Получить конфигурацию по ISO2 коду."""
    iso2 = iso2.upper()
    for config in SUPPORTED_COUNTRIES.values():
        if config.iso2 == iso2:
            return config
    return None


def get_country_by_mrz_code(mrz_code: str) -> Optional[CountryConfig]:
    """Получить конфигурацию по MRZ коду страны."""
    mrz_code = mrz_code.upper()
    for config in SUPPORTED_COUNTRIES.values():
        if config.mrz_country_code == mrz_code:
            return config
    return None


def get_countries_by_script(script: Script) -> List[CountryConfig]:
    """Получить все страны с указанным алфавитом."""
    return [c for c in SUPPORTED_COUNTRIES.values() if c.script == script]


def get_all_countries() -> List[CountryConfig]:
    """Получить список всех стран."""
    return list(SUPPORTED_COUNTRIES.values())


def get_country_names() -> List[str]:
    """Получить список названий стран для UI."""
    return [c.display_name for c in SUPPORTED_COUNTRIES.values()]


def get_ocr_languages() -> List[str]:
    """Получить уникальные языки OCR."""
    langs = set()
    for config in SUPPORTED_COUNTRIES.values():
        langs.add(config.ocr_lang)
    return sorted(list(langs))