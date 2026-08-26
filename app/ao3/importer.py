"""Orquesta el import: pagina bookmarks/historial, trae cada fic, lo guarda.

Diseño de resumibilidad: no hay un archivo de checkpoint aparte. La propia
tabla `fics` (columna `ultima_revision`) es el estado de progreso. Si el
proceso se corta a mitad, correr el mismo comando de nuevo vuelve a recorrer
las páginas de listado (barato: una petición por página) pero salta cada fic
ya importado recientemente sin pedirlo de nuevo. Es más simple y más
correcto que un checkpoint de "última página", que además se invalidaría
solo si el orden de bookmarks/historial cambia entre corridas.

Nota de diseño: el historial de AO3 ("readings") es historial de *visitas* a
la página, no de lectura terminada — abrir un fic ya lo cuenta ahí, aunque no
se haya leído. `import history` por eso solo puebla el catálogo de fics
(tabla `fics`), nunca `lecturas`.

El estado de lectura (leído/pendiente/abandonado) sale de `import bookmarks`,
interpretando los bookmark tags de la usuaria (ver `reading_status.py`):
"Leídos <año>" -> lectura terminada, "por leer" -> pendiente, y cualquier
otro tag (favoritos, apodos de fandom/ship, etc.) se guarda como colección
personal en vez de perderse.

Archivado automático: cada vez que se pide la página completa de un fic (fic
nuevo, o refresco por --force/vencimiento), el HTML de esa respuesta ya lo
tenemos en memoria — así que de paso se guarda una copia cruda en
data/archivo/{ao3_id}.html y se registra en `archivos` (formato "html"), sin
pedir nada extra a AO3. Es la protección real contra "el autor borró su
fic": no depende de que la usuaria se acuerde de correr `download` a mano.
"""

from __future__ import annotations

import datetime
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.ao3.client import RateLimitedClient, RequestFailedError, SessionRequestLimitReached
from app.ao3.parser import (
    BookmarkItem,
    BookmarksPage,
    ListingPage,
    ParsedFic,
    infer_ship_tipo,
    parse_bookmarks_page,
    parse_history_page,
    parse_work_page,
)
from app.ao3.reading_status import clasificar_tags
from app.config import settings
from app.models import Archivo, Coleccion, Fandom, Fic, Lectura, Novedad, Personaje, Ship, TagAdicional

WORK_URL = "https://archiveofourown.org/works/{ao3_id}?view_adult=true&view_full_work=true"
BOOKMARKS_URL = "https://archiveofourown.org/users/{username}/bookmarks?page={page}"
HISTORY_URL = "https://archiveofourown.org/users/{username}/readings?page={page}"
# "Marked for Later" no es un bookmark tag: es un botón aparte en la página
# de cada work, y AO3 lo expone como un filtro de la propia History
# (?show=to-read), no una entrada nueva del menú. Mismo listado/parser que
# HISTORY_URL (misma estructura de <li>), solo cambia el filtro server-side.
HISTORY_MARKED_URL = "https://archiveofourown.org/users/{username}/readings?show=to-read&page={page}"
# Las suscripciones son otra cosa aparte de los bookmarks: podés suscribirte
# a un fic sin bookmarkearlo (o al revés). AO3 las lista en su propia
# página, mezcladas con suscripciones a series/autores — parse_subscriptions_page
# ya filtra esas últimas porque no tienen link a /works/.
SUBSCRIPTIONS_URL = "https://archiveofourown.org/users/{username}/subscriptions?page={page}"

DEFAULT_STALE_DAYS = 30


@dataclass
class ImportRunResult:
    tipo: str
    fics_nuevos: int = 0
    fics_actualizados: int = 0
    fics_sin_cambios: int = 0
    errores: int = 0
    detalles_error: list[str] = field(default_factory=list)
    detenido_por_limite: bool = False


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def _get_or_create(db: Session, model, nombre: str, **extra):
    obj = db.query(model).filter_by(nombre=nombre).one_or_none()
    if obj is None:
        obj = model(nombre=nombre, **extra)
        db.add(obj)
        db.flush()
    return obj


def needs_refresh(fic: Fic | None, *, force: bool, stale_days: int) -> bool:
    if force or fic is None:
        return True
    if fic.deleted_detected_at is not None:
        return False  # ya sabemos que no existe; check-deleted lo reintenta explícitamente
    if fic.ultima_revision is None:
        return True
    edad = _utcnow() - fic.ultima_revision
    return edad.days >= stale_days


