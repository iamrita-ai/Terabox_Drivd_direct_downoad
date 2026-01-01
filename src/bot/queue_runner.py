from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Optional

from pyrogram import Client
from pyrogram.types import Message

from src.downloaders.dispatch import download_any
from src.utils.files import rm_any, zip_paths
from src.utils.thumbs import make_thumbnail
from src.utils.progress import ProgressState, format_progress
from src.utils.human import human_bytes
from .task_manager import TASKS, RunningTask
from .handlers.common import try_pin

log = logging.getLogger("queue_runner")


def _classify(path: str) -> str:
    ext = Path(path).suffix.lower().lstrip(".")
    if ext in {"mp4", "mkv", "mov", "webm", "avi"}:
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


async def ensure_runner(client: Client, chat_id: int, thread_id: Optional[int]) -> None:
    if TASKS.has_runner(chat_id, thread_id):
        return

    cancel_event = asyncio.Event()

    async def _run():
        q = TASKS.get_queue(chat_id, thread_id)
        while True:
            item = await q.get()
            try:
                await _process_job(client, item, cancel_event)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.exception("Job failed: %r", e)
            finally:
                q.task_done()

            if q.empty():
                break

        # runner done
        TASKS.runners.pop((chat_id, thread_id), None)

    task = asyncio.create_task(_run())
    TASKS.set_runner(chat_id, thread_id, RunningTask(task=task, cancel_event=cancel_event))


async def _process_job(client: Client, item: dict, cancel_event: asyncio.Event) -> None:
    """
    item:
      chat_id, thread_id, from_user_id, from_username, origin_msg_id, links[list[str]]
    """
    chat_id = item["chat_id"]
    thread_id = item.get("thread_id")
    origin_msg_id = item.get("origin_msg_id")
    links = item.get("links", [])

    total_tasks = len(links)
    if total_tasks == 0:
        return

    # status message
    status = await client.send_message(
        chat_id=chat_id,
        text=f"Task started: 0/{total_tasks}",
        message_thread_id=thread_id,
        reply_to_message_id=origin_msg_id,
    )
    await try_pin(client, chat_id, status.id)

    # Work dir
    work_dir = tempfile.mkdtemp(prefix="job_", dir="/tmp")
    counters = Counter()
    failed = 0

    async def edit_status(text: str) -> None:
        try:
            await status.edit_text(text)
        except Exception:
            pass

    for idx, url in enumerate(links, start=1):
        if cancel_event.is_set():
            await edit_status("✅ Cancelled.")
            break

        await edit_status(f"Running task: {idx}/{total_tasks}\n\nURL:\n{url}")

        # download folder for this link
        link_dir = str(Path(work_dir) / f"link_{idx}")
        os.makedirs(link_dir, exist_ok=True)

        # progress hook from sync downloader (thread) -> schedule edit
        last_text = {"v": ""}

        def on_progress_text(t: str) -> None:
            # reduce redundant edits
            if t == last_text["v"]:
                return
            last_text["v"] = t
            client.loop.create_task(edit_status(t))  # type: ignore[attr-defined]

        # Download in thread (sync downloader)
        try:
            max_bytes = None  # Part-3 me free/premium enforce
            file_path, filename = await asyncio.to_thread(
                download_any,
                url,
                link_dir,
                on_progress_text=on_progress_text,
                interval_sec=client.cfg.PROGRESS_EDIT_EVERY_SEC,  # type: ignore[attr-defined]
                cancel_event=cancel_event,
                max_bytes=max_bytes,
            )
        except Exception as e:
            failed += 1
            await edit_status(f"❌ Failed task {idx}/{total_tasks}\n{url}\nReason: {e}")
            continue

        # If multiple files present (future folder downloads), zip them.
        # Currently direct/gdrive returns single file; but this keeps logic ready.
        files = []
        for p in Path(link_dir).rglob("*"):
            if p.is_file():
                files.append(str(p))

        send_paths = []
        if len(files) == 0:
            failed += 1
            await edit_status(f"❌ Download produced no file: {url}")
            continue
        elif len(files) == 1:
            send_paths = [files[0]]
        else:
            zip_path = str(Path(link_dir) / "folder.zip")
            zip_paths(zip_path, files, base_dir=link_dir)
            send_paths = [zip_path]

        # Upload each file
        for sp in send_paths:
            if cancel_event.is_set():
                break

            size = os.path.getsize(sp) if os.path.exists(sp) else 0
            fname = Path(sp).name

            # Build thumbnail
            thumb = make_thumbnail(sp, link_dir)

            # Upload progress
            state = ProgressState(start_ts=time.time(), last_edit_ts=0.0)
            last_done = {"t": 0.0}

            def upload_progress(current: int, total: int):
                now = time.time()
                if now - last_done["t"] < client.cfg.PROGRESS_EDIT_EVERY_SEC:  # type: ignore[attr-defined]
                    return
                last_done["t"] = now
                txt = format_progress("Uploading", fname, current, total, state)
                client.loop.create_task(edit_status(txt))  # type: ignore[attr-defined]

            # Send as document (keeps extension exactly)
            try:
                await client.send_document(
                    chat_id=chat_id,
                    document=sp,
                    thumb=thumb if thumb and os.path.exists(thumb) else None,
                    caption=f"✅ {fname}\nSize: {human_bytes(size)}",
                    message_thread_id=thread_id,
                    reply_to_message_id=origin_msg_id,
                    progress=upload_progress,
                )
                counters[_classify(sp)] += 1
            except Exception as e:
                failed += 1
                await edit_status(f"❌ Upload failed: {fname}\nReason: {e}")

            # cleanup single file and thumb
            if thumb:
                rm_any(thumb)
            rm_any(sp)

        # cleanup link folder
        rm_any(link_dir)

    # Final summary
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

    # cleanup whole job dir
    rm_any(work_dir)
