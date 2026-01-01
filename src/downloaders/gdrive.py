from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple

import gdown

from src.utils.progress import ProgressState, format_progress
import time


def _extract_name(path: str) -> str:
    return Path(path).name


def download_gdrive(
    url: str,
    out_dir: str,
    *,
    on_progress_text,
    interval_sec: int = 8,
    cancel_event=None,
    max_bytes: Optional[int] = None,
) -> Tuple[str, str]:
    """
    Best-effort gdrive public download using gdown (no OAuth).
    Returns (file_path, filename)

    Note: gdown doesn't provide clean per-chunk callback; we emulate progress using file size polling.
    """
    os.makedirs(out_dir, exist_ok=True)

    # gdown output path: if directory, it decides filename
    temp_out = str(Path(out_dir) / "gdrive_download")

    state = ProgressState(start_ts=time.time(), last_edit_ts=0.0)
    last_size = 0

    def _ticker():
        nonlocal last_size
        now = time.time()
        if now - state.last_edit_ts >= interval_sec:
            state.last_edit_ts = now
            # size so far
            try:
                if os.path.exists(temp_out):
                    last_size = os.path.getsize(temp_out)
            except Exception:
                pass
            on_progress_text(format_progress("Downloading", "GoogleDrive", last_size, None, state))

    # gdown is sync; call from thread
    started = time.time()
    while time.time() - started < 0.5:
        _ticker()

    # actual download
    path = gdown.download(url=url, output=temp_out, quiet=True, fuzzy=True)

    if cancel_event and cancel_event.is_set():
        raise RuntimeError("Cancelled")

    if not path or not os.path.exists(path):
        raise RuntimeError("Google Drive download failed")

    filename = _extract_name(path)

    # rename to real filename if it doesn't have one
    # gdown sometimes saves with correct name already; keep.
    final_path = str(Path(out_dir) / filename)
    if Path(path).resolve() != Path(final_path).resolve():
        try:
            os.replace(path, final_path)
        except Exception:
            final_path = path

    size = os.path.getsize(final_path)
    if max_bytes and size > max_bytes:
        raise RuntimeError(f"File too large: {size} bytes > limit")

    on_progress_text(format_progress("Downloading", filename, size, size, state))
    return final_path, filename
