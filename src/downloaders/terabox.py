from __future__ import annotations

from typing import Optional, Tuple


def download_terabox(
    url: str,
    out_dir: str,
    *,
    on_progress_text,
    interval_sec: int = 8,
    cancel_event=None,
    max_bytes: Optional[int] = None,
) -> Tuple[str, str]:
    """
    TeraBox public share downloading without session is not stable across all link types.
    Part-3 me best-effort extractor add karunga.

    For now, raise clear error so bot reports failure.
    """
    raise RuntimeError("TeraBox downloader (no-session) not enabled yet. Coming in Part-3.")
