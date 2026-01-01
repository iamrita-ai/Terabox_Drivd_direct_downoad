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


def _tb_session() -> requests.Session:
    """
    Force cookies via Cookie header (best for Render + multiple subdomains).
    """
    s = requests.Session()
    s.headers.update({
        "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120 Safari/537.36",
        "accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        "accept-language": "en-US,en;q=0.9",
    })

    ck = os.getenv("TERABOX_COOKIES", "").strip()
    if ck:
        # Single line: k=v; k2=v2
        s.headers["cookie"] = ck

    return s


def _parse_link(url: str) -> Tuple[str, str, Optional[int], Optional[str], Optional[str]]:
    """
    Returns: (base, surl, fsid, dir_path, file_name)

    Supports:
    - https://www.1024tera.com/sharing/videoPlay?surl=...&fsid=...
    - https://www.1024tera.com/s/<surl>
    - https://www.terabox.com/s/<surl>
    """
    u = url.strip()
    pu = urlparse(u)
    qs = parse_qs(pu.query)

    base = f"{pu.scheme or 'https'}://{pu.netloc}"

    surl = None
    if "surl" in qs and qs["surl"]:
        surl = qs["surl"][0]
    else:
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


def _detect_block(html: str, final_url: str) -> None:
    h = (html or "").lower()
    u = (final_url or "").lower()

    # Cloudflare / anti-bot (common on 1024tera)
    if (
        "cloudflare" in h
        or "just a moment" in h
        or "checking your browser" in h
        or "/cdn-cgi/" in h
        or "cf-browser-verification" in h
    ):
        raise RuntimeError(
            "TeraBox: Cloudflare/anti-bot page received. "
            "You must include Cloudflare cookies like cf_clearance (and sometimes __cf_bm) in TERABOX_COOKIES."
        )

    # Login/redirect
    if ("login" in u) or ("passport" in u) or ("signin" in u) or ("sign in" in h and "password" in h):
        raise RuntimeError(
            "TeraBox: redirected to login. TERABOX_COOKIES missing/expired or wrong domain cookies."
        )


def _fetch(sess: requests.Session, url: str, referer: str) -> Tuple[str, str]:
    r = sess.get(url, timeout=30, allow_redirects=True, headers={"referer": referer})
    r.raise_for_status()
    html = r.text or ""
    final_url = r.url or url
    _detect_block(html, final_url)
    return html, final_url


def _extract_meta_from_text(text: str) -> Optional[Tuple[str, str, str, str]]:
    """
    Try many patterns to get sign/timestamp/shareid/uk from HTML/JS text.
    """
    sign = None
    for pat in [
        r'"sign"\s*:\s*"([^"]+)"',
        r"sign\s*:\s*'([^']+)'",
        r"sign\s*=\s*\"([^\"]+)\"",
        r"sign\s*=\s*'([^']+)'",
    ]:
        m = re.search(pat, text)
        if m:
            sign = m.group(1)
            break

    ts = None
    for pat in [
        r'"timestamp"\s*:\s*(\d+)',
        r"timestamp\s*:\s*'(\d+)'",
        r"timestamp\s*=\s*(\d+)",
    ]:
        m = re.search(pat, text)
        if m:
            ts = m.group(1)
            break

    shareid = None
    for pat in [
        r'"shareid"\s*:\s*(\d+)',
        r'"share_id"\s*:\s*(\d+)',
        r'"shareId"\s*:\s*(\d+)',
        r"shareid\s*=\s*(\d+)",
    ]:
        m = re.search(pat, text)
        if m:
            shareid = m.group(1)
            break

    uk = None
    for pat in [
        r'"uk"\s*:\s*(\d+)',
        r'"share_uk"\s*:\s*(\d+)',
        r"uk\s*=\s*(\d+)",
    ]:
        m = re.search(pat, text)
        if m:
            uk = m.group(1)
            break

    if sign and ts and shareid and uk:
        return sign, ts, shareid, uk
    return None


def _deep_find(obj: Any, key: str) -> Optional[Any]:
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            r = _deep_find(v, key)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _deep_find(v, key)
            if r is not None:
                return r
    return None


def _share_list_json(sess: requests.Session, base: str, surl: str, referer: str, dir_path: str = "") -> Dict[str, Any]:
    url = f"{base}/share/list"
    params = {
        "app_id": "250528",
        "web": "1",
        "channel": "dubox",
        "clienttype": "0",
        "shorturl": surl,
        "root": "1" if not dir_path else "0",
        "dir": dir_path,
        "num": "1000",
        "page": "1",
        "order": "name",
        "desc": "0",
    }
    r = sess.get(url, params=params, timeout=30, headers={"referer": referer, "x-requested-with": "XMLHttpRequest"})
    r.raise_for_status()
    data = r.json()
    errno = data.get("errno", 0)
    if str(errno) != "0":
        raise RuntimeError(f"TeraBox list error: errno={errno}")
    return data


