from __future__ import annotations

import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, aliased

from app.ao3 import downloader
from app.ao3.client import RequestFailedError, SessionRequestLimitReached
from app.api.ao3_session import build_authenticated_client
from app.api.serializers import to_archivo_out, to_detail, to_list_item
from app.config import settings
from app.database import get_session
from app.models import (
    ColeccionFic,
    EtiquetaPersonal,
    Fandom,
    Fic,
    FicEtiquetaPersonal,
    Lectura,
    Personaje,
    Resena,
    ResenaImagen,
    Ship,
    TagAdicional,
)
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
    ship: list[str] = Query([], description="Nombre(s) exacto(s) de relationship (OR si hay varios)"),
    personaje: list[str] = Query([], description="Nombre(s) exacto(s) de personaje (OR si hay varios)"),
    tag: list[str] = Query([], description="Nombre(s) exacto(s) de tag adicional (OR si hay varios)"),
    rating: str | None = Query(None, description="Rating exacto de AO3 (ej. 'Explicit')"),
    warning: str | None = Query(None, description="Un warning exacto de AO3 (ej. 'Major Character Death')"),
    categoria: str | None = Query(None, description="Categoría exacta de AO3 (ej. 'F/F')"),
    idioma: str | None = Query(None, description="Idioma exacto de AO3 (ej. 'English')"),
    etiqueta: str | None = Query(None, description="Nombre exacto de etiqueta personal"),
    coleccion: int | None = Query(None, description="Id de colección"),
    estado: str | None = Query(None, description="Estado de la lectura más reciente"),
    completo: bool | None = Query(None, description="Filtra por fic.complete (True=completos, False=WIP)"),
    con_nota: bool = Query(False, description="Si es True, solo fics con nota_bookmark"),
    rating_exacto: float | None = Query(None, ge=1, le=5, description="Solo fics con alguna reseña de exactamente este puntaje"),
    hizo_llorar: bool = Query(False, description="Si es True, solo fics con alguna reseña marcada 'me hizo llorar'"),
    es_relectura: bool = Query(False, description="Si es True, solo fics con al menos una relectura registrada"),
    con_resena: bool | None = Query(
        None, description="True = solo fics con alguna reseña propia, False = solo sin reseña"
    ),
    anio: int | None = Query(None, description="Restringe a fics con una lectura 'leido' completada este año"),
    leido_desde: datetime.date | None = Query(None, description="Solo fics leídos (fecha_fin) desde esta fecha"),
    leido_hasta: datetime.date | None = Query(None, description="Solo fics leídos (fecha_fin) hasta esta fecha"),
    agregado_desde: datetime.date | None = Query(None, description="Solo fics agregados a la biblioteca desde esta fecha"),
    agregado_hasta: datetime.date | None = Query(None, description="Solo fics agregados a la biblioteca hasta esta fecha"),
    incluir_borrados: bool = False,
    orden: str = Query(
        "titulo",
        description="'titulo' (alfabético), 'ultima_lectura' (más reciente primero), "
        "'recientes' (agregados a la biblioteca más recientemente primero) o "
        "'palabras' (más palabras primero)",
    ),
    limit: int = Query(50, le=1000),
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
    # .any(Modelo.nombre.in_(lista)): "el fic tiene AL MENOS UNO de estos"
    # (OR entre los valores elegidos) — no uno .any() por valor, que sería AND
    # (exigiría tenerlos todos a la vez).
    if ship:
        query = query.filter(Fic.ships.any(Ship.nombre.in_(ship)))
    if personaje:
        query = query.filter(Fic.personajes.any(Personaje.nombre.in_(personaje)))
    if tag:
        query = query.filter(Fic.tags_adicionales.any(TagAdicional.nombre.in_(tag)))
    if rating:
        query = query.filter(Fic.rating == rating)
    if warning:
        # categorias/warnings son "A|B|C" en texto (ver models.py) — un LIKE
        # simple podría matchear una subcadena de otro warning por error, así
        # que se busca el segmento exacto entre delimitadores "|".
        query = query.filter(func.instr("|" + Fic.warnings + "|", f"|{warning}|") > 0)
    if categoria:
        query = query.filter(func.instr("|" + Fic.categorias + "|", f"|{categoria}|") > 0)
    if idioma:
        query = query.filter(Fic.idioma == idioma)
    if con_nota:
        query = query.filter(Fic.nota_bookmark.isnot(None))
    if rating_exacto is not None:
        query = query.filter(Fic.resenas.any(Resena.rating == rating_exacto))
    if hizo_llorar:
        query = query.filter(Fic.resenas.any(Resena.hizo_llorar.is_(True)))
    if es_relectura:
        query = query.filter(Fic.lecturas.any(Lectura.es_relectura.is_(True)))
    if con_resena is True:
        query = query.filter(Fic.resenas.any())
    elif con_resena is False:
        query = query.filter(~Fic.resenas.any())
    if etiqueta:
        query = query.join(Fic.etiquetas_personales).filter(EtiquetaPersonal.nombre == etiqueta)
    if coleccion is not None:
        query = query.join(ColeccionFic, ColeccionFic.fic_id == Fic.id).filter(
            ColeccionFic.coleccion_id == coleccion
        )
    if completo is not None:
        query = query.filter(Fic.complete == completo)
    if anio is not None:
        # .distinct(): si releíste el mismo fic dos veces en el mismo año, el
        # join a Lectura lo traería duplicado.
        query = query.join(Lectura, Lectura.fic_id == Fic.id).filter(
            Lectura.estado == "leido",
            func.strftime("%Y", Lectura.fecha_fin) == str(anio),
        ).distinct()
    if leido_desde is not None or leido_hasta is not None:
        # Alias propio: si ya se hizo join a Lectura más arriba (por "anio"),
        # un segundo join sin alias pisaría las condiciones en vez de sumarse.
        LecturaLeida = aliased(Lectura)
        condiciones = [LecturaLeida.estado == "leido"]
        if leido_desde is not None:
            condiciones.append(LecturaLeida.fecha_fin >= leido_desde)
        if leido_hasta is not None:
            condiciones.append(LecturaLeida.fecha_fin <= leido_hasta)
        query = query.join(LecturaLeida, LecturaLeida.fic_id == Fic.id).filter(*condiciones).distinct()
    if agregado_desde is not None:
        query = query.filter(Fic.fecha_primer_import >= agregado_desde)
    if agregado_hasta is not None:
        # fecha_primer_import es datetime; sumamos un día para que "hasta
        # el 10" incluya todo el 10, no solo hasta las 00:00.
        query = query.filter(
            Fic.fecha_primer_import < agregado_hasta + datetime.timedelta(days=1)
        )
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
    if orden == "recientes":
        query = query.order_by(Fic.fecha_primer_import.desc())
    elif orden == "palabras":
        query = query.order_by(Fic.word_count.desc())
    elif orden == "ultima_lectura":
        ultimas_fechas = (
            db.query(Lectura.fic_id, func.max(Lectura.fecha_fin).label("ultima_fecha"))
            .group_by(Lectura.fic_id)
            .subquery()
        )
        query = query.outerjoin(ultimas_fechas, ultimas_fechas.c.fic_id == Fic.id).order_by(
            ultimas_fechas.c.ultima_fecha.desc().nulls_last(), Fic.titulo
        )
    else:
        query = query.order_by(Fic.titulo)

    fics = query.offset(offset).limit(limit).all()
    return [to_list_item(f) for f in fics]


