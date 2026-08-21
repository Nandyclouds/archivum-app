from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import EtiquetaPersonal
from app.schemas import EtiquetaPersonalOut

router = APIRouter(prefix="/etiquetas", tags=["etiquetas"])


@router.get("", response_model=list[EtiquetaPersonalOut])
def listar_etiquetas(db: Session = Depends(get_session)):
    return db.query(EtiquetaPersonal).order_by(EtiquetaPersonal.nombre).all()


@router.delete("/{etiqueta_id}", status_code=204)
def borrar_etiqueta(etiqueta_id: int, db: Session = Depends(get_session)):
    """Borra la etiqueta entera (de todos los fics que la tengan), no solo de uno."""
    etiqueta = db.get(EtiquetaPersonal, etiqueta_id)
    if etiqueta is None:
        raise HTTPException(status_code=404, detail="Etiqueta no encontrada")
    db.delete(etiqueta)
    db.commit()
