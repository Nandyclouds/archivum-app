from pathlib import Path

import pytest
import responses
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.ao3 import auth
from app.api import ao3_session
from app.api.routers import ao3_import, fics
from app.config import Settings, settings
from app.database import Base, get_session
from app.main import app

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _archivo_dir_temporal(tmp_path, monkeypatch):
    monkeypatch.setattr(Settings, "archivo_dir", property(lambda self: tmp_path))


@pytest.fixture(autouse=True)
def _sin_delay_real(monkeypatch):
    """Los endpoints /ao3 pegan a AO3 de verdad (rate limit real incluido).
    Para los tests, mismo cliente pero sin esperar los segundos reales —
    cada router importó `build_authenticated_client` por nombre, así que hay
    que parchear la referencia en cada uno, no solo en ao3_session."""

    def sin_delay():
        return ao3_session.build_authenticated_client(sleep_fn=lambda s: None)

    monkeypatch.setattr(ao3_import, "build_authenticated_client", sin_delay)
    monkeypatch.setattr(fics, "build_authenticated_client", sin_delay)


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
def client(db_session):
    return TestClient(app)


def _mock_login():
    responses.add(responses.GET, auth.LOGIN_URL, body=_read("login_page.html"), status=200)
    responses.add(responses.POST, auth.LOGIN_URL, status=302)


@responses.activate
def test_importar_fic_por_url(client, monkeypatch):
    monkeypatch.setattr(settings, "ao3_contact_email", "test@example.com")
    monkeypatch.setattr(settings, "ao3_username", "usuaria")
    monkeypatch.setattr(settings, "ao3_password", "secreta")

    _mock_login()
    responses.add(
        responses.GET,
        "https://archiveofourown.org/works/1?view_adult=true&view_full_work=true",
        body=_read("work_page.html"),
        status=200,
    )

    r = client.post("/api/ao3/import-fic", json={"url": "https://archiveofourown.org/works/1"})

    assert r.status_code == 200
    body = r.json()
    assert body["titulo"] == "El Peso de las Estrellas"
    assert body["ao3_id"] == "1"


@responses.activate
def test_importar_fic_por_solo_id(client, monkeypatch):
    monkeypatch.setattr(settings, "ao3_contact_email", "test@example.com")
    _mock_login()
    responses.add(
        responses.GET,
        "https://archiveofourown.org/works/1?view_adult=true&view_full_work=true",
        body=_read("work_page.html"),
        status=200,
    )

    r = client.post("/api/ao3/import-fic", json={"url": "1"})
    assert r.status_code == 200


def test_importar_fic_url_invalida(client, monkeypatch):
    monkeypatch.setattr(settings, "ao3_contact_email", "test@example.com")
    r = client.post("/api/ao3/import-fic", json={"url": "https://example.com/nada"})
    assert r.status_code == 400


def test_importar_fic_sin_contact_email(client, monkeypatch):
    monkeypatch.setattr(settings, "ao3_contact_email", "")
    r = client.post("/api/ao3/import-fic", json={"url": "1"})
    assert r.status_code == 500


@responses.activate
def test_importar_fic_login_invalido(client, monkeypatch):
    monkeypatch.setattr(settings, "ao3_contact_email", "test@example.com")
    responses.add(responses.GET, auth.LOGIN_URL, body=_read("login_page.html"), status=200)
    responses.add(responses.POST, auth.LOGIN_URL, status=200)  # sin 302 = credenciales inválidas

    r = client.post("/api/ao3/import-fic", json={"url": "1"})
    assert r.status_code == 502


@responses.activate
def test_importar_fic_404(client, monkeypatch):
    monkeypatch.setattr(settings, "ao3_contact_email", "test@example.com")
    _mock_login()
    responses.add(
        responses.GET,
        "https://archiveofourown.org/works/999?view_adult=true&view_full_work=true",
        status=404,
    )

    r = client.post("/api/ao3/import-fic", json={"url": "999"})
    assert r.status_code == 404


@responses.activate
def test_descargar_epub_desde_la_app(client, monkeypatch):
    monkeypatch.setattr(settings, "ao3_contact_email", "test@example.com")
    _mock_login()
    responses.add(
        responses.GET,
        "https://archiveofourown.org/works/1?view_adult=true&view_full_work=true",
        body=_read("work_page.html"),
        status=200,
    )
    fic_id = client.post("/api/ao3/import-fic", json={"url": "1"}).json()["id"]

    _mock_login()
    responses.add(
        responses.GET,
        "https://archiveofourown.org/works/1?view_adult=true&view_full_work=true",
        body=_read("work_page.html"),
        status=200,
    )
    responses.add(
        responses.GET,
        "https://archiveofourown.org/downloads/1/El_Peso_de_las_Estrellas.epub?updated_at=123",
        body=b"contenido epub",
        status=200,
    )

    r = client.post(f"/api/fics/{fic_id}/download-epub")

    assert r.status_code == 200
    body = r.json()
    assert body["formato"] == "epub"
    assert body["fic_titulo"] == "El Peso de las Estrellas"
    assert Path(body["ruta_local"]).read_bytes() == b"contenido epub"


def test_descargar_epub_fic_inexistente(client, monkeypatch):
    monkeypatch.setattr(settings, "ao3_contact_email", "test@example.com")
    r = client.post("/api/fics/999/download-epub")
    assert r.status_code == 404