# Vocabulario cerrado de AO3 para rating/warnings/categorias — hardcodeado
# porque el orden importa para que se vea como en AO3 (rating de más suave a
# más fuerte) y porque conviene mostrar las opciones aunque la biblioteca
# todavía no tenga ningún fic con ese valor.
RATINGS_AO3 = [
    "Not Rated",
    "General Audiences",
    "Teen And Up Audiences",
    "Mature",
    "Explicit",
]
WARNINGS_AO3 = [
    "No Archive Warnings Apply",
    "Creator Chose Not To Use Archive Warnings",
    "Graphic Depictions Of Violence",
    "Major Character Death",
    "Rape/Non-Con",
    "Underage",
]
CATEGORIAS_AO3 = ["F/F", "F/M", "Gen", "M/M", "Multi", "Other"]


@router.get("/opciones-filtro")
def opciones_filtro(db: Session = Depends(get_session)):
    """Valores disponibles para los filtros de Buscar: fijos para rating/
    warnings/categorías (vocabulario cerrado de AO3), sacados de la
    biblioteca para personajes/tags/idiomas (vocabulario abierto, no tiene
    sentido hardcodearlo)."""
    ships = [n for (n,) in db.query(Ship.nombre).order_by(Ship.nombre).all()]
    personajes = [
        n for (n,) in db.query(Personaje.nombre).order_by(Personaje.nombre).all()
    ]
    tags = [n for (n,) in db.query(TagAdicional.nombre).order_by(TagAdicional.nombre).all()]
    idiomas = [
        n
        for (n,) in db.query(Fic.idioma).filter(Fic.idioma.isnot(None)).distinct().order_by(Fic.idioma).all()
    ]
    return {
        "ratings": RATINGS_AO3,
        "warnings": WARNINGS_AO3,
        "categorias": CATEGORIAS_AO3,
        "ships": ships,
        "personajes": personajes,
        "tags": tags,
        "idiomas": idiomas,
    }


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


