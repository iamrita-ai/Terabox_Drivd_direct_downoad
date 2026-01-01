from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import unquote, urlparse

import requests

from src.utils.progress import ProgressState, format_progress


def _filename_from_headers(url: str, headers: dict) -> str:
    cd = headers.get("content-disposition") or headers.get("Content-Disposition") or ""
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd)
    if m:
        return unquote(m.group(1)).strip()

    path = urlparse(url).path
    name = Path(path).name or "file"
    return name


def head_content_length(url: str, timeout: int = 20) -> Optional[int]:
    try:
        r = requests.head(url, allow_redirects=True, timeout=timeout)
        cl = r.headers.get("content-length")
        return int(cl) if cl else None
    except Exception:
        return None


def download_direct(
    url: str,
    out_dir: str,
    *,
    on_progress_text,  # callable(text:str) -> None
    interval_sec: int = 8,
    cancel_event=None,
    max_bytes: Optional[int] = None,
) -> Tuple[str, str]:
    """
    Returns (file_path, filename)
    Runs sync; call using asyncio.to_thread.
    """
    os.makedirs(out_dir, exist_ok=True)

    with requests.get(url, stream=True, allow_redirects=True, timeout=30) as r:
        r.raise_for_status()

        total = r.headers.get("content-length")
        total_int = int(total) if total and total.isdigit() else None

        filename = _filename_from_headers(url, r.headers)
        if not filename:
            filename = "file"

        out_path = str(Path(out_dir) / filename)

        if max_bytes and total_int and total_int > max_bytes:
            raise RuntimeError(f"File too large: {total_int} bytes > limit")

        state = ProgressState(start_ts=time.time(), last_edit_ts=0.0)

        done = 0
        chunk = 1024 * 1024  # 1MB

        with open(out_path, "wb") as f:
            for part in r.iter_content(chunk_size=chunk):
                if cancel_event and cancel_event.is_set():
                    raise RuntimeError("Cancelled")

                if not part:
                    continue
                f.write(part)
                done += len(part)

                now = time.time()
                if now - state.last_edit_ts >= interval_sec:
                    state.last_edit_ts = now
                    on_progress_text(
                        format_progress("Downloading", filename, done, total_int, state)
                    )

        # final update
        on_progress_text(format_progress("Downloading", filename, done, total_int, state))
        return out_path, filename
