from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .types import (
    GenerateResult,
    ImageResult,
    InputPart,
    SpeechResult,
    TranscriptionResult,
)


class BaseAIProvider(ABC):
    @abstractmethod
    def generate(
        self,
        *,
        model: str,
        parts: List[InputPart],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> GenerateResult:
        raise NotImplementedError

    @abstractmethod
    def generate_image(
        self,
        *,
        prompt: str,
        model: str,
        size: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> ImageResult:
        raise NotImplementedError

    @abstractmethod
    def transcribe_audio(
        self,
        *,
        audio_bytes: bytes,
        model: str,
        mime_type: str = "audio/wav",
        language: Optional[str] = None,
        prompt: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> TranscriptionResult:
        raise NotImplementedError

    @abstractmethod
    def synthesize_speech(
        self,
        *,
        text: str,
        model: str,
        voice: Optional[str] = None,
        audio_format: str = "mp3",
        extra: Optional[Dict[str, Any]] = None,
    ) -> SpeechResult:
        raise NotImplementedError
