"""
Конфигурация приложения через Pydantic Settings
"""
import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения HR System."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # ==========================================================================
    # ОСНОВНЫЕ НАСТРОЙКИ
    # ==========================================================================
    port: int = 8000
    host: str = "0.0.0.0"
    debug: bool = False
    
    # ==========================================================================
    # БЕЗОПАСНОСТЬ
    # ==========================================================================
    secret_key: str = "hr_system_secret_key_change_in_production"
    hash_algorithm: str = "bcrypt"
    access_token_expire_minutes: int = 480
    bcrypt_salt_rounds: int = 12
    
    # ==========================================================================
    # CORS
    # ==========================================================================
    allowed_origins: str = "*"
    
    @property
    def allowed_origins_list(self) -> List[str]:
        """Список разрешённых origin."""
        if self.allowed_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.allowed_origins.split(",")]
    
    # ==========================================================================
    # ПУТИ К ФАЙЛАМ
    # ==========================================================================
    passwords_file: Path = Path("Excel_files/ПАРОЛЬ_ДОСТУП.xlsx")
    database_path: Path = Path("data/hr_system.db")
    upload_folder: Path = Path("data/uploads")
    reports_folder: Path = Path("data/reports")
    log_folder: Path = Path("data/logs")
    mrz_cache_folder: Path = Path("data/mrz_cache")
    ocr_cache_folder: Path = Path("data/ocr_cache")
    
    # ==========================================================================
    # ЛОГИРОВАНИЕ
    # ==========================================================================
    log_level: str = "INFO"
    log_format: str = "json"  # json или text
    
    # ==========================================================================
    # ОГРАНИЧЕНИЯ
    # ==========================================================================
    max_upload_size: int = 104857600  # 100 MB
    rate_limit_per_minute: int = 60
    
    # ==========================================================================
    # OCR И MRZ
    # ==========================================================================
    tesseract_path: Optional[str] = None
    ocr_cache_enabled: bool = True
    ocr_cache_ttl: int = 3600  # секунды
    
    # ==========================================================================
    # МОНИТОРИНГ
    # ==========================================================================
    prometheus_enabled: bool = False
    prometheus_port: int = 9090
    
    # ==========================================================================
    # ВАЛИДАЦИЯ ПУТЕЙ
    # ==========================================================================
    def validate_paths(self) -> None:
        """Создание необходимых директорий."""
        for path in [
            self.upload_folder,
            self.reports_folder,
            self.log_folder,
            self.mrz_cache_folder,
            self.ocr_cache_folder,
            self.database_path.parent
        ]:
            path.mkdir(parents=True, exist_ok=True)
    
    # ==========================================================================
    # СВОЙСТВА
    # ==========================================================================
    @property
    def is_production(self) -> bool:
        """Проверка режима production."""
        return not self.debug
    
    @property
    def jwt_algorithm(self) -> str:
        """Алгоритм для JWT."""
        return "HS256"


@lru_cache()
def get_settings() -> Settings:
    """Получение настроек (кэшируется)."""
    return Settings()


# Глобальный экземпляр настроек
settings = get_settings()
