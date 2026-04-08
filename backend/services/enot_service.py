from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from urllib import error, parse, request

from fastapi import HTTPException, status

from config import settings


def ensure_enot_configured() -> None:
    if settings.has_enot_credentials:
        return

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="ENOT credentials are not configured.",
    )


def parse_provider_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def create_invoice(*, payment_id: str, amount_rub: int, device_id: str, plan_code: str, plan_title: str) -> dict:
    ensure_enot_configured()

    payload = {
        "amount": amount_rub,
        "order_id": payment_id,
        "currency": settings.enot_currency,
        "shop_id": settings.enot_shop_id,
        "hook_url": settings.enot_hook_url,
        "success_url": settings.enot_success_url,
        "fail_url": settings.enot_fail_url,
        "expire": settings.enot_expire_minutes,
        "comment": f"{settings.app_name}: {plan_title}",
        "custom_fields": json.dumps(
            {
                "paymentId": payment_id,
                "deviceId": device_id,
                "planId": plan_code,
            },
            ensure_ascii=False,
        ),
    }
    return _request_json("POST", "/invoice/create", payload=payload)


def get_invoice_info(*, order_id: str | None = None, invoice_id: str | None = None) -> dict:
    ensure_enot_configured()
    if not order_id and not invoice_id:
        raise ValueError("order_id or invoice_id is required")

    query = {"shop_id": settings.enot_shop_id}
    if order_id:
        query["order_id"] = order_id
    if invoice_id:
        query["invoice_id"] = invoice_id

    return _request_json("GET", "/invoice/info", query=query)


def verify_webhook_signature(payload: dict, signature: str | None) -> bool:
    if not settings.enot_webhook_secret:
        return True
    if not signature:
        return False

    message = json.dumps(
        payload,
        sort_keys=True,
        separators=(", ", ": "),
        ensure_ascii=False,
    ).encode("utf-8")
    digest = hmac.new(
        settings.enot_webhook_secret.encode("utf-8"),
        msg=message,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(signature.strip().lower(), digest.lower())


def normalize_provider_status(value: str | None) -> str:
    return (value or "").strip().lower()


def _request_json(method: str, path: str, *, payload: dict | None = None, query: dict | None = None) -> dict:
    url = f"{settings.enot_api_base.rstrip('/')}/{path.lstrip('/')}"
    if query:
        url = f"{url}?{parse.urlencode(query)}"

    headers = {
        "Accept": "application/json",
        "x-api-key": settings.enot_api_key,
    }
    data: bytes | None = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = request.Request(url, headers=headers, data=data, method=method.upper())
    try:
        with request.urlopen(req, timeout=20) as response:
            body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_extract_error_message(response_body) or f"ENOT returned HTTP {exc.code}.",
        ) from exc
    except error.URLError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ENOT request failed: {exc.reason}",
        ) from exc

    try:
        parsed = json.loads(body) if body else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ENOT returned invalid JSON.",
        ) from exc

    if parsed and parsed.get("status_check") is False:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=parsed.get("error") or parsed.get("message") or "ENOT request failed.",
        )

    return parsed


def _extract_error_message(raw_body: str) -> str | None:
    try:
        parsed = json.loads(raw_body)
    except json.JSONDecodeError:
        return None

    if isinstance(parsed, dict):
        return parsed.get("error") or parsed.get("message")
    return None
