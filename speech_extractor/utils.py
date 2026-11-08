from __future__ import annotations

import re
import sys
import uuid
from pathlib import Path
from typing import Any

import orjson

# Invalid on Windows, macOS, or Linux path components, plus control characters.
_INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED_WINDOWS = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$", re.IGNORECASE)


def sanitize_component_raw(value: str, replacement: str = "_") -> str:
    """Sanitize a path component, preserving an empty result for fallback logic."""
    value = _INVALID_FILENAME.sub(replacement, str(value))
    value = value.rstrip(" .").strip()
    if not value:
        return ""
    if _RESERVED_WINDOWS.match(value):
        value = f"_{value}"
    return value


def sanitize_component(value: str, replacement: str = "_") -> str:
    """Sanitize one cross-platform path component without removing Unicode text."""
    return sanitize_component_raw(value, replacement=replacement) or "_"


def has_invalid_component_characters(value: str) -> bool:
    """Return whether a user-entered name would be changed by path sanitization."""
    stripped = str(value).strip()
    return sanitize_component_raw(stripped) != stripped


def new_id() -> str:
    return str(uuid.uuid4())


def app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def default_project_dir() -> Path:
    return app_base_dir() / "Project"


def load_json(path: Path) -> dict[str, Any]:
    return orjson.loads(path.read_bytes())


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2 | orjson.OPT_APPEND_NEWLINE))
    tmp.replace(path)


def format_time(seconds: float) -> str:
    milliseconds = max(0, int(round(float(seconds) * 1000)))
    hours, rem = divmod(milliseconds, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def parse_inf_float(text: str) -> float:
    value = text.strip().lower()
    if value in {"inf", "+inf", "infinity", "+infinity", "∞"}:
        return float("inf")
    return float(value)
