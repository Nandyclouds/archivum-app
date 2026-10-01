import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main_module
from app.auth import crear_sesion, hashear_password
from app.config import settings
from app.control_models import Cuenta
from app.crypto import desencriptar
from app.database import Base, get_session
from app.main import app


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine)
    session = TestSessionLocal()

    def override_get_session():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app)
    app.dependency_overrides.clear()
    session.close()


@pytest.fixture()
def cuenta_logueada(monkeypatch):
    """Una cuenta real (no la _CUENTA_UNICA de modo sin login), con sesión
    válida — para probar el endpoint de credenciales de AO3 tal como lo usa
    producción (ARCHIVUM_AUTH_TOKEN puesto)."""
    monkeypatch.setattr(settings, "archivum_auth_token", "en-produccion")
    monkeypatch.setattr(settings, "archivum_encryption_key", "zMWJb0d6tsHnMWQJBWVfTFbMnDaR5f6b9yfsMbVF8_w=")

    control_engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    main_module.ControlBase.metadata.create_all(control_engine)
    TestControlSessionLocal = sessionmaker(bind=control_engine)
    monkeypatch.setattr(main_module, "ControlSessionLocal", TestControlSessionLocal)

    import app.control_db as control_db_module

    monkeypatch.setattr(control_db_module, "ControlSessionLocal", TestControlSessionLocal)

    with TestControlSessionLocal() as db:
        cuenta = Cuenta(email="nanda@example.com", password_hash=hashear_password("x"), es_admin=True)
        db.add(cuenta)
        db.commit()
        db.refresh(cuenta)
        token = crear_sesion(db, cuenta)

    yield token


def _headers(token):
    return {"X-Archivum-Token": token}


def test_guardar_credenciales_de_ao3(client, cuenta_logueada):
    r = client.put(
        "/api/auth/ao3-credenciales",
        json={"ao3_username": "mi-usuario-ao3", "ao3_password": "mi-secreta"},
        headers=_headers(cuenta_logueada),
    )
    assert r.status_code == 200
    assert r.json() == {"ao3_username": "mi-usuario-ao3"}

    r = client.get("/api/auth/yo", headers=_headers(cuenta_logueada))
    assert r.json()["ao3_username"] == "mi-usuario-ao3"


def test_la_contraseña_se_guarda_cifrada(client, cuenta_logueada):
    client.put(
        "/api/auth/ao3-credenciales",
        json={"ao3_username": "mi-usuario-ao3", "ao3_password": "mi-secreta"},
        headers=_headers(cuenta_logueada),
    )

    import app.control_db as control_db_module

    with control_db_module.ControlSessionLocal() as db:
        cuenta = db.query(Cuenta).filter_by(email="nanda@example.com").one()
        assert cuenta.ao3_password_encriptada != "mi-secreta"
        assert desencriptar(cuenta.ao3_password_encriptada) == "mi-secreta"


def test_borrar_credenciales_de_ao3(client, cuenta_logueada):
    client.put(
        "/api/auth/ao3-credenciales",
        json={"ao3_username": "mi-usuario-ao3", "ao3_password": "mi-secreta"},
        headers=_headers(cuenta_logueada),
    )
    r = client.delete("/api/auth/ao3-credenciales", headers=_headers(cuenta_logueada))
    assert r.status_code == 204

    r = client.get("/api/auth/yo", headers=_headers(cuenta_logueada))
    assert r.json()["ao3_username"] is None


def test_rechaza_usuario_o_contraseña_vacíos(client, cuenta_logueada):
    r = client.put(
        "/api/auth/ao3-credenciales",
        json={"ao3_username": "  ", "ao3_password": "mi-secreta"},
        headers=_headers(cuenta_logueada),
    )
    assert r.status_code == 422

    r = client.put(
        "/api/auth/ao3-credenciales",
        json={"ao3_username": "mi-usuario-ao3", "ao3_password": ""},
        headers=_headers(cuenta_logueada),
    )
    assert r.status_code == 422
