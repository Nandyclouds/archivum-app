"""Personalización del perfil: avatar y portada.

No hay usuarios/cuentas (ver Tarea 1) — esto es "cómo se ve mi copia de la
app" (una sola fila de config, `PerfilConfig` id=1), no un perfil social.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_session
from app.models import Coleccion, Fic, PerfilConfig

router = APIRouter(prefix="/perfil", tags=["perfil"])

TIPOS_PERMITIDOS = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
TIPOS_PERMITIDOS_GIF = {"image/gif": ".gif", "image/webp": ".webp"}
TAMANO_MAXIMO_GIF = 25 * 1024 * 1024  # 25MB
TAMANO_MAXIMO = 8 * 1024 * 1024  # 8MB, de sobra para una foto de perfil/portada

# La grilla "Favoritos" del perfil NO es un concepto aparte: apunta a la
# colección "Favoritos" de siempre (la misma que ya existe si alguna vez
# taggeaste bookmarks así en AO3, o que se crea sola la primera vez que
# agregás un fic desde acá). Un fic marcado desde el perfil aparece también
# en Colecciones, y viceversa — una sola lista, no dos que se puedan
# desincronizar.
FAVORITOS_NOMBRE = "Favoritos"
FAVORITOS_VISIBLES = 4


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
        "avatar_posicion": config.avatar_posicion if config else "50% 50%",
        "portada_posicion": config.portada_posicion if config else "50% 50%",
        "cita_texto": config.cita_texto if config else None,
        "cita_fuente": config.cita_fuente if config else None,
        "nombre_usuario": config.nombre_usuario if config else None,
        "handle": config.handle if config else None,
        "pronombres": config.pronombres if config else None,
        "insignia": config.insignia if config else None,
        "bio": config.bio if config else None,
        "tiene_gif1": bool(config and config.gif1_ruta),
        "tiene_gif2": bool(config and config.gif2_ruta),
        "tiene_gif3": bool(config and config.gif3_ruta),
    }


class PerfilUpdate(BaseModel):
    cita_texto: str | None = None
    cita_fuente: str | None = None
    nombre_usuario: str | None = None
    handle: str | None = None
    pronombres: str | None = None
    insignia: str | None = None
    bio: str | None = None


@router.patch("")
def actualizar_perfil(payload: PerfilUpdate, db: Session = Depends(get_session)):
    """Solo toca los campos que vinieron en el pedido (no pisa el resto) —
    así guardar el usuario no borra la cita, y viceversa."""
    config = _get_or_create_config(db)
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        if isinstance(valor, str):
            valor = valor.strip() or None
        setattr(config, campo, valor)
    db.commit()
    return {"ok": True}


class PosicionUpdate(BaseModel):
    x: float = Field(ge=0, le=100)
    y: float = Field(ge=0, le=100)


@router.put("/posicion/{tipo}")
def actualizar_posicion(tipo: str, payload: PosicionUpdate, db: Session = Depends(get_session)):
    if tipo not in ("avatar", "portada"):
        raise HTTPException(status_code=404, detail="Tipo de imagen inválido.")
    config = _get_or_create_config(db)
    setattr(config, f"{tipo}_posicion", f"{payload.x:.1f}% {payload.y:.1f}%")
    db.commit()
    return {"ok": True}


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
    setattr(config, f"{tipo}_posicion", "50% 50%")  # foto nueva, el recorte viejo ya no aplica
    db.commit()


@router.post("/avatar")
async def subir_avatar(archivo: UploadFile = File(...), db: Session = Depends(get_session)):
    await _guardar_imagen(db, "avatar", archivo)
    return {"ok": True}


@router.post("/portada")
async def subir_portada(archivo: UploadFile = File(...), db: Session = Depends(get_session)):
    await _guardar_imagen(db, "portada", archivo)
    return {"ok": True}


async def _guardar_gif(db: Session, indice: int, archivo: UploadFile) -> None:
    if archivo.content_type not in TIPOS_PERMITIDOS_GIF:
        raise HTTPException(status_code=415, detail="Formato no soportado (usá GIF o WEBP).")
    contenido = await archivo.read()
    if len(contenido) > TAMANO_MAXIMO_GIF:
        raise HTTPException(status_code=413, detail="El gif pesa más de 25MB.")

    settings.perfil_dir.mkdir(parents=True, exist_ok=True)
    extension = TIPOS_PERMITIDOS_GIF[archivo.content_type]
    ruta = settings.perfil_dir / f"gif{indice}{extension}"
    ruta.write_bytes(contenido)

    config = _get_or_create_config(db)
    setattr(config, f"gif{indice}_ruta", str(ruta))
    db.commit()


@router.post("/gif/{indice}")
async def subir_gif(indice: int, archivo: UploadFile = File(...), db: Session = Depends(get_session)):
    if indice not in (1, 2, 3):
        raise HTTPException(status_code=404, detail="Índice de gif inválido.")
    await _guardar_gif(db, indice, archivo)
    return {"ok": True}


@router.delete("/gif/{indice}", status_code=204)
def borrar_gif(indice: int, db: Session = Depends(get_session)):
    if indice not in (1, 2, 3):
        raise HTTPException(status_code=404, detail="Índice de gif inválido.")
    config = _get_or_create_config(db)
    ruta_str = getattr(config, f"gif{indice}_ruta", None)
    if ruta_str:
        ruta = Path(ruta_str)
        if ruta.is_file():
            ruta.unlink()
        setattr(config, f"gif{indice}_ruta", None)
        db.commit()


def _get_coleccion_favoritos(db: Session) -> Coleccion | None:
    return db.query(Coleccion).filter_by(nombre=FAVORITOS_NOMBRE).one_or_none()


def _parse_destacados(raw: str | None) -> list[int]:
    if not raw:
        return []
    return [int(x) for x in raw.split(",") if x]


@router.get("/favoritos")
def listar_favoritos(db: Session = Depends(get_session)):
    coleccion = _get_coleccion_favoritos(db)
    if coleccion is None:
        return {"coleccion_id": None, "total": 0, "fics": [], "todos": [], "destacados_ids": []}

    todos = sorted(coleccion.fics, key=lambda f: f.titulo)
    fics_por_id = {f.id: f for f in todos}

    config = db.get(PerfilConfig, 1)
    destacados_ids = _parse_destacados(config.favoritos_destacados if config else None)
    # Ids elegidos a mano que ya no están en la colección (se sacaron del
    # favorito) se ignoran solos acá, sin necesidad de limpiar la config.
    visibles = [fics_por_id[i] for i in destacados_ids if i in fics_por_id]
    if not visibles:
        # Nadie eligió destacados todavía: fallback de siempre, alfabético.
        visibles = todos[:FAVORITOS_VISIBLES]

    return {
        "coleccion_id": coleccion.id,
        "total": len(todos),
        "fics": [{"fic_id": f.id, "titulo": f.titulo, "autor": f.autor} for f in visibles[:FAVORITOS_VISIBLES]],
        "todos": [{"fic_id": f.id, "titulo": f.titulo, "autor": f.autor} for f in todos],
        "destacados_ids": [i for i in destacados_ids if i in fics_por_id],
    }


class DestacadosUpdate(BaseModel):
    fic_ids: list[int]


@router.put("/favoritos/destacados")
def actualizar_destacados(payload: DestacadosUpdate, db: Session = Depends(get_session)):
    """Elige a mano cuáles de los Favoritos se muestran en el grid visible
    (máximo 4). Vacío = volver al fallback alfabético."""
    if len(payload.fic_ids) > FAVORITOS_VISIBLES:
        raise HTTPException(status_code=422, detail=f"Máximo {FAVORITOS_VISIBLES} favoritos destacados.")

    coleccion = _get_coleccion_favoritos(db)
    ids_validos = {f.id for f in coleccion.fics} if coleccion else set()
    if any(fid not in ids_validos for fid in payload.fic_ids):
        raise HTTPException(status_code=422, detail="Todos los ids deben ser fics que ya están en Favoritos.")

    config = _get_or_create_config(db)
    config.favoritos_destacados = ",".join(str(i) for i in payload.fic_ids) or None
    db.commit()
    return {"ok": True}


class FavoritoCreate(BaseModel):
    fic_id: int


@router.post("/favoritos", status_code=201)
def agregar_favorito(payload: FavoritoCreate, db: Session = Depends(get_session)):
    fic = db.get(Fic, payload.fic_id)
    if fic is None:
        raise HTTPException(status_code=404, detail="Fic no encontrado.")

    coleccion = _get_coleccion_favoritos(db)
    if coleccion is None:
        coleccion = Coleccion(nombre=FAVORITOS_NOMBRE, tipo="personalizada")
        db.add(coleccion)
        db.flush()
    if fic in coleccion.fics:
        raise HTTPException(status_code=409, detail="Ese fic ya está en Favoritos.")
    coleccion.fics.append(fic)
    db.commit()
    return {"ok": True}


@router.delete("/favoritos/{fic_id}", status_code=204)
def quitar_favorito(fic_id: int, db: Session = Depends(get_session)):
    coleccion = _get_coleccion_favoritos(db)
    if coleccion is None:
        return
    fic = db.get(Fic, fic_id)
    if fic is not None and fic in coleccion.fics:
        coleccion.fics.remove(fic)
        db.commit()


@router.get("/imagen/{tipo}")
def obtener_imagen(tipo: str, db: Session = Depends(get_session)):
    if tipo not in ("avatar", "portada", "gif1", "gif2", "gif3"):
        raise HTTPException(status_code=404, detail="Tipo de imagen inválido.")
    config = db.get(PerfilConfig, 1)
    ruta_str = getattr(config, f"{tipo}_ruta", None) if config else None
    if not ruta_str:
        raise HTTPException(status_code=404, detail="Todavía no subiste esa imagen.")
    ruta = Path(ruta_str)
    if not ruta.is_file():
        raise HTTPException(status_code=410, detail="La imagen ya no está en el disco.")
    return FileResponse(ruta)