def _detectar_novedades(db: Session, fic: Fic, parsed: ParsedFic) -> list[str]:
    """Compara el estado viejo del fic contra lo recién parseado, ANTES de
    pisarlo, y deja una Novedad si sumó capítulo(s) o pasó a completo. Se
    llama solo para fics ya conocidos (uno nuevo no tiene "antes" con qué
    comparar) — ver upsert_fic. Devuelve los tipos detectados (para que el
    caller pueda, por ejemplo, mandar un mail con lo que encontró)."""
    tipos = []
    if parsed.chapters_published > fic.chapters_published:
        db.add(
            Novedad(fic_id=fic.id, tipo="capitulo_nuevo", capitulos_publicados=parsed.chapters_published)
        )
        tipos.append("capitulo_nuevo")
    if parsed.complete and not fic.complete:
        db.add(
            Novedad(fic_id=fic.id, tipo="completado", capitulos_publicados=parsed.chapters_published)
        )
        tipos.append("completado")
    return tipos


def upsert_fic(db: Session, parsed: ParsedFic) -> tuple[Fic, bool, list[str]]:
    """Crea o actualiza el Fic y sus relaciones many-to-many. Devuelve
    (fic, es_nuevo, novedades_detectadas)."""

    fic = db.query(Fic).filter_by(ao3_id=parsed.ao3_id).one_or_none()
    es_nuevo = fic is None
    novedades_detectadas: list[str] = []
    if fic is None:
        fic = Fic(ao3_id=parsed.ao3_id, url=WORK_URL.format(ao3_id=parsed.ao3_id))
        db.add(fic)
    else:
        novedades_detectadas = _detectar_novedades(db, fic, parsed)

    fic.titulo = parsed.titulo
    fic.autor = parsed.autor
    fic.autor_url = parsed.autor_url
    fic.word_count = parsed.word_count
    fic.chapters_published = parsed.chapters_published
    fic.chapters_total = parsed.chapters_total
    fic.complete = parsed.complete
    fic.restricted = parsed.restricted
    fic.rating = parsed.rating
    fic.idioma = parsed.idioma
    fic.categorias = "|".join(parsed.categorias) or None
    fic.warnings = "|".join(parsed.warnings) or None
    fic.summary = parsed.summary
    fic.fecha_publicacion = (
        datetime.date.fromisoformat(parsed.fecha_publicacion) if parsed.fecha_publicacion else None
    )
    fic.fecha_actualizacion = (
        datetime.date.fromisoformat(parsed.fecha_actualizacion) if parsed.fecha_actualizacion else None
    )
    fic.ultima_revision = _utcnow()
    fic.deleted_detected_at = None  # si estaba marcado borrado y ahora responde, se desmarca

    fic.fandoms = [_get_or_create(db, Fandom, n) for n in parsed.fandoms]
    fic.personajes = [_get_or_create(db, Personaje, n) for n in parsed.personajes]
    fic.tags_adicionales = [_get_or_create(db, TagAdicional, n) for n in parsed.tags_adicionales]
    fic.ships = [
        _get_or_create(db, Ship, n, tipo=infer_ship_tipo(n)) for n in parsed.ships
    ]

    db.flush()
    return fic, es_nuevo, novedades_detectadas


class FicNotFoundError(Exception):
    def __init__(self, ao3_id: str, fic: Fic | None = None):
        self.ao3_id = ao3_id
        self.fic = fic
        super().__init__(f"El fic {ao3_id} devolvió 404 (puede haber sido borrado).")


def import_single_fic(
    db: Session,
    client: RateLimitedClient,
    ao3_id: str,
    *,
    force: bool = False,
    stale_days: int = DEFAULT_STALE_DAYS,
    archivo_dir: Path | None = None,
) -> tuple[Fic, str]:
    """Importa un fic por ao3_id. Devuelve (fic, 'nuevo' | 'actualizado' | 'cacheado')."""

    existing = db.query(Fic).filter_by(ao3_id=ao3_id).one_or_none()
    if not needs_refresh(existing, force=force, stale_days=stale_days):
        return existing, "cacheado"

    response = client.get(WORK_URL.format(ao3_id=ao3_id))
    if response.status_code == 404:
        if existing is not None:
            existing.deleted_detected_at = _utcnow()
            existing.ultima_revision = _utcnow()
            db.flush()
        raise FicNotFoundError(ao3_id, fic=existing)
    response.raise_for_status()

    parsed = parse_work_page(response.text, ao3_id)
    fic, es_nuevo, _ = upsert_fic(db, parsed)
    guardar_snapshot_html(db, fic, response.text, archivo_dir)
    return fic, ("nuevo" if es_nuevo else "actualizado")


