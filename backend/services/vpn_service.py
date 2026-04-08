from __future__ import annotations

from secrets import token_urlsafe

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from schemas import VpnSessionResponse
from services.device_service import get_or_create_device
from services.server_service import get_server_by_id
from services.subscription_service import allows_vpn, refresh_subscription


def create_vpn_session(db: Session, *, device_id: str, server_id: str) -> VpnSessionResponse:
    device = get_or_create_device(db, device_id=device_id)
    subscription = refresh_subscription(db, device)
    if not allows_vpn(subscription.access_status):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Подписка для этого устройства не активна.",
        )

    server = get_server_by_id(server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сервер не найден.")
    if not server.is_online:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Сервер временно недоступен.")

    return VpnSessionResponse(
        sessionId=token_urlsafe(18),
        serverId=server.id,
        serverHost=server.host,
        serverCountry=server.country,
        serverCity=server.city,
        authToken=token_urlsafe(32),
        dnsServers=["1.1.1.1", "8.8.8.8"],
        mtu=1400,
    )
