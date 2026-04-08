from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class AccessStatus(str, Enum):
    INACTIVE = "inactive"
    ACTIVE = "active"
    BANNED = "banned"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"


class UserDevice(Base):
    __tablename__ = "user_devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    device_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    platform: Mapped[str] = mapped_column(String(32), default="android")
    app_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    device_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    payments: Mapped[list["Payment"]] = relationship(back_populates="user_device", cascade="all, delete-orphan")
    subscription: Mapped["Subscription | None"] = relationship(back_populates="user_device", uselist=False)


class TariffPlan(Base):
    __tablename__ = "tariff_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(String(255))
    amount_rub: Mapped[int] = mapped_column(Integer)
    duration_days: Mapped[int] = mapped_column(Integer)
    benefits_json: Mapped[str] = mapped_column(Text, default="[]")
    badge: Mapped[str | None] = mapped_column(String(64), nullable=True)
    discount_percent: Mapped[int] = mapped_column(Integer, default=0)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    payments: Mapped[list["Payment"]] = relationship(back_populates="tariff_plan")
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="tariff_plan")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    payment_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_device_id: Mapped[int] = mapped_column(ForeignKey("user_devices.id"), index=True)
    tariff_plan_id: Mapped[int] = mapped_column(ForeignKey("tariff_plans.id"), index=True)
    amount_rub: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(16), default="RUB")
    status: Mapped[PaymentStatus] = mapped_column(SqlEnum(PaymentStatus), default=PaymentStatus.PENDING, index=True)
    provider_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider: Mapped[str] = mapped_column(String(32), default="enot")
    enot_invoice_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True, index=True)
    enot_payment_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    raw_create_response_json: Mapped[str] = mapped_column(Text, default="{}")
    raw_webhook_json: Mapped[str] = mapped_column(Text, default="{}")
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user_device: Mapped["UserDevice"] = relationship(back_populates="payments")
    tariff_plan: Mapped["TariffPlan"] = relationship(back_populates="payments")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_device_id: Mapped[int] = mapped_column(ForeignKey("user_devices.id"), unique=True, index=True)
    tariff_plan_id: Mapped[int | None] = mapped_column(ForeignKey("tariff_plans.id"), nullable=True)
    access_status: Mapped[AccessStatus] = mapped_column(SqlEnum(AccessStatus), default=AccessStatus.INACTIVE, index=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_payment_id: Mapped[int | None] = mapped_column(ForeignKey("payments.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user_device: Mapped["UserDevice"] = relationship(back_populates="subscription")
    tariff_plan: Mapped["TariffPlan | None"] = relationship(back_populates="subscriptions")
    last_payment: Mapped["Payment | None"] = relationship(foreign_keys=[last_payment_id])
