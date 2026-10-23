import base64
import datetime
import json
from pathlib import Path

import pytest
import responses
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.control_db as control_db_module
import app.main as main_module
from app.auth import crear_sesion, hashear_password
from app.config import Settings, settings
from app.control_models import Cuenta
from app.crypto import encriptar
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


@pytest.fixture(autouse=True)
def _archivo_dir_temporal(tmp_path, monkeypatch):
    monkeypatch.setattr(Settings, "archivo_dir", lambda self, cuenta_id: tmp_path)
    monkeypatch.setattr(Settings, "archivo_dir_legado", property(lambda self: tmp_path))


@pytest.fixture()
def con_sync_secret(monkeypatch):
    monkeypatch.setattr(settings, "archivum_sync_secret", "el-secreto-de-maquina")
    yield "el-secreto-de-maquina"


@pytest.fixture()
def control_db(monkeypatch):
    """Base de control en memoria — las rutas de sync por cuenta resuelven
    request.state.cuenta a partir de ?cuenta_id=, así que necesitan una
    cuenta de verdad ahí, no solo el secreto."""
    control_engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    main_module.ControlBase.metadata.create_all(control_engine)
    TestControlSessionLocal = sessionmaker(bind=control_engine)
    monkeypatch.setattr(main_module, "ControlSessionLocal", TestControlSessionLocal)
    monkeypatch.setattr(control_db_module, "ControlSessionLocal", TestControlSessionLocal)
    return TestControlSessionLocal


@pytest.fixture()
def cuenta_id(control_db) -> int:
    with control_db() as db:
        cuenta = Cuenta(email="nanda@example.com", password_hash=hashear_password("x"), es_admin=True)
        db.add(cuenta)
        db.commit()
        db.refresh(cuenta)
        return cuenta.id


@pytest.fixture()
def cuenta_logueada(control_db, monkeypatch):
    """Una sesión de usuario normal (no sync-secret), con AO3 ya conectado —
    para los tests de /trigger, que lo habla el frontend."""
    monkeypatch.setattr(settings, "archivum_auth_token", "en-produccion")
    monkeypatch.setattr(settings, "archivum_encryption_key", "zMWJb0d6tsHnMWQJBWVfTFbMnDaR5f6b9yfsMbVF8_w=")

    with control_db() as db:
        cuenta = Cuenta(
            email="nanda@example.com",
            password_hash=hashear_password("x"),
            es_admin=True,
            ao3_username="lunaescribe",
            ao3_password_encriptada=encriptar("secreta"),
        )
        db.add(cuenta)
        db.commit()
        db.refresh(cuenta)
        token = crear_sesion(db, cuenta)
    return token


def _headers(secret):
    return {"X-Sync-Secret": secret}


def _token_headers(token):
    return {"X-Archivum-Token": token}


# ---------------------------------------------------------------------------
# Rutas que habla el workflow de GitHub Actions (ARCHIVUM_SYNC_SECRET)
# ---------------------------------------------------------------------------


def test_rutas_sync_sin_secreto_configurado_rechazan_todo(client, cuenta_id):
    # Fail-closed: sin ARCHIVUM_SYNC_SECRET seteado en este server, ni
    # mandando el header queda accesible.
    response = client.get(
        "/api/sync/known-ids", headers=_headers("cualquiera"), params={"cuenta_id": cuenta_id}
    )
    assert response.status_code == 401


def test_known_ids_rechaza_sin_secreto(client, con_sync_secret, cuenta_id):
    response = client.get("/api/sync/known-ids", params={"cuenta_id": cuenta_id})
    assert response.status_code == 401


def test_known_ids_rechaza_secreto_incorrecto(client, con_sync_secret, cuenta_id):
    response = client.get("/api/sync/known-ids", headers=_headers("otro"), params={"cuenta_id": cuenta_id})
    assert response.status_code == 401


def test_known_ids_rechaza_sin_cuenta_id(client, con_sync_secret):
    response = client.get("/api/sync/known-ids", headers=_headers(con_sync_secret))
    assert response.status_code == 400


def test_known_ids_rechaza_cuenta_id_inexistente(client, con_sync_secret, control_db):
    response = client.get("/api/sync/known-ids", headers=_headers(con_sync_secret), params={"cuenta_id": 999})
    assert response.status_code == 401


