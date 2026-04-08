from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import ensure_utc
from schemas import DeviceInitRequest, DeviceInitResponse
from services.device_service import get_or_create_device_with_state
from services.subscription_service import activate_free_trial


router = APIRouter(tags=["device"])


@router.post("/device/init", response_model=DeviceInitResponse)
def init_device(payload: DeviceInitRequest, db: Session = Depends(get_db)) -> DeviceInitResponse:
    device, is_new_device = get_or_create_device_with_state(
        db,
        device_id=payload.device_id,
        platform=payload.platform,
        app_version=payload.app_version,
        device_model=payload.device_model,
    )
    if is_new_device:
        activate_free_trial(db, device)

    db.commit()
    db.refresh(device)
    return DeviceInitResponse(
        deviceId=device.device_id,
        createdAt=ensure_utc(device.first_seen_at) or device.first_seen_at,
        lastSeenAt=ensure_utc(device.last_seen_at) or device.last_seen_at,
    )
