import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import TariffPlan


DEFAULT_PLANS = [
    {
        "code": "plan_1m",
        "title": "1 месяц",
        "description": "Быстрый старт для доступа к VPN на 30 дней.",
        "amount_rub": 100,
        "duration_days": 30,
        "benefits": [
            "Полный доступ к VPN на 30 дней",
            "Автоматическая активация после оплаты",
            "Подходит для старта и коротких поездок",
        ],
        "badge": None,
        "discount_percent": 0,
        "is_featured": False,
        "sort_order": 1,
    },
    {
        "code": "plan_3m",
        "title": "3 месяца",
        "description": "Лучший тариф для постоянного ежедневного использования.",
        "amount_rub": 250,
        "duration_days": 90,
        "benefits": [
            "Доступ к VPN на 90 дней",
            "Самая выгодная цена за месяц",
            "Оплата через ENOT без ручной проверки",
        ],
        "badge": "Выгодно",
        "discount_percent": 17,
        "is_featured": True,
        "sort_order": 2,
    },
]


def seed_tariff_plans(db: Session) -> None:
    for payload in DEFAULT_PLANS:
        plan = db.scalar(select(TariffPlan).where(TariffPlan.code == payload["code"]))
        if plan is None:
            db.add(
                TariffPlan(
                    code=payload["code"],
                    title=payload["title"],
                    description=payload["description"],
                    amount_rub=payload["amount_rub"],
                    duration_days=payload["duration_days"],
                    benefits_json=json.dumps(payload["benefits"], ensure_ascii=False),
                    badge=payload["badge"],
                    discount_percent=payload["discount_percent"],
                    is_featured=payload["is_featured"],
                    sort_order=payload["sort_order"],
                )
            )
            continue

        plan.title = payload["title"]
        plan.description = payload["description"]
        plan.amount_rub = payload["amount_rub"]
        plan.duration_days = payload["duration_days"]
        plan.benefits_json = json.dumps(payload["benefits"], ensure_ascii=False)
        plan.badge = payload["badge"]
        plan.discount_percent = payload["discount_percent"]
        plan.is_featured = payload["is_featured"]
        plan.sort_order = payload["sort_order"]
        plan.is_active = True

    db.commit()
