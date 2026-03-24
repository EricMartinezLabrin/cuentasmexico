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
from .utils import b64_encode, safe_get


class OpenAIProvider(BaseAIProvider):
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.openai.com",
        timeout: int = 60,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _raise_for_error(self, response: requests.Response) -> None:
        if response.ok:
            return
        details: Dict[str, Any] | str
        try:
            details = response.json()
        except Exception:
            details = response.text
        raise AIProviderError(
            "OpenAI request failed",
            status_code=response.status_code,
            details=details,
        )

    def _to_openai_content(self, part: InputPart) -> Dict[str, Any]:
        if part.kind == "text":
            return {"type": "input_text", "text": part.text or ""}

        if part.kind == "image":
            if part.url:
                return {"type": "input_image", "image_url": part.url}
            if part.data is None:
                raise AIProviderError("Image part requires data or url")
            mime = part.mime_type or "image/png"
            image_b64 = b64_encode(part.data)
            return {
                "type": "input_image",
                "image_url": f"data:{mime};base64,{image_b64}",
            }

        if part.kind == "audio":
            if part.data is None:
                raise AIProviderError("Audio part requires data")
            mime = part.mime_type or "audio/wav"
            audio_b64 = b64_encode(part.data)
            audio_format = mime.split("/")[-1]
            return {
                "type": "input_audio",
                "input_audio": {"data": audio_b64, "format": audio_format},
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
        url = f"{self.base_url}/v1/responses"
        payload: Dict[str, Any] = {
            "model": model,
            "input": [
                {
                    "role": "user",
                    "content": [self._to_openai_content(p) for p in parts],
                }
            ],
        }
        if system_prompt:
            payload["instructions"] = system_prompt
        if temperature is not None:
            payload["temperature"] = temperature
        if max_output_tokens is not None:
            payload["max_output_tokens"] = max_output_tokens
        if extra:
            payload.update(extra)

        response = requests.post(
            url,
            headers=self._headers(),
            data=json.dumps(payload),
            timeout=self.timeout,
        )

        # Algunos modelos (p.ej. ciertos GPT-5) no aceptan `temperature`.
        # Reintentamos automáticamente sin ese parámetro para evitar fallos UX.
        if not response.ok and "temperature" in payload:
            try:
                err_json = response.json()
                err_message = str(err_json.get("error", {}).get("message", "")).lower()
            except Exception:
                err_message = ""
            if "unsupported parameter" in err_message and "temperature" in err_message:
                payload.pop("temperature", None)
                response = requests.post(
                    url,
                    headers=self._headers(),
                    data=json.dumps(payload),
                    timeout=self.timeout,
                )

        self._raise_for_error(response)
        data = response.json()

        text = data.get("output_text", "") or ""
        images: List[str] = []
        audios: List[str] = []

        for output_item in data.get("output", []) or []:
            for content_item in output_item.get("content", []) or []:
                if content_item.get("type") == "output_text":
                    text += content_item.get("text", "")
                elif content_item.get("type") in {"output_image", "image"}:
                    b64 = content_item.get("b64_json") or safe_get(
                        content_item, "image_base64"
                    )
                    if b64:
                        images.append(b64)
                elif content_item.get("type") in {"output_audio", "audio"}:
                    b64 = safe_get(content_item, "audio", "data") or content_item.get(
                        "data"
                    )
                    if b64:
                        audios.append(b64)

        return GenerateResult(
            text=text.strip(),
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
        url = f"{self.base_url}/v1/images/generations"
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "response_format": "b64_json",
        }
        if size:
            payload["size"] = size
        if extra:
            payload.update(extra)

        response = requests.post(
            url,
            headers=self._headers(),
            data=json.dumps(payload),
            timeout=self.timeout,
        )
        self._raise_for_error(response)
        data = response.json()

        images = [item.get("b64_json") for item in data.get("data", []) if item.get("b64_json")]
        return ImageResult(images_base64=images, raw=data)

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
        url = f"{self.base_url}/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        data: Dict[str, Any] = {"model": model}
        if language:
            data["language"] = language
        if prompt:
            data["prompt"] = prompt
        if extra:
            data.update(extra)

        ext = mime_type.split("/")[-1]
        files = {"file": (f"audio.{ext}", audio_bytes, mime_type)}
        response = requests.post(
            url,
            headers=headers,
            data=data,
            files=files,
            timeout=self.timeout,
        )
        self._raise_for_error(response)
        result = response.json()
        return TranscriptionResult(text=result.get("text", ""), raw=result)

    def synthesize_speech(
        self,
        *,
        text: str,
        model: str,
        voice: Optional[str] = None,
        audio_format: str = "mp3",
        extra: Optional[Dict[str, Any]] = None,
    ) -> SpeechResult:
        url = f"{self.base_url}/v1/audio/speech"
        payload: Dict[str, Any] = {
            "model": model,
            "input": text,
            "format": audio_format,
        }
        if voice:
            payload["voice"] = voice
        if extra:
            payload.update(extra)

        response = requests.post(
            url,
            headers=self._headers(),
            data=json.dumps(payload),
            timeout=self.timeout,
        )
        self._raise_for_error(response)
        mime = response.headers.get("Content-Type", "audio/mpeg")
        return SpeechResult(audio_bytes=response.content, mime_type=mime, raw={})
