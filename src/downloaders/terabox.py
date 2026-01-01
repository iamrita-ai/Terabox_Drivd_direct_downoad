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
    fs_id: Optional[int] = None
    dlink: Optional[str] = None


def _tb_session() -> Tuple[requests.Session, Optional[str]]:
    """
    Returns (session, cookie_header_string_or_none)
    We prefer forcing Cookie header because requests' cookie jar can be domain-restricted.
    """
    s = requests.Session()
    s.headers.update({
        "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120 Safari/537.36",
        "accept": "application/json,text/plain,*/*",
    })

    ck = os.getenv("TERABOX_COOKIES", "").strip()
    if ck:
        # force cookie header for all requests
        s.headers["cookie"] = ck
        return s, ck

    return s, None


def _parse_terabox_link(url: str) -> Tuple[str, str, Optional[int], Optional[str], Optional[str]]:
    """
    Returns: (base, surl, fsid, dir_path, file_name)
    base keeps the same domain (1024tera vs terabox) so endpoints match the share.
    """
    u = url.strip()
    pu = urlparse(u)
    qs = parse_qs(pu.query)

    base = f"{pu.scheme or 'https'}://{pu.netloc}"

    surl = None
    if "surl" in qs and qs["surl"]:
        surl = qs["surl"][0]
    else:
        # also support /s/<surl>
        m = re.search(r"/s/([A-Za-z0-9_-]+)", pu.path)
        if m:
            surl = m.group(1)

    if not surl:
        raise RuntimeError("TeraBox: surl not found in link")

    fsid = None
    if "fsid" in qs and qs["fsid"] and qs["fsid"][0].isdigit():
        fsid = int(qs["fsid"][0])

    dir_path = qs.get("dir", [None])[0]
    file_name = qs.get("fileName", [None])[0]

    return base, surl, fsid, dir_path, file_name


def _fetch_html(sess: requests.Session, url: str, referer: str) -> str:
    r = sess.get(url, timeout=30, headers={"referer": referer})
    r.raise_for_status()
    return r.text


def _extract_meta(html: str) -> Tuple[str, str, str, str]:
    """
    Extract sign, timestamp, shareid, uk from various terabox/1024tera page patterns.
    """
    # sign
    sign = None
    for pat in [
        r'"sign"\s*:\s*"([^"]+)"',
        r"sign\s*:\s*'([^']+)'",
        r"sign\s*:\s*\"([^\"]+)\"",
        r"sign\s*=\s*\"([^\"]+)\"",
        r"sign\s*=\s*'([^']+)'",
    ]:
        m = re.search(pat, html)
        if m:
            sign = m.group(1)
            break

    # timestamp
    ts = None
    for pat in [
        r'"timestamp"\s*:\s*(\d+)',
        r"timestamp\s*:\s*'(\d+)'",
        r"timestamp\s*:\s*(\d+)",
        r"timestamp\s*=\s*(\d+)",
    ]:
        m = re.search(pat, html)
        if m:
            ts = m.group(1)
            break

    # shareid
    shareid = None
    for pat in [
        r'"shareid"\s*:\s*(\d+)',
        r'"share_id"\s*:\s*(\d+)',
        r'"shareId"\s*:\s*(\d+)',
        r"shareid\s*=\s*(\d+)",
    ]:
        m = re.search(pat, html)
        if m:
            shareid = m.group(1)
            break

    # uk
    uk = None
    for pat in [
        r'"uk"\s*:\s*(\d+)',
        r'"share_uk"\s*:\s*(\d+)',
        r"uk\s*=\s*(\d+)",
    ]:
        m = re.search(pat, html)
        if m:
            uk = m.group(1)
            break

    if not (sign and ts and shareid and uk):
        raise RuntimeError("TeraBox: could not extract sign/timestamp/shareid/uk (needs cookies/login or page pattern changed)")

    return sign, ts, shareid, uk


def _list_dir(sess: requests.Session, base: str, surl: str, dir_path: Optional[str]) -> List[TBItem]:
    url = f"{base}/share/list"

    # root=1 for root listing; for dir listing root=0 usually works better
    is_root = (not dir_path) or (dir_path == "/")
    params = {
        "app_id": "250528",
        "web": "1",
        "channel": "dubox",
        "clienttype": "0",
        "shorturl": surl,
        "root": "1" if is_root else "0",
        "dir": "" if is_root else (dir_path or ""),
        "num": "1000",
        "page": "1",
        "order": "name",
        "desc": "0",
    }

    r = sess.get(url, params=params, timeout=30, headers={"referer": f"{base}/s/{surl}"})
    r.raise_for_status()
    data: Dict[str, Any] = r.json()

    errno = data.get("errno", 0)
    if str(errno) != "0":
        raise RuntimeError(f"TeraBox list error: errno={errno}")

    lst = data.get("list") or []
    out: List[TBItem] = []
    for x in lst:
        out.append(
            TBItem(
                isdir=int(x.get("isdir", 0)),
                name=str(x.get("server_filename") or x.get("name") or "file"),
                path=str(x.get("path") or ""),
                size=int(x.get("size") or 0),
                fs_id=int(x.get("fs_id")) if x.get("fs_id") is not None else None,
                dlink=x.get("dlink"),
            )
        )
    return out


