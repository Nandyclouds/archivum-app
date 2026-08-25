"""Bandeja de "Novedades": cambios detectados en fics ya conocidos al
volver a pedirle la página a AO3 (capítulo nuevo, se completó). Se generan
en app/ao3/importer.py (_detectar_novedades) durante un sync normal — este
router es solo lectura/lo de marcar leída."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.serializers import to_novedad_out
from app.database import get_session
from app.models import Novedad
from app.schemas import NovedadOut

router = APIRouter(prefix="/novedades", tags=["novedades"])


@router.get("", response_model=list[NovedadOut])
def listar_novedades(solo_no_leidas: bool = True, db: Session = Depends(get_session)):
    query = db.query(Novedad)
    if solo_no_leidas:
        query = query.filter(Novedad.leida.is_(False))
    novedades = query.order_by(Novedad.detectado_en.desc()).all()
    return [to_novedad_out(n) for n in novedades]


@router.post("/{novedad_id}/marcar-leida", response_model=NovedadOut)
def marcar_leida(novedad_id: int, db: Session = Depends(get_session)):
    novedad = db.get(Novedad, novedad_id)
    if novedad is None:
        raise HTTPException(status_code=404, detail="Novedad no encontrada")
    novedad.leida = True
    db.commit()
    return to_novedad_out(novedad)


@router.post("/marcar-todas-leidas")
def marcar_todas_leidas(db: Session = Depends(get_session)):
    db.query(Novedad).filter(Novedad.leida.is_(False)).update({"leida": True})
    db.commit()
    return {"ok": True}
