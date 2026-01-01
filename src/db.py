import datetime as dt
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase


class Database:
    def __init__(self, cfg):
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

    async def all_user_ids(self) -> list[int]:
        out: list[int] = []
        async for doc in self.users.find({}, {"user_id": 1}):
            uid = doc.get("user_id")
            if isinstance(uid, int):
                out.append(uid)
        return out

    async def is_premium(self, user_id: int) -> bool:
        doc = await self.premium.find_one({"user_id": user_id})
        if not doc:
            return False
        expires_at = doc.get("expires_at")
        if not expires_at:
            return False
        return expires_at > dt.datetime.utcnow()

    async def set_premium(self, user_id: int, days: int) -> dt.datetime:
        expires_at = dt.datetime.utcnow() + dt.timedelta(days=days)
        await self.premium.update_one(
            {"user_id": user_id},
            {"$set": {"user_id": user_id, "expires_at": expires_at}},
            upsert=True,
        )
        return expires_at

    async def remove_premium(self, user_id: int) -> None:
        await self.premium.delete_one({"user_id": user_id})

    # ---- Settings ----
    async def get_settings(self, user_id: int) -> dict[str, Any]:
        doc = await self.settings.find_one({"user_id": user_id})
        return doc or {"user_id": user_id}

    async def set_setting(self, user_id: int, key: str, value: Any) -> None:
        await self.settings.update_one(
            {"user_id": user_id},
            {"$set": {"user_id": user_id, key: value}},
            upsert=True,
        )

    async def reset_settings(self, user_id: int) -> None:
        await self.settings.delete_one({"user_id": user_id})

    # ---- Daily usage (counts per LINK/task) ----
    def _today_key(self) -> str:
        return dt.datetime.utcnow().strftime("%Y-%m-%d")

    async def get_daily_used(self, user_id: int) -> int:
        doc = await self.daily.find_one({"user_id": user_id, "date": self._today_key()})
        return int(doc.get("used", 0)) if doc else 0

    async def consume_daily_quota(self, user_id: int, want: int, limit: int) -> int:
        """
        Returns allowed amount; increments used by allowed.
        """
        want = max(0, int(want))
        if want == 0:
            return 0

        used = await self.get_daily_used(user_id)
        remaining = max(0, limit - used)
        allowed = min(want, remaining)

        if allowed > 0:
            await self.daily.update_one(
                {"user_id": user_id, "date": self._today_key()},
                {
                    "$setOnInsert": {"user_id": user_id, "date": self._today_key()},
                    "$inc": {"used": allowed},
                },
                upsert=True,
            )
        return allowed
