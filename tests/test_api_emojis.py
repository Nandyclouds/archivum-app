import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_session
from app.main import app


@pytest.fixture()
def db_session(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(type(settings), "emojis_dir", property(lambda self: tmp_path / "emojis"))

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


def _imagen_png() -> bytes:
    # PNG 1x1 mínimo válido.
    return bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753"
        "de0000000c4944415478da6360606060000000050001a5f645400000000049454e44ae426082"
    )


def test_crear_y_listar_emoji(client):
    r = client.post(
        "/api/emojis",
        data={"nombre": "dinosaurio"},
        files={"archivo": ("dino.png", io.BytesIO(_imagen_png()), "image/png")},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["nombre"] == "dinosaurio"

    r = client.get("/api/emojis")
    assert r.status_code == 200
    assert [e["nombre"] for e in r.json()] == ["dinosaurio"]


def test_crear_emoji_nombre_invalido(client):
    r = client.post(
        "/api/emojis",
        data={"nombre": "con espacio!"},
        files={"archivo": ("dino.png", io.BytesIO(_imagen_png()), "image/png")},
    )
    assert r.status_code == 422


def test_crear_emoji_duplicado(client):
    files = {"archivo": ("dino.png", io.BytesIO(_imagen_png()), "image/png")}
    client.post("/api/emojis", data={"nombre": "dinosaurio"}, files=files)
    r = client.post(
        "/api/emojis",
        data={"nombre": "dinosaurio"},
        files={"archivo": ("dino2.png", io.BytesIO(_imagen_png()), "image/png")},
    )
    assert r.status_code == 409


def test_obtener_imagen_y_borrar(client):
    creado = client.post(
        "/api/emojis",
        data={"nombre": "dinosaurio"},
        files={"archivo": ("dino.png", io.BytesIO(_imagen_png()), "image/png")},
    ).json()

    r = client.get(f"/api/emojis/{creado['id']}/imagen")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"

    r = client.delete(f"/api/emojis/{creado['id']}")
    assert r.status_code == 204
    assert client.get("/api/emojis").json() == []
    assert client.get(f"/api/emojis/{creado['id']}/imagen").status_code == 404
