from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from .config import MODEL_CHOICES
from .utils import app_base_dir, sanitize_component


def model_cache_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "speech-extractor" / "ctranslate2"


def list_cached_models() -> list[str]:
    items: set[str] = set()
    try:
        from huggingface_hub import scan_cache_dir
        info = scan_cache_dir()
        for repo in info.repos:
            if getattr(repo, "repo_type", None) == "model":
                items.add(repo.repo_id)
    except Exception:
        pass
    cache = model_cache_dir()
    if cache.exists():
        for item in cache.iterdir():
            if item.is_dir() and (item / "model.bin").is_file():
                items.add(str(item))
    return sorted(items, key=str.casefold)


def _has_ct2_weights(path: Path) -> bool:
    return path.is_dir() and (path / "model.bin").is_file()


def _is_ct2_model(path: Path) -> bool:
    # faster-whisper needs both the CTranslate2 weights and tokenizer.json.
    return _has_ct2_weights(path) and (path / "tokenizer.json").is_file()


def _prepare_ct2_model_with_tokenizer(source_path: Path, output_dir: Path, log_cb=None) -> str:
    """Prepare CT2 weights when a community repo omitted tokenizer.json."""
    from transformers import WhisperTokenizerFast

    if log_cb:
        log_cb("CTranslate2 weights found; generating the missing tokenizer.json...")

    tokenizer = WhisperTokenizerFast.from_pretrained(str(source_path))
    output_dir.mkdir(parents=True, exist_ok=True)

    # Keep the Hugging Face snapshot untouched and avoid duplicating large weights.
    for item in source_path.iterdir():
        if item.name == "tokenizer.json":
            continue
        target = output_dir / item.name
        if target.exists() or target.is_symlink():
            continue
        try:
            target.symlink_to(item, target_is_directory=item.is_dir())
        except OSError:
            if item.is_file():
                shutil.copy2(item, target)
            elif item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)

    tokenizer.backend_tokenizer.save(str(output_dir / "tokenizer.json"))
    if not _is_ct2_model(output_dir):
        raise RuntimeError("Could not prepare a usable CTranslate2 model: model.bin or tokenizer.json is missing.")
    return str(output_dir)


def resolve_model(model_id: str, device: str, log_cb=None) -> str:
    """Resolve a CT2 model or download+convert a Transformers Whisper model once."""
    model_id = model_id.strip()
    local = Path(model_id).expanduser()
    if local.exists():
        if _is_ct2_model(local):
            return str(local.resolve())
        source_path = local.resolve()
        cache_key = sanitize_component(source_path.name)
    else:
        # First try direct faster-whisper support; Systran/faster-whisper-* repos are CT2.
        if model_id.startswith("Systran/faster-whisper-"):
            return model_id
        from huggingface_hub import HfApi, snapshot_download
        if log_cb:
            log_cb(f"Downloading model files: {model_id}")
        # Prefer a single safetensors checkpoint over duplicate PyTorch/Flax copies.
        repo_files = set(HfApi().list_repo_files(model_id))
        common = [
            "config.json", "generation_config.json", "preprocessor_config.json",
            "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json",
            "added_tokens.json", "vocab.json", "merges.txt", "normalizer.json",
        ]
        if "model.bin" in repo_files:
            weights = ["model.bin"]
        elif "model.safetensors" in repo_files:
            weights = ["model.safetensors"]
        elif "pytorch_model.bin" in repo_files:
            weights = ["pytorch_model.bin"]
        else:
            # Sharded repositories are supported when their index identifies the shards.
            weights = [name for name in repo_files if name.endswith((".safetensors", ".bin")) and
                       (name.startswith("model-") or name.startswith("pytorch_model-"))]
            weights += [name for name in repo_files if name.endswith((".safetensors.index.json", ".bin.index.json"))]
        source_path = Path(snapshot_download(repo_id=model_id, allow_patterns=common + weights))
        if _is_ct2_model(source_path):
            return str(source_path)
        cache_key = re.sub(r"[^A-Za-z0-9._-]+", "__", model_id)
    output_dir = model_cache_dir() / cache_key
    if _is_ct2_model(output_dir):
        return str(output_dir)

    # A few community CT2 repos ship model.bin without tokenizer.json.
    if _has_ct2_weights(source_path):
        return _prepare_ct2_model_with_tokenizer(source_path, output_dir, log_cb)
    if _has_ct2_weights(output_dir):
        return _prepare_ct2_model_with_tokenizer(output_dir, output_dir, log_cb)

    converter = shutil.which("ct2-transformers-converter")
    if not converter:
        raise RuntimeError(
            "This model is in Transformers format, not CTranslate2 format. "
            "Install the conversion dependencies (see README), including the "
            "ct2-transformers-converter command."
        )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    if log_cb:
        log_cb(f"Preparing tokenizer and converting {model_id} to CTranslate2 (first run only)...")

    # Transformers Whisper checkpoints commonly contain vocab.json + merges.txt
    # but no tokenizer.json. The CT2 converter requires tokenizer.json, so stage
    # a lightweight view of the snapshot and generate that file there. Large
    # model weights are symlinked, not copied; the HF snapshot stays untouched.
    from transformers import WhisperTokenizerFast
    staging_dir = output_dir.parent / f".{output_dir.name}.conversion"
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)
    try:
        for item in source_path.iterdir():
            target = staging_dir / item.name
            try:
                target.symlink_to(item, target_is_directory=item.is_dir())
            except OSError:
                if item.is_file():
                    shutil.copy2(item, target)
                elif item.is_dir():
                    shutil.copytree(item, target, dirs_exist_ok=True)

        tokenizer = WhisperTokenizerFast.from_pretrained(str(source_path))
        tokenizer.save_pretrained(str(staging_dir))

        quantization = "float16" if device == "cuda" else "int8"
        command = [
            converter, "--model", str(staging_dir), "--output_dir", str(output_dir),
            "--copy_files", "tokenizer.json", "preprocessor_config.json",
            "--quantization", quantization,
        ]
        result = subprocess.run(command, capture_output=True, text=True)
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)
    if result.returncode != 0 or not _is_ct2_model(output_dir):
        details = (result.stderr or result.stdout or "No converter output")[-5000:]
        raise RuntimeError(f"Model conversion failed.\n{details}")
    return str(output_dir)


def detect_device(requested: str = "Auto") -> tuple[str, str]:
    if requested.casefold() == "cpu":
        return "cpu", "int8"
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda", "float16"
    except Exception:
        pass
    if requested.casefold() == "cuda":
        raise RuntimeError("CUDA was requested, but no usable CTranslate2 CUDA device was detected.")
    return "cpu", "int8"
