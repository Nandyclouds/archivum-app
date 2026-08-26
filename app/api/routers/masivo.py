"""Acciones en lote sobre varios fics a la vez — la contraparte del modo de
selección múltiple del frontend (mantener apretado un fic en una lista para
elegir varios y aplicarles algo junto). Reusa la misma lógica que ya existe
para un solo fic, pero de manera que un solo pedido HTTP alcance para todos
en vez de que el frontend tenga que mandar N pedidos sueltos."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Coleccion, EtiquetaPersonal, Fic, Lectura
from app.schemas import ESTADOS_LECTURA

router = APIRouter(prefix="/masivo", tags=["masivo"])


class LecturasMasivoRequest(BaseModel):
    fic_ids: list[int] = Field(min_length=1)
    estado: str


@router.post("/lecturas")
def actualizar_lecturas_masivo(payload: LecturasMasivoRequest, db: Session = Depends(get_session)):
    if payload.estado not in ESTADOS_LECTURA:
        return {"actualizados": 0}

    actualizados = 0
    for fic_id in payload.fic_ids:
        fic = db.get(Fic, fic_id)
        if fic is None:
            continue
        ultima = (
            db.query(Lectura)
            .filter(Lectura.fic_id == fic_id)
            .order_by(Lectura.id.desc())
            .first()
        )
        if ultima is not None:
            ultima.estado = payload.estado
        else:
            db.add(Lectura(fic_id=fic_id, estado=payload.estado))
        actualizados += 1
    db.commit()
    return {"actualizados": actualizados}


class EtiquetaMasivoRequest(BaseModel):
    fic_ids: list[int] = Field(min_length=1)
    nombre: str


@router.post("/etiquetas")
def agregar_etiqueta_masivo(payload: EtiquetaMasivoRequest, db: Session = Depends(get_session)):
    nombre = payload.nombre.strip()
    if not nombre:
        return {"actualizados": 0}

    etiqueta = (
        db.query(EtiquetaPersonal)
        .filter(func.lower(EtiquetaPersonal.nombre) == nombre.lower())
        .one_or_none()
    )
    if etiqueta is None:
        etiqueta = EtiquetaPersonal(nombre=nombre)
        db.add(etiqueta)
        db.flush()

    actualizados = 0
    for fic_id in payload.fic_ids:
        fic = db.get(Fic, fic_id)
        if fic is None:
            continue
        if etiqueta not in fic.etiquetas_personales:
            fic.etiquetas_personales.append(etiqueta)
        actualizados += 1
    db.commit()
    return {"actualizados": actualizados}


class ColeccionMasivoRequest(BaseModel):
    fic_ids: list[int] = Field(min_length=1)
    coleccion_id: int


@router.post("/colecciones")
def agregar_a_coleccion_masivo(payload: ColeccionMasivoRequest, db: Session = Depends(get_session)):
    coleccion = db.get(Coleccion, payload.coleccion_id)
    if coleccion is None:
        return {"actualizados": 0}

    actualizados = 0
    for fic_id in payload.fic_ids:
        fic = db.get(Fic, fic_id)
        if fic is None:
            continue
        if fic not in coleccion.fics:
            coleccion.fics.append(fic)
        actualizados += 1
    db.commit()
    return {"actualizados": actualizados}
