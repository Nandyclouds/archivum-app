import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.database import Base, get_session
from app.main import app


@pytest.fixture(autouse=True)
def _perfil_dir_temporal(tmp_path, monkeypatch):
    monkeypatch.setattr(Settings, "perfil_dir", property(lambda self: tmp_path))


@pytest.fixture()
def client():
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
    yield TestClient(app)
    app.dependency_overrides.clear()
    session.close()


def _imagen_falsa():
    return io.BytesIO(b"contenido de imagen falsa")


def test_obtener_perfil_vacio(client):
    r = client.get("/api/perfil")
    assert r.json() == {"tiene_avatar": False, "tiene_portada": False}


def test_subir_avatar(client, tmp_path):
    r = client.post(
        "/api/perfil/avatar", files={"archivo": ("foto.jpg", _imagen_falsa(), "image/jpeg")}
    )
    assert r.status_code == 200

    r = client.get("/api/perfil")
    assert r.json() == {"tiene_avatar": True, "tiene_portada": False}

    assert (tmp_path / "avatar.jpg").read_bytes() == b"contenido de imagen falsa"


def test_subir_portada(client):
    r = client.post(
        "/api/perfil/portada", files={"archivo": ("banner.png", _imagen_falsa(), "image/png")}
    )
    assert r.status_code == 200
    assert client.get("/api/perfil").json()["tiene_portada"] is True


def test_subir_formato_no_soportado(client):
    r = client.post(
        "/api/perfil/avatar", files={"archivo": ("archivo.gif", _imagen_falsa(), "image/gif")}
    )
    assert r.status_code == 415


def test_obtener_imagen_inexistente(client):
    r = client.get("/api/perfil/imagen/avatar")
    assert r.status_code == 404


def test_obtener_imagen_tipo_invalido(client):
    r = client.get("/api/perfil/imagen/banner")
    assert r.status_code == 404


def test_obtener_imagen_subida(client):
    client.post("/api/perfil/avatar", files={"archivo": ("foto.jpg", _imagen_falsa(), "image/jpeg")})
    r = client.get("/api/perfil/imagen/avatar")
    assert r.status_code == 200
    assert r.content == b"contenido de imagen falsa"


def test_reemplazar_avatar_actualiza_la_ruta(client, tmp_path):
    client.post("/api/perfil/avatar", files={"archivo": ("uno.jpg", _imagen_falsa(), "image/jpeg")})
    client.post(
        "/api/perfil/avatar",
        files={"archivo": ("dos.png", io.BytesIO(b"otra imagen"), "image/png")},
    )
    r = client.get("/api/perfil/imagen/avatar")
    assert r.content == b"otra imagen"
