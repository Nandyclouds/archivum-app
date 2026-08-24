import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.database import Base, get_session
from app.main import app
from app.models import Fic


@pytest.fixture(autouse=True)
def _perfil_dir_temporal(tmp_path, monkeypatch):
    monkeypatch.setattr(Settings, "perfil_dir", property(lambda self: tmp_path))


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


def _crear_fic(db, *, ao3_id="1", titulo="Un fic") -> Fic:
    fic = Fic(
        ao3_id=ao3_id,
        titulo=titulo,
        autor="autora",
        url=f"https://archiveofourown.org/works/{ao3_id}",
    )
    db.add(fic)
    db.commit()
    db.refresh(fic)
    return fic


def _imagen_falsa():
    return io.BytesIO(b"contenido de imagen falsa")


def test_obtener_perfil_vacio(client):
    r = client.get("/api/perfil")
    assert r.json() == {
        "tiene_avatar": False,
        "tiene_portada": False,
        "cita_texto": None,
        "cita_fuente": None,
    }


def test_subir_avatar(client, tmp_path):
    r = client.post(
        "/api/perfil/avatar", files={"archivo": ("foto.jpg", _imagen_falsa(), "image/jpeg")}
    )
    assert r.status_code == 200

    r = client.get("/api/perfil")
    assert r.json()["tiene_avatar"] is True
    assert r.json()["tiene_portada"] is False

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


def test_actualizar_cita(client):
    r = client.patch("/api/perfil", json={"cita_texto": "una cita", "cita_fuente": "un fic"})
    assert r.status_code == 200

    r = client.get("/api/perfil")
    assert r.json()["cita_texto"] == "una cita"
    assert r.json()["cita_fuente"] == "un fic"


def test_borrar_cita_con_texto_vacio(client):
    client.patch("/api/perfil", json={"cita_texto": "una cita", "cita_fuente": "un fic"})
    client.patch("/api/perfil", json={"cita_texto": "", "cita_fuente": ""})

    r = client.get("/api/perfil")
    assert r.json()["cita_texto"] is None
    assert r.json()["cita_fuente"] is None


def test_favoritos_vacio(client):
    assert client.get("/api/perfil/favoritos").json() == []


def test_agregar_y_listar_favoritos(client, db_session):
    fic = _crear_fic(db_session, ao3_id="1", titulo="Mi favorito")

    r = client.post("/api/perfil/favoritos", json={"fic_id": fic.id})
    assert r.status_code == 201

    favoritos = client.get("/api/perfil/favoritos").json()
    assert favoritos == [{"fic_id": fic.id, "titulo": "Mi favorito", "orden": 0}]


def test_agregar_favorito_fic_inexistente(client):
    r = client.post("/api/perfil/favoritos", json={"fic_id": 999})
    assert r.status_code == 404


def test_agregar_favorito_duplicado(client, db_session):
    fic = _crear_fic(db_session, ao3_id="1")
    client.post("/api/perfil/favoritos", json={"fic_id": fic.id})

    r = client.post("/api/perfil/favoritos", json={"fic_id": fic.id})
    assert r.status_code == 409


def test_agregar_mas_de_cuatro_favoritos(client, db_session):
    for i in range(4):
        fic = _crear_fic(db_session, ao3_id=str(i))
        assert client.post("/api/perfil/favoritos", json={"fic_id": fic.id}).status_code == 201

    quinto = _crear_fic(db_session, ao3_id="5")
    r = client.post("/api/perfil/favoritos", json={"fic_id": quinto.id})
    assert r.status_code == 409


def test_quitar_favorito(client, db_session):
    fic = _crear_fic(db_session, ao3_id="1")
    client.post("/api/perfil/favoritos", json={"fic_id": fic.id})

    r = client.delete(f"/api/perfil/favoritos/{fic.id}")
    assert r.status_code == 204
    assert client.get("/api/perfil/favoritos").json() == []


def test_quitar_favorito_inexistente_no_falla(client):
    r = client.delete("/api/perfil/favoritos/999")
    assert r.status_code == 204


def test_reemplazar_avatar_actualiza_la_ruta(client, tmp_path):
    client.post("/api/perfil/avatar", files={"archivo": ("uno.jpg", _imagen_falsa(), "image/jpeg")})
    client.post(
        "/api/perfil/avatar",
        files={"archivo": ("dos.png", io.BytesIO(b"otra imagen"), "image/png")},
    )
    r = client.get("/api/perfil/imagen/avatar")
    assert r.content == b"otra imagen"
