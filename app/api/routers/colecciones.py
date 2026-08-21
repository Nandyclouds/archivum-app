from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Coleccion, Fic
from app.schemas import ColeccionCreate, ColeccionOut, ColeccionUpdate

router = APIRouter(prefix="/colecciones", tags=["colecciones"])


def _to_out(coleccion: Coleccion) -> ColeccionOut:
    return ColeccionOut(
        id=coleccion.id,
        nombre=coleccion.nombre,
        descripcion=coleccion.descripcion,
        color=coleccion.color,
        orden=coleccion.orden,
        tipo=coleccion.tipo,
        cantidad_fics=len(coleccion.fics),
    )


def _get_coleccion_or_404(db: Session, coleccion_id: int) -> Coleccion:
    coleccion = db.get(Coleccion, coleccion_id)
    if coleccion is None:
        raise HTTPException(status_code=404, detail="Colección no encontrada")
    return coleccion


@router.get("", response_model=list[ColeccionOut])
def listar_colecciones(db: Session = Depends(get_session)):
    colecciones = db.query(Coleccion).order_by(Coleccion.orden, Coleccion.nombre).all()
    return [_to_out(c) for c in colecciones]


@router.get("/{coleccion_id}", response_model=ColeccionOut)
def obtener_coleccion(coleccion_id: int, db: Session = Depends(get_session)):
    return _to_out(_get_coleccion_or_404(db, coleccion_id))


@router.post("", response_model=ColeccionOut, status_code=201)
def crear_coleccion(payload: ColeccionCreate, db: Session = Depends(get_session)):
    coleccion = Coleccion(**payload.model_dump(), tipo="personalizada")
    db.add(coleccion)
    db.commit()
    db.refresh(coleccion)
    return _to_out(coleccion)


@router.patch("/{coleccion_id}", response_model=ColeccionOut)
def actualizar_coleccion(coleccion_id: int, payload: ColeccionUpdate, db: Session = Depends(get_session)):
    coleccion = _get_coleccion_or_404(db, coleccion_id)
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(coleccion, campo, valor)
    db.commit()
    db.refresh(coleccion)
    return _to_out(coleccion)


@router.delete("/{coleccion_id}", status_code=204)
def borrar_coleccion(coleccion_id: int, db: Session = Depends(get_session)):
    coleccion = _get_coleccion_or_404(db, coleccion_id)
    db.delete(coleccion)
    db.commit()


@router.put("/{coleccion_id}/fics/{fic_id}", status_code=204)
def agregar_fic(coleccion_id: int, fic_id: int, db: Session = Depends(get_session)):
    coleccion = _get_coleccion_or_404(db, coleccion_id)
    fic = db.get(Fic, fic_id)
    if fic is None:
        raise HTTPException(status_code=404, detail="Fic no encontrado")
    if fic not in coleccion.fics:
        coleccion.fics.append(fic)
        db.commit()


@router.delete("/{coleccion_id}/fics/{fic_id}", status_code=204)
def quitar_fic(coleccion_id: int, fic_id: int, db: Session = Depends(get_session)):
    coleccion = _get_coleccion_or_404(db, coleccion_id)
    fic = db.get(Fic, fic_id)
    if fic is not None and fic in coleccion.fics:
        coleccion.fics.remove(fic)
        db.commit()
