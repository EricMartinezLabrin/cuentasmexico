OPENAI_TEXT_CHOICES = [
    ("gpt-5.4", "GPT-5.4"),
    ("gpt-5.4-pro", "GPT-5.4 Pro"),
    ("gpt-5-mini", "GPT-5 mini"),
]

OPENAI_IMAGE_CHOICES = [
    ("gpt-image-1.5", "GPT Image 1.5"),
    ("chatgpt-image-latest", "chatgpt-image-latest"),
    ("gpt-image-1-mini", "GPT Image 1 mini"),
]

OPENAI_TRANSCRIPTION_CHOICES = [
    ("gpt-4o-transcribe", "GPT-4o Transcribe"),
    ("gpt-4o-mini-transcribe", "GPT-4o mini Transcribe"),
    ("whisper-1", "Whisper"),
]

OPENAI_SPEECH_CHOICES = [
    ("gpt-4o-mini-tts", "GPT-4o mini TTS"),
    ("tts-1-hd", "TTS-1 HD"),
    ("tts-1", "TTS-1"),
]

GEMINI_TEXT_CHOICES = [
    ("gemini-3-pro-preview", "Gemini 3 Pro Preview"),
    ("gemini-3-flash-preview", "Gemini 3 Flash Preview"),
    ("gemini-2.5-pro", "Gemini 2.5 Pro"),
]

GEMINI_IMAGE_CHOICES = [
    ("gemini-2.5-flash-image", "Gemini 2.5 Flash Image"),
    ("gemini-3-pro-preview", "Gemini 3 Pro Preview"),
    ("gemini-2.0-flash-preview-image-generation", "Gemini 2.0 Flash Image Preview"),
]

GEMINI_TRANSCRIPTION_CHOICES = [
    ("gemini-3-flash-preview", "Gemini 3 Flash Preview"),
    ("gemini-2.5-flash", "Gemini 2.5 Flash"),
    ("gemini-2.5-flash-lite", "Gemini 2.5 Flash-Lite"),
]

GEMINI_SPEECH_CHOICES = [
    ("gemini-2.5-pro-preview-tts", "Gemini 2.5 Pro TTS"),
    ("gemini-2.5-flash-preview-tts", "Gemini 2.5 Flash TTS"),
    ("gemini-2.5-flash-native-audio-preview-12-2025", "Gemini 2.5 Flash Native Audio"),
]


def chat_model_choices(provider: str):
    provider = (provider or "").lower().strip()
    if provider == "openai":
        return OPENAI_TEXT_CHOICES
    if provider == "gemini":
        return GEMINI_TEXT_CHOICES
    return []
