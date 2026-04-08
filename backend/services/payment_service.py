from __future__ import annotations

import json
from datetime import timedelta
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import settings
from models import AccessStatus, Payment, PaymentStatus, TariffPlan, ensure_utc, utcnow
from schemas import PaymentOrderResponse, PaymentStatusResponse
from services.device_service import get_or_create_device
from services.enot_service import create_invoice, get_invoice_info, normalize_provider_status, parse_provider_datetime
from services.subscription_service import activate_subscription, refresh_subscription


FINAL_PROVIDER_FAILURE_STATUSES = {"fail", "failed", "expired", "refund", "canceled", "cancelled"}


def create_payment_order(db: Session, *, device_id: str, plan_id: str) -> Payment:
    device = get_or_create_device(db, device_id=device_id)
    subscription = refresh_subscription(db, device)
    if subscription.access_status == AccessStatus.BANNED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Устройство заблокировано.")

    plan = _get_plan(db, plan_id)
    payment_id = f"pay_{uuid4().hex}"
    provider_response = create_invoice(
        payment_id=payment_id,
        amount_rub=plan.amount_rub,
        device_id=device.device_id,
        plan_code=plan.code,
        plan_title=plan.title,
    )
    provider_data = provider_response.get("data") or {}
    expires_at = parse_provider_datetime(provider_data.get("expired")) or parse_provider_datetime(provider_data.get("expired_at"))
    if expires_at is None:
        expires_at = utcnow() + timedelta(minutes=settings.enot_expire_minutes)

    payment = Payment(
        payment_id=payment_id,
        user_device_id=device.id,
        tariff_plan_id=plan.id,
        amount_rub=plan.amount_rub,
        currency=settings.enot_currency,
        status=PaymentStatus.PENDING,
        provider_status="created",
        enot_invoice_id=_safe_str(provider_data.get("id")),
        enot_payment_url=provider_data.get("url"),
        raw_create_response_json=json.dumps(provider_response, ensure_ascii=False),
        expires_at=expires_at,
    )
    db.add(payment)
    db.flush()
    return payment


def get_payment(db: Session, payment_id: str) -> Payment:
    payment = db.scalar(select(Payment).where(Payment.payment_id == payment_id))
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Платеж не найден.")
    return payment


def refresh_payment_status(db: Session, payment: Payment) -> Payment:
    payment.created_at = ensure_utc(payment.created_at) or payment.created_at
    payment.expires_at = ensure_utc(payment.expires_at)
    payment.paid_at = ensure_utc(payment.paid_at)

    if payment.status == PaymentStatus.PAID:
        refresh_subscription(db, payment.user_device)
        return payment
    if payment.status == PaymentStatus.FAILED:
        refresh_subscription(db, payment.user_device)
        return payment

    if payment.expires_at and payment.expires_at <= utcnow() and payment.status == PaymentStatus.PENDING:
        payment.status = PaymentStatus.FAILED
        payment.provider_status = payment.provider_status or "expired"
        payment.failure_reason = "Срок действия счета истек до подтверждения оплаты."
        db.flush()
        return payment

    if settings.has_enot_credentials:
        provider_response = get_invoice_info(order_id=payment.payment_id, invoice_id=payment.enot_invoice_id)
        sync_payment_from_provider(db, payment, provider_response, persist_to_webhook_log=False)

    refresh_subscription(db, payment.user_device)
    db.flush()
    return payment


