from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.ao3 import downloader
from app.ao3.client import RequestFailedError, SessionRequestLimitReached
from app.api.ao3_session import build_authenticated_client
from app.api.serializers import to_archivo_out, to_detail, to_list_item
from app.config import settings
from app.database import get_session
from app.models import ColeccionFic, EtiquetaPersonal, Fandom, Fic, FicEtiquetaPersonal, Lectura, Resena, Ship
from app.schemas import (
    ArchivoOut,
    EtiquetaPersonalCreate,
    EtiquetaPersonalOut,
    FicDetail,
    FicListItem,
    LecturaCreate,
    LecturaOut,
    LecturaUpdate,
    ResenaCreate,
    ResenaOut,
    ResenaUpdate,
)

router = APIRouter(prefix="/fics", tags=["fics"])


def _get_fic_or_404(db: Session, fic_id: int) -> Fic:
    fic = db.get(Fic, fic_id)
    if fic is None:
        raise HTTPException(status_code=404, detail="Fic no encontrado")
    return fic


@router.get("", response_model=list[FicListItem])
def listar_fics(
    db: Session = Depends(get_session),
    q: str | None = Query(None, description="Busca en título y autor"),
    fandom: str | None = Query(None, description="Nombre exacto de fandom"),
    ship: str | None = Query(None, description="Nombre exacto de ship/relación"),
    etiqueta: str | None = Query(None, description="Nombre exacto de etiqueta personal"),
    coleccion: int | None = Query(None, description="Id de colección"),
    estado: str | None = Query(None, description="Estado de la lectura más reciente"),
    completo: bool | None = Query(None, description="Filtra por fic.complete (True=completos, False=WIP)"),
    incluir_borrados: bool = False,
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    query = db.query(Fic)
    if not incluir_borrados:
        query = query.filter(Fic.deleted_detected_at.is_(None))
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Fic.titulo.ilike(like), Fic.autor.ilike(like)))
    if fandom:
        query = query.join(Fic.fandoms).filter(Fandom.nombre == fandom)
    if ship:
        query = query.join(Fic.ships).filter(Ship.nombre == ship)
    if etiqueta:
        query = query.join(Fic.etiquetas_personales).filter(EtiquetaPersonal.nombre == etiqueta)
    if coleccion is not None:
        query = query.join(ColeccionFic, ColeccionFic.fic_id == Fic.id).filter(
            ColeccionFic.coleccion_id == coleccion
        )
    if completo is not None:
        query = query.filter(Fic.complete == completo)
    if estado:
        ultimas = (
            db.query(Lectura.fic_id, func.max(Lectura.id).label("ultima_id"))
            .group_by(Lectura.fic_id)
            .subquery()
        )
        query = (
            query.join(ultimas, ultimas.c.fic_id == Fic.id)
            .join(Lectura, Lectura.id == ultimas.c.ultima_id)
            .filter(Lectura.estado == estado)
        )
    fics = query.order_by(Fic.titulo).offset(offset).limit(limit).all()
    return [to_list_item(f) for f in fics]


@router.get("/{fic_id}", response_model=FicDetail)
def obtener_fic(fic_id: int, db: Session = Depends(get_session)):
    return to_detail(_get_fic_or_404(db, fic_id))


@router.post("/{fic_id}/lecturas", response_model=LecturaOut, status_code=201)
def crear_lectura(fic_id: int, payload: LecturaCreate, db: Session = Depends(get_session)):
    _get_fic_or_404(db, fic_id)
    lectura = Lectura(fic_id=fic_id, **payload.model_dump())
    db.add(lectura)
    db.commit()
    db.refresh(lectura)
    return lectura


def _get_lectura_or_404(db: Session, fic_id: int, lectura_id: int) -> Lectura:
    lectura = db.get(Lectura, lectura_id)
    if lectura is None or lectura.fic_id != fic_id:
        raise HTTPException(status_code=404, detail="Lectura no encontrada")
    return lectura


