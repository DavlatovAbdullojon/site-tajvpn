import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from models import TariffPlan
from schemas import TariffPlanResponse


router = APIRouter(tags=["plans"])


@router.get("/plans", response_model=list[TariffPlanResponse])
def get_plans(db: Session = Depends(get_db)) -> list[TariffPlanResponse]:
    plans = db.scalars(
        select(TariffPlan)
        .where(TariffPlan.is_active.is_(True))
        .order_by(TariffPlan.sort_order.asc(), TariffPlan.id.asc())
    ).all()
    return [
        TariffPlanResponse(
            id=plan.code,
            title=plan.title,
            description=plan.description,
            amountRub=plan.amount_rub,
            durationDays=plan.duration_days,
            benefits=_parse_benefits(plan.benefits_json),
            badge=plan.badge,
            discountPercent=plan.discount_percent,
            isFeatured=plan.is_featured,
        )
        for plan in plans
    ]


def _parse_benefits(raw_value: str) -> list[str]:
    try:
        data = json.loads(raw_value or "[]")
    except json.JSONDecodeError:
        return []
    return [str(item) for item in data]
