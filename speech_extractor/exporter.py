from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any, Callable

from .audio import copy_wav_fragment
from .project import active_chunks
from .utils import format_time, sanitize_component


_WINDOWS_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitized_export_stem(text: str, limit: int = 100) -> tuple[str, bool]:
    sanitized = sanitize_component(text, replacement="_")
    # Empty corrected text is a meaningful skip condition, not a filename.
    if sanitized == "_" and not text.strip():
        return "", False
    truncated = len(sanitized) > limit
    if truncated:
        sanitized = sanitized[:limit].rstrip(" .")
    return sanitized, truncated


def export_project(data: dict[str, Any], project_dir: Path, export_dir: Path,
                   numbered: bool = True, make_zip: bool = False,
                   log_cb: Callable[[str], None] | None = None) -> Path:
    ref_path = project_dir / "reference.wav"
    if not ref_path.is_file():
        raise FileNotFoundError("reference.wav is missing from this project")
    if not export_dir.is_dir():
        raise FileNotFoundError("The selected export directory does not exist")
    chunks = active_chunks(data)
    if not chunks:
        raise ValueError("There are no active fragments to export")

    used_names: set[str] = set()
    number_width = len(str(len(chunks)))
    srt_entries: list[str] = []
    wav_paths: list[Path] = []
    speakers = data.get("speakers", {}) or {}

    for index, chunk in enumerate(chunks, start=1):
        start = float(chunk.get("start", 0.0))
        end = float(chunk.get("end", 0.0))
        raw_text = str(chunk.get("corrected_text", ""))
        stem, was_truncated = sanitized_export_stem(raw_text, 100)
        if was_truncated and log_cb:
            log_cb(f"WARNING {index:03d}: text was truncated to 100 characters for the WAV filename.")
        if not stem and not numbered:
            if log_cb:
                log_cb(f"WARNING {index:03d}: empty filename after sanitization; skipped ({start:.3f}–{end:.3f}s).")
            continue

        prefix = f"{index:0{number_width}d}_" if numbered else ""
        base = f"{prefix}{stem}"
        speaker = str(chunk.get("speaker", "") or "").strip()
        if speaker and speaker in speakers:
            speaker_folder = sanitize_component(speaker)
            target_dir = export_dir / speaker_folder
        else:
            target_dir = export_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        candidate = f"{base}.wav"
        if not numbered:
            suffix = 2
            while (target_dir / candidate).exists() or candidate.casefold() in used_names:
                candidate = f"{base}{suffix}.wav"
                suffix += 1
        else:
            # Prefixes make names unique unless the project is exported repeatedly; preserve old files.
            if (target_dir / candidate).exists():
                suffix = 2
                while (target_dir / f"{base}{suffix}.wav").exists():
                    suffix += 1
                candidate = f"{base}{suffix}.wav"
        used_names.add(candidate.casefold())
        target_path = target_dir / candidate
        try:
            copy_wav_fragment(ref_path, target_path, start, end)
        except Exception as exc:
            if log_cb:
                log_cb(f"WARNING {index:03d}: fragment {start:.3f}–{end:.3f}s was skipped: {exc}")
            continue
        wav_paths.append(target_path)
        srt_entries.append(
            f"{len(srt_entries) + 1}\n{format_time(start)} --> {format_time(end)}\n{raw_text.strip()}"
        )
        if log_cb:
            log_cb(f"Exported {target_path.relative_to(export_dir)}")

    srt_path = export_dir / "ai_subtitle.srt"
    srt_path.write_text("\n\n".join(srt_entries) + ("\n" if srt_entries else ""), encoding="utf-8-sig")

    if make_zip:
        zip_path = export_dir / f"{sanitize_component(str(data.get('name', 'Project')))}.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for wav_path in wav_paths:
                archive.write(wav_path, wav_path.relative_to(export_dir).as_posix())
            archive.write(srt_path, srt_path.relative_to(export_dir).as_posix())
        if log_cb:
            log_cb(f"Created ZIP: {zip_path}")
    return export_dir
