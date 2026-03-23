from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Sequence

from .base import BaseAIProvider
from .config import get_active_provider, get_model_for_task, get_provider_api_key
from .exceptions import AIProviderError
from .gemini_provider import GeminiProvider
from .mcp_readonly_db import ReadOnlyDatabaseMCP
from .openai_provider import OpenAIProvider
from .types import (
    GenerateResult,
    ImageResult,
    InputPart,
    SpeechResult,
    TranscriptionResult,
)


class AIClient:
    """
    Fachada única para usar IA en cualquier parte del proyecto.
    """

    def __init__(self, provider: BaseAIProvider, *, provider_name: Optional[str] = None) -> None:
        self.provider = provider
        self.provider_name = (provider_name or get_active_provider()).lower().strip()

    @classmethod
    def from_provider_name(
        cls,
        provider_name: str,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 60,
    ) -> "AIClient":
        provider = provider_name.lower().strip()
        if provider == "openai":
            key = api_key or get_provider_api_key("openai") or os.getenv("OPENAI_API_KEY")
            if not key:
                raise AIProviderError("OPENAI_API_KEY is required")
            return cls(
                OpenAIProvider(
                    api_key=key,
                    base_url=base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com"),
                    timeout=timeout,
                ),
                provider_name="openai",
            )
        if provider == "gemini":
            key = api_key or get_provider_api_key("gemini") or os.getenv("GEMINI_API_KEY")
            if not key:
                raise AIProviderError("GEMINI_API_KEY is required")
            return cls(
                GeminiProvider(
                    api_key=key,
                    base_url=base_url
                    or os.getenv(
                        "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
                    ),
                    timeout=timeout,
                ),
                provider_name="gemini",
            )
        raise AIProviderError(f"Unsupported provider: {provider_name}")

    @classmethod
    def from_settings(cls, *, timeout: int = 60) -> "AIClient":
        return cls.from_provider_name(get_active_provider(), timeout=timeout)

    def generate(
        self,
        *,
        model: Optional[str] = None,
        prompt: Optional[str] = None,
        parts: Optional[List[InputPart]] = None,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> GenerateResult:
        model_name = model or get_model_for_task("text", provider=self.provider_name)
        if not model_name:
            raise AIProviderError("No model configured for text task")
        content_parts = list(parts or [])
        if prompt:
            content_parts.insert(0, InputPart.from_text(prompt))
        if not content_parts:
            raise AIProviderError("At least one prompt or part is required")
        return self.provider.generate(
            model=model_name,
            parts=content_parts,
            system_prompt=system_prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            extra=extra,
        )

    def generate_image(
        self,
        *,
        prompt: str,
        model: Optional[str] = None,
        size: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> ImageResult:
        model_name = model or get_model_for_task("image", provider=self.provider_name)
        if not model_name:
            raise AIProviderError("No model configured for image task")
        return self.provider.generate_image(prompt=prompt, model=model_name, size=size, extra=extra)

    def transcribe_audio(
        self,
        *,
        audio_bytes: bytes,
        model: Optional[str] = None,
        mime_type: str = "audio/wav",
        language: Optional[str] = None,
        prompt: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> TranscriptionResult:
        model_name = model or get_model_for_task("transcription", provider=self.provider_name)
        if not model_name:
            raise AIProviderError("No model configured for transcription task")
        return self.provider.transcribe_audio(
            audio_bytes=audio_bytes,
            model=model_name,
            mime_type=mime_type,
            language=language,
            prompt=prompt,
            extra=extra,
        )

    def synthesize_speech(
        self,
        *,
        text: str,
        model: Optional[str] = None,
        voice: Optional[str] = None,
        audio_format: str = "mp3",
        extra: Optional[Dict[str, Any]] = None,
    ) -> SpeechResult:
        model_name = model or get_model_for_task("speech", provider=self.provider_name)
        if not model_name:
            raise AIProviderError("No model configured for speech task")
        return self.provider.synthesize_speech(
            text=text,
            model=model_name,
            voice=voice,
            audio_format=audio_format,
            extra=extra,
        )

    def answer_with_db_context(
        self,
        *,
        model: Optional[str] = None,
        question: str,
        queries: Sequence[str],
        mcp: ReadOnlyDatabaseMCP,
        system_prompt: Optional[str] = None,
        params_list: Optional[Sequence[Sequence[object]]] = None,
        limit: Optional[int] = None,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
    ) -> GenerateResult:
        context_text = mcp.build_context_text(
            question=question,
            queries=queries,
            params_list=params_list,
            limit=limit,
        )
        model_name = model or get_model_for_task("text", provider=self.provider_name)
        if not model_name:
            raise AIProviderError("No model configured for text task")
        return self.generate(
            model=model_name,
            prompt=context_text,
            system_prompt=system_prompt
            or (
                "Eres analista de negocio. Responde solo con evidencia del contexto SQL. "
                "Si falta informacion, indicalo sin inventar."
            ),
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
