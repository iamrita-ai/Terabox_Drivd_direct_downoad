from __future__ import annotations

import time
from dataclasses import dataclass
from .human import human_bytes, human_time


@dataclass
class ProgressState:
    start_ts: float
    last_edit_ts: float
    last_done: int = 0


def progress_bar(pct: float, width: int = 20) -> str:
    pct = max(0.0, min(100.0, pct))
    filled = int((pct / 100.0) * width)
    return "[" + ("●" * filled) + ("○" * (width - filled)) + "]"


def format_progress(
    phase: str,
    filename: str,
    done: int,
    total: int | None,
    state: ProgressState,
) -> str:
    now = time.time()
    elapsed = max(0.001, now - state.start_ts)
    speed = done / elapsed  # bytes/sec

    if total and total > 0:
        pct = (done / total) * 100.0
        remaining = max(0, total - done)
        eta = remaining / max(1.0, speed)
        total_str = human_bytes(total)
    else:
        pct = 0.0
        eta = 0
        total_str = "Unknown"

    return (
        f"{phase}\n"
        f"{filename}\n"
        f"to my server\n"
        f"{progress_bar(pct)}\n"
        f"◌ Progress😉: 〘 {pct:.2f}% 〙\n"
        f"Done: 〘{human_bytes(done)} of {total_str}〙\n"
        f"◌ Speed🚀: 〘 {human_bytes(int(speed))}/s 〙\n"
        f"◌ Time Left⏳: 〘 {human_time(eta)} 〙"
    )
