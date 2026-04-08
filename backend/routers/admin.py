from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models import AccessStatus, Payment, PaymentStatus, Subscription, UserDevice, ensure_utc, utcnow
from schemas import (
    AdminActionResponse,
    AdminDeviceResponse,
    AdminOverviewResponse,
    AdminPaymentResponse,
    AdminStatsResponse,
    AdminSubscriptionUpdateRequest,
)
from services.subscription_service import (
    ban_user,
    extend_subscription_by_days,
    refresh_subscription,
    restore_after_unban,
    set_manual_subscription_end,
)
from services.payment_service import confirm_latest_pending_payment


router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin_token(x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")) -> None:
    if not settings.admin_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ADMIN_TOKEN не настроен.",
        )
    if x_admin_token != settings.admin_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный ADMIN_TOKEN.")


@router.get("/overview", response_model=AdminOverviewResponse, dependencies=[Depends(require_admin_token)])
def get_admin_overview(db: Session = Depends(get_db)) -> AdminOverviewResponse:
    now = utcnow()
    total_devices = db.scalar(select(func.count()).select_from(UserDevice)) or 0
    active_rows = db.scalars(select(Subscription).where(Subscription.access_status == AccessStatus.ACTIVE)).all()
    active_subscriptions = sum(1 for item in active_rows if ensure_utc(item.ends_at) and ensure_utc(item.ends_at) > now)
    pending_payments = db.scalar(select(func.count()).select_from(Payment).where(Payment.status == PaymentStatus.PENDING)) or 0
    paid_payments = db.scalar(select(func.count()).select_from(Payment).where(Payment.status == PaymentStatus.PAID)) or 0
    failed_payments = db.scalar(select(func.count()).select_from(Payment).where(Payment.status == PaymentStatus.FAILED)) or 0
    revenue_rub = db.scalar(select(func.coalesce(func.sum(Payment.amount_rub), 0)).where(Payment.status == PaymentStatus.PAID)) or 0

    recent_payments = db.scalars(select(Payment).order_by(Payment.created_at.desc(), Payment.id.desc()).limit(10)).all()
    devices = db.scalars(select(UserDevice).order_by(UserDevice.last_seen_at.desc(), UserDevice.id.desc()).limit(20)).all()

    overview = AdminOverviewResponse(
        stats=AdminStatsResponse(
            totalDevices=total_devices,
            activeSubscriptions=active_subscriptions,
            pendingPayments=pending_payments,
            paidPayments=paid_payments,
            failedPayments=failed_payments,
            revenueRub=revenue_rub,
        ),
        recentPayments=[_serialize_payment(payment) for payment in recent_payments],
        devices=[_serialize_device(db, device) for device in devices],
    )
    db.commit()
    return overview


@router.get("/payments", response_model=list[AdminPaymentResponse], dependencies=[Depends(require_admin_token)])
def list_payments(db: Session = Depends(get_db)) -> list[AdminPaymentResponse]:
    payments = db.scalars(select(Payment).order_by(Payment.created_at.desc(), Payment.id.desc())).all()
    return [_serialize_payment(payment) for payment in payments]


@router.get("/devices", response_model=list[AdminDeviceResponse], dependencies=[Depends(require_admin_token)])
def list_devices(db: Session = Depends(get_db)) -> list[AdminDeviceResponse]:
    devices = db.scalars(select(UserDevice).order_by(UserDevice.last_seen_at.desc(), UserDevice.id.desc())).all()
    response = [_serialize_device(db, device) for device in devices]
    db.commit()
    return response


@router.post("/devices/{device_id}/ban", response_model=AdminActionResponse, dependencies=[Depends(require_admin_token)])
def ban_device(device_id: str, db: Session = Depends(get_db)) -> AdminActionResponse:
    device = _get_device_or_404(db, device_id)
    subscription = ban_user(db, device)
    db.commit()
    db.refresh(subscription)

    return AdminActionResponse(
        message="Устройство заблокировано. Доступ к VPN отключён.",
        deviceId=device.device_id,
        accessStatus=subscription.access_status,
    )


