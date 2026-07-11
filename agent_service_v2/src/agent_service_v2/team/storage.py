from __future__ import annotations

import os

from agentscope.app.storage import RedisStorage


def build_team_storage() -> RedisStorage:
    return RedisStorage(
        host=os.getenv("AGENTSCOPE_REDIS_HOST", "localhost"),
        port=int(os.getenv("AGENTSCOPE_REDIS_PORT", "6379")),
        db=int(os.getenv("AGENTSCOPE_REDIS_DB", "0")),
        password=os.getenv("AGENTSCOPE_REDIS_PASSWORD") or None,
        key_ttl=86400,
    )
