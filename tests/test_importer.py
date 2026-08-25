import datetime
import re
from pathlib import Path

import pytest
import responses
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.ao3 import importer
from app.ao3.client import RateLimitedClient, RequestFailedError
from app.database import Base
from app.ao3.parser import ParsedFic
from app.models import Archivo, Coleccion, Fic, Lectura, Novedad

FIXTURES = Path(__file__).parent / "fixtures"

_PAGINATION_BLOCK_RE = re.compile(r'<ol class="pagination[^"]*".*?</ol>', re.DOTALL)


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _bookmarks_page_single(name: str = "bookmarks_page.html") -> str:
    """Misma fixture, pero con la paginación recortada a una sola página."""
    single_page = '<ol class="pagination actions pagy"><li><a class="current">1</a></li></ol>'
    return _PAGINATION_BLOCK_RE.sub(single_page, _read(name))


@pytest.fixture(autouse=True)
def _archivo_dir_temporal(tmp_path, monkeypatch):
    """Evita que los tests escriban snapshots HTML en el data/archivo/ real."""
    from app.config import Settings

    monkeypatch.setattr(Settings, "archivo_dir", property(lambda self: tmp_path))


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture()
def client():
    return RateLimitedClient(
        contact_email="test@example.com",
        min_delay_seconds=0,
        sleep_fn=lambda s: None,
    )


@responses.activate
def test_import_single_fic_nuevo(db, client):
    responses.add(
        responses.GET,
        "https://archiveofourown.org/works/1?view_adult=true&view_full_work=true",
        body=_read("work_page.html"),
        status=200,
    )

    fic, estado = importer.import_single_fic(db, client, "1")

    assert estado == "nuevo"
    assert fic.titulo == "El Peso de las Estrellas"
    assert [f.nombre for f in fic.fandoms] == ["Star Wars: Original Trilogy"]
    assert fic.ships[0].tipo == "romantico"


@responses.activate
def test_import_single_fic_guarda_snapshot_html_automaticamente(db, client, tmp_path):
    responses.add(
        responses.GET,
        "https://archiveofourown.org/works/1?view_adult=true&view_full_work=true",
        body=_read("work_page.html"),
        status=200,
    )

    fic, _ = importer.import_single_fic(db, client, "1", archivo_dir=tmp_path)

    archivo = db.query(Archivo).filter_by(fic_id=fic.id, formato="html").one()
    assert archivo.ruta_local == str(tmp_path / "1.html")
    assert "El Peso de las Estrellas" in Path(archivo.ruta_local).read_text(encoding="utf-8")
    assert archivo.tamano > 0


@responses.activate
def test_import_single_fic_refresco_pisa_el_snapshot_anterior(db, client, tmp_path):
    for _ in range(2):
        responses.add(
            responses.GET,
            "https://archiveofourown.org/works/1?view_adult=true&view_full_work=true",
            body=_read("work_page.html"),
            status=200,
        )
    importer.import_single_fic(db, client, "1", archivo_dir=tmp_path)
    fic, _ = importer.import_single_fic(db, client, "1", force=True, archivo_dir=tmp_path)

    assert db.query(Archivo).filter_by(fic_id=fic.id, formato="html").count() == 1


@responses.activate
def test_import_single_fic_cacheado_no_reescribe_snapshot(db, client, tmp_path):
    responses.add(
        responses.GET,
        "https://archiveofourown.org/works/1?view_adult=true&view_full_work=true",
        body=_read("work_page.html"),
        status=200,
    )
    fic, _ = importer.import_single_fic(db, client, "1", archivo_dir=tmp_path)
    archivo_antes = db.query(Archivo).filter_by(fic_id=fic.id, formato="html").one()
    fecha_antes = archivo_antes.fecha_descarga

    # cacheado: no pega a la red (no hay más respuestas registradas) ni toca el archivo
    importer.import_single_fic(db, client, "1", archivo_dir=tmp_path)

    archivo_despues = db.query(Archivo).filter_by(fic_id=fic.id, formato="html").one()
    assert archivo_despues.fecha_descarga == fecha_antes


