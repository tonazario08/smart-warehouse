"""Read-only, independently role-gated operational outcomes and linked vouchers."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.anomalies import operational_service as service
from app.anomalies.operational_service import OperationalVoucherView, Results, Summary
from app.auth.dependencies import Permission, require_permission
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models import User

router = APIRouter(prefix="/operational-anomalies", tags=["operational-anomalies"])
Db = Annotated[Session, Depends(get_session)]
Config = Annotated[Settings, Depends(get_settings)]
Read = Annotated[User, Depends(require_permission(Permission.ANOMALY_READ))]
Voucher = Annotated[
    User,
    Depends(
        require_permission(
            Permission.INVENTORY_HISTORY_READ, require_permission(Permission.ANOMALY_READ)
        )
    ),
]


@router.get("", response_model=Results)
def results(
    actor: Read,
    session: Db,
    settings: Config,
    response: Response,
    page: Annotated[int, Query(ge=1, le=10000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    response.headers["Cache-Control"] = "no-store"
    return service.results(session, settings, page, page_size)


@router.get("/{transaction_id}", response_model=Summary)
def result(transaction_id: int, actor: Read, session: Db, settings: Config, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return service.result(session, settings, transaction_id)


@router.get("/{transaction_id}/outbound", response_model=OperationalVoucherView)
def outbound(
    transaction_id: int, actor: Voucher, session: Db, settings: Config, response: Response
):
    response.headers["Cache-Control"] = "no-store"
    return service.outbound(session, settings, transaction_id)