def guardar_snapshot_html(db: Session, fic: Fic, html: str, archivo_dir: Path | None = None) -> Archivo:
    """Guarda una copia cruda del HTML del fic tal como vino de AO3.

    Se pisa el archivo anterior en cada refresco (misma ruta, mismo `formato`
    "html" en `archivos`): no se guarda historial de versiones, solo la
    última copia conocida. Alcanza para el objetivo de "no perder el fic si
    el autor lo borra"; versionado completo sería sobreingeniería acá.
    """
    archivo_dir = archivo_dir or settings.archivo_dir
    archivo_dir.mkdir(parents=True, exist_ok=True)
    contenido = html.encode("utf-8")
    ruta = archivo_dir / f"{fic.ao3_id}.html"
    ruta.write_bytes(contenido)

    archivo = db.query(Archivo).filter_by(fic_id=fic.id, formato="html").one_or_none()
    if archivo is None:
        archivo = Archivo(fic_id=fic.id, formato="html")
        db.add(archivo)
    archivo.ruta_local = str(ruta)
    archivo.hash_sha256 = hashlib.sha256(contenido).hexdigest()
    archivo.tamano = len(contenido)
    archivo.fecha_descarga = _utcnow()
    db.flush()
    return archivo


_SIN_INFO_DE_NOTA = object()  # distingue "no vino de bookmarks" de "vino, y no tiene nota"


def apply_bookmark_tags(
    db: Session, fic: Fic, tags: list[str], bookmarked_at: str | None, nota=_SIN_INFO_DE_NOTA
) -> None:
    """Traduce los bookmark tags de un fic a `lecturas`/`colecciones`, y de
    paso guarda la nota privada del bookmark si mandaron una.

    `nota` solo se pisa si el llamador la pasó explícitamente (viene de la
    página de bookmarks, que es la única que la tiene) — así el sync de
    "Marked for Later"/WIPs, que llama a esta misma función pero sin haber
    visto la página de bookmarks, no borra una nota que ya estaba guardada.

    Idempotente: correr esto de nuevo sobre el mismo fic con los mismos tags
    no duplica filas (se fija si ya existe una lectura 'leido' para ese año,
    una lectura 'pendiente'/'abandonado' para ese fic, o si ya está en la
    colección correspondiente, antes de crear algo).
    """
    if nota is not _SIN_INFO_DE_NOTA:
        fic.nota_bookmark = nota

    if not tags:
        return

    clasificado = clasificar_tags(tags)
    bookmark_date = datetime.date.fromisoformat(bookmarked_at) if bookmarked_at else None

    for idx, anio in enumerate(clasificado.anios_leido):
        ya_existe = (
            db.query(Lectura)
            .filter(Lectura.fic_id == fic.id, Lectura.estado == "leido")
            .filter(func.strftime("%Y", Lectura.fecha_fin) == str(anio))
            .first()
        )
        if ya_existe is not None:
            continue
        # Solo tenemos la fecha exacta de bookmarkeo, no la de lectura. Si su
        # año coincide con este tag, la usamos; si no (releyó en otro año y
        # solo agregó el tag nuevo), aproximamos al 1 de julio de ese año.
        if bookmark_date is not None and bookmark_date.year == anio:
            fecha_fin = bookmark_date
        else:
            fecha_fin = datetime.date(anio, 7, 1)
        db.add(
            Lectura(
                fic_id=fic.id,
                fecha_fin=fecha_fin,
                estado="leido",
                es_relectura=(idx > 0) or clasificado.marca_relectura,
            )
        )

    if not clasificado.anios_leido:
        estado_simple = None
        if clasificado.pendiente:
            estado_simple = "pendiente"
        elif clasificado.abandonado:
            estado_simple = "abandonado"
        if estado_simple is not None:
            ya_existe = (
                db.query(Lectura)
                .filter(Lectura.fic_id == fic.id, Lectura.estado == estado_simple)
                .first()
            )
            if ya_existe is None:
                db.add(Lectura(fic_id=fic.id, estado=estado_simple, es_relectura=False))

    for nombre_tag in clasificado.tags_coleccion:
        coleccion = (
            db.query(Coleccion).filter_by(nombre=nombre_tag, tipo="bookmark_tag").one_or_none()
        )
        if coleccion is None:
            coleccion = Coleccion(nombre=nombre_tag, tipo="bookmark_tag")
            db.add(coleccion)
            db.flush()
        if fic not in coleccion.fics:
            coleccion.fics.append(fic)

    db.flush()


