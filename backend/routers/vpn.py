from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from schemas import VpnSessionRequest, VpnSessionResponse
from services.vpn_service import create_vpn_session


router = APIRouter(tags=["vpn"])


@router.post("/vpn/session", response_model=VpnSessionResponse)
def create_session(payload: VpnSessionRequest, db: Session = Depends(get_db)) -> VpnSessionResponse:
    response = create_vpn_session(db, device_id=payload.device_id, server_id=payload.server_id)
    db.commit()
    return response