def _walk(sess: requests.Session, base: str, surl: str, dir_path: Optional[str]) -> List[TBItem]:
    items = _list_dir(sess, base, surl, dir_path)
    files: List[TBItem] = []
    for it in items:
        if it.isdir == 1 and it.path:
            files.extend(_walk(sess, base, surl, it.path))
        else:
            files.append(it)
    return files


def _get_dlink(sess: requests.Session, base: str, surl: str, fs_id: int, sign: str, timestamp: str, shareid: str, uk: str) -> str:
    url = f"{base}/share/download"
    params = {
        "app_id": "250528",
        "channel": "dubox",
        "clienttype": "0",
        "web": "1",
        "shorturl": surl,
        "sign": sign,
        "timestamp": timestamp,
        "shareid": shareid,
        "uk": uk,
        "fid_list": f"[{fs_id}]",
    }

    # try GET then POST (some variants prefer POST)
    r = sess.get(url, params=params, timeout=30, headers={"referer": f"{base}/s/{surl}"})
    if r.status_code >= 400:
        r = sess.post(url, data=params, timeout=30, headers={"referer": f"{base}/s/{surl}"})

    r.raise_for_status()
    data = r.json()

    errno = data.get("errno", 0)
    if str(errno) != "0":
        raise RuntimeError(f"TeraBox download-api error: errno={errno}")

    dlink = data.get("dlink")
    if not dlink and isinstance(data.get("list"), list) and data["list"]:
        dlink = data["list"][0].get("dlink")

    if not dlink:
        raise RuntimeError("TeraBox: could not obtain dlink (cookies may be missing/expired)")
    return str(dlink)


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
    Supports:
    - /s/<surl> share links
    - sharing/videoPlay?surl=...&fsid=... (downloads that specific file)
    - folder listing best-effort
    """
    os.makedirs(out_dir, exist_ok=True)
    base, surl, fsid, dir_path, file_name = _parse_terabox_link(url)

    sess, _ = _tb_session()

    referer = f"{base}/s/{surl}"

    # 1) Try to extract meta from the exact page user sent (videoPlay often has meta)
    html = None
    try:
        html = _fetch_html(sess, url, referer=referer)
    except Exception:
        html = None

    # 2) Fallback to /s/<surl>
    if not html:
        html = _fetch_html(sess, f"{base}/s/{surl}", referer=base)

    sign, timestamp, shareid, uk = _extract_meta(html)

    # If fsid present (videoPlay link), download ONLY that file (fast + reliable)
    targets: List[TBItem] = []
    if fsid:
        targets = [TBItem(isdir=0, name=file_name or "file", path=dir_path or "", size=0, fs_id=fsid)]
    else:
        targets = _walk(sess, base, surl, dir_path)

    if not targets:
        raise RuntimeError("TeraBox: no files found")

    first_path = ""
    first_name = ""

    dl_headers = {
        "referer": referer,
        "user-agent": sess.headers.get("user-agent", ""),
        # Cookie header is already attached to session if TERABOX_COOKIES set.
    }

    for idx, it in enumerate(targets, start=1):
        if cancel_event and cancel_event.is_set():
            raise RuntimeError("Cancelled")

        if it.isdir == 1:
            continue

        if it.size and max_bytes and it.size > max_bytes:
            raise RuntimeError(f"TeraBox file too large: {it.size} bytes > limit")

        if not it.fs_id:
            raise RuntimeError("TeraBox: missing fs_id")

        dlink = it.dlink
        if not dlink:
            dlink = _get_dlink(sess, base, surl, it.fs_id, sign, timestamp, shareid, uk)

        p, n = download_direct(
            dlink,
            out_dir,
            on_progress_text=on_progress_text,
            interval_sec=interval_sec,
            cancel_event=cancel_event,
            max_bytes=max_bytes,
            rate_limit_bps=rate_limit_bps,
            headers=dl_headers,
            session=sess,
        )

        if idx == 1:
            first_path, first_name = p, n

    return first_path, first_name
