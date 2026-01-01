from __future__ import annotations

import os
import shutil
import zipfile
from pathlib import Path
from typing import Iterable


def safe_mkdir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def rm_any(path: str) -> None:
    try:
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        else:
            os.remove(path)
    except Exception:
        pass


def zip_paths(out_zip: str, paths: Iterable[str], base_dir: str | None = None) -> str:
    """
    Zip given files/dirs into out_zip.
    """
    out = Path(out_zip)
    out.parent.mkdir(parents=True, exist_ok=True)

    base = Path(base_dir) if base_dir else None

    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in paths:
            pp = Path(p)
            if not pp.exists():
                continue

            if pp.is_dir():
                for root, _, files in os.walk(pp):
                    for f in files:
                        fp = Path(root) / f
                        arc = fp.relative_to(base) if base and fp.is_relative_to(base) else fp.name
                        z.write(fp, arcname=str(arc))
            else:
                arc = pp.relative_to(base) if base and pp.is_relative_to(base) else pp.name
                z.write(pp, arcname=str(arc))

    return str(out)