def _meta_from_list_and_tplconfig(sess: requests.Session, base: str, surl: str, referer: str) -> Optional[Tuple[str, str, str, str]]:
    """
    Strong fallback:
    1) share/list -> get shareid + uk (often available)
    2) share/tplconfig (or variants) -> get sign + timestamp
    """
    data = _share_list_json(sess, base, surl, referer, dir_path="")

    shareid = _deep_find(data, "shareid") or _deep_find(data, "share_id") or _deep_find(data, "shareId")
    uk = _deep_find(data, "uk") or _deep_find(data, "share_uk")

    # Sometimes list already includes sign/timestamp too:
    sign = _deep_find(data, "sign")
    ts = _deep_find(data, "timestamp")
    if sign and ts and shareid and uk:
        return str(sign), str(ts), str(shareid), str(uk)

    if not (shareid and uk):
        return None

    candidates = [
        (f"{base}/share/tplconfig", {"app_id": "250528", "shareid": shareid, "uk": uk, "fields": "sign,timestamp"}),
        (f"{base}/share/tplconfig", {"app_id": "250528", "shareid": shareid, "uk": uk}),
        (f"{base}/sharing/tplconfig", {"app_id": "250528", "shareid": shareid, "uk": uk}),
        (f"{base}/share/init", {"app_id": "250528", "shareid": shareid, "uk": uk}),
    ]

    for url, params in candidates:
        try:
            r = sess.get(url, params=params, timeout=30, headers={"referer": referer, "x-requested-with": "XMLHttpRequest"})
            if "application/json" not in (r.headers.get("content-type", "").lower()):
                continue
            j = r.json()
            errno = j.get("errno", 0)
            if str(errno) != "0":
                continue
            sign2 = _deep_find(j, "sign")
            ts2 = _deep_find(j, "timestamp")
            if sign2 and ts2:
                return str(sign2), str(ts2), str(shareid), str(uk)
        except Exception:
            continue

    return None


def _list_dir(sess: requests.Session, base: str, surl: str, dir_path: Optional[str]) -> List[TBItem]:
    data = _share_list_json(sess, base, surl, referer=f"{base}/s/{surl}", dir_path="" if not dir_path or dir_path == "/" else dir_path)
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

    r = sess.get(url, params=params, timeout=30, headers={"referer": f"{base}/s/{surl}", "x-requested-with": "XMLHttpRequest"})
    if r.status_code >= 400:
        r = sess.post(url, data=params, timeout=30, headers={"referer": f"{base}/s/{surl}", "x-requested-with": "XMLHttpRequest"})

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
    os.makedirs(out_dir, exist_ok=True)

    base, surl, fsid, dir_path, file_name = _parse_link(url)
    sess = _tb_session()
    referer = f"{base}/s/{surl}"

    # Fetch HTML (try exact url then /s/<surl>)
    html = ""
    try:
        html, _ = _fetch(sess, url, referer=referer)
    except Exception:
        html, _ = _fetch(sess, f"{base}/s/{surl}", referer=base)

    # 1) Meta from HTML
    meta = _extract_meta_from_text(html)

    # 2) Strong fallback: share/list + tplconfig
    if not meta:
        meta = _meta_from_list_and_tplconfig(sess, base, surl, referer=referer)

    if not meta:
        raise RuntimeError(
            "TeraBox: could not extract sign/timestamp/shareid/uk. "
            "If you are using 1024tera, most likely Cloudflare is blocking requests. "
            "Add cf_clearance (and sometimes __cf_bm) to TERABOX_COOKIES, then retry."
        )

    sign, timestamp, shareid, uk = meta

    # targets
    targets: List[TBItem]
    if fsid:
        targets = [TBItem(isdir=0, name=file_name or "file", path=dir_path or "", size=0, fs_id=fsid)]
    else:
        targets = _walk(sess, base, surl, dir_path)

    if not targets:
        raise RuntimeError("TeraBox: no files found")

    first_path = ""
    first_name = ""

    dl_headers = {"referer": referer, "user-agent": sess.headers.get("user-agent", "")}

    for idx, it in enumerate(targets, start=1):
        if cancel_event and cancel_event.is_set():
            raise RuntimeError("Cancelled")
        if it.isdir == 1:
            continue
        if not it.fs_id:
            raise RuntimeError("TeraBox: missing fs_id")
        if it.size and max_bytes and it.size > max_bytes:
            raise RuntimeError(f"TeraBox file too large: {it.size} bytes > limit")

        dlink = it.dlink or _get_dlink(sess, base, surl, it.fs_id, sign, timestamp, shareid, uk)

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
