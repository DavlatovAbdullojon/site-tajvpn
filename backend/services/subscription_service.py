from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import AccessStatus, Payment, PaymentStatus, Subscription, UserDevice, ensure_utc, utcnow


def allows_vpn(access_status: AccessStatus) -> bool:
    return access_status == AccessStatus.ACTIVE


def ensure_subscription(db: Session, device: UserDevice) -> Subscription:
    subscription = db.scalar(select(Subscription).where(Subscription.user_device_id == device.id))
    if subscription is None:
        subscription = Subscription(
            user_device_id=device.id,
            access_status=AccessStatus.INACTIVE,
        )
        db.add(subscription)
        db.flush()
    return subscription


def refresh_subscription(db: Session, device: UserDevice) -> Subscription:
    subscription = ensure_subscription(db, device)
    subscription.starts_at = ensure_utc(subscription.starts_at)
    subscription.ends_at = ensure_utc(subscription.ends_at)

    if subscription.access_status != AccessStatus.BANNED and subscription.ends_at and subscription.ends_at <= utcnow():
        subscription.access_status = AccessStatus.INACTIVE
        subscription.tariff_plan_id = None
    db.flush()
    return subscription


def activate_subscription(db: Session, payment: Payment) -> Subscription:
    subscription = ensure_subscription(db, payment.user_device)
    subscription.starts_at = ensure_utc(subscription.starts_at)
    subscription.ends_at = ensure_utc(subscription.ends_at)

    if subscription.access_status == AccessStatus.BANNED:
        subscription.last_payment_id = payment.id
        db.flush()
        return subscription

    now = ensure_utc(payment.paid_at) or utcnow()
    extension_start = now
    if subscription.access_status == AccessStatus.ACTIVE and subscription.ends_at and subscription.ends_at > now:
        extension_start = subscription.ends_at
    else:
        subscription.starts_at = now

    subscription.tariff_plan_id = payment.tariff_plan_id
    subscription.last_payment_id = payment.id
    subscription.access_status = AccessStatus.ACTIVE
    subscription.ends_at = extension_start + timedelta(days=payment.tariff_plan.duration_days)
    db.flush()
    return subscription


def ban_user(db: Session, device: UserDevice) -> Subscription:
    subscription = ensure_subscription(db, device)
    subscription.access_status = AccessStatus.BANNED
    db.flush()
    return subscription


def restore_after_unban(db: Session, device: UserDevice) -> Subscription:
    subscription = ensure_subscription(db, device)
    subscription.ends_at = ensure_utc(subscription.ends_at)
    now = utcnow()
    if (
        subscription.last_payment
        and subscription.last_payment.status == PaymentStatus.PAID
        and subscription.ends_at
        and subscription.ends_at > now
    ):
        subscription.access_status = AccessStatus.ACTIVE
    else:
        subscription.access_status = AccessStatus.INACTIVE
        if subscription.ends_at and subscription.ends_at <= now:
            subscription.tariff_plan_id = None

    db.flush()
    return subscription


def subscription_message(subscription: Subscription) -> str:
    messages = {
        AccessStatus.INACTIVE: "Подписка не активна. Выберите тариф и оплатите через ENOT.",
        AccessStatus.ACTIVE: "Подписка активна. Доступ к VPN открыт.",
        AccessStatus.BANNED: "Устройство заблокировано. Доступ к VPN закрыт.",
    }
    return messages[subscription.access_status]