@router.patch("/{fic_id}/lecturas/{lectura_id}", response_model=LecturaOut)
def actualizar_lectura(
    fic_id: int, lectura_id: int, payload: LecturaUpdate, db: Session = Depends(get_session)
):
    lectura = _get_lectura_or_404(db, fic_id, lectura_id)
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(lectura, campo, valor)
    db.commit()
    db.refresh(lectura)
    return lectura


@router.delete("/{fic_id}/lecturas/{lectura_id}", status_code=204)
def borrar_lectura(fic_id: int, lectura_id: int, db: Session = Depends(get_session)):
    lectura = _get_lectura_or_404(db, fic_id, lectura_id)
    db.delete(lectura)
    db.commit()


@router.post("/{fic_id}/resenas", response_model=ResenaOut, status_code=201)
def crear_resena(fic_id: int, payload: ResenaCreate, db: Session = Depends(get_session)):
    _get_fic_or_404(db, fic_id)
    datos = payload.model_dump()
    if datos.get("fecha") is None:
        datos["fecha"] = datetime.date.today()
    resena = Resena(fic_id=fic_id, **datos)
    db.add(resena)
    db.commit()
    db.refresh(resena)
    return resena


def _get_resena_or_404(db: Session, fic_id: int, resena_id: int) -> Resena:
    resena = db.get(Resena, resena_id)
    if resena is None or resena.fic_id != fic_id:
        raise HTTPException(status_code=404, detail="Reseña no encontrada")
    return resena


@router.patch("/{fic_id}/resenas/{resena_id}", response_model=ResenaOut)
def actualizar_resena(
    fic_id: int, resena_id: int, payload: ResenaUpdate, db: Session = Depends(get_session)
):
    resena = _get_resena_or_404(db, fic_id, resena_id)
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(resena, campo, valor)
    db.commit()
    db.refresh(resena)
    return resena


@router.delete("/{fic_id}/resenas/{resena_id}", status_code=204)
def borrar_resena(fic_id: int, resena_id: int, db: Session = Depends(get_session)):
    resena = _get_resena_or_404(db, fic_id, resena_id)
    db.delete(resena)
    db.commit()


@router.post("/{fic_id}/download-epub", response_model=ArchivoOut)
def descargar_epub(fic_id: int, db: Session = Depends(get_session)):
    """Baja el EPUB de este fic ya, desde la app (sin terminal). Requiere
    login a AO3 (~4s) + la descarga en sí, respetando el mismo rate limit
    que el resto del importador."""
    fic = _get_fic_or_404(db, fic_id)
    client = build_authenticated_client()
    try:
        archivo = downloader.download_fic_epub(db, client, fic, settings.archivo_dir)
        db.commit()
    except downloader.DownloadError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (RequestFailedError, SessionRequestLimitReached) as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return to_archivo_out(archivo)


@router.post("/{fic_id}/etiquetas", response_model=EtiquetaPersonalOut, status_code=201)
def agregar_etiqueta(fic_id: int, payload: EtiquetaPersonalCreate, db: Session = Depends(get_session)):
    """Etiqueta libre de la usuaria (no una colección): si no existe la crea,
    y la asocia al fic. Reutiliza la etiqueta si ya existe con ese nombre."""
    fic = _get_fic_or_404(db, fic_id)
    nombre = payload.nombre.strip()
    if not nombre:
        raise HTTPException(status_code=422, detail="El nombre de la etiqueta no puede estar vacío")

    etiqueta = db.query(EtiquetaPersonal).filter_by(nombre=nombre).one_or_none()
    if etiqueta is None:
        etiqueta = EtiquetaPersonal(nombre=nombre)
        db.add(etiqueta)
        db.flush()
    if etiqueta not in fic.etiquetas_personales:
        fic.etiquetas_personales.append(etiqueta)
        db.commit()
    return etiqueta


@router.delete("/{fic_id}/etiquetas/{etiqueta_id}", status_code=204)
def quitar_etiqueta(fic_id: int, etiqueta_id: int, db: Session = Depends(get_session)):
    fic = _get_fic_or_404(db, fic_id)
    etiqueta = db.get(EtiquetaPersonal, etiqueta_id)
    if etiqueta is not None and etiqueta in fic.etiquetas_personales:
        fic.etiquetas_personales.remove(etiqueta)
        db.commit()
