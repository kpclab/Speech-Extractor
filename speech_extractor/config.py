from __future__ import annotations

APP_NAME = "Speech Extractor"
APP_VERSION = "1.0.0"
PAGE_SIZE = 30
AUDIO_SAMPLE_RATE = 48_000
AUDIO_SAMPLE_WIDTH = 2  # PCM signed 16-bit
DEFAULT_WHISPER_MODEL = "Systran/faster-whisper-large-v3"
MODEL_CHOICES = [
    "Systran/faster-whisper-large-v3",
    "Systran/faster-whisper-medium",
    "Systran/faster-whisper-small",
    "Systran/faster-whisper-base",
    "Systran/faster-whisper-tiny",
    "seastar105/whisper-medium-komixv2",
]


def build_model_choices(cached_models: list[str] | tuple[str, ...]) -> list[str]:
    """Return built-in choices in their configured order, then other cached models.

    The KomiX model is simply the last *built-in/default* choice. Cached custom
    models remain in the separate section after the built-in choices.
    """
    excluded = {"openai/whisper-large-v3".casefold()}
    builtins = [model for model in MODEL_CHOICES if model.casefold() not in excluded]
    builtin_keys = {model.casefold() for model in builtins}
    extras_by_key = {
        model.casefold(): model
        for model in cached_models
        if model.casefold() not in excluded and model.casefold() not in builtin_keys
    }
    extras = sorted(extras_by_key.values(), key=str.casefold)
    return builtins + extras

WHISPER_DEFAULTS = {
    "beam_size": 5,
    "temperature": 0.5,
    # Custom-mode default requested by the app; the library default is True.
    "condition_on_previous_text": False,
    "compression_ratio_threshold": 2.4,
    "log_prob_threshold": -1.0,
    "no_speech_threshold": 0.6,
}

VAD_DEFAULTS = {
    "threshold": 0.5,
    "min_speech_duration_ms": 0,
    "max_speech_duration_s": float("inf"),
    "min_silence_duration_ms": 2000,
    "speech_pad_ms": 400,
}
LANGUAGES = ("English", "한국어", "日本語")