def test_known_ids_devuelve_los_fics_existentes(client, con_sync_secret, cuenta_id, db_session):
    db_session.add(Fic(ao3_id="42", titulo="X", autor="a", url="https://archiveofourown.org/works/42"))
    db_session.commit()

    response = client.get(
        "/api/sync/known-ids", headers=_headers(con_sync_secret), params={"cuenta_id": cuenta_id}
    )
    assert response.status_code == 200
    assert response.json() == {"ao3_ids": ["42"]}


def test_incompletos_devuelve_solo_wips_nunca_revisados(client, con_sync_secret, cuenta_id, db_session):
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

    response = client.get(
        "/api/sync/incompletos", headers=_headers(con_sync_secret), params={"cuenta_id": cuenta_id}
    )
    assert response.status_code == 200
    assert response.json() == {"ao3_ids": ["1"]}


def test_ingest_fic_guarda_el_fic(client, con_sync_secret, cuenta_id, db_session):
    response = client.post(
        "/api/sync/ingest-fic",
        headers=_headers(con_sync_secret),
        params={"cuenta_id": cuenta_id},
        json={"ao3_id": "1", "html": _read("work_page.html")},
    )
    assert response.status_code == 200
    assert response.json() == {
        "ao3_id": "1",
        "es_nuevo": True,
        "titulo": "El Peso de las Estrellas",
        "novedades": [],
    }

    fic = db_session.query(Fic).filter_by(ao3_id="1").one()
    assert fic.titulo == "El Peso de las Estrellas"

    archivo = db_session.query(Archivo).filter_by(fic_id=fic.id, formato="html").one()
    assert Path(archivo.ruta_local).exists()