@responses.activate
def test_import_single_fic_cacheado_no_pega_a_la_red(db, client):
    responses.add(
        responses.GET,
        "https://archiveofourown.org/works/1?view_adult=true&view_full_work=true",
        body=_read("work_page.html"),
        status=200,
    )
    importer.import_single_fic(db, client, "1")

    # Segunda llamada: si intentara pegarle a la red de nuevo, `responses`
    # reventaría porque ya no queda ninguna respuesta registrada.
    _, estado = importer.import_single_fic(db, client, "1")
    assert estado == "cacheado"


@responses.activate
def test_import_single_fic_force_ignora_cache(db, client):
    responses.add(
        responses.GET,
        "https://archiveofourown.org/works/1?view_adult=true&view_full_work=true",
        body=_read("work_page.html"),
        status=200,
    )
    importer.import_single_fic(db, client, "1")

    responses.add(
        responses.GET,
        "https://archiveofourown.org/works/1?view_adult=true&view_full_work=true",
        body=_read("work_page.html"),
        status=200,
    )
    _, estado = importer.import_single_fic(db, client, "1", force=True)
    assert estado == "actualizado"


@responses.activate
def test_import_single_fic_stale_se_refresca(db, client):
    responses.add(
        responses.GET,
        "https://archiveofourown.org/works/1?view_adult=true&view_full_work=true",
        body=_read("work_page.html"),
        status=200,
    )
    importer.import_single_fic(db, client, "1")
    fic = db.query(Fic).filter_by(ao3_id="1").one()
    fic.ultima_revision = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(days=40)
    db.commit()

    responses.add(
        responses.GET,
        "https://archiveofourown.org/works/1?view_adult=true&view_full_work=true",
        body=_read("work_page.html"),
        status=200,
    )
    _, estado = importer.import_single_fic(db, client, "1", stale_days=30)
    assert estado == "actualizado"


@responses.activate
def test_import_single_fic_404_marca_borrado(db, client):
    responses.add(
        responses.GET,
        "https://archiveofourown.org/works/1?view_adult=true&view_full_work=true",
        body=_read("work_page.html"),
        status=200,
    )
    importer.import_single_fic(db, client, "1")

    responses.add(
        responses.GET,
        "https://archiveofourown.org/works/1?view_adult=true&view_full_work=true",
        status=404,
    )
    with pytest.raises(importer.FicNotFoundError):
        importer.import_single_fic(db, client, "1", force=True)

    fic = db.query(Fic).filter_by(ao3_id="1").one()
    assert fic.deleted_detected_at is not None
    assert db.query(Fic).count() == 1  # nunca se borra la fila


@responses.activate
def test_run_bulk_import_bookmarks_crea_lecturas_y_colecciones_desde_tags(db, client):
    responses.add(
        responses.GET,
        "https://archiveofourown.org/users/luna/bookmarks?page=1",
        body=_bookmarks_page_single(),
        status=200,
    )
    responses.add(
        responses.GET,
        "https://archiveofourown.org/works/1?view_adult=true&view_full_work=true",
        body=_read("work_page.html"),
        status=200,
    )
    responses.add(
        responses.GET,
        "https://archiveofourown.org/works/2?view_adult=true&view_full_work=true",
        body=_read("work_page_wip_restricted.html"),
        status=200,
    )

    result = importer.run_bulk_import(db, client, tipo="bookmarks", username="luna")

    assert result.fics_nuevos == 2
    assert result.errores == 0
    assert db.query(Fic).count() == 2

    fic1 = db.query(Fic).filter_by(ao3_id="1").one()
    fic2 = db.query(Fic).filter_by(ao3_id="2").one()
    assert fic2.restricted is True

    # fic1 tenía los tags "Leídos 2026" + "Favoritos"
    lectura1 = db.query(Lectura).filter_by(fic_id=fic1.id).one()
    assert lectura1.estado == "leido"
    assert lectura1.fecha_fin == datetime.date(2026, 3, 15)  # fecha real del bookmark
    assert lectura1.es_relectura is False
    coleccion = db.query(Coleccion).filter_by(nombre="Favoritos", tipo="bookmark_tag").one()
    assert [f.ao3_id for f in coleccion.fics] == ["1"]

    # fic2 tenía el tag "por leer"
    lectura2 = db.query(Lectura).filter_by(fic_id=fic2.id).one()
    assert lectura2.estado == "pendiente"


