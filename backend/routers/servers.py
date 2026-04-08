from fastapi import APIRouter

from schemas import ServerResponse
from services.server_service import get_servers


router = APIRouter(tags=["servers"])


@router.get("/servers", response_model=list[ServerResponse])
def list_servers() -> list[ServerResponse]:
    return get_servers()
