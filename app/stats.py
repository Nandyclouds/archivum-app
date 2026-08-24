"""Queries de estadísticas sobre la biblioteca.

Todas las funciones reciben una Session de SQLAlchemy ya abierta y devuelven
listas de tuplas simples o dicts, listas para servir desde la API o imprimir
en el CLI. No hay estado ni side effects.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models import Coleccion, Fandom, Fic, FicFandom, FicShip, Lectura, Resena, Ship


@dataclass
class PeriodoPalabras:
    periodo: str  # "2026-01" o "2026"
    palabras: int
    fics: int


def palabras_leidas_por_mes(session: Session, anio: int | None = None) -> list[PeriodoPalabras]:
    """Palabras leídas agrupadas por mes (fecha_fin de lecturas con estado 'leido')."""
    periodo = func.strftime("%Y-%m", Lectura.fecha_fin)
    query = (
        session.query(
            periodo.label("periodo"),
            func.coalesce(func.sum(Fic.word_count), 0).label("palabras"),
            func.count(Lectura.id).label("fics"),
        )
        .join(Fic, Fic.id == Lectura.fic_id)
        .filter(Lectura.estado == "leido", Lectura.fecha_fin.isnot(None))
    )
    if anio is not None:
        query = query.filter(func.strftime("%Y", Lectura.fecha_fin) == str(anio))
    query = query.group_by(periodo).order_by(periodo)
    return [PeriodoPalabras(*row) for row in query.all()]


def palabras_leidas_por_anio(session: Session) -> list[PeriodoPalabras]:
    periodo = func.strftime("%Y", Lectura.fecha_fin)
    query = (
        session.query(
            periodo.label("periodo"),
            func.coalesce(func.sum(Fic.word_count), 0).label("palabras"),
            func.count(Lectura.id).label("fics"),
        )
        .join(Fic, Fic.id == Lectura.fic_id)
        .filter(Lectura.estado == "leido", Lectura.fecha_fin.isnot(None))
        .group_by(periodo)
        .order_by(periodo)
    )
    return [PeriodoPalabras(*row) for row in query.all()]


def _filtrar_por_anio_leido(query, join_col, anio: int):
    """Restringe una query de fandoms/ships a fics leídos en un año dado.

    `anio` filtra por `Lectura.fecha_fin` (cuándo se terminó de leer), no por
    fecha de publicación del fic — "top fandoms de 2024" significa "lo que
    más leíste en 2024", pudiendo incluir fics publicados en cualquier año.
    """
    return query.join(Lectura, Lectura.fic_id == join_col).filter(
        Lectura.estado == "leido",
        Lectura.fecha_fin.isnot(None),
        func.strftime("%Y", Lectura.fecha_fin) == str(anio),
    )


def top_fandoms(session: Session, limite: int = 10, anio: int | None = None) -> list[tuple[str, int]]:
    """Fandoms con más fics en la biblioteca, de más a menos.

    Con `anio`, restringe a fics cuya lectura se completó ese año (ver
    `_filtrar_por_anio_leido`).
    """
    query = (
        session.query(Fandom.nombre, func.count(func.distinct(FicFandom.fic_id)).label("total"))
        .join(FicFandom, FicFandom.fandom_id == Fandom.id)
    )
    if anio is not None:
        query = _filtrar_por_anio_leido(query, FicFandom.fic_id, anio)
    query = (
        query.group_by(Fandom.nombre)
        .order_by(func.count(func.distinct(FicFandom.fic_id)).desc())
        .limit(limite)
    )
    return list(query.all())


def top_ships(
    session: Session, limite: int = 10, tipo: str | None = None, anio: int | None = None
) -> list[tuple[str, int]]:
    """Ships con más fics en la biblioteca, de más a menos.

    AO3 distingue "/" (pairing romántico) de "&" (relación platónica/familiar)
    en el nombre del tag, y eso ya se guarda en `Ship.tipo` al importar (ver
    `parser.infer_ship_tipo`). Sin filtrar por tipo acá, "ships favoritos"
    termina mezclando parejas románticas con vínculos de amistad/familia.
    Pasar tipo='romantico' o tipo='platonico' para separarlos. Con `anio`,
    restringe a fics leídos ese año (ver `_filtrar_por_anio_leido`).
    """
    query = (
        session.query(Ship.nombre, func.count(func.distinct(FicShip.fic_id)).label("total"))
        .join(FicShip, FicShip.ship_id == Ship.id)
    )
    if tipo is not None:
        query = query.filter(Ship.tipo == tipo)
    if anio is not None:
        query = _filtrar_por_anio_leido(query, FicShip.fic_id, anio)
    query = (
        query.group_by(Ship.nombre)
        .order_by(func.count(func.distinct(FicShip.fic_id)).desc())
        .limit(limite)
    )
    return list(query.all())


# Límites superiores (exclusivos) de cada bucket, en palabras.
BUCKETS_LONGITUD = [
    ("drabble (<1k)", 1_000),
    ("corto (1k-10k)", 10_000),
    ("mediano (10k-40k)", 40_000),
    ("largo (40k-100k)", 100_000),
    ("epico (100k+)", None),
]


def distribucion_longitud(session: Session) -> list[tuple[str, int]]:
    """Cantidad de fics por rango de word_count."""
    whens = []
    limite_anterior = 0
    for etiqueta, limite in BUCKETS_LONGITUD:
        if limite is None:
            whens.append((Fic.word_count >= limite_anterior, etiqueta))
        else:
            whens.append(
                ((Fic.word_count >= limite_anterior) & (Fic.word_count < limite), etiqueta)
            )
        limite_anterior = limite or limite_anterior

    bucket = case(*whens, else_="sin_clasificar")
    query = (
        session.query(bucket.label("bucket"), func.count(Fic.id))
        .group_by(bucket)
    )
    orden = {etiqueta: i for i, (etiqueta, _) in enumerate(BUCKETS_LONGITUD)}
    resultados = list(query.all())
    resultados.sort(key=lambda r: orden.get(r[0], len(orden)))
    return resultados


def ratio_wip_vs_completos(session: Session) -> dict[str, int]:
    query = session.query(Fic.complete, func.count(Fic.id)).group_by(Fic.complete)
    conteo = {"completos": 0, "wip": 0}
    for complete, total in query.all():
        conteo["completos" if complete else "wip"] = total
    return conteo


def total_relecturas(session: Session) -> int:
    return session.query(func.count(Lectura.id)).filter(Lectura.es_relectura.is_(True)).scalar()


def relecturas_por_fic(session: Session, limite: int = 10) -> list[tuple[str, int]]:
    """Fics más releídos, de más a menos."""
    query = (
        session.query(Fic.titulo, func.count(Lectura.id).label("relecturas"))
        .join(Lectura, Lectura.fic_id == Fic.id)
        .filter(Lectura.es_relectura.is_(True))
        .group_by(Fic.id)
        .order_by(func.count(Lectura.id).desc())
        .limit(limite)
    )
    return list(query.all())


def promedio_rating_por_fandom(session: Session, minimo_resenas: int = 1) -> list[tuple[str, float, int]]:
    """Promedio de rating personal por fandom, con cantidad de reseñas consideradas."""
    query = (
        session.query(
            Fandom.nombre,
            func.avg(Resena.rating).label("promedio"),
            func.count(Resena.id).label("total_resenas"),
        )
        .join(FicFandom, FicFandom.fandom_id == Fandom.id)
        .join(Resena, Resena.fic_id == FicFandom.fic_id)
        .group_by(Fandom.nombre)
        .having(func.count(Resena.id) >= minimo_resenas)
        .order_by(func.avg(Resena.rating).desc())
    )
    return list(query.all())


def conteo_por_estado_lectura(session: Session) -> dict[str, int]:
    """Cantidad de fics distintos según el estado de su lectura más reciente
    (si un fic tiene varias lecturas -relecturas-, solo cuenta la última)."""
    ultimas = (
        session.query(Lectura.fic_id, func.max(Lectura.id).label("ultima_id"))
        .group_by(Lectura.fic_id)
        .subquery()
    )
    query = (
        session.query(Lectura.estado, func.count(Lectura.id))
        .join(ultimas, Lectura.id == ultimas.c.ultima_id)
        .group_by(Lectura.estado)
    )
    return dict(query.all())


def racha_dias_lectura(session: Session) -> int:
    """Días consecutivos con al menos una lectura terminada, terminando en
    el día de lectura más reciente registrado (no necesariamente hoy).

    OJO: `fecha_fin` muchas veces es una aproximación, no la fecha exacta en
    que se terminó de leer (ver `importer.apply_bookmark_tags`: cuando un tag
    "Leídos <año>" no coincide con el año del bookmark real, se aproxima al
    1 de julio de ese año). Esta racha es tan precisa como esas fechas.
    """
    fechas = (
        session.query(Lectura.fecha_fin)
        .filter(Lectura.estado == "leido", Lectura.fecha_fin.isnot(None))
        .distinct()
        .all()
    )
    dias = sorted({f[0] for f in fechas}, reverse=True)
    if not dias:
        return 0
    racha = 1
    for anterior, siguiente in zip(dias, dias[1:]):
        if (anterior - siguiente).days == 1:
            racha += 1
        else:
            break
    return racha


def resumen_general(session: Session) -> dict:
    """Bloque de números para el panel principal: palabras, fics, fandoms, ships.

    `total_lecturas_leido` y `total_palabras_leidas` cuentan cada lectura
    (incluidas relecturas) por separado: si releíste un fic de 1000 palabras,
    suma 2 lecturas y 2000 palabras, no 1. `total_fics` es el tamaño de la
    biblioteca completa (incluye pendientes/sin marcar), no "leídos".
    """
    total_fics = session.query(func.count(Fic.id)).scalar()
    total_lecturas_leido = (
        session.query(func.count(Lectura.id)).filter(Lectura.estado == "leido").scalar()
    )
    total_palabras_leidas = (
        session.query(func.coalesce(func.sum(Fic.word_count), 0))
        .join(Lectura, Lectura.fic_id == Fic.id)
        .filter(Lectura.estado == "leido")
        .scalar()
    )
    total_fandoms = session.query(func.count(func.distinct(FicFandom.fandom_id))).scalar()
    total_ships = session.query(func.count(func.distinct(FicShip.ship_id))).scalar()
    return {
        "total_fics": total_fics,
        "total_lecturas_leido": total_lecturas_leido,
        "total_palabras_leidas": total_palabras_leidas,
        "total_fandoms": total_fandoms,
        "total_ships": total_ships,
    }
