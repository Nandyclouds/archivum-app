"""Emojis/stickers personalizados — subís una imagen, le ponés un nombre, y
queda disponible como :nombre: en cualquier texto propio (bio, notas,
reseñas...) vía <ConEmoji> del lado del frontend. Mismo patrón de guardado
en disco que el avatar/portada del perfil (ver perfil.py)."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_session
from app.models import EmojiPersonalizado
from app.schemas import EmojiPersonalizadoOut

router = APIRouter(prefix="/emojis", tags=["emojis"])

TIPOS_PERMITIDOS = {
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/jpeg": ".jpg",
    "image/svg+xml": ".svg",
}
TAMANO_MAXIMO = 2 * 1024 * 1024  # 2MB, de sobra para un sticker chiquito
NOMBRE_VALIDO = re.compile(r"^[a-z0-9_]{2,30}$")


@router.get("", response_model=list[EmojiPersonalizadoOut])
def listar(db: Session = Depends(get_session)):
    return db.query(EmojiPersonalizado).order_by(EmojiPersonalizado.nombre).all()


@router.post("", response_model=EmojiPersonalizadoOut, status_code=201)
async def crear(
    nombre: str = Form(...),
    archivo: UploadFile = File(...),
    db: Session = Depends(get_session),
):
    nombre = nombre.strip().lower()
    if not NOMBRE_VALIDO.match(nombre):
        raise HTTPException(
            status_code=422,
            detail="El nombre solo puede tener minúsculas, números y guion bajo (2 a 30 caracteres).",
        )
    if db.query(EmojiPersonalizado).filter_by(nombre=nombre).one_or_none():
        raise HTTPException(status_code=409, detail=f"Ya existe un emoji :{nombre}:.")
    if archivo.content_type not in TIPOS_PERMITIDOS:
        raise HTTPException(status_code=415, detail="Formato no soportado (usá PNG, WEBP, GIF, JPG o SVG).")

    contenido = await archivo.read()
    if len(contenido) > TAMANO_MAXIMO:
        raise HTTPException(status_code=413, detail="La imagen pesa más de 2MB.")

    settings.emojis_dir.mkdir(parents=True, exist_ok=True)
    extension = TIPOS_PERMITIDOS[archivo.content_type]
    ruta = settings.emojis_dir / f"{nombre}{extension}"
    ruta.write_bytes(contenido)

    emoji = EmojiPersonalizado(nombre=nombre, ruta_archivo=str(ruta))
    db.add(emoji)
    db.commit()
    db.refresh(emoji)
    return emoji


@router.delete("/{emoji_id}", status_code=204)
def borrar(emoji_id: int, db: Session = Depends(get_session)):
    emoji = db.get(EmojiPersonalizado, emoji_id)
    if emoji is None:
        return
    ruta = Path(emoji.ruta_archivo)
    if ruta.is_file():
        ruta.unlink()
    db.delete(emoji)
    db.commit()


@router.get("/{emoji_id}/imagen")
def obtener_imagen(emoji_id: int, db: Session = Depends(get_session)):
    emoji = db.get(EmojiPersonalizado, emoji_id)
    if emoji is None:
        raise HTTPException(status_code=404, detail="Emoji no encontrado.")
    ruta = Path(emoji.ruta_archivo)
    if not ruta.is_file():
        raise HTTPException(status_code=410, detail="El archivo ya no está en el disco.")
    return FileResponse(ruta)
