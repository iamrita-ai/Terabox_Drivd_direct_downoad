from __future__ import annotations

def human_bytes(n: int) -> str:
    n = int(n)
    if n < 1024:
        return f"{n} B"
    units = ["KB", "MB", "GB", "TB"]
    v = float(n)
    for u in units:
        v /= 1024.0
        if v < 1024.0:
            return f"{v:.2f} {u}"
    return f"{v:.2f} PB"


def human_time(seconds: float) -> str:
    seconds = max(0, int(seconds))
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}h, {m}m, {s}s"
    if m > 0:
        return f"{m}m, {s}s"
    return f"{s}s"
