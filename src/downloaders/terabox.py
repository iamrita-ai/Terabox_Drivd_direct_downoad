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

    # Optional cookies from env
    ck = os.getenv("TERABOX_COOKIES", "").strip()
    if ck:
        # naive cookie parse: "a=b; c=d"
        for part in ck.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            k, v = part.split("=", 1)
            s.cookies.set(k.strip(), v.strip())

    return s


def _fetch_share_page(sess: requests.Session, surl: str) -> str:
    # share page
    page_url = f"https://www.terabox.com/s/{surl}"
    r = sess.get(page_url, timeout=30, headers={"referer": "https://www.terabox.com/"})
    r.raise_for_status()
    return r.text


def _extract_meta(html: str) -> Tuple[str, str, str, str]:
    """
    Extract sign, timestamp, shareid, uk from share page html.
    Multiple regex fallbacks.
    """
    # sign
    sign = None
    for pat in [r'"sign"\s*:\s*"([^"]+)"', r"sign\s*:\s*'([^']+)'", r"sign\s*=\s*\"([^\"]+)\""]:
        m = re.search(pat, html)
        if m:
            sign = m.group(1)
            break

    ts = None
    for pat in [r'"timestamp"\s*:\s*(\d+)', r"timestamp\s*:\s*'(\d+)'", r"timestamp\s*=\s*(\d+)"]:
        m = re.search(pat, html)
        if m:
            ts = m.group(1)
            break

    shareid = None
    for pat in [r'"shareid"\s*:\s*(\d+)', r'"share_id"\s*:\s*(\d+)', r"shareid\s*=\s*(\d+)"]:
        m = re.search(pat, html)
        if m:
            shareid = m.group(1)
            break

    uk = None
    for pat in [r'"uk"\s*:\s*(\d+)', r"uk\s*=\s*(\d+)"]:
        m = re.search(pat, html)
        if m:
            uk = m.group(1)
            break

    if not (sign and ts and shareid and uk):
        raise RuntimeError("TeraBox: could not extract sign/timestamp/shareid/uk (share may require login)")

    return sign, ts, shareid, uk


def _list_dir(sess: requests.Session, surl: str, dir_path: str = "/") -> List[TBItem]:
    url = "https://www.terabox.com/share/list"
    params = {
        "app_id": "250528",
        "web": "1",
        "channel": "dubox",
        "clienttype": "0",
        "shorturl": surl,
        "root": "1",
        "dir": "" if dir_path == "/" else dir_path,
        "num": "1000",
        "page": "1",
        "order": "name",
        "desc": "0",
    }
    r = sess.get(url, params=params, timeout=30, headers={"referer": f"https://www.terabox.com/s/{surl}"})
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


def _walk(sess: requests.Session, surl: str, dir_path: str = "/") -> List[TBItem]:
    items = _list_dir(sess, surl, dir_path=dir_path)
    files: List[TBItem] = []
    for it in items:
        if it.isdir == 1 and it.path:
            files.extend(_walk(sess, surl, dir_path=it.path))
        else:
            files.append(it)
    return files


def _get_dlink(sess: requests.Session, surl: str, fs_id: int, sign: str, timestamp: str, shareid: str, uk: str) -> str:
    """
    Calls share/download to get dlink.
    """
    url = "https://www.terabox.com/share/download"
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
    r = sess.get(url, params=params, timeout=30, headers={"referer": f"https://www.terabox.com/s/{surl}"})
    r.raise_for_status()
    data = r.json()
    errno = data.get("errno", 0)
    if str(errno) != "0":
        raise RuntimeError(f"TeraBox download-api error: errno={errno}")

    dlink = data.get("dlink")
    if not dlink and isinstance(data.get("list"), list) and data["list"]:
        dlink = data["list"][0].get("dlink")

    if not dlink:
        raise RuntimeError("TeraBox: could not obtain dlink (share may require login/cookies)")
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
    Best-effort public TeraBox share download (no Telegram session needed).
    Works for many shares; some may still require login/cookies.
    Downloads all files in share (folder supported) into out_dir.
    """
    os.makedirs(out_dir, exist_ok=True)
    surl = _extract_surl(url)
    sess = _tb_session()

    html = _fetch_share_page(sess, surl)
    sign, timestamp, shareid, uk = _extract_meta(html)

    items = _walk(sess, surl, dir_path="/")
    if not items:
        raise RuntimeError("TeraBox: no files found")

    first_path = ""
    first_name = ""

    # headers that often help TeraBox dlinks
    dl_headers = {
        "referer": f"https://www.terabox.com/s/{surl}",
        "user-agent": sess.headers.get("user-agent", ""),
    }

    for idx, it in enumerate(items, start=1):
        if cancel_event and cancel_event.is_set():
            raise RuntimeError("Cancelled")

        if it.isdir == 1:
            continue

        if it.size and max_bytes and it.size > max_bytes:
            raise RuntimeError(f"TeraBox file too large: {it.size} bytes > limit")

        dlink = it.dlink
        if not dlink:
            if not it.fs_id:
                raise RuntimeError("TeraBox: missing fs_id for file")
            dlink = _get_dlink(sess, surl, it.fs_id, sign, timestamp, shareid, uk)

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
