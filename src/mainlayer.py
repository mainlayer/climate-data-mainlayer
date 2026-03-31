"""
Mainlayer payment middleware for FastAPI.

Validates API keys against the Mainlayer platform and enforces per-endpoint
pricing. Mainlayer is the payment rail for AI agents — think Stripe, but for
machine-to-machine commerce.

Base URL: https://api.mainlayer.xyz
Auth:     Authorization: Bearer <api_key>
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

MAINLAYER_API_URL = os.getenv("MAINLAYER_API_URL", "https://api.mainlayer.xyz")
MAINLAYER_SERVICE_KEY = os.getenv("MAINLAYER_SERVICE_KEY", "")

# Cache validated keys briefly to reduce latency on repeated calls.
_auth_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_TTL_SECONDS = 30

_bearer = HTTPBearer(auto_error=False)


async def _validate_key(api_key: str) -> dict[str, Any]:
    """
    Call the Mainlayer auth endpoint to verify an agent API key.

    Returns the decoded token payload (agent_id, balance, etc.) on success.
    Raises HTTPException on failure.
    """
    now = time.monotonic()
    cached = _auth_cache.get(api_key)
    if cached and (now - cached[0]) < _CACHE_TTL_SECONDS:
        return cached[1]

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{MAINLAYER_API_URL}/v1/auth/verify",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "X-Service-Key": MAINLAYER_SERVICE_KEY,
                },
            )
    except httpx.RequestError as exc:
        # If Mainlayer is unreachable fall through to dev-mode below.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "MAINLAYER_UNREACHABLE", "message": str(exc)},
        )

    if resp.status_code == 401:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_API_KEY", "message": "Invalid or expired API key."},
        )
    if resp.status_code == 402:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "code": "INSUFFICIENT_BALANCE",
                "message": "Insufficient balance. Please top up your Mainlayer account.",
            },
        )
    if not resp.is_success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "MAINLAYER_ERROR", "message": "Unexpected response from Mainlayer."},
        )

    payload: dict[str, Any] = resp.json()
    _auth_cache[api_key] = (now, payload)
    return payload


async def _charge(api_key: str, endpoint: str, amount_usd: float) -> None:
    """
    Deduct `amount_usd` from the agent's balance via the Mainlayer charge API.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{MAINLAYER_API_URL}/v1/charges",
                json={"endpoint": endpoint, "amount_usd": amount_usd},
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "X-Service-Key": MAINLAYER_SERVICE_KEY,
                },
            )
    except httpx.RequestError:
        # Best-effort charge — do not block the response if the charge call fails.
        pass


# ---------------------------------------------------------------------------
# Public dependency
# ---------------------------------------------------------------------------


class MainlayerAuth:
    """
    FastAPI dependency that enforces Mainlayer auth and per-call pricing.

    Usage::

        @router.get("/weather/current")
        async def current(auth: MainlayerAuth = Depends(MainlayerAuth(price=0.001))):
            ...
    """

    def __init__(self, price: float, endpoint: str = "") -> None:
        self.price = price
        self.endpoint = endpoint

    async def __call__(self, request: Request) -> dict[str, Any]:
        dev_mode = os.getenv("MAINLAYER_DEV_MODE", "false").lower() == "true"

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            if dev_mode:
                return {"agent_id": "dev", "balance_usd": 9999.0}
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "MISSING_AUTH",
                    "message": "Authorization header required. Use: Authorization: Bearer <api_key>",
                },
            )

        api_key = auth_header.removeprefix("Bearer ").strip()

        if dev_mode:
            return {"agent_id": "dev", "balance_usd": 9999.0, "api_key": api_key}

        payload = await _validate_key(api_key)

        endpoint_name = self.endpoint or str(request.url.path)
        await _charge(api_key, endpoint_name, self.price)

        return payload
