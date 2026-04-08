from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import ensure_utc
from schemas import DeviceInitRequest, DeviceInitResponse
from services.device_service import get_or_create_device


router = APIRouter(tags=["device"])


@router.post("/device/init", response_model=DeviceInitResponse)
def init_device(payload: DeviceInitRequest, db: Session = Depends(get_db)) -> DeviceInitResponse:
    device = get_or_create_device(
        db,
        device_id=payload.device_id,
        platform=payload.platform,
        app_version=payload.app_version,
        device_model=payload.device_model,
    )
    db.commit()
    db.refresh(device)
    return DeviceInitResponse(
        deviceId=device.device_id,
        createdAt=ensure_utc(device.first_seen_at) or device.first_seen_at,
        lastSeenAt=ensure_utc(device.last_seen_at) or device.last_seen_at,
    )
