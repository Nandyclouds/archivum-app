from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import ImportLog
from app.schemas import ImportLogOut

router = APIRouter(prefix="/import-log", tags=["import-log"])


@router.get("", response_model=list[ImportLogOut])
def listar_import_log(limit: int = 20, db: Session = Depends(get_session)):
    return db.query(ImportLog).order_by(ImportLog.fecha.desc()).limit(limit).all()
