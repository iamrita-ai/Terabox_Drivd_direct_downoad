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
    max_bytes: Optional[int] = None,
    rate_limit_bps: Optional[float] = None,
) -> Tuple[str, str]:
    r = resolve_provider(url)

    if r.provider == "gdrive":
        return download_gdrive(
            r.url,
            out_dir,
            on_progress_text=on_progress_text,
            interval_sec=interval_sec,
            cancel_event=cancel_event,
            max_bytes=max_bytes,
        )

    if r.provider == "terabox":
        return download_terabox(
            r.url,
            out_dir,
            on_progress_text=on_progress_text,
            interval_sec=interval_sec,
            cancel_event=cancel_event,
            max_bytes=max_bytes,
            rate_limit_bps=rate_limit_bps,
        )

    return download_direct(
        r.url,
        out_dir,
        on_progress_text=on_progress_text,
        interval_sec=interval_sec,
        cancel_event=cancel_event,
        max_bytes=max_bytes,
        rate_limit_bps=rate_limit_bps,
    )
