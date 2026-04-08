from fastapi import APIRouter, HTTPException, Request, status

from config import settings
from database import SessionLocal
from services.enot_service import verify_webhook_signature
from services.payment_service import get_payment, sync_payment_from_provider


router = APIRouter(tags=["webhooks"])


@router.post(settings.enot_hook_path)
async def handle_enot_webhook(request: Request) -> dict[str, bool]:
    payload = await request.json()
    signature = request.headers.get("x-api-sha256-signature")
    if not verify_webhook_signature(payload, signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid ENOT signature.")

    order_id = str(payload.get("order_id") or "").strip()
    if not order_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Webhook does not include order_id.")

    with SessionLocal() as db:
        payment = get_payment(db, order_id)
        sync_payment_from_provider(db, payment, payload, persist_to_webhook_log=True)
        db.commit()

    return {"ok": True}
