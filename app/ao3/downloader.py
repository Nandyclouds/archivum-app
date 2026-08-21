"""Descarga el EPUB que AO3 ya ofrece para cada fic y lo registra en `archivos`.

El link de descarga incluye un timestamp (?updated_at=...) que puede quedar
viejo, así que siempre se vuelve a pedir la página del fic para sacar el link
vigente en vez de guardar uno cacheado. Mismo cliente rate-limitado que el
resto del importador — nada de esto pega a la red por fuera de él.
"""

from __future__ import annotations

import datetime
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from app.ao3.client import RateLimitedClient, SessionRequestLimitReached
from app.ao3.importer import WORK_URL
from app.ao3.parser import parse_work_page
from app.models import Archivo, Fic


class DownloadError(Exception):
    pass


class NoEpubDisponibleError(DownloadError):
    def __init__(self, ao3_id: str):
        self.ao3_id = ao3_id
        super().__init__(
            f"AO3 no ofrece EPUB para el fic {ao3_id} (puede ser un formato no "
            "disponible para esta obra)."
        )


@dataclass
class DownloadRunResult:
    descargados: int = 0
    errores: int = 0
    detalles_error: list[str] = field(default_factory=list)
    detenido_por_limite: bool = False


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def download_fic_epub(
    db: Session, client: RateLimitedClient, fic: Fic, archivo_dir: Path
) -> Archivo:
    if fic.deleted_detected_at is not None:
        raise DownloadError(
            f"El fic {fic.ao3_id} está marcado como borrado en AO3; no se puede volver a descargar."
        )

    page_response = client.get(WORK_URL.format(ao3_id=fic.ao3_id))
    page_response.raise_for_status()
    parsed = parse_work_page(page_response.text, fic.ao3_id)
    if parsed.epub_url is None:
        raise NoEpubDisponibleError(fic.ao3_id)

    epub_response = client.get(parsed.epub_url)
    epub_response.raise_for_status()
    content = epub_response.content

    archivo_dir.mkdir(parents=True, exist_ok=True)
    ruta = archivo_dir / f"{fic.ao3_id}.epub"
    ruta.write_bytes(content)

    archivo = db.query(Archivo).filter_by(fic_id=fic.id, formato="epub").one_or_none()
    if archivo is None:
        archivo = Archivo(fic_id=fic.id, formato="epub")
        db.add(archivo)

    archivo.ruta_local = str(ruta)
    archivo.hash_sha256 = hashlib.sha256(content).hexdigest()
    archivo.tamano = len(content)
    archivo.fecha_descarga = _utcnow()

    db.flush()
    return archivo


def download_all_unarchived(
    db: Session, client: RateLimitedClient, archivo_dir: Path
) -> DownloadRunResult:
    ya_archivados = db.query(Archivo.fic_id).filter_by(formato="epub").subquery()
    fics = (
        db.query(Fic)
        .filter(Fic.deleted_detected_at.is_(None))
        .filter(~Fic.id.in_(db.query(ya_archivados.c.fic_id)))
        .all()
    )

    result = DownloadRunResult()
    try:
        for fic in fics:
            try:
                download_fic_epub(db, client, fic, archivo_dir)
                db.commit()
                result.descargados += 1
            except SessionRequestLimitReached:
                db.rollback()
                raise
            except Exception as exc:  # noqa: BLE001 - un fic con error no debe tumbar toda la descarga
                db.rollback()
                result.errores += 1
                result.detalles_error.append(f"{fic.ao3_id}: {exc}")
    except SessionRequestLimitReached as exc:
        result.detenido_por_limite = True
        result.detalles_error.append(str(exc))

    return result
