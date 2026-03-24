from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class InputPart:
    """
    Bloque de entrada multimodal.

    - text: usar `text`
    - image/audio: usar `data` (bytes crudos o base64) + `mime_type`
      opcionalmente `url` para recursos remotos.
    """

    kind: str
    text: Optional[str] = None
    data: Optional[bytes | str] = None
    mime_type: Optional[str] = None
    url: Optional[str] = None

    @classmethod
    def from_text(cls, text: str) -> "InputPart":
        return cls(kind="text", text=text)

    @classmethod
    def from_image(
        cls,
        *,
        data: bytes | str | None = None,
        mime_type: str = "image/png",
        url: str | None = None,
    ) -> "InputPart":
        return cls(kind="image", data=data, mime_type=mime_type, url=url)

    @classmethod
    def from_audio(
        cls,
        *,
        data: bytes | str | None = None,
        mime_type: str = "audio/wav",
        url: str | None = None,
    ) -> "InputPart":
        return cls(kind="audio", data=data, mime_type=mime_type, url=url)


@dataclass
class GenerateResult:
    text: str = ""
    images_base64: List[str] = field(default_factory=list)
    audios_base64: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ImageResult:
    images_base64: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TranscriptionResult:
    text: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SpeechResult:
    audio_bytes: bytes = b""
    mime_type: str = "audio/mpeg"
    raw: Dict[str, Any] = field(default_factory=dict)
