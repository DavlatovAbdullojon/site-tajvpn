from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from schemas import PaymentCreateRequest, PaymentOrderResponse, PaymentStatusResponse
from services.payment_service import build_payment_order_response, build_payment_status_response, create_payment_order, get_payment, refresh_payment_status


router = APIRouter(tags=["payments"])


@router.post("/payments/create", response_model=PaymentOrderResponse)
def create_payment(payload: PaymentCreateRequest, db: Session = Depends(get_db)) -> PaymentOrderResponse:
    payment = create_payment_order(db, device_id=payload.device_id, plan_id=payload.plan_id)
    db.commit()
    db.refresh(payment)
    return build_payment_order_response(payment)


@router.get("/payments/{payment_id}/status", response_model=PaymentStatusResponse)
def get_payment_status(payment_id: str, db: Session = Depends(get_db)) -> PaymentStatusResponse:
    payment = get_payment(db, payment_id)
    refresh_payment_status(db, payment)
    db.commit()
    db.refresh(payment)
    return build_payment_status_response(db, payment)
