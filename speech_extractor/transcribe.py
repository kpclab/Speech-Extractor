from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .models import detect_device, resolve_model
from .windows_cuda import configure_windows_cuda_runtime
from .project import create_chunk


def transcribe_reference(reference_path: Path, model_id: str, vad_parameters: dict[str, Any] | None,
                         device_choice: str = "Auto", progress: Callable[[str], None] | None = None,
                         cancel_check: Callable[[], bool] | None = None,
                         chunk_callback: Callable[[dict[str, Any]], None] | None = None,
                         whisper_parameters: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    # On Windows, NVIDIA pip wheels install their DLLs below
    # site-packages/nvidia/*/bin. Register those folders before importing
    # faster-whisper/CTranslate2, whose CUDA libraries are loaded lazily.
    cuda_dll_dirs = configure_windows_cuda_runtime()
    if progress and cuda_dll_dirs:
        progress("Configured CUDA runtime DLL paths from the project environment.")

    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("faster-whisper is not installed. Install project dependencies with `uv sync` first.") from exc

    device, compute_type = detect_device(device_choice)
    resolved_model = resolve_model(model_id, device, progress)
    if progress:
        progress(f"Loading Whisper model on {device} ({compute_type})...")
    model = WhisperModel(resolved_model, device=device, compute_type=compute_type)

    kwargs: dict[str, Any] = {
        "task": "transcribe",  # Explicitly transcribe; do not translate.
        "vad_filter": True,
        "word_timestamps": True,
    }
    # Preserve faster-whisper's built-in VadOptions defaults when the UI's Default box is on.
    if vad_parameters is not None:
        kwargs["vad_parameters"] = vad_parameters
    # Keep faster-whisper defaults untouched when the UI default mode is selected.
    if whisper_parameters is not None:
        allowed_parameters = {
            "beam_size", "temperature", "condition_on_previous_text",
            "compression_ratio_threshold", "log_prob_threshold", "no_speech_threshold",
        }
        kwargs.update({key: value for key, value in whisper_parameters.items() if key in allowed_parameters})

    segments, info = model.transcribe(str(reference_path), **kwargs)
    results: list[dict[str, Any]] = []
    for idx, segment in enumerate(segments, start=1):
        if cancel_check and cancel_check():
            raise InterruptedError("Transcription cancelled")
        text = (segment.text or "").strip()
        if not text:
            continue
        chunk = create_chunk(segment.start, segment.end, text)
        results.append(chunk)
        if chunk_callback:
            chunk_callback(chunk)
        if progress:
            progress(f"Transcribed {idx} segments... ({segment.start:.2f}s–{segment.end:.2f}s)")

    meta = {
        "language": getattr(info, "language", None),
        "language_probability": getattr(info, "language_probability", None),
        "duration": getattr(info, "duration", None),
        "duration_after_vad": getattr(info, "duration_after_vad", None),
        "model": model_id,
        "device": device,
        "compute_type": compute_type,
    }
    return results, meta
