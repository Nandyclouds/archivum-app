"""Endpoints que hablan con el workflow de GitHub Actions, no con el frontend.

Cuando la app corre en un host sin salida a AO3 (PythonAnywhere free tier),
las tres cosas que necesitan pegarle a AO3 en el momento — importar un fic
por link, descargar un EPUB, traer bookmarks nuevos — no se pueden hacer
localmente. En cambio:

1. El frontend llama a `POST /sync/trigger`, que dispara un workflow de
   GitHub Actions (que sí tiene salida a internet) vía la API de GitHub.
2. Ese workflow corre `scripts/gh_action_sync.py`, que scrapea AO3 con la
   misma lógica de siempre (app/ao3/*) y manda el resultado de vuelta acá.
3. Los endpoints `ingest-*`/`known-ids` reciben eso y hacen los mismos
   guardados que haría un import local (`upsert_fic`, `guardar_snapshot_html`,
   `apply_bookmark_tags`, `guardar_epub`), separados de la parte que pega a
   AO3 para que se puedan reusar desde las dos puntas.

Autenticación: estas rutas NUNCA las habla el frontend, así que no usan
ARCHIVUM_AUTH_TOKEN — usan ARCHIVUM_SYNC_SECRET (ver main.py). `trigger` es
la excepción: la llama el frontend, así que pasa por el token normal.
"""

from __future__ import annotations

import base64
import datetime

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ao3.downloader import guardar_epub
from app.ao3.importer import apply_bookmark_tags, guardar_snapshot_html, upsert_fic
from app.ao3.parser import parse_work_page
from app.config import settings
from app.database import get_session
from app.models import Fic

router = APIRouter(prefix="/sync", tags=["sync"])


# ---------------------------------------------------------------------------
# Disparo del workflow (lo llama el frontend)
# ---------------------------------------------------------------------------


class TriggerRequest(BaseModel):
    modo: str  # "bookmarks" | "fic" | "epub" | "marcados" | "wips"
    url: str | None = None
    ao3_id: str | None = None


@router.post("/trigger")
def disparar_sync(payload: TriggerRequest):
    if not settings.github_pat or not settings.github_repo:
        raise HTTPException(
            status_code=503,
            detail="GITHUB_PAT/GITHUB_REPO no configurados en el .env de este servidor.",
        )
    if payload.modo not in {"bookmarks", "fic", "epub", "marcados", "wips"}:
        raise HTTPException(status_code=400, detail=f"Modo desconocido: {payload.modo}")
    if payload.modo == "fic" and not payload.url:
        raise HTTPException(status_code=400, detail="Falta 'url' para modo=fic.")
    if payload.modo == "epub" and not payload.ao3_id:
        raise HTTPException(status_code=400, detail="Falta 'ao3_id' para modo=epub.")

    dispatch_url = (
        f"https://api.github.com/repos/{settings.github_repo}/actions/workflows/"
        f"{settings.github_workflow_file}/dispatches"
    )
    inputs = {"modo": payload.modo}
    if payload.url:
        inputs["url"] = payload.url
    if payload.ao3_id:
        inputs["ao3_id"] = payload.ao3_id

    response = requests.post(
        dispatch_url,
        headers={
            "Authorization": f"Bearer {settings.github_pat}",
            "Accept": "application/vnd.github+json",
        },
        json={"ref": "main", "inputs": inputs},
        timeout=15,
    )
    if response.status_code != 204:
        raise HTTPException(
            status_code=502,
            detail=f"GitHub rechazó el disparo del workflow ({response.status_code}): {response.text[:300]}",
        )
    return {"disparado": True}


# ---------------------------------------------------------------------------
# Ingesta (la habla el workflow de GitHub Actions)
# ---------------------------------------------------------------------------


@router.get("/known-ids")
def known_ids(db: Session = Depends(get_session)):
    """IDs de fics que ya tenemos, para que el sync de bookmarks se salte los conocidos."""
    ids = [row[0] for row in db.query(Fic.ao3_id).all()]
    return {"ao3_ids": ids}


@router.get("/incompletos")
def fics_incompletos(stale_days: int = 3, db: Session = Depends(get_session)):
    """IDs de fics marcados 'complete=False' que conviene volver a pedirle a
    AO3 (para detectar capítulos nuevos o que se haya completado — ver
    Novedad). `stale_days` evita re-chequear el mismo WIP en cada corrida:
    solo entran los que no se revisaron en esa cantidad de días (o nunca)."""
    limite = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(
        days=stale_days
    )
    query = db.query(Fic.ao3_id).filter(
        Fic.complete.is_(False),
        Fic.deleted_detected_at.is_(None),
        (Fic.ultima_revision.is_(None)) | (Fic.ultima_revision < limite),
    )
    return {"ao3_ids": [row[0] for row in query.all()]}


class IngestFicRequest(BaseModel):
    ao3_id: str
    # Opcional a propósito: para un fic que YA está en la biblioteca, el
    # runner de GitHub Actions manda solo los tags actualizados del
    # bookmark, sin re-pedir ni re-mandar el HTML entero (no hace falta:
    # nada del fic en sí cambió, solo cómo lo tiene taggeado la usuaria en
    # AO3 — y eso ya lo sabe de haber listado la página de bookmarks, sin
    # gastar otra petición). Si el fic todavía no existe, html es
    # obligatorio (si no, no hay de dónde sacar título/fandoms/etc.).
    html: str | None = None
    bookmark_tags: list[str] | None = None
    bookmarked_at: str | None = None


@router.post("/ingest-fic")
def ingest_fic(payload: IngestFicRequest, db: Session = Depends(get_session)):
    if payload.html:
        parsed = parse_work_page(payload.html, payload.ao3_id)
        fic, es_nuevo = upsert_fic(db, parsed)
        guardar_snapshot_html(db, fic, payload.html)
    else:
        fic = db.query(Fic).filter_by(ao3_id=payload.ao3_id).one_or_none()
        if fic is None:
            raise HTTPException(
                status_code=404,
                detail=f"Fic {payload.ao3_id} no encontrado (mandá 'html' para crearlo).",
            )
        es_nuevo = False

    if payload.bookmark_tags:
        apply_bookmark_tags(db, fic, payload.bookmark_tags, payload.bookmarked_at)
    db.commit()
    return {"ao3_id": fic.ao3_id, "es_nuevo": es_nuevo}


class IngestEpubRequest(BaseModel):
    ao3_id: str
    content_base64: str


@router.post("/ingest-epub")
def ingest_epub(payload: IngestEpubRequest, db: Session = Depends(get_session)):
    fic = db.query(Fic).filter_by(ao3_id=payload.ao3_id).one_or_none()
    if fic is None:
        raise HTTPException(status_code=404, detail=f"Fic {payload.ao3_id} no encontrado.")
    contenido = base64.b64decode(payload.content_base64)
    guardar_epub(db, fic, contenido, settings.archivo_dir)
    db.commit()
    return {"ao3_id": fic.ao3_id, "bytes": len(contenido)}
