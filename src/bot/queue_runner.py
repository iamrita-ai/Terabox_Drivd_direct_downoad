from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import time
import subprocess
from collections import Counter
from pathlib import Path
from typing import Optional, Tuple, List

import requests
from pyrogram import Client

from src.downloaders.dispatch import download_any
from src.utils.files import rm_any, zip_paths
from src.utils.thumbs import make_thumbnail
from src.utils.progress import ProgressState, format_progress
from src.utils.human import human_bytes
from .task_manager import TASKS, RunningTask
from .handlers.common import try_pin
from .logs import send_log

log = logging.getLogger("queue_runner")

VIDEO_EXT = {"mp4", "mkv", "mov", "webm", "avi"}


def _ext(path: str) -> str:
    return Path(path).suffix.lower().lstrip(".")


def _is_video(path: str) -> bool:
    return _ext(path) in VIDEO_EXT


def _classify(path: str) -> str:
    ext = _ext(path)
    if ext in VIDEO_EXT:
        return "videos"
    if ext in {"jpg", "jpeg", "png", "webp"}:
        return "photos"
    if ext in {"mp3", "m4a", "aac", "ogg", "wav", "flac"}:
        return "audios"
    if ext in {"pdf"}:
        return "pdf"
    if ext in {"apk"}:
        return "apk"
    return "others"


def _remux_to_mp4(in_path: str, out_path: str) -> bool:
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", in_path, "-c", "copy", "-movflags", "+faststart", out_path],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return os.path.exists(out_path) and os.path.getsize(out_path) > 0
    except Exception:
        return False


async def _resolve_thumb_value_to_path(client: Client, value: str, out_path: str) -> Optional[str]:
    try:
        if value.startswith("http://") or value.startswith("https://"):
            r = requests.get(value, timeout=30)
            r.raise_for_status()
            Path(out_path).write_bytes(r.content)
            return out_path if os.path.exists(out_path) else None
        p = await client.download_media(value, file_name=out_path)
        return p if p and os.path.exists(p) else None
    except Exception:
        return None


async def ensure_runner(client: Client, chat_id: int, thread_id: Optional[int]) -> None:
    # stale runner auto-clean is in TaskManager.has_runner()
    if TASKS.has_runner(chat_id, thread_id):
        return

    cancel_event = asyncio.Event()

    async def _run():
        key = (chat_id, thread_id)
        q = TASKS.get_queue(chat_id, thread_id)
        try:
            while True:
                item = await q.get()
                try:
                    await _process_job(client, item, cancel_event)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    log.exception("Job failed: %r", e)
                    try:
                        await send_log(client, f"❌ JOB CRASHED (runner)\nKey: {key}\nErr: {e!r}")
                    except Exception:
                        pass
                finally:
                    q.task_done()

                if q.empty():
                    break
        finally:
            TASKS.runners.pop(key, None)

    task = asyncio.create_task(_run())
    TASKS.set_runner(chat_id, thread_id, RunningTask(task=task, cancel_event=cancel_event))


