from __future__ import annotations

import logging
import time
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass

from fastapi import Request, Response

logger = logging.getLogger("rag_api.requests")


@dataclass
class PathMetrics:
    count: int = 0
    total_latency_ms: float = 0.0
    max_latency_ms: float = 0.0

    def record(self, latency_ms: float) -> None:
        self.count += 1
        self.total_latency_ms += latency_ms
        self.max_latency_ms = max(self.max_latency_ms, latency_ms)

    def to_dict(self) -> dict[str, float | int]:
        avg_latency_ms = self.total_latency_ms / self.count if self.count else 0.0
        return {
            "count": self.count,
            "avg_latency_ms": round(avg_latency_ms, 2),
            "max_latency_ms": round(self.max_latency_ms, 2),
        }


class InMemoryMetrics:
    def __init__(self) -> None:
        self.total_requests = 0
        self.status_codes: Counter[str] = Counter()
        self.paths: defaultdict[str, PathMetrics] = defaultdict(PathMetrics)

    def record(self, *, path: str, status_code: int, latency_ms: float) -> None:
        self.total_requests += 1
        self.status_codes[str(status_code)] += 1
        self.paths[path].record(latency_ms)

    def snapshot(self) -> dict[str, object]:
        return {
            "total_requests": self.total_requests,
            "status_codes": dict(self.status_codes),
            "paths": {path: metrics.to_dict() for path, metrics in sorted(self.paths.items())},
        }


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def request_id_from(request: Request) -> str:
    return request.headers.get("X-Request-ID") or str(uuid.uuid4())


def get_metrics(request: Request) -> InMemoryMetrics:
    metrics = getattr(request.app.state, "metrics", None)
    if metrics is None:
        metrics = InMemoryMetrics()
        request.app.state.metrics = metrics
    return metrics


async def observability_middleware(request: Request, call_next) -> Response:
    request_id = request_id_from(request)
    start = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        latency_ms = (time.perf_counter() - start) * 1000
        metrics = get_metrics(request)
        metrics.record(path=request.url.path, status_code=status_code, latency_ms=latency_ms)
        logger.info(
            "request_id=%s method=%s path=%s status_code=%s latency_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            status_code,
            latency_ms,
        )
        if "response" in locals():
            response.headers["X-Request-ID"] = request_id
