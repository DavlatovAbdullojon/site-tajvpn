from sqlalchemy import select
from sqlalchemy.orm import Session

from models import UserDevice, utcnow


def get_or_create_device_with_state(
    db: Session,
    device_id: str,
    platform: str = "android",
    app_version: str | None = None,
    device_model: str | None = None,
) -> tuple[UserDevice, bool]:
    device = db.scalar(select(UserDevice).where(UserDevice.device_id == device_id))

    if device is None:
        device = UserDevice(
            device_id=device_id,
            platform=platform,
            app_version=app_version,
            device_model=device_model,
        )
        db.add(device)
        db.flush()
        return device, True

    device.platform = platform or device.platform
    device.app_version = app_version or device.app_version
    device.device_model = device_model or device.device_model
    device.last_seen_at = utcnow()
    db.flush()
    return device, False


def get_or_create_device(
    db: Session,
    device_id: str,
    platform: str = "android",
    app_version: str | None = None,
    device_model: str | None = None,
) -> UserDevice:
    device, _ = get_or_create_device_with_state(
        db,
        device_id=device_id,
        platform=platform,
        app_version=app_version,
        device_model=device_model,
    )
    return device
