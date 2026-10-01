import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main_module
from app.auth import crear_sesion, hashear_password
from app.config import settings
from app.control_models import Cuenta
from app.database import Base, get_session
from app.main import app


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
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
def con_token(monkeypatch):
    """Simula producción con ARCHIVUM_AUTH_TOKEN puesto: el token real es el
    de una sesión creada por login, no el secreto del .env directamente."""
    monkeypatch.setattr(settings, "archivum_auth_token", "el-secreto")

    control_engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    main_module.ControlBase.metadata.create_all(control_engine)
    TestControlSessionLocal = sessionmaker(bind=control_engine)
    monkeypatch.setattr(main_module, "ControlSessionLocal", TestControlSessionLocal)

    with TestControlSessionLocal() as db:
        cuenta = Cuenta(email="test@example.com", password_hash=hashear_password("x"), es_admin=True)
        db.add(cuenta)
        db.commit()
        db.refresh(cuenta)
        token = crear_sesion(db, cuenta)

    yield token


def test_sin_token_configurado_no_pide_nada(client):
    # ARCHIVUM_AUTH_TOKEN vacío (default) = comportamiento de siempre, sin auth.
    assert client.get("/api/fics").status_code == 200


def test_con_token_configurado_rechaza_sin_credencial(client, con_token):
    assert client.get("/api/fics").status_code == 401


def test_con_token_configurado_acepta_header_correcto(client, con_token):
    response = client.get("/api/fics", headers={"X-Archivum-Token": con_token})
    assert response.status_code == 200


def test_con_token_configurado_rechaza_header_incorrecto(client, con_token):
    response = client.get("/api/fics", headers={"X-Archivum-Token": "otro"})
    assert response.status_code == 401


def test_con_token_configurado_acepta_query_param(client, con_token):
    response = client.get(f"/api/fics?token={con_token}")
    assert response.status_code == 200


def test_health_siempre_accesible_sin_token(client, con_token):
    assert client.get("/api/health").status_code == 200


def test_preflight_cors_no_pide_token(client, con_token):
    # El navegador manda OPTIONS sin headers custom antes del GET/POST real
    # (preflight de CORS) — si esto se bloquea, el browser nunca intenta la
    # petición real con el token puesto.
    response = client.options(
        "/api/fics",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
