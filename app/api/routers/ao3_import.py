"""Importar un fic al toque pegando su URL, desde la app (sin terminal).

A diferencia de `import bookmarks`/`import history` (que pueden tardar
horas y por eso viven en el CLI), importar UN fic es rápido: login + una
página. Es seguro exponerlo como endpoint síncrono.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ao3 import importer
from app.ao3.client import RequestFailedError, SessionRequestLimitReached
from app.ao3.parser import work_id_from_url
from app.api.ao3_session import build_authenticated_client
from app.api.serializers import to_detail
from app.database import get_session
from app.schemas import FicDetail

router = APIRouter(prefix="/ao3", tags=["ao3"])


class ImportarFicRequest(BaseModel):
    url: str
    force: bool = False


@router.post("/import-fic", response_model=FicDetail)
def importar_fic_por_url(payload: ImportarFicRequest, db: Session = Depends(get_session)):
    ao3_id = work_id_from_url(payload.url)
    if ao3_id is None:
        raise HTTPException(status_code=400, detail=f"No reconozco un id de fic en '{payload.url}'.")

    client = build_authenticated_client()
    try:
        fic, _ = importer.import_single_fic(db, client, ao3_id, force=payload.force)
        db.commit()
    except importer.FicNotFoundError as exc:
        db.commit()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RequestFailedError, SessionRequestLimitReached) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return to_detail(fic)
