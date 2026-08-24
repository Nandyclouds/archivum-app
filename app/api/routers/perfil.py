"""Personalización del perfil: avatar y portada.

No hay usuarios/cuentas (ver Tarea 1) — esto es "cómo se ve mi copia de la
app" (una sola fila de config, `PerfilConfig` id=1), no un perfil social.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_session
from app.models import PerfilConfig

router = APIRouter(prefix="/perfil", tags=["perfil"])

TIPOS_PERMITIDOS = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
TAMANO_MAXIMO = 8 * 1024 * 1024  # 8MB, de sobra para una foto de perfil/portada


def _get_or_create_config(db: Session) -> PerfilConfig:
    config = db.get(PerfilConfig, 1)
    if config is None:
        config = PerfilConfig(id=1)
        db.add(config)
        db.flush()
    return config


@router.get("")
def obtener_perfil(db: Session = Depends(get_session)):
    config = db.get(PerfilConfig, 1)
    return {
        "tiene_avatar": bool(config and config.avatar_ruta),
        "tiene_portada": bool(config and config.portada_ruta),
    }


async def _guardar_imagen(db: Session, tipo: str, archivo: UploadFile) -> None:
    if archivo.content_type not in TIPOS_PERMITIDOS:
        raise HTTPException(status_code=415, detail="Formato no soportado (usá JPG, PNG o WEBP).")
    contenido = await archivo.read()
    if len(contenido) > TAMANO_MAXIMO:
        raise HTTPException(status_code=413, detail="La imagen pesa más de 8MB.")

    settings.perfil_dir.mkdir(parents=True, exist_ok=True)
    extension = TIPOS_PERMITIDOS[archivo.content_type]
    ruta = settings.perfil_dir / f"{tipo}{extension}"
    ruta.write_bytes(contenido)

    config = _get_or_create_config(db)
    setattr(config, f"{tipo}_ruta", str(ruta))
    db.commit()


@router.post("/avatar")
async def subir_avatar(archivo: UploadFile = File(...), db: Session = Depends(get_session)):
    await _guardar_imagen(db, "avatar", archivo)
    return {"ok": True}


@router.post("/portada")
async def subir_portada(archivo: UploadFile = File(...), db: Session = Depends(get_session)):
    await _guardar_imagen(db, "portada", archivo)
    return {"ok": True}


@router.get("/imagen/{tipo}")
def obtener_imagen(tipo: str, db: Session = Depends(get_session)):
    if tipo not in ("avatar", "portada"):
        raise HTTPException(status_code=404, detail="Tipo de imagen inválido.")
    config = db.get(PerfilConfig, 1)
    ruta_str = getattr(config, f"{tipo}_ruta", None) if config else None
    if not ruta_str:
        raise HTTPException(status_code=404, detail="Todavía no subiste esa imagen.")
    ruta = Path(ruta_str)
    if not ruta.is_file():
        raise HTTPException(status_code=410, detail="La imagen ya no está en el disco.")
    return FileResponse(ruta)
