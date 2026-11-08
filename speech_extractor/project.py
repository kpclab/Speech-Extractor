from __future__ import annotations

import copy
import shutil
from pathlib import Path
from typing import Any

import send2trash

from .config import VAD_DEFAULTS
from .utils import has_invalid_component_characters, load_json, new_id, sanitize_component, sanitize_component_raw, save_json


class ProjectError(RuntimeError):
    pass


def make_project_data(name: str, source: Path, vad_settings: dict[str, Any], model_id: str,
                      stereo: bool, whisper_settings: dict[str, Any] | str = "faster-whisper defaults") -> dict[str, Any]:
    return {
        "name": name,
        "source": str(source.resolve()),
        "speakers": {},
        "chunks": [],
        "history": [],
        "phase": "created",
        "default_speaker": "",
        "settings": {
            "audio_channels": 2 if stereo else 1,
            "sample_rate": 48000,
            "sample_format": "pcm_s16le",
            "whisper_model": model_id,
            "vad_filter": True,
            "vad_parameters": vad_settings,
            "whisper_parameters": whisper_settings,
        },
    }


def create_project(root: Path, name: str, source: Path, vad_settings: dict[str, Any],
                   model_id: str, stereo: bool,
                   whisper_settings: dict[str, Any] | str = "faster-whisper defaults") -> tuple[Path, dict[str, Any]]:
    if not source.is_file():
        raise ProjectError(f"Source file does not exist: {source}")
    root.mkdir(parents=True, exist_ok=True)
    raw_name = str(name or "").strip()
    project_id = new_id()
    if raw_name:
        if len(raw_name) > 100:
            raise ProjectError("Project name must contain 1–100 characters.")
        if has_invalid_component_characters(raw_name):
            raise ProjectError("Project name contains characters that are not valid on Windows, macOS, or Linux.")
        project_name = raw_name
    else:
        # A blank name falls back to the sanitized source filename, then UUID.
        project_name = sanitize_component_raw(source.stem)[:100]
        if not project_name.strip():
            project_name = project_id
    safe_name = sanitize_component(project_name)
    project_dir = root / project_id
    project_dir.mkdir(parents=False, exist_ok=False)
    data = make_project_data(project_name, source, vad_settings, model_id, stereo, whisper_settings)
    data["folder_name"] = safe_name
    save_json(project_dir / "info.json", data)
    return project_dir, data


def save_project(project_dir: Path, data: dict[str, Any]) -> None:
    if not project_dir.is_dir():
        raise ProjectError("Project folder is not available")
    save_json(project_dir / "info.json", data)


def list_projects(root: Path) -> list[tuple[str, Path, dict[str, Any]]]:
    """Search exactly one directory level below root: root/<UUID>/info.json."""
    found: list[tuple[str, Path, dict[str, Any]]] = []
    if not root.exists():
        return found
    for info_path in root.glob("*/info.json"):
        try:
            data = load_json(info_path)
            name = data.get("name")
            if isinstance(name, str) and name.strip():
                found.append((name, info_path.parent, data))
        except Exception:
            continue
    return sorted(found, key=lambda item: item[0].casefold())


def open_project(project_dir: Path) -> dict[str, Any]:
    info_path = project_dir / "info.json"
    if not info_path.is_file():
        raise ProjectError(f"info.json not found in {project_dir}")
    data = load_json(info_path)
    for key, default in (("speakers", {}), ("chunks", []), ("history", []), ("settings", {})):
        if not isinstance(data.get(key), type(default)):
            data[key] = default
    return data


def move_project_to_trash(project_dir: Path) -> None:
    project_dir = Path(project_dir).expanduser()
    try:
        target = project_dir.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ProjectError("Project folder no longer exists") from exc
    if not target.is_dir():
        raise ProjectError(f"Project path is not a directory: {target}")

    # On Windows, pywin32 enables send2trash's modern IFileOperation backend.
    # Without it, send2trash falls back to legacy SHFileOperation, which can
    # return ERROR_BAD_PATHNAME (WinError 161) for otherwise valid folder paths.
    # The Windows-only pywin32 dependency is declared in pyproject.toml.
    send2trash.send2trash(str(target))


def snapshot_chunks(data: dict[str, Any], operation: str) -> None:
    history = data.setdefault("history", [])
    history.append({"operation": operation, "chunks": copy.deepcopy(data.get("chunks", []))})
    if len(history) > 50:
        del history[:-50]


def undo_last(data: dict[str, Any]) -> bool:
    history = data.setdefault("history", [])
    if not history:
        return False
    snapshot = history.pop()
    data["chunks"] = snapshot.get("chunks", [])
    return True


def active_chunks(data: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        (chunk for chunk in data.get("chunks", []) if chunk.get("status", True)),
        key=lambda chunk: (float(chunk.get("start", 0)), float(chunk.get("end", 0))),
    )


def create_chunk(start: float, end: float, text: str, speaker: str = "") -> dict[str, Any]:
    return {
        "id": new_id(),
        "start": round(float(start), 3),
        "end": round(float(end), 3),
        "speaker": speaker,
        "original_text": text,
        "corrected_text": text,
        "reviewed": False,
        "status": True,
    }