def _walk_listing_work_ids(
    client: RateLimitedClient,
    url_template: str,
    username: str,
    parse_page,
    *,
    start_page: int = 1,
    max_pages: int | None = None,
    progreso: dict | None = None,
):
    """`progreso`, si se pasa, se actualiza con la página que se está por
    pedir ANTES de pedirla — así el que llama sabe desde dónde reanudar si
    la request de esa página falla, en vez de tener que reintentar desde la
    página 1 (ver gh_action_sync.py: con AO3 fallando seguido, reintentar
    siempre desde el principio nunca llega a las páginas de más adelante)."""
    page_num = start_page
    total_pages = None
    while total_pages is None or page_num <= total_pages:
        if max_pages is not None and page_num - start_page >= max_pages:
            return
        if progreso is not None:
            progreso["pagina"] = page_num
        response = client.get(url_template.format(username=username, page=page_num))
        response.raise_for_status()
        listing: ListingPage = parse_page(response.text)
        total_pages = listing.total_pages
        for work_id in listing.work_ids:
            yield work_id
        page_num += 1


def _walk_bookmark_items(
    client: RateLimitedClient,
    username: str,
    *,
    start_page: int = 1,
    max_pages: int | None = None,
    progreso: dict | None = None,
):
    """Ver la docstring de `_walk_listing_work_ids` — mismo propósito para
    `progreso`."""
    page_num = start_page
    total_pages = None
    while total_pages is None or page_num <= total_pages:
        if max_pages is not None and page_num - start_page >= max_pages:
            return
        if progreso is not None:
            progreso["pagina"] = page_num
        response = client.get(BOOKMARKS_URL.format(username=username, page=page_num))
        response.raise_for_status()
        listing: BookmarksPage = parse_bookmarks_page(response.text)
        total_pages = listing.total_pages
        for item in listing.items:
            yield item
        page_num += 1


def _run_bookmarks_import(
    db: Session,
    client: RateLimitedClient,
    *,
    username: str,
    force: bool,
    stale_days: int,
    start_page: int,
    max_pages: int | None,
    archivo_dir: Path | None = None,
) -> ImportRunResult:
    result = ImportRunResult(tipo="bookmarks")
    try:
        item: BookmarkItem
        for item in _walk_bookmark_items(
            client, username, start_page=start_page, max_pages=max_pages
        ):
            try:
                fic, estado = import_single_fic(
                    db, client, item.work_id, force=force, stale_days=stale_days, archivo_dir=archivo_dir
                )
                if estado == "nuevo":
                    result.fics_nuevos += 1
                elif estado == "actualizado":
                    result.fics_actualizados += 1
                else:
                    result.fics_sin_cambios += 1
                apply_bookmark_tags(db, fic, item.tags, item.bookmarked_at, nota=item.nota)
                db.commit()
            except FicNotFoundError as exc:
                if exc.fic is not None:
                    apply_bookmark_tags(db, exc.fic, item.tags, item.bookmarked_at, nota=item.nota)
                db.commit()
                result.errores += 1
                result.detalles_error.append(str(exc))
            except SessionRequestLimitReached:
                db.rollback()
                raise
            except Exception as exc:  # noqa: BLE001 - un fic con error no debe tumbar todo el import
                db.rollback()
                result.errores += 1
                result.detalles_error.append(f"{item.work_id}: {exc}")
    except SessionRequestLimitReached as exc:
        result.detenido_por_limite = True
        result.detalles_error.append(str(exc))
    except RequestFailedError as exc:
        # Pasa al pedir una página de LISTADO de bookmarks (no un fic
        # puntual, ese caso ya lo cubre el except Exception de arriba). AO3
        # nos está frenando en serio, no un 429 pasajero. Cortar acá en vez
        # de reventar con traceback: lo importado hasta ahora queda guardado
        # (cada fic hace su propio commit), y correr el comando de nuevo más
        # tarde retoma solo, salteando lo ya cacheado.
        result.detenido_por_limite = True
        result.detalles_error.append(
            f"AO3 nos siguió devolviendo error incluso después de reintentar: {exc}. "
            "Esperá un rato (10-15 min) antes de volver a correr el import."
        )

    return result


