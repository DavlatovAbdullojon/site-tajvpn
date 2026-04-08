from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from config import settings
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


def activate_free_trial(db: Session, device: UserDevice, *, duration_days: int | None = None) -> Subscription:
    subscription = ensure_subscription(db, device)
    subscription.starts_at = ensure_utc(subscription.starts_at)
    subscription.ends_at = ensure_utc(subscription.ends_at)

    if subscription.access_status == AccessStatus.BANNED:
        return subscription
    if subscription.last_payment_id is not None:
        return subscription

    now = utcnow()
    if subscription.access_status == AccessStatus.ACTIVE and subscription.ends_at and subscription.ends_at > now:
        return subscription

    trial_days = duration_days or settings.free_trial_days
    subscription.access_status = AccessStatus.ACTIVE
    subscription.starts_at = now
    subscription.ends_at = now + timedelta(days=trial_days)
    subscription.tariff_plan_id = None
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


def set_manual_subscription_end(db: Session, device: UserDevice, *, ends_at) -> Subscription:
    subscription = ensure_subscription(db, device)
    subscription.starts_at = ensure_utc(subscription.starts_at)
    subscription.ends_at = ensure_utc(ends_at)

    now = utcnow()
    if subscription.starts_at is None and subscription.ends_at and subscription.ends_at > now:
        subscription.starts_at = now

    if subscription.access_status == AccessStatus.BANNED:
        db.flush()
        return subscription

    if subscription.ends_at and subscription.ends_at > now:
        subscription.access_status = AccessStatus.ACTIVE
    else:
        subscription.access_status = AccessStatus.INACTIVE
        subscription.tariff_plan_id = None

    db.flush()
    return subscription


def extend_subscription_by_days(db: Session, device: UserDevice, *, days: int = 30) -> Subscription:
    subscription = ensure_subscription(db, device)
    subscription.starts_at = ensure_utc(subscription.starts_at)
    subscription.ends_at = ensure_utc(subscription.ends_at)

    now = utcnow()
    extension_start = subscription.ends_at if subscription.ends_at and subscription.ends_at > now else now

    if subscription.starts_at is None:
        subscription.starts_at = now

    subscription.ends_at = extension_start + timedelta(days=days)

    if subscription.access_status != AccessStatus.BANNED:
        subscription.access_status = AccessStatus.ACTIVE

    db.flush()
    return subscription


def subscription_message(subscription: Subscription) -> str:
    if (
        subscription.access_status == AccessStatus.ACTIVE
        and subscription.last_payment_id is None
        and subscription.starts_at is not None
        and subscription.ends_at is not None
        and (subscription.ends_at - subscription.starts_at) <= timedelta(days=settings.free_trial_days, minutes=1)
    ):
        return f"Бесплатный период активен. У вас есть {settings.free_trial_days} дней бесплатного доступа к VPN."

    messages = {
        AccessStatus.INACTIVE: "Подписка не активна. Откройте оплату, напишите администратору в Telegram и отправьте чек.",
        AccessStatus.ACTIVE: "Подписка активна. Доступ к VPN открыт.",
        AccessStatus.BANNED: "Устройство заблокировано. Доступ к VPN закрыт.",
    }
    return messages[subscription.access_status]