def test_ingest_fic_con_bookmark_tags_crea_lectura(client, con_sync_secret, cuenta_id, db_session):
    response = client.post(
        "/api/sync/ingest-fic",
        headers=_headers(con_sync_secret),
        params={"cuenta_id": cuenta_id},
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


def test_ingest_fic_sin_html_ni_fic_existente_da_404(client, con_sync_secret, cuenta_id):
    response = client.post(
        "/api/sync/ingest-fic",
        headers=_headers(con_sync_secret),
        params={"cuenta_id": cuenta_id},
        json={"ao3_id": "no-existe", "bookmark_tags": ["por leer"]},
    )
    assert response.status_code == 404


def test_ingest_fic_sin_html_actualiza_tags_de_un_fic_existente(client, con_sync_secret, cuenta_id, db_session):
    db_session.add(Fic(ao3_id="1", titulo="X", autor="a", url="https://archiveofourown.org/works/1"))
    db_session.commit()

    response = client.post(
        "/api/sync/ingest-fic",
        headers=_headers(con_sync_secret),
        params={"cuenta_id": cuenta_id},
        json={"ao3_id": "1", "bookmark_tags": ["por leer"]},
    )
    assert response.status_code == 200
    assert response.json()["es_nuevo"] is False

    fic = db_session.query(Fic).filter_by(ao3_id="1").one()
    assert len(fic.lecturas) == 1
    assert fic.lecturas[0].estado == "pendiente"


def test_ingest_epub_guarda_el_archivo(client, con_sync_secret, cuenta_id, db_session):
    fic = Fic(ao3_id="1", titulo="X", autor="a", url="https://archiveofourown.org/works/1")
    db_session.add(fic)
    db_session.commit()

    contenido = b"contenido falso de un epub"
    response = client.post(
        "/api/sync/ingest-epub",
        headers=_headers(con_sync_secret),
        params={"cuenta_id": cuenta_id},
        json={"ao3_id": "1", "content_base64": base64.b64encode(contenido).decode()},
    )
    assert response.status_code == 200
    assert response.json() == {"ao3_id": "1", "bytes": len(contenido)}

    archivo = db_session.query(Archivo).filter_by(fic_id=fic.id, formato="epub").one()
    assert Path(archivo.ruta_local).read_bytes() == contenido


def test_ingest_epub_fic_inexistente_da_404(client, con_sync_secret, cuenta_id):
    response = client.post(
        "/api/sync/ingest-epub",
        headers=_headers(con_sync_secret),
        params={"cuenta_id": cuenta_id},
        json={"ao3_id": "no-existe", "content_base64": base64.b64encode(b"x").decode()},
    )
    assert response.status_code == 404


def test_credenciales_ao3_devuelve_lo_que_configuro_la_cuenta(client, con_sync_secret, control_db, monkeypatch):
    monkeypatch.setattr(settings, "archivum_encryption_key", "zMWJb0d6tsHnMWQJBWVfTFbMnDaR5f6b9yfsMbVF8_w=")
    with control_db() as db:
        cuenta = Cuenta(
            email="nanda@example.com",
            password_hash=hashear_password("x"),
            ao3_username="lunaescribe",
            ao3_password_encriptada=encriptar("secreta"),
        )
        db.add(cuenta)
        db.commit()
        db.refresh(cuenta)
        cuenta_id_real = cuenta.id

    response = client.get(
        "/api/sync/credenciales-ao3", headers=_headers(con_sync_secret), params={"cuenta_id": cuenta_id_real}
    )
    assert response.status_code == 200
    assert response.json() == {
        "ao3_username": "lunaescribe",
        "ao3_password": "secreta",
        "email": "nanda@example.com",
    }


def test_credenciales_ao3_cuenta_sin_ao3_conectado_da_409(client, con_sync_secret, cuenta_id):
    response = client.get(
        "/api/sync/credenciales-ao3", headers=_headers(con_sync_secret), params={"cuenta_id": cuenta_id}
    )
    assert response.status_code == 409


def test_cuentas_activas_solo_lista_las_que_tienen_ao3_conectado(client, con_sync_secret, control_db, monkeypatch):
    monkeypatch.setattr(settings, "archivum_encryption_key", "zMWJb0d6tsHnMWQJBWVfTFbMnDaR5f6b9yfsMbVF8_w=")
    with control_db() as db:
        con_ao3 = Cuenta(
            email="con@example.com",
            password_hash=hashear_password("x"),
            ao3_username="con",
            ao3_password_encriptada=encriptar("x"),
        )
        sin_ao3 = Cuenta(email="sin@example.com", password_hash=hashear_password("x"))
        db.add_all([con_ao3, sin_ao3])
        db.commit()
        db.refresh(con_ao3)
        con_ao3_id = con_ao3.id

    response = client.get("/api/sync/cuentas-activas", headers=_headers(con_sync_secret))
    assert response.status_code == 200
    assert response.json() == {"cuenta_ids": [con_ao3_id]}


def test_cuentas_activas_rechaza_sin_secreto(client, con_sync_secret, control_db):
    response = client.get("/api/sync/cuentas-activas")
    assert response.status_code == 401


def test_notificar_novedades_sin_gmail_configurado_no_manda(client, con_sync_secret, cuenta_id, monkeypatch):
    monkeypatch.setattr(settings, "gmail_address", "")
    monkeypatch.setattr(settings, "gmail_app_password", "")
    response = client.post(
        "/api/sync/notificar-novedades",
        headers=_headers(con_sync_secret),
        params={"cuenta_id": cuenta_id},
        json={"novedades": [{"ao3_id": "1", "titulo": "X", "tipos": ["capitulo_nuevo"]}]},
    )
    assert response.status_code == 200
    assert response.json() == {"enviado": False}


def test_notificar_novedades_sin_novedades_no_manda(client, con_sync_secret, cuenta_id, monkeypatch):
    monkeypatch.setattr(settings, "gmail_address", "bot@example.com")
    monkeypatch.setattr(settings, "gmail_app_password", "clave-de-app")
    response = client.post(
        "/api/sync/notificar-novedades",
        headers=_headers(con_sync_secret),
        params={"cuenta_id": cuenta_id},
        json={"novedades": []},
    )
    assert response.status_code == 200
    assert response.json() == {"enviado": False}


# ---------------------------------------------------------------------------
# /trigger (lo habla el frontend)
# ---------------------------------------------------------------------------


def test_trigger_sin_github_configurado_devuelve_503(client, cuenta_logueada):
    response = client.post("/api/sync/trigger", headers=_token_headers(cuenta_logueada), json={"modo": "bookmarks"})
    assert response.status_code == 503


def test_trigger_modo_desconocido(client, cuenta_logueada, monkeypatch):
    monkeypatch.setattr(settings, "github_pat", "token-falso")
    monkeypatch.setattr(settings, "github_repo", "usuario/repo")
    response = client.post("/api/sync/trigger", headers=_token_headers(cuenta_logueada), json={"modo": "invalido"})
    assert response.status_code == 400


def test_trigger_modo_fic_sin_url(client, cuenta_logueada, monkeypatch):
    monkeypatch.setattr(settings, "github_pat", "token-falso")
    monkeypatch.setattr(settings, "github_repo", "usuario/repo")
    response = client.post("/api/sync/trigger", headers=_token_headers(cuenta_logueada), json={"modo": "fic"})
    assert response.status_code == 400


def test_trigger_modo_epub_sin_ao3_id(client, cuenta_logueada, monkeypatch):
    monkeypatch.setattr(settings, "github_pat", "token-falso")
    monkeypatch.setattr(settings, "github_repo", "usuario/repo")
    response = client.post("/api/sync/trigger", headers=_token_headers(cuenta_logueada), json={"modo": "epub"})
    assert response.status_code == 400


def test_trigger_sin_credenciales_de_ao3_da_409(client, control_db, monkeypatch):
    monkeypatch.setattr(settings, "archivum_auth_token", "en-produccion")
    monkeypatch.setattr(settings, "github_pat", "token-falso")
    monkeypatch.setattr(settings, "github_repo", "usuario/repo")
    with control_db() as db:
        cuenta = Cuenta(email="sin-ao3@example.com", password_hash=hashear_password("x"))
        db.add(cuenta)
        db.commit()
        db.refresh(cuenta)
        token = crear_sesion(db, cuenta)

    response = client.post("/api/sync/trigger", headers=_token_headers(token), json={"modo": "bookmarks"})
    assert response.status_code == 409


@responses.activate
def test_trigger_dispara_el_workflow_de_github_con_cuenta_id(client, cuenta_logueada, monkeypatch):
    monkeypatch.setattr(settings, "github_pat", "token-falso")
    monkeypatch.setattr(settings, "github_repo", "usuario/repo")
    monkeypatch.setattr(settings, "github_workflow_file", "ao3-sync.yml")

    responses.add(
        responses.POST,
        "https://api.github.com/repos/usuario/repo/actions/workflows/ao3-sync.yml/dispatches",
        status=204,
    )

    response = client.post("/api/sync/trigger", headers=_token_headers(cuenta_logueada), json={"modo": "bookmarks"})
    assert response.status_code == 200
    assert response.json() == {"disparado": True}

    llamada = responses.calls[0].request
    assert llamada.headers["Authorization"] == "Bearer token-falso"
    body = json.loads(llamada.body)
    assert body["inputs"]["cuenta_id"] == "1"
    assert body["inputs"]["modo"] == "bookmarks"


@responses.activate
def test_trigger_modo_fic_manda_la_url(client, cuenta_logueada, monkeypatch):
    monkeypatch.setattr(settings, "github_pat", "token-falso")
    monkeypatch.setattr(settings, "github_repo", "usuario/repo")

    responses.add(
        responses.POST,
        "https://api.github.com/repos/usuario/repo/actions/workflows/ao3-sync.yml/dispatches",
        status=204,
    )

    response = client.post(
        "/api/sync/trigger",
        headers=_token_headers(cuenta_logueada),
        json={"modo": "fic", "url": "https://archiveofourown.org/works/1"},
    )
    assert response.status_code == 200

    body = json.loads(responses.calls[0].request.body)
    assert body["inputs"]["url"] == "https://archiveofourown.org/works/1"


@responses.activate
def test_trigger_propaga_error_de_github(client, cuenta_logueada, monkeypatch):
    monkeypatch.setattr(settings, "github_pat", "token-falso")
    monkeypatch.setattr(settings, "github_repo", "usuario/repo")

    responses.add(
        responses.POST,
        "https://api.github.com/repos/usuario/repo/actions/workflows/ao3-sync.yml/dispatches",
        status=404,
        body="Not Found",
    )

    response = client.post("/api/sync/trigger", headers=_token_headers(cuenta_logueada), json={"modo": "bookmarks"})
    assert response.status_code == 502
