import re
from pathlib import Path

import pytest
import responses
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.ao3 import auth
from app.api.routers import sync as sync_router
from app.config import settings
from app.database import Base, get_session
from app.main import app
from app.models import Fic, ImportLog

FIXTURES = Path(__file__).parent / "fixtures"

_PAGINATION_BLOCK_RE = re.compile(r'<ol class="pagination[^"]*".*?</ol>', re.DOTALL)


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _bookmarks_page_single() -> str:
    """Misma fixture, pero con la paginación recortada a una sola página —
    si no, _walk_bookmark_items sigue de largo a la página 2, que no está
    mockeada."""
    single_page = '<ol class="pagination actions pagy"><li><a class="current">1</a></li></ol>'
    return _PAGINATION_BLOCK_RE.sub(single_page, _read("bookmarks_page.html"))


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    def override_get_session():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_session] = override_get_session
    yield session
    app.dependency_overrides.clear()
    session.close()


@pytest.fixture()
def client(db_session, monkeypatch):
    # El TestClient corre las BackgroundTasks antes de devolver la
    # respuesta, pero _ejecutar_sync abre su PROPIA sesión (no puede reusar
    # la de la request) — para que vea los mismos datos que el test, se la
    # redirige a la sesión en memoria de este fixture.
    monkeypatch.setattr(sync_router, "nueva_sesion_para_cuenta", lambda cuenta_id: db_session)
    return TestClient(app)


@pytest.fixture(autouse=True)
def _archivo_dir_temporal(tmp_path, monkeypatch):
    from app.config import Settings

    monkeypatch.setattr(Settings, "archivo_dir", lambda self, cuenta_id: tmp_path)


@pytest.fixture(autouse=True)
def _sin_credenciales_de_ao3_por_defecto(monkeypatch):
    """El .env local de desarrollo tiene credenciales de AO3 reales (para
    poder probar la app contra AO3 de verdad) — sin este fixture, un test
    que no las necesita terminaría pegándole a AO3 por la red en vez de
    fallar rápido con 'no configurado'."""
    monkeypatch.setattr(settings, "ao3_contact_email", "")
    monkeypatch.setattr(settings, "ao3_username", "")
    monkeypatch.setattr(settings, "ao3_password", "")


@pytest.fixture()
def con_credenciales_ao3(monkeypatch):
    monkeypatch.setattr(settings, "ao3_contact_email", "test@example.com")
    monkeypatch.setattr(settings, "ao3_username", "luna")
    monkeypatch.setattr(settings, "ao3_password", "secreta")
    # Sin esto, cada petición espera el rate limit real (varios segundos):
    # _ejecutar_sync no tiene forma de inyectar sleep_fn=None como hacen los
    # tests de ao3_import, así que se lo saca a la configuración en sí.
    monkeypatch.setattr(settings, "ao3_min_delay_seconds", 0)


def _mock_login():
    responses.add(responses.GET, auth.LOGIN_URL, body=_read("login_page.html"), status=200)
    responses.add(responses.POST, auth.LOGIN_URL, status=302)


def test_trigger_modo_desconocido(client):
    response = client.post("/api/sync/trigger", json={"modo": "invalido"})
    assert response.status_code == 400


def test_trigger_modo_fic_sin_url(client):
    response = client.post("/api/sync/trigger", json={"modo": "fic"})
    assert response.status_code == 400


def test_trigger_modo_epub_sin_ao3_id(client):
    response = client.post("/api/sync/trigger", json={"modo": "epub"})
    assert response.status_code == 400


def test_trigger_responde_al_toque(client):
    # Sin AO3_CONTACT_EMAIL configurado, la tarea en segundo plano falla al
    # armar el cliente — pero la respuesta de /trigger ya se mandó antes de
    # que eso pase (se ve en el ImportLog con error, no en la respuesta).
    response = client.post("/api/sync/trigger", json={"modo": "bookmarks"})
    assert response.status_code == 200
    assert response.json() == {"disparado": True}


def test_trigger_sin_credenciales_de_ao3_deja_el_error_en_el_log(client, db_session):
    client.post("/api/sync/trigger", json={"modo": "bookmarks"})
    log = db_session.query(ImportLog).one()
    assert log.errores == 1
    assert "AO3_CONTACT_EMAIL" in log.errores_detalle


@responses.activate
def test_trigger_modo_fic_importa_el_fic(client, db_session, con_credenciales_ao3):
    _mock_login()
    responses.add(
        responses.GET,
        "https://archiveofourown.org/works/1?view_adult=true&view_full_work=true",
        body=_read("work_page.html"),
        status=200,
    )
    responses.add(
        responses.GET,
        "https://archiveofourown.org/users/luna/bookmarks?page=1",
        body=_bookmarks_page_single(),
        status=200,
    )

    response = client.post(
        "/api/sync/trigger", json={"modo": "fic", "url": "https://archiveofourown.org/works/1"}
    )
    assert response.status_code == 200

    fic = db_session.query(Fic).filter_by(ao3_id="1").one()
    assert fic.titulo == "El Peso de las Estrellas"
    log = db_session.query(ImportLog).one()
    assert log.tipo == "fic"
    assert log.fics_nuevos == 1


@responses.activate
def test_trigger_modo_bookmarks_sincroniza_y_registra_el_log(client, db_session, con_credenciales_ao3):
    _mock_login()
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

    response = client.post("/api/sync/trigger", json={"modo": "bookmarks"})
    assert response.status_code == 200

    assert db_session.query(Fic).count() == 2
    log = db_session.query(ImportLog).one()
    assert log.tipo == "bookmarks"
    assert log.fics_nuevos == 2
