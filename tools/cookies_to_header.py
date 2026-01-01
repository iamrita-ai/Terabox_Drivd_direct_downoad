#!/usr/bin/env python3
"""
Convert Netscape-style cookie export lines to a Cookie header string.

Input format (per line):
domain  include_subdomains  path  secure  expiry  name  value

Example line:
.1024tera.com TRUE / TRUE 1798807978 ndus YvWTkB8...

Usage:
  python tools/cookies_to_header.py cookies.txt --domain 1024tera.com
  python tools/cookies_to_header.py cookies.txt --domain terabox.com
  python tools/cookies_to_header.py cookies.txt --domain 1024tera.com --only ndus ndut_fmv ndut_fmt csrfToken
"""

from __future__ import annotations

import argparse
import time
from typing import Dict, List, Optional, Tuple


def parse_line(line: str) -> Optional[Tuple[str, str]]:
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    # Netscape cookie export is space-separated; last 2 tokens are name/value
    parts = line.split()
    if len(parts) < 7:
        return None

    domain = parts[0].lstrip(".")
    name = parts[5]
    value = parts[6]

    # expiry filter (optional)
    try:
        expiry = int(parts[4])
    except Exception:
        expiry = 0

    if expiry and expiry < int(time.time()):
        return None

    return (domain, f"{name}={value}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", help="cookies export text file")
    ap.add_argument("--domain", required=True, help="filter domain (e.g. 1024tera.com)")
    ap.add_argument("--only", nargs="*", default=None, help="only include these cookie names")
    args = ap.parse_args()

    want_domain = args.domain.lower().lstrip(".")
    only = set([x.strip() for x in args.only]) if args.only else None

    seen: Dict[str, str] = {}

    with open(args.file, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            parsed = parse_line(raw)
            if not parsed:
                continue
            domain, kv = parsed
            domain = domain.lower().lstrip(".")

            # include subdomains
            if not (domain == want_domain or domain.endswith("." + want_domain)):
                continue

            name = kv.split("=", 1)[0]
            if only is not None and name not in only:
                continue

            seen[name] = kv

    if not seen:
        raise SystemExit("No cookies matched. Check --domain or input file.")

    # stable order
    out = "; ".join(seen[k] for k in sorted(seen.keys()))
    print(out)


if __name__ == "__main__":
    main()
