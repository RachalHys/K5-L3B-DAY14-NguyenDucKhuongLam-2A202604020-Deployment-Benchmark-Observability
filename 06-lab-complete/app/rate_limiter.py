"""Giới hạn request trong cửa sổ trượt 60 giây theo API key."""

from hashlib import sha256
from uuid import uuid4

from fastapi import HTTPException

from .config import settings
from .redis_client import r

WINDOW_MS = 60_000

# Dùng đồng hồ Redis và thực hiện cả bước kiểm tra lẫn ghi trong một thao tác.
SLIDING_WINDOW = """
local key = KEYS[1]
local window_ms = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local now = redis.call('TIME')
local now_ms = tonumber(now[1]) * 1000 + math.floor(tonumber(now[2]) / 1000)

redis.call('ZREMRANGEBYSCORE', key, '-inf', now_ms - window_ms)
if redis.call('ZCARD', key) >= limit then
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    return math.ceil((tonumber(oldest[2]) + window_ms - now_ms) / 1000)
end

redis.call('ZADD', key, now_ms, ARGV[3])
redis.call('PEXPIRE', key, window_ms)
return 0
"""


async def check_rate_limit(key: str) -> None:
    key_hash = sha256(key.encode()).hexdigest()
    retry_after = await r.eval(
        SLIDING_WINDOW,
        1,
        f"rate_limit:{key_hash}",
        WINDOW_MS,
        settings.rate_limit_per_minute,
        uuid4().hex,
    )
    if retry_after:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )
