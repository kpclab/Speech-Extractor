from __future__ import annotations

import math
import wave
from pathlib import Path
from typing import Callable


from .config import AUDIO_SAMPLE_RATE


def convert_to_reference(source_path: Path, output_path: Path, channels: int = 2,
                         progress: Callable[[str], None] | None = None) -> None:
    """Decode any PyAV-supported media and write 48 kHz signed 16-bit PCM WAV."""
    try:
        import av
    except ImportError as exc:
        raise RuntimeError("PyAV is not installed. Install project dependencies with `uv sync` first.") from exc
    layout = "stereo" if channels == 2 else "mono"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wrote_samples = 0
    try:
        with av.open(str(source_path), mode="r") as input_container:
            audio_streams = input_container.streams.audio
            if not audio_streams:
                raise RuntimeError("The selected source contains no audio stream.")
            source_stream = audio_streams[0]
            resampler = av.AudioResampler(format="s16", layout=layout, rate=AUDIO_SAMPLE_RATE)
            with av.open(str(output_path), mode="w", format="wav") as output_container:
                output_stream = output_container.add_stream(
                    "pcm_s16le", rate=AUDIO_SAMPLE_RATE, layout=layout
                )
                for frame in input_container.decode(source_stream):
                    frame.pts = None
                    for converted in resampler.resample(frame):
                        for packet in output_stream.encode(converted):
                            output_container.mux(packet)
                        wrote_samples += converted.samples
                    if progress and wrote_samples and wrote_samples % (AUDIO_SAMPLE_RATE * 30) < 2048:
                        progress(f"Decoded approximately {wrote_samples / AUDIO_SAMPLE_RATE:.0f} seconds")
                for converted in resampler.resample(None):
                    for packet in output_stream.encode(converted):
                        output_container.mux(packet)
                    wrote_samples += converted.samples
                for packet in output_stream.encode(None):
                    output_container.mux(packet)
        with wave.open(str(output_path), "rb") as check:
            if check.getnframes() <= 0 or check.getframerate() != AUDIO_SAMPLE_RATE:
                raise RuntimeError("Converted WAV is empty or has an unexpected sample rate.")
            if check.getnchannels() != channels or check.getsampwidth() != 2:
                raise RuntimeError("Converted WAV does not match the requested PCM format.")
    except Exception:
        try:
            output_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def wav_info(path: Path) -> tuple[int, int, int, int, float]:
    with wave.open(str(path), "rb") as wf:
        channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        sample_rate = wf.getframerate()
        frames = wf.getnframes()
        return channels, sample_width, sample_rate, frames, frames / sample_rate


def copy_wav_fragment(reference_path: Path, output_path: Path, start: float, end: float) -> None:
    """Sample-accurate PCM frame copy: no decode/re-encode and therefore no quality loss."""
    with wave.open(str(reference_path), "rb") as src:
        params = src.getparams()
        rate = params.framerate
        total_frames = params.nframes
        first = max(0, min(total_frames, int(math.floor(start * rate))))
        last = max(first, min(total_frames, int(math.ceil(end * rate))))
        if last <= first:
            raise ValueError("Fragment has zero or negative duration")
        src.setpos(first)
        raw_frames = src.readframes(last - first)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), "wb") as dst:
        dst.setparams(params)
        dst.writeframes(raw_frames)


def read_waveform(path: Path, start: float, end: float, max_points: int = 1400):
    """Return min/max envelope points for a time window, using a short random WAV read."""
    import numpy as np

    with wave.open(str(path), "rb") as wf:
        rate = wf.getframerate()
        channels = wf.getnchannels()
        width = wf.getsampwidth()
        total = wf.getnframes()
        first = max(0, min(total, int(start * rate)))
        last = max(first, min(total, int(end * rate)))
        if last <= first:
            return np.zeros(1, dtype=np.float32), np.zeros(1, dtype=np.float32)
        wf.setpos(first)
        raw = wf.readframes(last - first)
    if width == 2:
        arr = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif width == 1:
        arr = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    elif width == 4:
        arr = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    else:
        return np.zeros(1, dtype=np.float32), np.zeros(1, dtype=np.float32)
    if channels > 1:
        arr = arr.reshape(-1, channels).mean(axis=1)
    bucket = max(1, int(math.ceil(len(arr) / max_points)))
    usable = (len(arr) // bucket) * bucket
    if usable == 0:
        return arr, arr
    grouped = arr[:usable].reshape(-1, bucket)
    return grouped.min(axis=1), grouped.max(axis=1)
