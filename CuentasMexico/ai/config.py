from __future__ import annotations

import os
from typing import Dict, Optional


def _get_django_settings():
    try:
        from django.conf import settings as django_settings

        if django_settings.configured:
            return django_settings
    except Exception:
        return None
    return None


def _get_setting(name: str, default=None):
    django_settings = _get_django_settings()
    if django_settings and hasattr(django_settings, name):
        return getattr(django_settings, name)
    return os.getenv(name, default)


def get_active_provider() -> str:
    db_provider = _get_db_provider()
    if db_provider in {"openai", "gemini"}:
        return db_provider
    provider = str(_get_setting("AI_PROVIDER", "openai")).strip().lower()
    return provider if provider in {"openai", "gemini"} else "openai"


def get_provider_models(provider: Optional[str] = None) -> Dict[str, str]:
    active_provider = (provider or get_active_provider()).lower()
    db_models = _get_db_models(active_provider)
    if db_models:
        return db_models

    models_map = _get_setting("AI_MODELS", {})
    if isinstance(models_map, dict):
        provider_models = models_map.get(active_provider, {})
        if isinstance(provider_models, dict):
            return provider_models
    return {}


def get_model_for_task(task: str, provider: Optional[str] = None) -> Optional[str]:
    provider_models = get_provider_models(provider=provider)
    return provider_models.get(task)


def get_provider_api_key(provider: Optional[str] = None) -> Optional[str]:
    active_provider = (provider or get_active_provider()).lower()
    db_key = _get_db_api_key(active_provider)
    if db_key:
        return db_key
    if active_provider == "openai":
        return str(_get_setting("OPENAI_API_KEY", "") or "").strip() or None
    if active_provider == "gemini":
        return str(_get_setting("GEMINI_API_KEY", "") or "").strip() or None
    return None


def get_db_mcp_config() -> Dict[str, object]:
    allowed_tables_raw = str(_get_setting("AI_DB_ALLOWED_TABLES", "") or "")
    allowed_tables = [t.strip() for t in allowed_tables_raw.split(",") if t.strip()]
    return {
        "allowed_tables": allowed_tables,
        "max_rows": int(_get_setting("AI_DB_MAX_ROWS", 200)),
        "include_schema": str(_get_setting("AI_DB_INCLUDE_SCHEMA", "true")).lower()
        in {"1", "true", "yes", "on"},
    }


def _get_db_provider() -> Optional[str]:
    try:
        from adm.models import AISettings

        obj = AISettings.get_settings()
        return str(obj.provider or "").strip().lower()
    except Exception:
        return None


def _get_db_models(provider: str) -> Dict[str, str]:
    try:
        from adm.models import AISettings

        obj = AISettings.get_settings()
        if provider == "openai":
            return {
                "text": obj.openai_model_text,
                "hybrid": obj.openai_model_hybrid,
                "image": obj.openai_model_image,
                "transcription": obj.openai_model_transcription,
                "speech": obj.openai_model_speech,
            }
        if provider == "gemini":
            return {
                "text": obj.gemini_model_text,
                "hybrid": obj.gemini_model_hybrid,
                "image": obj.gemini_model_image,
                "transcription": obj.gemini_model_transcription,
                "speech": obj.gemini_model_speech,
            }
    except Exception:
        return {}
    return {}


def _get_db_api_key(provider: str) -> Optional[str]:
    try:
        from adm.models import AISettings

        obj = AISettings.get_settings()
        if provider == "openai":
            return str(obj.openai_api_key or "").strip() or None
        if provider == "gemini":
            return str(obj.gemini_api_key or "").strip() or None
    except Exception:
        return None
    return None
