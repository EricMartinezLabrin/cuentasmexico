from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import requests

from .base import BaseAIProvider
from .exceptions import AIProviderError
from .types import (
    GenerateResult,
    ImageResult,
    InputPart,
    SpeechResult,
    TranscriptionResult,
)
from .utils import b64_decode, b64_encode, is_url


class GeminiProvider(BaseAIProvider):
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        timeout: int = 60,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _endpoint(self, model: str, action: str = "generateContent") -> str:
        return f"{self.base_url}/models/{model}:{action}?key={self.api_key}"

    def _raise_for_error(self, response: requests.Response) -> None:
        if response.ok:
            return
        details: Dict[str, Any] | str
        try:
            details = response.json()
        except Exception:
            details = response.text
        raise AIProviderError(
            "Gemini request failed",
            status_code=response.status_code,
            details=details,
        )

    def _to_gemini_part(self, part: InputPart) -> Dict[str, Any]:
        if part.kind == "text":
            return {"text": part.text or ""}

        if part.kind in {"image", "audio"}:
            mime = part.mime_type or (
                "image/png" if part.kind == "image" else "audio/wav"
            )
            if part.url and is_url(part.url):
                return {"file_data": {"mime_type": mime, "file_uri": part.url}}
            if part.data is None:
                raise AIProviderError(f"{part.kind} part requires data or url")
            return {
                "inline_data": {
                    "mime_type": mime,
                    "data": b64_encode(part.data),
                }
            }

        raise AIProviderError(f"Unsupported part kind: {part.kind}")

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
        payload: Dict[str, Any] = {
            "contents": [{"role": "user", "parts": [self._to_gemini_part(p) for p in parts]}]
        }
        if system_prompt:
            payload["system_instruction"] = {"parts": [{"text": system_prompt}]}
        if temperature is not None or max_output_tokens is not None:
            payload["generationConfig"] = {}
            if temperature is not None:
                payload["generationConfig"]["temperature"] = temperature
            if max_output_tokens is not None:
                payload["generationConfig"]["maxOutputTokens"] = max_output_tokens
        if extra:
            payload.update(extra)

        response = requests.post(
            self._endpoint(model),
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=self.timeout,
        )
        self._raise_for_error(response)
        data = response.json()

        text_chunks: List[str] = []
        images: List[str] = []
        audios: List[str] = []

        candidates = data.get("candidates", []) or []
        if candidates:
            content = candidates[0].get("content", {})
            for part in content.get("parts", []) or []:
                if "text" in part:
                    text_chunks.append(part["text"])
                inline_data = part.get("inline_data") or part.get("inlineData")
                if inline_data and inline_data.get("data"):
                    mime = inline_data.get("mime_type") or inline_data.get("mimeType", "")
                    if mime.startswith("image/"):
                        images.append(inline_data["data"])
                    elif mime.startswith("audio/"):
                        audios.append(inline_data["data"])

        return GenerateResult(
            text="\n".join(chunk for chunk in text_chunks if chunk).strip(),
            images_base64=images,
            audios_base64=audios,
            raw=data,
        )

    def generate_image(
        self,
        *,
        prompt: str,
        model: str,
        size: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> ImageResult:
        payload_extra: Dict[str, Any] = {
            "generationConfig": {
                "responseModalities": ["IMAGE"],
            }
        }
        if size:
            payload_extra["generationConfig"]["imageSize"] = size
        if extra:
            payload_extra.update(extra)
        result = self.generate(
            model=model,
            parts=[InputPart.from_text(prompt)],
            extra=payload_extra,
        )
        return ImageResult(images_base64=result.images_base64, raw=result.raw)

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
        language_hint = f" en {language}" if language else ""
        instruction = prompt or f"Transcribe con precisión el audio{language_hint}."
        result = self.generate(
            model=model,
            parts=[
                InputPart.from_text(instruction),
                InputPart.from_audio(data=audio_bytes, mime_type=mime_type),
            ],
            extra=extra,
        )
        return TranscriptionResult(text=result.text, raw=result.raw)

    def synthesize_speech(
        self,
        *,
        text: str,
        model: str,
        voice: Optional[str] = None,
        audio_format: str = "mp3",
        extra: Optional[Dict[str, Any]] = None,
    ) -> SpeechResult:
        payload_extra: Dict[str, Any] = {
            "generationConfig": {"responseModalities": ["AUDIO"]}
        }
        if voice:
            payload_extra["speechConfig"] = {"voiceConfig": {"name": voice}}
        if extra:
            payload_extra.update(extra)
        result = self.generate(
            model=model,
            parts=[InputPart.from_text(text)],
            extra=payload_extra,
        )
        if not result.audios_base64:
            raise AIProviderError("Gemini did not return audio output", details=result.raw)
        mime = "audio/mpeg" if audio_format == "mp3" else f"audio/{audio_format}"
        return SpeechResult(
            audio_bytes=b64_decode(result.audios_base64[0]),
            mime_type=mime,
            raw=result.raw,
        )
