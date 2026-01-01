from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class ResolvedLink:
    provider: str  # direct|gdrive|terabox
    url: str


_GDRIVE_RE = re.compile(r"(drive\.google\.com|docs\.google\.com)", re.IGNORECASE)
_TERABOX_RE = re.compile(r"(terabox\.com|1024tera\.com|teraboxapp\.com)", re.IGNORECASE)


def resolve_provider(url: str) -> ResolvedLink:
    u = url.strip()
    host = urlparse(u).netloc.lower()

    if _GDRIVE_RE.search(host) or _GDRIVE_RE.search(u):
        return ResolvedLink(provider="gdrive", url=u)
    if _TERABOX_RE.search(host) or _TERABOX_RE.search(u):
        return ResolvedLink(provider="terabox", url=u)
    return ResolvedLink(provider="direct", url=u)