@responses.activate
def test_run_bulk_import_bookmarks_es_idempotente(db, client):
    body = _bookmarks_page_single()
    responses.add(responses.GET, "https://archiveofourown.org/users/luna/bookmarks?page=1", body=body, status=200)
    responses.add(
        responses.GET,
        "https://archiveofourown.org/works/1?view_adult=true&view_full_work=true",
        body=_read("work_page.html"),
        status=200,
    )
    responses.add(
        responses.GET,
        "https://archiveofourown.org/works/2?view_adult=true&view_full_work=true",
        body=_read("work_page_wip_restricted.html"),
        status=200,
    )
    importer.run_bulk_import(db, client, tipo="bookmarks", username="luna")

    # Segunda corrida: los fics ya están cacheados (no vuelven a pedirse),
    # pero el listado de bookmarks sí se vuelve a recorrer y re-clasificar.
    responses.add(responses.GET, "https://archiveofourown.org/users/luna/bookmarks?page=1", body=body, status=200)
    importer.run_bulk_import(db, client, tipo="bookmarks", username="luna")

    assert db.query(Lectura).count() == 2  # no se duplicaron
    assert db.query(Coleccion).count() == 1
    fic1 = db.query(Fic).filter_by(ao3_id="1").one()
    coleccion = db.query(Coleccion).filter_by(nombre="Favoritos").one()
    assert [f.ao3_id for f in coleccion.fics] == ["1"]  # no se duplicó el link


@responses.activate
def test_relectura_en_otro_anio_agrega_segunda_lectura(db, client):
    html = _bookmarks_page_single().replace(
        '<li><a class="tag" href="?bookmark_tag_id=leidos+2026">Leídos 2026</a></li>\n        '
        '<li><a class="tag" href="?bookmark_tag_id=favoritos">Favoritos</a></li>',
        '<li><a class="tag" href="?bookmark_tag_id=leidos+2024">Leídos 2024</a></li>\n        '
        '<li><a class="tag" href="?bookmark_tag_id=leidos+2026">Leídos 2026</a></li>',
    )
    responses.add(responses.GET, "https://archiveofourown.org/users/luna/bookmarks?page=1", body=html, status=200)
    responses.add(
        responses.GET,
        "https://archiveofourown.org/works/1?view_adult=true&view_full_work=true",
        body=_read("work_page.html"),
        status=200,
    )
    responses.add(
        responses.GET,
        "https://archiveofourown.org/works/2?view_adult=true&view_full_work=true",
        body=_read("work_page_wip_restricted.html"),
        status=200,
    )

    importer.run_bulk_import(db, client, tipo="bookmarks", username="luna")

    fic1 = db.query(Fic).filter_by(ao3_id="1").one()
    lecturas = db.query(Lectura).filter_by(fic_id=fic1.id).order_by(Lectura.fecha_fin).all()
    assert [l.fecha_fin.year for l in lecturas] == [2024, 2026]
    assert lecturas[0].es_relectura is False  # la primera vez que lo leyó
    assert lecturas[1].es_relectura is True  # releído en 2026
    # el bookmark real es de 2026-03-15: el tag de 2024 no puede usar esa
    # fecha exacta (años no coinciden), así que cae al 1 de julio aproximado
    assert lecturas[0].fecha_fin == datetime.date(2024, 7, 1)
    assert lecturas[1].fecha_fin == datetime.date(2026, 3, 15)


@responses.activate
def test_run_bulk_import_se_detiene_por_limite_de_sesion(db):
    limited_client = RateLimitedClient(
        contact_email="test@example.com",
        min_delay_seconds=0,
        sleep_fn=lambda s: None,
        max_requests_per_session=1,
    )
    responses.add(
        responses.GET,
        "https://archiveofourown.org/users/luna/bookmarks?page=1",
        body=_read("bookmarks_page.html"),
        status=200,
    )

    result = importer.run_bulk_import(db, limited_client, tipo="bookmarks", username="luna")

    assert result.detenido_por_limite is True
    assert result.fics_nuevos == 0


@responses.activate
def test_run_bulk_import_429_persistente_al_listar_paginas_no_revienta(db, client):
    # Bug real: un 429 sostenido de AO3 al pedir una página de LISTADO de
    # bookmarks (no un fic puntual) se escapaba del manejo de errores y
    # tumbaba todo el proceso con un traceback en vez de cortar prolijo.
    for _ in range(client.max_backoff_retries + 1):
        responses.add(
            responses.GET, "https://archiveofourown.org/users/luna/bookmarks?page=1", status=429
        )

    result = importer.run_bulk_import(db, client, tipo="bookmarks", username="luna")

    assert result.detenido_por_limite is True
    assert any("AO3" in d for d in result.detalles_error)