def sync_payment_from_provider(db: Session, payment: Payment, provider_response: dict, *, persist_to_webhook_log: bool) -> Payment:
    data = provider_response.get("data") if isinstance(provider_response.get("data"), dict) else provider_response
    provider_status = normalize_provider_status(data.get("status") or provider_response.get("status"))
    if not provider_status and payment.provider_status:
        provider_status = normalize_provider_status(payment.provider_status)

    if persist_to_webhook_log:
        payment.raw_webhook_json = json.dumps(provider_response, ensure_ascii=False)

    invoice_id = _safe_str(data.get("invoice_id")) or _safe_str(data.get("id"))
    if invoice_id:
        payment.enot_invoice_id = invoice_id
    payment.enot_payment_url = data.get("url") or payment.enot_payment_url
    payment.provider_status = provider_status or payment.provider_status
    payment.expires_at = (
        parse_provider_datetime(data.get("expired_at"))
        or parse_provider_datetime(data.get("expired"))
        or ensure_utc(payment.expires_at)
    )

    if provider_status == "success":
        payment.status = PaymentStatus.PAID
        payment.paid_at = parse_provider_datetime(data.get("paid_at")) or parse_provider_datetime(data.get("pay_time")) or utcnow()
        payment.failure_reason = None
        activate_subscription(db, payment)
    elif provider_status in FINAL_PROVIDER_FAILURE_STATUSES:
        payment.status = PaymentStatus.FAILED
        payment.failure_reason = _build_failure_reason(provider_status)
    elif payment.status != PaymentStatus.FAILED:
        payment.status = PaymentStatus.PENDING

    db.flush()
    return payment


def build_payment_order_response(payment: Payment) -> PaymentOrderResponse:
    created_at = ensure_utc(payment.created_at) or utcnow()
    expires_at = ensure_utc(payment.expires_at) or (created_at + timedelta(minutes=settings.enot_expire_minutes))
    return PaymentOrderResponse(
        paymentId=payment.payment_id,
        deviceId=payment.user_device.device_id,
        planId=payment.tariff_plan.code,
        amountRub=payment.amount_rub,
        createdAt=created_at,
        expiresAt=expires_at,
        paymentUrl=payment.enot_payment_url,
        providerInvoiceId=payment.enot_invoice_id,
        qrCodeUrl=None,
        qrPayload=None,
    )


def build_payment_status_response(db: Session, payment: Payment) -> PaymentStatusResponse:
    subscription = refresh_subscription(db, payment.user_device)
    state, title, detail = _resolve_payment_state(payment)
    return PaymentStatusResponse(
        paymentId=payment.payment_id,
        state=state,
        checkedAt=utcnow(),
        title=title,
        detail=detail,
        activatedUntil=ensure_utc(subscription.ends_at) if subscription.access_status == AccessStatus.ACTIVE else None,
    )


def _get_plan(db: Session, plan_id: str) -> TariffPlan:
    plan = db.scalar(select(TariffPlan).where(TariffPlan.code == plan_id))
    if plan is None and plan_id.isdigit():
        plan = db.get(TariffPlan, int(plan_id))
    if plan is None or not plan.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тариф не найден.")
    return plan


def _build_failure_reason(provider_status: str) -> str:
    if provider_status == "expired":
        return "Срок действия счета истек."
    if provider_status in {"canceled", "cancelled"}:
        return "Платеж был отменен."
    if provider_status == "refund":
        return "Платеж был возвращен."
    return "Платеж не был подтвержден."


def _resolve_payment_state(payment: Payment) -> tuple[str, str, str]:
    if payment.status == PaymentStatus.PAID:
        return (
            "succeeded",
            "Подписка активирована",
            "ENOT подтвердил оплату, доступ к VPN уже открыт на этом устройстве.",
        )

    if payment.status == PaymentStatus.FAILED:
        provider_status = normalize_provider_status(payment.provider_status)
        if provider_status in {"expired", "canceled", "cancelled"}:
            return (
                "cancelled",
                "Платеж отменен",
                payment.failure_reason or "Счет больше не активен.",
            )
        return (
            "failed",
            "Оплата не прошла",
            payment.failure_reason or "ENOT не подтвердил этот платеж.",
        )

    return (
        "pending",
        "Ожидаем оплату",
        "Завершите оплату на странице ENOT, после этого статус обновится автоматически.",
    )


def _safe_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