@router.post("/devices/{device_id}/unban", response_model=AdminActionResponse, dependencies=[Depends(require_admin_token)])
def unban_device(device_id: str, db: Session = Depends(get_db)) -> AdminActionResponse:
    device = _get_device_or_404(db, device_id)
    subscription = restore_after_unban(db, device)
    db.commit()
    db.refresh(subscription)

    return AdminActionResponse(
        message="Устройство разблокировано. Статус доступа пересчитан.",
        deviceId=device.device_id,
        accessStatus=subscription.access_status,
    )


@router.post("/devices/{device_id}/subscription", response_model=AdminActionResponse, dependencies=[Depends(require_admin_token)])
def update_device_subscription(
    device_id: str,
    payload: AdminSubscriptionUpdateRequest,
    db: Session = Depends(get_db),
) -> AdminActionResponse:
    device = _get_device_or_404(db, device_id)
    subscription = set_manual_subscription_end(db, device, ends_at=payload.expires_at)
    confirm_latest_pending_payment(
        db,
        device_id=device.id,
        tariff_plan_id=subscription.tariff_plan_id,
    )
    db.commit()
    db.refresh(subscription)

    return AdminActionResponse(
        message="Дата окончания подписки обновлена.",
        deviceId=device.device_id,
        accessStatus=subscription.access_status,
    )


@router.post("/devices/{device_id}/extend", response_model=AdminActionResponse, dependencies=[Depends(require_admin_token)])
def extend_device_subscription(device_id: str, db: Session = Depends(get_db)) -> AdminActionResponse:
    device = _get_device_or_404(db, device_id)
    subscription = extend_subscription_by_days(db, device, days=30)
    confirm_latest_pending_payment(
        db,
        device_id=device.id,
        tariff_plan_id=subscription.tariff_plan_id,
    )
    db.commit()
    db.refresh(subscription)

    return AdminActionResponse(
        message="Подписка продлена на 30 дней.",
        deviceId=device.device_id,
        accessStatus=subscription.access_status,
    )


def _get_device_or_404(db: Session, device_id: str) -> UserDevice:
    device = db.scalar(select(UserDevice).where(UserDevice.device_id == device_id))
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Устройство не найдено.")
    return device


def _serialize_payment(payment: Payment) -> AdminPaymentResponse:
    return AdminPaymentResponse(
        paymentId=payment.payment_id,
        deviceId=payment.user_device.device_id,
        planId=payment.tariff_plan.code,
        planTitle=payment.tariff_plan.title,
        amountRub=payment.amount_rub,
        status=payment.status.value,
        providerStatus=payment.provider_status,
        paymentUrl=payment.enot_payment_url,
        createdAt=ensure_utc(payment.created_at) or payment.created_at,
        expiresAt=ensure_utc(payment.expires_at),
        paidAt=ensure_utc(payment.paid_at),
        failureReason=payment.failure_reason,
    )


def _serialize_device(db: Session, device: UserDevice) -> AdminDeviceResponse:
    subscription = refresh_subscription(db, device)
    total_payments, last_payment_at = db.execute(
        select(func.count(Payment.id), func.max(Payment.created_at)).where(Payment.user_device_id == device.id)
    ).one()

    return AdminDeviceResponse(
        deviceId=device.device_id,
        platform=device.platform,
        appVersion=device.app_version,
        deviceModel=device.device_model,
        firstSeenAt=ensure_utc(device.first_seen_at) or device.first_seen_at,
        lastSeenAt=ensure_utc(device.last_seen_at) or device.last_seen_at,
        accessStatus=subscription.access_status,
        subscriptionEndsAt=ensure_utc(subscription.ends_at),
        activePlanTitle=subscription.tariff_plan.title if subscription.tariff_plan else None,
        totalPayments=int(total_payments or 0),
        lastPaymentAt=ensure_utc(last_payment_at),
    )
