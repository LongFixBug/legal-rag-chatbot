from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from app.services.rate_limit import FixedWindowRateLimiter
from app.services.registry import AppServices, get_services


def _client_identifier(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _get_rate_limiter(request: Request) -> FixedWindowRateLimiter:
    limiter = getattr(request.app.state, "rate_limiter", None)
    if limiter is None:
        limiter = FixedWindowRateLimiter()
        request.app.state.rate_limiter = limiter
    return limiter


def _enforce_limit(request: Request, scope: str, limit: int) -> None:
    limiter = _get_rate_limiter(request)
    allowed, retry_after = limiter.allow(scope=scope, identifier=_client_identifier(request), limit=limit)
    if allowed:
        return
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Rate limit exceeded. Please retry later.",
        headers={"Retry-After": str(retry_after)},
    )


async def enforce_chat_rate_limit(
    request: Request,
    services: AppServices = Depends(get_services),
) -> None:
    if not services.settings.rate_limit_enabled:
        return
    _enforce_limit(request, "chat.query", services.settings.chat_rate_limit_per_minute)


async def enforce_document_mutation_rate_limit(
    request: Request,
    services: AppServices = Depends(get_services),
) -> None:
    if not services.settings.rate_limit_enabled:
        return
    _enforce_limit(request, "documents.mutation", services.settings.document_mutation_rate_limit_per_minute)