def _run_history_import(
    db: Session,
    client: RateLimitedClient,
    *,
    username: str,
    force: bool,
    stale_days: int,
    start_page: int,
    max_pages: int | None,
    archivo_dir: Path | None = None,
) -> ImportRunResult:
    result = ImportRunResult(tipo="history")
    try:
        for ao3_id in _walk_listing_work_ids(
            client, HISTORY_URL, username, parse_history_page, start_page=start_page, max_pages=max_pages
        ):
            try:
                _, estado = import_single_fic(
                    db, client, ao3_id, force=force, stale_days=stale_days, archivo_dir=archivo_dir
                )
                if estado == "nuevo":
                    result.fics_nuevos += 1
                elif estado == "actualizado":
                    result.fics_actualizados += 1
                else:
                    result.fics_sin_cambios += 1
                db.commit()
            except FicNotFoundError as exc:
                db.commit()
                result.errores += 1
                result.detalles_error.append(str(exc))
            except SessionRequestLimitReached:
                db.rollback()
                raise
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                result.errores += 1
                result.detalles_error.append(f"{ao3_id}: {exc}")
    except SessionRequestLimitReached as exc:
        result.detenido_por_limite = True
        result.detalles_error.append(str(exc))
    except RequestFailedError as exc:
        result.detenido_por_limite = True
        result.detalles_error.append(
            f"AO3 nos siguió devolviendo error incluso después de reintentar: {exc}. "
            "Esperá un rato (10-15 min) antes de volver a correr el import."
        )

    return result


def run_bulk_import(
    db: Session,
    client: RateLimitedClient,
    *,
    tipo: str,
    username: str,
    force: bool = False,
    stale_days: int = DEFAULT_STALE_DAYS,
    start_page: int = 1,
    max_pages: int | None = None,
    archivo_dir: Path | None = None,
) -> ImportRunResult:
    kwargs = dict(
        username=username,
        force=force,
        stale_days=stale_days,
        start_page=start_page,
        max_pages=max_pages,
        archivo_dir=archivo_dir,
    )
    if tipo == "bookmarks":
        return _run_bookmarks_import(db, client, **kwargs)
    if tipo == "history":
        return _run_history_import(db, client, **kwargs)
    raise ValueError(f"tipo de import desconocido: {tipo}")


def check_deleted(
    db: Session,
    client: RateLimitedClient,
    *,
    stale_days: int | None = None,
    archivo_dir: Path | None = None,
) -> ImportRunResult:
    """Revisita cada fic no marcado como borrado. Si AO3 devuelve 404, marca
    deleted_detected_at (nunca borra la fila). Si sigue vivo, de paso
    refresca sus metadatos."""

    result = ImportRunResult(tipo="check-deleted")
    query = db.query(Fic).filter(Fic.deleted_detected_at.is_(None))
    if stale_days is not None:
        limite = _utcnow() - datetime.timedelta(days=stale_days)
        query = query.filter((Fic.ultima_revision.is_(None)) | (Fic.ultima_revision < limite))

    ao3_ids = [fic.ao3_id for fic in query.all()]

    try:
        for ao3_id in ao3_ids:
            try:
                _, estado = import_single_fic(db, client, ao3_id, force=True, archivo_dir=archivo_dir)
                if estado == "actualizado":
                    result.fics_actualizados += 1
                else:
                    result.fics_sin_cambios += 1
                db.commit()
            except FicNotFoundError:
                db.commit()
                result.fics_actualizados += 1  # se marcó deleted_detected_at
            except SessionRequestLimitReached:
                db.rollback()
                raise
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                result.errores += 1
                result.detalles_error.append(f"{ao3_id}: {exc}")
    except SessionRequestLimitReached as exc:
        result.detenido_por_limite = True
        result.detalles_error.append(str(exc))

    return result
