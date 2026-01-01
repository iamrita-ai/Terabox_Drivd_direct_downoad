import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

log = logging.getLogger("task_manager")


@dataclass
class RunningTask:
    task: asyncio.Task
    cancel_event: asyncio.Event


class TaskManager:
    """
    Per chat+topic queue. Part-2 me actual download/upload worker attach hoga.
    """
    def __init__(self) -> None:
        self.queues: Dict[Tuple[int, Optional[int]], asyncio.Queue] = {}
        self.runners: Dict[Tuple[int, Optional[int]], RunningTask] = {}

    def get_key(self, chat_id: int, thread_id: Optional[int]) -> Tuple[int, Optional[int]]:
        return (chat_id, thread_id)

    def get_queue(self, chat_id: int, thread_id: Optional[int]) -> asyncio.Queue:
        key = self.get_key(chat_id, thread_id)
        if key not in self.queues:
            self.queues[key] = asyncio.Queue()
        return self.queues[key]

    async def enqueue(self, chat_id: int, thread_id: Optional[int], item: dict) -> None:
        q = self.get_queue(chat_id, thread_id)
        await q.put(item)

    def has_runner(self, chat_id: int, thread_id: Optional[int]) -> bool:
        return self.get_key(chat_id, thread_id) in self.runners

    def set_runner(self, chat_id: int, thread_id: Optional[int], running: RunningTask) -> None:
        self.runners[self.get_key(chat_id, thread_id)] = running

    def get_runner(self, chat_id: int, thread_id: Optional[int]) -> Optional[RunningTask]:
        return self.runners.get(self.get_key(chat_id, thread_id))

    async def cancel(self, chat_id: int, thread_id: Optional[int]) -> bool:
        key = self.get_key(chat_id, thread_id)
        running = self.runners.get(key)
        if not running:
            return False

        running.cancel_event.set()
        if not running.task.done():
            running.task.cancel()

        # Drain queue
        q = self.queues.get(key)
        if q:
            while not q.empty():
                try:
                    q.get_nowait()
                    q.task_done()
                except Exception:
                    break

        self.runners.pop(key, None)
        return True


TASKS = TaskManager()