TIPOS_PERMITIDOS_IMAGEN_RESENA = {
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/jpeg": ".jpg",
}
TAMANO_MAXIMO_IMAGEN_RESENA = 15 * 1024 * 1024
MAX_IMAGENES_POR_RESENA = 6


@router.post("/{fic_id}/resenas/{resena_id}/imagenes", status_code=201)
async def subir_imagen_resena(
    fic_id: int, resena_id: int, archivo: UploadFile = File(...), db: Session = Depends(get_session)
):
    resena = _get_resena_or_404(db, fic_id, resena_id)
    if len(resena.imagenes) >= MAX_IMAGENES_POR_RESENA:
        raise HTTPException(status_code=422, detail=f"Máximo {MAX_IMAGENES_POR_RESENA} imágenes por reseña.")
    if archivo.content_type not in TIPOS_PERMITIDOS_IMAGEN_RESENA:
        raise HTTPException(status_code=415, detail="Formato no soportado (usá PNG, WEBP, GIF o JPG).")
    contenido = await archivo.read()
    if len(contenido) > TAMANO_MAXIMO_IMAGEN_RESENA:
        raise HTTPException(status_code=413, detail="La imagen pesa más de 15MB.")

    settings.resenas_dir.mkdir(parents=True, exist_ok=True)
    extension = TIPOS_PERMITIDOS_IMAGEN_RESENA[archivo.content_type]
    siguiente_orden = len(resena.imagenes)
    ruta = settings.resenas_dir / f"{resena_id}_{siguiente_orden}{extension}"
    ruta.write_bytes(contenido)

    imagen = ResenaImagen(resena_id=resena_id, ruta_archivo=str(ruta), orden=siguiente_orden)
    db.add(imagen)
    db.commit()
    db.refresh(resena)
    return ResenaOut.model_validate(resena)


@router.delete("/{fic_id}/resenas/{resena_id}/imagenes/{imagen_id}", status_code=204)
def borrar_imagen_resena(fic_id: int, resena_id: int, imagen_id: int, db: Session = Depends(get_session)):
    _get_resena_or_404(db, fic_id, resena_id)
    imagen = db.get(ResenaImagen, imagen_id)
    if imagen is None or imagen.resena_id != resena_id:
        return
    ruta = Path(imagen.ruta_archivo)
    if ruta.is_file():
        ruta.unlink()
    db.delete(imagen)
    db.commit()


@router.get("/{fic_id}/resenas/{resena_id}/imagenes/{imagen_id}")
def obtener_imagen_resena(fic_id: int, resena_id: int, imagen_id: int, db: Session = Depends(get_session)):
    _get_resena_or_404(db, fic_id, resena_id)
    imagen = db.get(ResenaImagen, imagen_id)
    if imagen is None or imagen.resena_id != resena_id:
        raise HTTPException(status_code=404, detail="Imagen no encontrada.")
    ruta = Path(imagen.ruta_archivo)
    if not ruta.is_file():
        raise HTTPException(status_code=410, detail="El archivo ya no está en el disco.")
    return FileResponse(ruta)


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

    # Case-insensitive: "Fluff" y "fluff" tienen que ser la misma etiqueta,
    # no dos separadas por un error de tipeo.
    etiqueta = (
        db.query(EtiquetaPersonal)
        .filter(func.lower(EtiquetaPersonal.nombre) == nombre.lower())
        .one_or_none()
    )
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
