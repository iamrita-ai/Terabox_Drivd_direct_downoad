from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def thumb_for_video(in_path: str, out_path: str) -> Optional[str]:
    # grab 1 frame at 1s
    _run([
        "ffmpeg", "-y",
        "-ss", "00:00:01",
        "-i", in_path,
        "-vframes", "1",
        "-vf", "scale=320:-1",
        out_path
    ])
    return out_path if os.path.exists(out_path) else None


def thumb_for_audio(in_path: str, out_path: str) -> Optional[str]:
    # simple waveform-ish image
    _run([
        "ffmpeg", "-y",
        "-i", in_path,
        "-filter_complex", "showwavespic=s=640x360",
        "-frames:v", "1",
        out_path
    ])
    return out_path if os.path.exists(out_path) else None


def thumb_for_pdf(in_path: str, out_path: str) -> Optional[str]:
    try:
        doc = fitz.open(in_path)
        if doc.page_count < 1:
            return None
        page = doc.load_page(0)
        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        pix.save(out_path)
        doc.close()
        return out_path if os.path.exists(out_path) else None
    except Exception:
        return None


def thumb_for_image(in_path: str, out_path: str) -> Optional[str]:
    try:
        img = Image.open(in_path)
        img.thumbnail((640, 640))
        img.convert("RGB").save(out_path, "JPEG", quality=85)
        return out_path if os.path.exists(out_path) else None
    except Exception:
        return None


def thumb_generic(filename: str, out_path: str) -> Optional[str]:
    try:
        img = Image.new("RGB", (640, 360), color=(20, 20, 20))
        d = ImageDraw.Draw(img)

        text = Path(filename).name
        # basic font fallback
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 28)
        except Exception:
            font = ImageFont.load_default()

        d.text((20, 140), text[:60], fill=(255, 255, 255), font=font)
        img.save(out_path, "JPEG", quality=85)
        return out_path
    except Exception:
        return None


def make_thumbnail(in_path: str, work_dir: str) -> Optional[str]:
    p = Path(in_path)
    ext = p.suffix.lower().strip(".")
    out = str(Path(work_dir) / "thumb.jpg")

    if ext in {"mp4", "mkv", "mov", "webm", "avi"}:
        return thumb_for_video(in_path, out)
    if ext in {"mp3", "m4a", "aac", "ogg", "wav", "flac"}:
        return thumb_for_audio(in_path, out)
    if ext in {"pdf"}:
        return thumb_for_pdf(in_path, out)
    if ext in {"jpg", "jpeg", "png", "webp"}:
        return thumb_for_image(in_path, out)

    return thumb_generic(p.name, out)
