from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from models import AccessStatus


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class DeviceInitRequest(ApiModel):
    device_id: str = Field(..., alias="deviceId", min_length=8, max_length=128)
    platform: str = "android"
    app_version: str | None = Field(default=None, alias="appVersion")
    device_model: str | None = Field(default=None, alias="deviceModel")


class DeviceInitResponse(ApiModel):
    device_id: str = Field(..., alias="deviceId")
    created_at: datetime = Field(..., alias="createdAt")
    last_seen_at: datetime = Field(..., alias="lastSeenAt")


class TariffPlanResponse(ApiModel):
    id: str
    title: str
    description: str
    amount_rub: int = Field(..., alias="amountRub")
    duration_days: int = Field(..., alias="durationDays")
    benefits: list[str] = Field(default_factory=list)
    badge: str | None = None
    discount_percent: int = Field(default=0, alias="discountPercent")
    is_featured: bool = Field(default=False, alias="isFeatured")


class PaymentCreateRequest(ApiModel):
    device_id: str = Field(..., alias="deviceId", min_length=8, max_length=128)
    plan_id: str = Field(..., alias="planId")


class PaymentOrderResponse(ApiModel):
    payment_id: str = Field(..., alias="paymentId")
    device_id: str = Field(..., alias="deviceId")
    plan_id: str = Field(..., alias="planId")
    amount_rub: int = Field(..., alias="amountRub")
    created_at: datetime = Field(..., alias="createdAt")
    expires_at: datetime = Field(..., alias="expiresAt")
    payment_url: str | None = Field(default=None, alias="paymentUrl")
    provider_invoice_id: str | None = Field(default=None, alias="providerInvoiceId")
    qr_code_url: str | None = Field(default=None, alias="qrCodeUrl")
    qr_payload: str | None = Field(default=None, alias="qrPayload")


class PaymentStatusResponse(ApiModel):
    payment_id: str = Field(..., alias="paymentId")
    state: str = Field(..., alias="status")
    checked_at: datetime = Field(..., alias="checkedAt")
    title: str
    detail: str
    activated_until: datetime | None = Field(default=None, alias="activatedUntil")


class SubscriptionStatusResponse(ApiModel):
    device_id: str = Field(..., alias="deviceId")
    access_status: AccessStatus = Field(..., alias="accessStatus")
    fetched_at: datetime = Field(..., alias="fetchedAt")
    expires_at: datetime | None = Field(default=None, alias="expiresAt")
    message: str


class ServerResponse(ApiModel):
    id: str
    country: str
    country_code: str = Field(..., alias="countryCode")
    city: str
    host: str
    latency_ms: int | None = Field(default=None, alias="latencyMs")
    is_online: bool = Field(default=True, alias="isOnline")
    is_recommended: bool = Field(default=False, alias="isRecommended")


class VpnSessionRequest(ApiModel):
    device_id: str = Field(..., alias="deviceId")
    server_id: str = Field(..., alias="serverId")


class VpnSessionResponse(ApiModel):
    session_id: str = Field(..., alias="sessionId")
    server_id: str = Field(..., alias="serverId")
    server_host: str = Field(..., alias="serverHost")
    server_country: str = Field(..., alias="serverCountry")
    server_city: str = Field(..., alias="serverCity")
    auth_token: str = Field(..., alias="authToken")
    dns_servers: list[str] = Field(..., alias="dnsServers")
    mtu: int


class AdminStatsResponse(ApiModel):
    total_devices: int = Field(..., alias="totalDevices")
    active_subscriptions: int = Field(..., alias="activeSubscriptions")
    pending_payments: int = Field(..., alias="pendingPayments")
    paid_payments: int = Field(..., alias="paidPayments")
    failed_payments: int = Field(..., alias="failedPayments")
    revenue_rub: int = Field(..., alias="revenueRub")


class AdminPaymentResponse(ApiModel):
    payment_id: str = Field(..., alias="paymentId")
    device_id: str = Field(..., alias="deviceId")
    plan_id: str = Field(..., alias="planId")
    plan_title: str = Field(..., alias="planTitle")
    amount_rub: int = Field(..., alias="amountRub")
    status: str
    provider_status: str | None = Field(default=None, alias="providerStatus")
    payment_url: str | None = Field(default=None, alias="paymentUrl")
    created_at: datetime = Field(..., alias="createdAt")
    expires_at: datetime | None = Field(default=None, alias="expiresAt")
    paid_at: datetime | None = Field(default=None, alias="paidAt")
    failure_reason: str | None = Field(default=None, alias="failureReason")


class AdminDeviceResponse(ApiModel):
    device_id: str = Field(..., alias="deviceId")
    platform: str
    app_version: str | None = Field(default=None, alias="appVersion")
    device_model: str | None = Field(default=None, alias="deviceModel")
    first_seen_at: datetime = Field(..., alias="firstSeenAt")
    last_seen_at: datetime = Field(..., alias="lastSeenAt")
    access_status: AccessStatus = Field(..., alias="accessStatus")
    subscription_ends_at: datetime | None = Field(default=None, alias="subscriptionEndsAt")
    active_plan_title: str | None = Field(default=None, alias="activePlanTitle")
    total_payments: int = Field(..., alias="totalPayments")
    last_payment_at: datetime | None = Field(default=None, alias="lastPaymentAt")


class AdminOverviewResponse(ApiModel):
    stats: AdminStatsResponse
    recent_payments: list[AdminPaymentResponse] = Field(default_factory=list, alias="recentPayments")
    devices: list[AdminDeviceResponse] = Field(default_factory=list)


class AdminActionResponse(ApiModel):
    message: str
    device_id: str = Field(..., alias="deviceId")
    access_status: AccessStatus = Field(..., alias="accessStatus")
