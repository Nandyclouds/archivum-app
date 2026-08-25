import base64
from pathlib import Path

import pytest
import responses
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_session
from app.main import app
from app.models import Archivo, Fic

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


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


@pytest.fixture()
def con_sync_secret(monkeypatch):
    monkeypatch.setattr(settings, "archivum_sync_secret", "el-secreto-de-maquina")
    yield "el-secreto-de-maquina"


@pytest.fixture(autouse=True)
def _archivo_dir_temporal(tmp_path, monkeypatch):
    from app.config import Settings

    monkeypatch.setattr(Settings, "archivo_dir", property(lambda self: tmp_path))


def _headers(secret):
    return {"X-Sync-Secret": secret}


def test_rutas_sync_sin_secreto_configurado_rechazan_todo(client):
    # Fail-closed: sin ARCHIVUM_SYNC_SECRET seteado, ni con header quedan accesibles.
    assert client.get("/api/sync/known-ids", headers=_headers("cualquiera")).status_code == 401


def test_known_ids_rechaza_sin_secreto(client, con_sync_secret):
    assert client.get("/api/sync/known-ids").status_code == 401


def test_known_ids_rechaza_secreto_incorrecto(client, con_sync_secret):
    response = client.get("/api/sync/known-ids", headers=_headers("otro"))
    assert response.status_code == 401


def test_known_ids_devuelve_los_fics_existentes(client, con_sync_secret, db_session):
    db_session.add(
        Fic(ao3_id="42", titulo="X", autor="a", url="https://archiveofourown.org/works/42")
    )
    db_session.commit()

    response = client.get("/api/sync/known-ids", headers=_headers(con_sync_secret))
    assert response.status_code == 200
    assert response.json() == {"ao3_ids": ["42"]}


def test_incompletos_rechaza_sin_secreto(client, con_sync_secret):
    assert client.get("/api/sync/incompletos").status_code == 401


def test_incompletos_devuelve_solo_wips_nunca_revisados(client, con_sync_secret, db_session):
    import datetime

    wip = Fic(ao3_id="1", titulo="WIP", autor="a", url="https://archiveofourown.org/works/1", complete=False)
    completo = Fic(
        ao3_id="2", titulo="Completo", autor="a", url="https://archiveofourown.org/works/2", complete=True
    )
    wip_reciente = Fic(
        ao3_id="3",
        titulo="WIP revisado hoy",
        autor="a",
        url="https://archiveofourown.org/works/3",
        complete=False,
        ultima_revision=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
    )
    db_session.add_all([wip, completo, wip_reciente])
    db_session.commit()

    response = client.get("/api/sync/incompletos", headers=_headers(con_sync_secret))
    assert response.status_code == 200
    assert response.json() == {"ao3_ids": ["1"]}


def test_ingest_fic_rechaza_sin_secreto(client):
    response = client.post("/api/sync/ingest-fic", json={"ao3_id": "1", "html": "<html></html>"})
    assert response.status_code == 401


def test_ingest_fic_guarda_el_fic(client, con_sync_secret, db_session, tmp_path):
    response = client.post(
        "/api/sync/ingest-fic",
        headers=_headers(con_sync_secret),
        json={"ao3_id": "1", "html": _read("work_page.html")},
    )
    assert response.status_code == 200
    assert response.json() == {"ao3_id": "1", "es_nuevo": True}

    fic = db_session.query(Fic).filter_by(ao3_id="1").one()
    assert fic.titulo == "El Peso de las Estrellas"

    archivo = db_session.query(Archivo).filter_by(fic_id=fic.id, formato="html").one()
    assert Path(archivo.ruta_local).exists()


def test_ingest_fic_con_bookmark_tags_crea_lectura(client, con_sync_secret, db_session):
    response = client.post(
        "/api/sync/ingest-fic",
        headers=_headers(con_sync_secret),
        json={
            "ao3_id": "1",
            "html": _read("work_page.html"),
            "bookmark_tags": ["Leidos 2025"],
            "bookmarked_at": "2025-06-01",
        },
    )
    assert response.status_code == 200

    fic = db_session.query(Fic).filter_by(ao3_id="1").one()
    assert len(fic.lecturas) == 1
    assert fic.lecturas[0].estado == "leido"


def test_ingest_fic_sin_html_actualiza_tags_de_fic_existente(client, con_sync_secret, db_session):
    """El runner manda esto para un fic YA conocido — no vuelve a pedir/
    mandar el HTML entero, solo re-aplica los tags actuales del bookmark."""
    client.post(
        "/api/sync/ingest-fic",
        headers=_headers(con_sync_secret),
        json={"ao3_id": "1", "html": _read("work_page.html")},
    )

    response = client.post(
        "/api/sync/ingest-fic",
        headers=_headers(con_sync_secret),
        json={"ao3_id": "1", "bookmark_tags": ["por leer"]},
    )
    assert response.status_code == 200
    assert response.json() == {"ao3_id": "1", "es_nuevo": False}

    fic = db_session.query(Fic).filter_by(ao3_id="1").one()
    assert len(fic.lecturas) == 1
    assert fic.lecturas[0].estado == "pendiente"


def test_ingest_fic_con_nota_la_guarda(client, con_sync_secret, db_session):
    client.post(
        "/api/sync/ingest-fic",
        headers=_headers(con_sync_secret),
        json={"ao3_id": "1", "html": _read("work_page.html"), "nota": "qué lindo esto"},
    )
    fic = db_session.query(Fic).filter_by(ao3_id="1").one()
    assert fic.nota_bookmark == "qué lindo esto"