@responses.activate
def test_run_bulk_import_limite_alcanzado_a_mitad_de_un_fic_no_cuenta_como_error(db):
    limited_client = RateLimitedClient(
        contact_email="test@example.com",
        min_delay_seconds=0,
        sleep_fn=lambda s: None,
        max_requests_per_session=2,  # alcanza para listar la página pero no para el 2do fic
    )
    responses.add(
        responses.GET,
        "https://archiveofourown.org/users/luna/bookmarks?page=1",
        body=_bookmarks_page_single(),
        status=200,
    )
    responses.add(
        responses.GET,
        "https://archiveofourown.org/works/1?view_adult=true&view_full_work=true",
        body=_read("work_page.html"),
        status=200,
    )

    result = importer.run_bulk_import(db, limited_client, tipo="bookmarks", username="luna")

    assert result.detenido_por_limite is True
    assert result.fics_nuevos == 1  # el primer fic sí se guardó antes de cortar
    assert result.errores == 0  # cortar por límite no es un "error" del fic


@responses.activate
def test_run_history_import_no_toca_lecturas(db, client):
    responses.add(
        responses.GET,
        "https://archiveofourown.org/users/luna/readings?page=1",
        body=_read("history_page.html"),
        status=200,
    )
    responses.add(
        responses.GET,
        "https://archiveofourown.org/works/1?view_adult=true&view_full_work=true",
        body=_read("work_page.html"),
        status=200,
    )
    responses.add(
        responses.GET,
        "https://archiveofourown.org/works/3?view_adult=true&view_full_work=true",
        body=_read("work_page_wip_restricted.html").replace('id="2"', 'id="3"'),
        status=200,
    )

    result = importer.run_bulk_import(db, client, tipo="history", username="luna")

    assert result.fics_nuevos == 2
    assert db.query(Lectura).count() == 0  # el historial nunca crea lecturas


def _parsed_fic(**overrides) -> ParsedFic:
    base = dict(
        ao3_id="1",
        titulo="Un fic",
        autor="autora",
        autor_url=None,
        word_count=1000,
        chapters_published=3,
        chapters_total=10,
        complete=False,
        restricted=False,
        rating=None,
        idioma=None,
        categorias=[],
        warnings=[],
        summary=None,
        fecha_publicacion=None,
        fecha_actualizacion=None,
        fandoms=[],
        ships=[],
        personajes=[],
        tags_adicionales=[],
    )
    base.update(overrides)
    return ParsedFic(**base)


def test_upsert_fic_nuevo_no_genera_novedad(db):
    importer.upsert_fic(db, _parsed_fic())
    assert db.query(Novedad).count() == 0


def test_upsert_fic_capitulo_nuevo_genera_novedad(db):
    importer.upsert_fic(db, _parsed_fic(chapters_published=3))
    importer.upsert_fic(db, _parsed_fic(chapters_published=5))

    novedades = db.query(Novedad).all()
    assert len(novedades) == 1
    assert novedades[0].tipo == "capitulo_nuevo"
    assert novedades[0].capitulos_publicados == 5


def test_upsert_fic_se_completa_genera_novedad(db):
    importer.upsert_fic(db, _parsed_fic(chapters_published=9, chapters_total=10, complete=False))
    importer.upsert_fic(db, _parsed_fic(chapters_published=10, chapters_total=10, complete=True))

    novedades = db.query(Novedad).all()
    tipos = {n.tipo for n in novedades}
    assert "capitulo_nuevo" in tipos
    assert "completado" in tipos


def test_upsert_fic_sin_cambios_no_genera_novedad(db):
    importer.upsert_fic(db, _parsed_fic(chapters_published=5, complete=False))
    importer.upsert_fic(db, _parsed_fic(chapters_published=5, complete=False))

    assert db.query(Novedad).count() == 0


def test_upsert_fic_ya_completo_no_repite_novedad(db):
    importer.upsert_fic(db, _parsed_fic(chapters_published=10, chapters_total=10, complete=True))
    importer.upsert_fic(db, _parsed_fic(chapters_published=10, chapters_total=10, complete=True))

    assert db.query(Novedad).filter_by(tipo="completado").count() == 0