async def _process_job(client: Client, item: dict, cancel_event: asyncio.Event) -> None:
    chat_id = item["chat_id"]
    origin_msg_id = item.get("origin_msg_id")
    from_user_id = item.get("from_user_id")
    from_username = item.get("from_username")
    chat_type = item.get("chat_type")  # "private" / "group" / "supergroup"
    links: List[str] = item.get("links", [])

    total_tasks = len(links)
    if total_tasks == 0:
        return

    is_prem = await client.db.is_premium(from_user_id)  # type: ignore[attr-defined]
    max_bytes = (client.cfg.PREMIUM_MAX_SIZE_MB if is_prem else client.cfg.FREE_MAX_SIZE_MB) * 1024 * 1024  # type: ignore[attr-defined]
    rate_bps = None
    if not is_prem:
        rate_bps = float(client.cfg.FREE_MAX_RATE_MBPS) * 1024 * 1024  # type: ignore[attr-defined]

    settings = await client.db.get_settings(from_user_id)  # type: ignore[attr-defined]
    custom_title = (settings.get("title") or "").strip() or None
    user_thumb_file_id = settings.get("thumb_file_id")

    # IMPORTANT: redirect only if PRIVATE chat request
    deliver_chat_id = chat_id
    if chat_type == "private":
        tc = settings.get("target_chat_id")
        if isinstance(tc, int):
            deliver_chat_id = tc

    # Topics support without message_thread_id:
    # We reply to the original message; Telegram will keep it in same topic/thread.
    status = await client.send_message(
        chat_id=deliver_chat_id,
        text=f"Task started: 0/{total_tasks}",
        reply_to_message_id=origin_msg_id if deliver_chat_id == chat_id else None,
    )
    await try_pin(client, deliver_chat_id, status.id)

    work_dir = tempfile.mkdtemp(prefix="job_", dir="/tmp")
    counters = Counter()
    failed = 0
    failed_links: List[Tuple[str, str]] = []

    async def edit_status(text: str) -> None:
        try:
            await status.edit_text(text)
        except Exception:
            pass

    await send_log(
        client,
        f"🚀 JOB START\nUser: @{from_username} ({from_user_id})\n"
        f"Chat: {chat_id} ({chat_type})\nDeliver: {deliver_chat_id}\n"
        f"Premium: {is_prem}\nLinks({len(links)}):\n" + "\n".join(links),
    )

    cached_pdf_thumb: Optional[str] = None
    if client.cfg.PDF_THUMB:  # type: ignore[attr-defined]
        cached_pdf_thumb = await _resolve_thumb_value_to_path(
            client,
            client.cfg.PDF_THUMB,  # type: ignore[attr-defined]
            str(Path(work_dir) / "pdf_env_thumb.jpg"),
        )

    cached_user_thumb: Optional[str] = None
    if user_thumb_file_id:
        cached_user_thumb = await _resolve_thumb_value_to_path(
            client,
            user_thumb_file_id,
            str(Path(work_dir) / "user_thumb.jpg"),
        )

    for idx, url in enumerate(links, start=1):
        if cancel_event.is_set():
            await edit_status("✅ Cancelled.")
            await send_log(client, f"⛔ JOB CANCELLED\nUser: @{from_username} ({from_user_id})")
            break

        await edit_status(f"{idx}/{total_tasks} task running...\n\nURL:\n{url}")

        link_dir = str(Path(work_dir) / f"link_{idx}")
        os.makedirs(link_dir, exist_ok=True)

        last_text = {"v": ""}

        def on_progress_text(t: str) -> None:
            if t == last_text["v"]:
                return
            last_text["v"] = t
            try:
                asyncio.run_coroutine_threadsafe(edit_status(t), client.loop)  # type: ignore[attr-defined]
            except Exception:
                pass

        try:
            await asyncio.to_thread(
                download_any,
                url,
                link_dir,
                on_progress_text=on_progress_text,
                interval_sec=client.cfg.PROGRESS_EDIT_EVERY_SEC,  # type: ignore[attr-defined]
                cancel_event=cancel_event,
                max_bytes=max_bytes,
                rate_limit_bps=rate_bps,
            )
        except Exception as e:
            failed += 1
            failed_links.append((url, str(e)))
            await edit_status(f"❌ Failed task {idx}/{total_tasks}\n{url}\nReason: {e}")
            await send_log(client, f"❌ LINK FAILED\nUser: @{from_username} ({from_user_id})\nURL: {url}\nReason: {e}")
            rm_any(link_dir)
            continue

        files = [str(p) for p in Path(link_dir).rglob("*") if p.is_file()]
        if not files:
            failed += 1
            failed_links.append((url, "No file produced"))
            await edit_status(f"❌ Download produced no file: {url}")
            rm_any(link_dir)
            continue

        if len(files) == 1:
            send_paths = [files[0]]
        else:
            zip_name = f"{(custom_title or 'folder')}_{idx}.zip"
            zip_path = str(Path(link_dir) / zip_name)
            zip_paths(zip_path, files, base_dir=link_dir)
            send_paths = [zip_path]

        for sp in send_paths:
            if cancel_event.is_set():
                break

            size = os.path.getsize(sp) if os.path.exists(sp) else 0
            fname = Path(sp).name
            ext = _ext(sp)

            if ext == "pdf" and cached_pdf_thumb and os.path.exists(cached_pdf_thumb):
                thumb_path = cached_pdf_thumb
            elif cached_user_thumb and os.path.exists(cached_user_thumb):
                thumb_path = cached_user_thumb
            else:
                thumb_path = make_thumbnail(sp, link_dir)

            state = ProgressState(start_ts=time.time(), last_edit_ts=0.0)
            last_done = {"t": 0.0}

            def upload_progress(current: int, total: int):
                now = time.time()
                if now - last_done["t"] < client.cfg.PROGRESS_EDIT_EVERY_SEC:  # type: ignore[attr-defined]
                    return
                last_done["t"] = now
                txt = format_progress("Uploading", fname, current, total, state)
                client.loop.create_task(edit_status(txt))  # type: ignore[attr-defined]

            send_path_final = sp
            remux_tmp = None
            if _is_video(sp) and client.cfg.REMUX_TO_MP4 and ext != "mp4":  # type: ignore[attr-defined]
                remux_tmp = str(Path(link_dir) / (Path(sp).stem + ".mp4"))
                if _remux_to_mp4(sp, remux_tmp):
                    send_path_final = remux_tmp

            try:
                if _is_video(send_path_final):
                    await client.send_video(
                        chat_id=deliver_chat_id,
                        video=send_path_final,
                        supports_streaming=True,
                        thumb=thumb_path if thumb_path and os.path.exists(thumb_path) else None,
                        caption=f"✅ {Path(send_path_final).name}\nSize: {human_bytes(size)}",
                        reply_to_message_id=origin_msg_id if deliver_chat_id == chat_id else None,
                        progress=upload_progress,
                    )
                else:
                    await client.send_document(
                        chat_id=deliver_chat_id,
                        document=send_path_final,
                        thumb=thumb_path if thumb_path and os.path.exists(thumb_path) else None,
                        caption=f"✅ {Path(send_path_final).name}\nSize: {human_bytes(size)}",
                        reply_to_message_id=origin_msg_id if deliver_chat_id == chat_id else None,
                        progress=upload_progress,
                    )

                counters[_classify(send_path_final)] += 1
            except Exception as e:
                failed += 1
                failed_links.append((url, f"Upload error: {e}"))
                await edit_status(f"❌ Upload failed: {fname}\nReason: {e}")
                await send_log(client, f"❌ UPLOAD FAILED\nUser: @{from_username} ({from_user_id})\nFile: {fname}\nURL: {url}\nReason: {e}")

            if remux_tmp:
                rm_any(remux_tmp)
            if thumb_path and isinstance(thumb_path, str) and thumb_path.startswith(link_dir):
                rm_any(thumb_path)
            rm_any(sp)

        rm_any(link_dir)

    done_total = sum(counters.values())
    summary = (
        f"✅ Completed\n\n"
        f"Tasks: {done_total}/{total_tasks}\n"
        f"Videos: {counters.get('videos', 0)}\n"
        f"Photos: {counters.get('photos', 0)}\n"
        f"Audios: {counters.get('audios', 0)}\n"
        f"PDF: {counters.get('pdf', 0)}\n"
        f"APK: {counters.get('apk', 0)}\n"
        f"Others: {counters.get('others', 0)}\n"
        f"Failed: {failed}\n"
    )
    await edit_status(summary)

    fail_lines = "\n".join([f"- {u} => {r}" for u, r in failed_links[:25]])
    await send_log(
        client,
        "✅ JOB DONE\n"
        f"User: @{from_username} ({from_user_id})\n"
        f"Premium: {is_prem}\n"
        f"Total links: {total_tasks}\n"
        f"Sent: {done_total}\n"
        f"Failed: {failed}\n"
        f"Breakdown: {dict(counters)}\n"
        + (f"Failed details:\n{fail_lines}" if fail_lines else ""),
    )

    rm_any(work_dir)
