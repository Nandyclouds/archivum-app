"""Listas de fics para recomendar por link público — ver ListaRecomendada en
models.py. Los endpoints de creación/listado/borrado piden el token de
usuario normal (misma auth que el resto de /api); GET /{token} es la
excepción pública, habilitada en app/main.py, porque quien recibe el link
no tiene ese token."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Fic, ListaRecomendada, ListaRecomendadaFic
from app.schemas import ListaRecomendadaCreate, ListaRecomendadaDetalle, ListaRecomendadaOut

router = APIRouter(prefix="/recomendaciones", tags=["recomendaciones"])


def _a_resumen(lista: ListaRecomendada) -> ListaRecomendadaOut:
    return ListaRecomendadaOut(
        id=lista.id,
        token=lista.token,
        titulo=lista.titulo,
        nota=lista.nota,
        creado_en=lista.creado_en,
        cantidad_fics=len(lista.fics),
    )


@router.get("", response_model=list[ListaRecomendadaOut])
def listar(db: Session = Depends(get_session)):
    listas = db.query(ListaRecomendada).order_by(ListaRecomendada.creado_en.desc()).all()
    return [_a_resumen(l) for l in listas]


@router.post("", response_model=ListaRecomendadaOut, status_code=201)
def crear(payload: ListaRecomendadaCreate, db: Session = Depends(get_session)):
    fics_por_id = {
        fic.id: fic for fic in db.query(Fic).filter(Fic.id.in_(payload.fic_ids)).all()
    }
    if not fics_por_id:
        raise HTTPException(status_code=400, detail="Ningún fic válido en la selección")

    lista = ListaRecomendada(
        token=secrets.token_urlsafe(9), titulo=payload.titulo, nota=payload.nota
    )
    db.add(lista)
    db.flush()

    orden = 0
    for fic_id in payload.fic_ids:
        fic = fics_por_id.get(fic_id)
        if fic is None:
            continue
        db.add(ListaRecomendadaFic(lista_id=lista.id, fic_id=fic.id, orden=orden))
        orden += 1

    db.commit()
    db.refresh(lista)
    return _a_resumen(lista)


@router.get("/{token}", response_model=ListaRecomendadaDetalle)
def obtener_publica(token: str, db: Session = Depends(get_session)):
    lista = db.query(ListaRecomendada).filter(ListaRecomendada.token == token).one_or_none()
    if lista is None:
        raise HTTPException(status_code=404, detail="Lista no encontrada")
    return ListaRecomendadaDetalle(
        token=lista.token,
        titulo=lista.titulo,
        nota=lista.nota,
        creado_en=lista.creado_en,
        fics=lista.fics,
    )


@router.delete("/{lista_id}", status_code=204)
def borrar(lista_id: int, db: Session = Depends(get_session)):
    lista = db.get(ListaRecomendada, lista_id)
    if lista is None:
        raise HTTPException(status_code=404, detail="Lista no encontrada")
    db.delete(lista)
    db.commit()
