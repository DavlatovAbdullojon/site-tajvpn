from __future__ import annotations

import json
from datetime import timedelta
from urllib.parse import quote
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import AccessStatus, Payment, PaymentStatus, Subscription, TariffPlan, ensure_utc, utcnow
from schemas import PaymentOrderResponse, PaymentStatusResponse
from services.device_service import get_or_create_device
from services.subscription_service import refresh_subscription


TELEGRAM_ADMIN_USERNAME = "tajvpn_admin"


def create_payment_order(db: Session, *, device_id: str, plan_id: str) -> Payment:
    device = get_or_create_device(db, device_id=device_id)
    subscription = refresh_subscription(db, device)
    if subscription.access_status == AccessStatus.BANNED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Устройство заблокировано.")

    plan = _get_plan(db, plan_id)
    payment_id = f"pay_{uuid4().hex}"
    created_at = utcnow()
    expires_at = created_at + timedelta(days=7)
    telegram_url = _build_telegram_chat_url(
        payment_id=payment_id,
        device_id=device.device_id,
        plan=plan,
    )

    payment = Payment(
        payment_id=payment_id,
        user_device_id=device.id,
        tariff_plan_id=plan.id,
        amount_rub=plan.amount_rub,
        currency="RUB",
        status=PaymentStatus.PENDING,
        provider="telegram_manual",
        provider_status="waiting_for_receipt",
        enot_payment_url=telegram_url,
        raw_create_response_json=json.dumps(
            {
                "provider": "telegram_manual",
                "telegramUrl": telegram_url,
                "deviceId": device.device_id,
                "planCode": plan.code,
                "planTitle": plan.title,
            },
            ensure_ascii=False,
        ),
        expires_at=expires_at,
    )
    db.add(payment)
    db.flush()
    return payment


def get_payment(db: Session, payment_id: str) -> Payment:
    payment = db.scalar(select(Payment).where(Payment.payment_id == payment_id))
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Платёж не найден.")
    return payment


def refresh_payment_status(db: Session, payment: Payment) -> Payment:
    payment.created_at = ensure_utc(payment.created_at) or payment.created_at
    payment.expires_at = ensure_utc(payment.expires_at)
    payment.paid_at = ensure_utc(payment.paid_at)

    db.flush()
    return payment


def sync_payment_from_provider(
    db: Session,
    payment: Payment,
    provider_response: dict,
    *,
    persist_to_webhook_log: bool,
) -> Payment:
    if persist_to_webhook_log:
        payment.raw_webhook_json = json.dumps(provider_response, ensure_ascii=False)
    db.flush()
    return payment


def confirm_latest_pending_payment(
    db: Session,
    *,
    device_id: int,
    tariff_plan_id: int | None = None,
) -> Payment | None:
    statement = (
        select(Payment)
        .where(Payment.user_device_id == device_id, Payment.status == PaymentStatus.PENDING)
        .order_by(Payment.created_at.desc(), Payment.id.desc())
    )
    if tariff_plan_id is not None:
        statement = statement.where(Payment.tariff_plan_id == tariff_plan_id)

    payment = db.scalar(statement.limit(1))
    if payment is None:
        return None

    payment.status = PaymentStatus.PAID
    payment.provider_status = "manually_confirmed"
    payment.paid_at = utcnow()
    payment.failure_reason = None
    db.flush()
    return payment


def build_payment_order_response(payment: Payment) -> PaymentOrderResponse:
    created_at = ensure_utc(payment.created_at) or utcnow()
    expires_at = ensure_utc(payment.expires_at) or (created_at + timedelta(days=7))
    return PaymentOrderResponse(
        paymentId=payment.payment_id,
        deviceId=payment.user_device.device_id,
        planId=payment.tariff_plan.code,
        amountRub=payment.amount_rub,
        createdAt=created_at,
        expiresAt=expires_at,
        paymentUrl=payment.enot_payment_url,
        providerInvoiceId=None,
        qrCodeUrl=None,
        qrPayload=None,
    )


def build_payment_status_response(db: Session, payment: Payment) -> PaymentStatusResponse:
    subscription = refresh_subscription(db, payment.user_device)
    state, title, detail = _resolve_payment_state(payment, subscription)
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


def _build_telegram_chat_url(*, payment_id: str, device_id: str, plan: TariffPlan) -> str:
    message = (
        "Здравствуйте! Хочу оплатить VPN.\n"
        f"Платёж: {payment_id}\n"
        f"Device ID: {device_id}\n"
        f"Тариф: {plan.title}\n"
        f"Сумма: {plan.amount_rub} RUB\n"
        "После оплаты отправлю чек сюда."
    )
    return f"https://t.me/{TELEGRAM_ADMIN_USERNAME}?text={quote(message)}"


def _resolve_payment_state(payment: Payment, subscription: Subscription) -> tuple[str, str, str]:
    if payment.status == PaymentStatus.PAID:
        return (
            "succeeded",
            "Доступ выдан",
            "Администратор подтвердил оплату и открыл доступ к VPN на этом устройстве.",
        )

    if payment.status == PaymentStatus.FAILED:
        return (
            "failed",
            "Заявка отклонена",
            payment.failure_reason or "Платёж не был подтверждён администратором.",
        )

    return (
        "pending",
        "Ожидает ручной проверки",
        "Откройте чат с @tajvpn_admin, оплатите, отправьте чек и дождитесь, пока администратор выдаст доступ в панели.",
    )
