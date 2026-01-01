import datetime as dt
import logging
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from .config import Config

log = logging.getLogger("db")


class Database:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.client = AsyncIOMotorClient(cfg.MONGO_URI)
        self.db: AsyncIOMotorDatabase = self.client[cfg.DB_NAME]

        self.users = self.db["users"]
        self.premium = self.db["premium"]
        self.settings = self.db["settings"]
        self.daily = self.db["daily_usage"]

    async def ensure_indexes(self) -> None:
        await self.users.create_index("user_id", unique=True)
        await self.premium.create_index("user_id", unique=True)
        await self.premium.create_index("expires_at")
        await self.settings.create_index("user_id", unique=True)
        await self.daily.create_index([("user_id", 1), ("date", 1)], unique=True)

    async def upsert_user(self, user_id: int, username: Optional[str]) -> None:
        await self.users.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "user_id": user_id,
                    "username": username,
                    "updated_at": dt.datetime.utcnow(),
                },
                "$setOnInsert": {"created_at": dt.datetime.utcnow()},
            },
            upsert=True,
        )

    async def is_premium(self, user_id: int) -> bool:
        doc = await self.premium.find_one({"user_id": user_id})
        if not doc:
            return False
        expires_at = doc.get("expires_at")
        if not expires_at:
            return False
        return expires_at > dt.datetime.utcnow()

    async def set_premium(self, user_id: int, days: int) -> None:
        expires_at = dt.datetime.utcnow() + dt.timedelta(days=days)
        await self.premium.update_one(
            {"user_id": user_id},
            {"$set": {"user_id": user_id, "expires_at": expires_at}},
            upsert=True,
        )

    async def remove_premium(self, user_id: int) -> None:
        await self.premium.delete_one({"user_id": user_id})

    async def get_settings(self, user_id: int) -> dict[str, Any]:
        doc = await self.settings.find_one({"user_id": user_id})
        return doc or {"user_id": user_id}

    async def reset_settings(self, user_id: int) -> None:
        await self.settings.delete_one({"user_id": user_id})