def test_ingest_fic_sin_clave_nota_no_borra_la_que_ya_habia(client, con_sync_secret, db_session):
    """El sync de Marked for Later/WIPs manda ingest-fic sin la clave
    "nota" en absoluto (nunca vio la página de bookmarks) — no debe
    pisar con None una nota que ya estaba guardada."""
    client.post(
        "/api/sync/ingest-fic",
        headers=_headers(con_sync_secret),
        json={"ao3_id": "1", "html": _read("work_page.html"), "nota": "nota original"},
    )

    client.post(
        "/api/sync/ingest-fic",
        headers=_headers(con_sync_secret),
        json={"ao3_id": "1", "bookmark_tags": ["Marked for Later"]},
    )

    fic = db_session.query(Fic).filter_by(ao3_id="1").one()
    assert fic.nota_bookmark == "nota original"


def test_ingest_fic_sin_html_ni_fic_existente_da_404(client, con_sync_secret):
    response = client.post(
        "/api/sync/ingest-fic",
        headers=_headers(con_sync_secret),
        json={"ao3_id": "no-existe", "bookmark_tags": ["por leer"]},
    )
    assert response.status_code == 404


def test_ingest_epub_rechaza_sin_secreto(client):
    response = client.post(
        "/api/sync/ingest-epub", json={"ao3_id": "1", "content_base64": "AAAA"}
    )
    assert response.status_code == 401


def test_ingest_epub_fic_inexistente(client, con_sync_secret):
    response = client.post(
        "/api/sync/ingest-epub",
        headers=_headers(con_sync_secret),
        json={"ao3_id": "no-existe", "content_base64": base64.b64encode(b"epub bytes").decode()},
    )
    assert response.status_code == 404


def test_ingest_epub_guarda_el_archivo(client, con_sync_secret, db_session, tmp_path):
    fic = Fic(ao3_id="1", titulo="X", autor="a", url="https://archiveofourown.org/works/1")
    db_session.add(fic)
    db_session.commit()

    contenido = b"contenido falso de un epub"
    response = client.post(
        "/api/sync/ingest-epub",
        headers=_headers(con_sync_secret),
        json={"ao3_id": "1", "content_base64": base64.b64encode(contenido).decode()},
    )
    assert response.status_code == 200
    assert response.json() == {"ao3_id": "1", "bytes": len(contenido)}

    archivo = db_session.query(Archivo).filter_by(fic_id=fic.id, formato="epub").one()
    assert Path(archivo.ruta_local).read_bytes() == contenido


def test_trigger_sin_github_configurado_devuelve_503(client):
    response = client.post("/api/sync/trigger", json={"modo": "bookmarks"})
    assert response.status_code == 503


def test_trigger_modo_desconocido(client, monkeypatch):
    monkeypatch.setattr(settings, "github_pat", "token-falso")
    monkeypatch.setattr(settings, "github_repo", "usuario/repo")
    response = client.post("/api/sync/trigger", json={"modo": "invalido"})
    assert response.status_code == 400


def test_trigger_modo_fic_sin_url(client, monkeypatch):
    monkeypatch.setattr(settings, "github_pat", "token-falso")
    monkeypatch.setattr(settings, "github_repo", "usuario/repo")
    response = client.post("/api/sync/trigger", json={"modo": "fic"})
    assert response.status_code == 400


@responses.activate
def test_trigger_modo_marcados(client, monkeypatch):
    monkeypatch.setattr(settings, "github_pat", "token-falso")
    monkeypatch.setattr(settings, "github_repo", "usuario/repo")
    monkeypatch.setattr(settings, "github_workflow_file", "ao3-sync.yml")

    responses.add(
        responses.POST,
        "https://api.github.com/repos/usuario/repo/actions/workflows/ao3-sync.yml/dispatches",
        status=204,
    )

    response = client.post("/api/sync/trigger", json={"modo": "marcados"})
    assert response.status_code == 200
    assert response.json() == {"disparado": True}


@responses.activate
def test_trigger_modo_wips(client, monkeypatch):
    monkeypatch.setattr(settings, "github_pat", "token-falso")
    monkeypatch.setattr(settings, "github_repo", "usuario/repo")
    monkeypatch.setattr(settings, "github_workflow_file", "ao3-sync.yml")

    responses.add(
        responses.POST,
        "https://api.github.com/repos/usuario/repo/actions/workflows/ao3-sync.yml/dispatches",
        status=204,
    )

    response = client.post("/api/sync/trigger", json={"modo": "wips"})
    assert response.status_code == 200
    assert response.json() == {"disparado": True}


@responses.activate
def test_trigger_dispara_el_workflow_de_github(client, monkeypatch):
    monkeypatch.setattr(settings, "github_pat", "token-falso")
    monkeypatch.setattr(settings, "github_repo", "usuario/repo")
    monkeypatch.setattr(settings, "github_workflow_file", "ao3-sync.yml")

    responses.add(
        responses.POST,
        "https://api.github.com/repos/usuario/repo/actions/workflows/ao3-sync.yml/dispatches",
        status=204,
    )

    response = client.post("/api/sync/trigger", json={"modo": "bookmarks"})
    assert response.status_code == 200
    assert response.json() == {"disparado": True}

    llamada = responses.calls[0].request
    assert llamada.headers["Authorization"] == "Bearer token-falso"


@responses.activate
def test_trigger_propaga_error_de_github(client, monkeypatch):
    monkeypatch.setattr(settings, "github_pat", "token-falso")
    monkeypatch.setattr(settings, "github_repo", "usuario/repo")

    responses.add(
        responses.POST,
        "https://api.github.com/repos/usuario/repo/actions/workflows/ao3-sync.yml/dispatches",
        status=404,
        body="Not Found",
    )

    response = client.post("/api/sync/trigger", json={"modo": "bookmarks"})
    assert response.status_code == 502
