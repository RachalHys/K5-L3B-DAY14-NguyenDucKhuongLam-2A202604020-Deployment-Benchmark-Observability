"""Theo dõi chi phí mock của agent theo ngày UTC trong Redis."""

from datetime import datetime, timezone

from fastapi import HTTPException

from .config import settings
from .redis_client import r

# Đơn giá giả lập theo USD trên 1.000 token.
PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006
BUDGET_RETENTION_SECONDS = 2 * 24 * 60 * 60


def _budget_key() -> str:
    return f"budget:{datetime.now(timezone.utc).date().isoformat()}"


async def check_budget() -> None:
    """Kiểm tra chi phí đã ghi nhận trước khi bắt đầu request mới."""
    spent = float(await r.get(_budget_key()) or 0)
    if spent >= settings.daily_budget_usd:
        raise HTTPException(status_code=402, detail="Daily budget exhausted")


async def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Cộng chi phí request đã hoàn thành và trả về số tiền vừa ghi nhận."""
    cost = (input_tokens * PRICE_INPUT_PER_1K + output_tokens * PRICE_OUTPUT_PER_1K) / 1000
    key = _budget_key()
    async with r.pipeline() as transaction:
        transaction.incrbyfloat(key, cost)
        transaction.expire(key, BUDGET_RETENTION_SECONDS)
        await transaction.execute()
    return cost
