from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

import requests

from .direct import download_direct


@dataclass
class TBItem:
    isdir: int
    name: str
    path: str
    size: int
    dlink: Optional[str] = None


_SURL_RE = re.compile(r"/s/([A-Za-z0-9_-]+)")


def _extract_surl(url: str) -> str:
    u = url.strip()
    m = _SURL_RE.search(urlparse(u).path)
    if m:
        return m.group(1)

    qs = parse_qs(urlparse(u).query)
    for key in ("surl", "shorturl"):
        if key in qs and qs[key]:
            return qs[key][0]
    raise RuntimeError("TeraBox: surl/shorturl not found in link")


def _tb_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120 Safari/537.36",
        "accept": "application/json,text/plain,*/*",
    })
    return s


def _list_dir(sess: requests.Session, surl: str, dir_path: str = "/") -> List[TBItem]:
    """
    Best-effort: tries share/list and hopes dlink is present.
    If dlink not returned, it will fail (some shares require extra signing/cookies).
    """
    url = "https://www.terabox.com/share/list"
    params = {
        "app_id": "250528",
        "web": "1",
        "channel": "dubox",
        "clienttype": "0",
        "shorturl": surl,
        "root": "1",
        "dir": dir_path if dir_path != "/" else "",
        "num": "1000",
        "page": "1",
        "order": "name",
        "desc": "0",
    }
    r = sess.get(url, params=params, timeout=30)
    r.raise_for_status()
    data: Dict[str, Any] = r.json()

    if data.get("errno") not in (0, "0", None):
        raise RuntimeError(f"TeraBox list error: {data.get('errno')}")

    lst = data.get("list") or []
    out: List[TBItem] = []
    for x in lst:
        out.append(
            TBItem(
                isdir=int(x.get("isdir", 0)),
                name=str(x.get("server_filename") or x.get("name") or "file"),
                path=str(x.get("path") or ""),
                size=int(x.get("size") or 0),
                dlink=x.get("dlink"),
            )
        )
    return out


def _walk(sess: requests.Session, surl: str, dir_path: str = "/") -> List[TBItem]:
    items = _list_dir(sess, surl, dir_path=dir_path)
    files: List[TBItem] = []
    for it in items:
        if it.isdir == 1 and it.path:
            files.extend(_walk(sess, surl, dir_path=it.path))
        else:
            files.append(it)
    return files


def download_terabox(
    url: str,
    out_dir: str,
    *,
    on_progress_text,
    interval_sec: int = 8,
    cancel_event=None,
    max_bytes: Optional[int] = None,
    rate_limit_bps: Optional[float] = None,
) -> Tuple[str, str]:
    """
    Downloads all files found in the share (folder supported best-effort).
    Saves into out_dir. Returns (first_file_path, first_file_name).

    Note: If share/list does not provide dlink, this may fail on some links.
    """
    os.makedirs(out_dir, exist_ok=True)
    surl = _extract_surl(url)
    sess = _tb_session()

    items = _walk(sess, surl, dir_path="/")
    if not items:
        raise RuntimeError("TeraBox: no files found")

    first_path = ""
    first_name = ""

    for idx, it in enumerate(items, start=1):
        if cancel_event and cancel_event.is_set():
            raise RuntimeError("Cancelled")

        if max_bytes and it.size and it.size > max_bytes:
            raise RuntimeError(f"TeraBox file too large: {it.size} bytes > limit")

        if not it.dlink:
            raise RuntimeError("TeraBox: dlink not available for this share (needs sign/cookies)")

        p, n = download_direct(
            it.dlink,
            out_dir,
            on_progress_text=on_progress_text,
            interval_sec=interval_sec,
            cancel_event=cancel_event,
            max_bytes=max_bytes,
            rate_limit_bps=rate_limit_bps,
        )

        if idx == 1:
            first_path, first_name = p, n

    return first_path, first_name
