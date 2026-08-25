"""Conversión de modelos ORM a schemas de respuesta, compartida entre routers."""

from __future__ import annotations

from pathlib import Path

from app.models import Archivo, Fic
from app.schemas import ArchivoOut, FicDetail, FicListItem


def estado_actual(fic: Fic) -> str | None:
    if not fic.lecturas:
        return None
    return max(fic.lecturas, key=lambda l: l.id).estado


def to_list_item(fic: Fic) -> FicListItem:
    item = FicListItem.model_validate(fic)
    item.estado_actual = estado_actual(fic)
    return item


def to_detail(fic: Fic) -> FicDetail:
    detail = FicDetail.model_validate(fic)
    detail.estado_actual = estado_actual(fic)
    return detail


def to_archivo_out(archivo: Archivo) -> ArchivoOut:
    return ArchivoOut(
        id=archivo.id,
        fic_id=archivo.fic_id,
        formato=archivo.formato,
        ruta_local=archivo.ruta_local,
        hash_sha256=archivo.hash_sha256,
        tamano=archivo.tamano,
        fecha_descarga=archivo.fecha_descarga,
        fic_titulo=archivo.fic.titulo,
        fic_url=archivo.fic.url,
        fic_deleted_detected_at=archivo.fic.deleted_detected_at,
        existe_en_disco=Path(archivo.ruta_local).is_file(),
    )
