"""Production AI Agent demonstrator for Day 14 Part 6."""

import json
import logging
from asyncio import to_thread
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from time import perf_counter

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from redis.exceptions import RedisError

from utils.mock_llm import ask as llm_ask

from .auth import verify_api_key
from .config import settings
from .cost_guard import check_budget, record_cost
from .rate_limiter import check_rate_limit
from .redis_client import r, redis_healthy


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "lvl": record.levelname,
            "event": record.getMessage(),
            **getattr(record, "fields", {}),
        })


logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("startup", extra={"fields": {"environment": settings.environment, "port": settings.port}})
    try:
        yield
    finally:
        await r.aclose()
        logger.info("shutdown")


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


@app.middleware("http")
async def log_request(request: Request, call_next):
    started = perf_counter()
    response = await call_next(request)
    logger.info("request", extra={"fields": {
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "ms": round((perf_counter() - started) * 1000, 2),
    }})
    return response


@app.exception_handler(RedisError)
async def redis_unavailable(_request: Request, _error: RedisError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": "Redis unavailable"})


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)

    @field_validator("question")
    @classmethod
    def question_is_not_blank(cls, question: str) -> str:
        if not question.strip():
            raise ValueError("question must not be blank")
        return question


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    if not await redis_healthy():
        raise HTTPException(status_code=503, detail="Redis unavailable")
    return {"ready": True}


@app.post("/ask")
async def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    await check_rate_limit(api_key)
    await check_budget()
    answer = await to_thread(llm_ask, body.question)
    # Giá trị giả lập: ước tính hai token cho mỗi từ như bài mẫu Part 4.
    await record_cost(len(body.question.split()) * 2, len(answer.split()) * 2)
    return {"question": body.question, "answer": answer}
