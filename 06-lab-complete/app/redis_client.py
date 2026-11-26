"""Redis client dùng chung trong mỗi worker, kết nối khi cần."""

from redis.asyncio import Redis
from redis.exceptions import RedisError

from .config import settings

r = Redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=1,
    socket_timeout=1,
)


async def redis_healthy() -> bool:
    try:
        return bool(await r.ping())
    except RedisError:
        return False
