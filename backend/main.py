from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import Base, SessionLocal, engine
from routers.admin import router as admin_router
from routers.device import router as device_router
from routers.plans import router as plans_router
from routers.payments import router as payments_router
from routers.servers import router as servers_router
from routers.subscription import router as subscription_router
from routers.vpn import router as vpn_router
from routers.webhooks import router as webhooks_router
from services.seed_service import seed_tariff_plans


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_tariff_plans(db)
    yield


app = FastAPI(
    title=settings.app_name,
    version="2.0.0",
    lifespan=lifespan,
)

allow_all_origins = settings.allowed_origins_list == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all_origins else settings.allowed_origins_list,
    allow_credentials=not allow_all_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(device_router)
app.include_router(plans_router)
app.include_router(payments_router)
app.include_router(subscription_router)
app.include_router(servers_router)
app.include_router(vpn_router)
app.include_router(admin_router)
app.include_router(webhooks_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}
