from __future__ import annotations

from typing import Optional, Tuple

from .resolver import resolve_provider
from .direct import download_direct
from .gdrive import download_gdrive
from .terabox import download_terabox


def download_any(
    url: str,
    out_dir: str,
    *,
    on_progress_text,
    interval_sec: int = 8,
    cancel_event=None,
    max_bytes: Optional[int] 
