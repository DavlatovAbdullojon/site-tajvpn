from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models import ensure_utc
from schemas import SubscriptionStatusResponse
from services.device_service import get_or_create_device
from services.subscription_service import refresh_subscription, subscription_message


router = APIRouter(tags=["subscription"])


@router.get("/subscription/status", response_model=SubscriptionStatusResponse)
def get_subscription_status(
    device_id: str = Query(..., alias="deviceId"),
    db: Session = Depends(get_db),
) -> SubscriptionStatusResponse:
    device = get_or_create_device(db, device_id=device_id)
    subscription = refresh_subscription(db, device)
    db.commit()
    db.refresh(subscription)

    return SubscriptionStatusResponse(
        deviceId=device.device_id,
        accessStatus=subscription.access_status,
        fetchedAt=ensure_utc(subscription.updated_at) or subscription.updated_at,
        expiresAt=ensure_utc(subscription.ends_at),
        message=subscription_message(subscription),
    )
