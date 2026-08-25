import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.database import Base, get_session
from app.main import app
from app.models import Coleccion, Fic


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
        "avatar_posicion": "50% 50%",
        "portada_posicion": "50% 50%",
        "cita_texto": None,
        "cita_fuente": None,
        "nombre_usuario": None,
        "handle": None,
        "pronombres": None,
        "insignia": None,
        "bio": None,
    }


def test_actualizar_posicion_avatar(client):
    r = client.put("/api/perfil/posicion/avatar", json={"x": 30, "y": 70})
    assert r.status_code == 200
    assert client.get("/api/perfil").json()["avatar_posicion"] == "30.0% 70.0%"


def test_actualizar_posicion_tipo_invalido(client):
    r = client.put("/api/perfil/posicion/banner", json={"x": 30, "y": 70})
    assert r.status_code == 404


def test_actualizar_posicion_fuera_de_rango(client):
    r = client.put("/api/perfil/posicion/avatar", json={"x": 130, "y": 70})
    assert r.status_code == 422


def test_subir_foto_nueva_resetea_posicion(client):
    client.put("/api/perfil/posicion/avatar", json={"x": 30, "y": 70})
    client.post("/api/perfil/avatar", files={"archivo": ("otra.jpg", _imagen_falsa(), "image/jpeg")})
    assert client.get("/api/perfil").json()["avatar_posicion"] == "50% 50%"


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


def test_actualizar_identidad(client):
    r = client.patch(
        "/api/perfil",
        json={
            "nombre_usuario": "mafe",
            "handle": "crislvsbooks",
            "pronombres": "she/her",
            "insignia": "Protagonist",
            "bio": "throw a punch, fall in love",
        },
    )
    assert r.status_code == 200

    body = client.get("/api/perfil").json()
    assert body["nombre_usuario"] == "mafe"
    assert body["handle"] == "crislvsbooks"
    assert body["pronombres"] == "she/her"
    assert body["insignia"] == "Protagonist"
    assert body["bio"] == "throw a punch, fall in love"


def test_actualizar_identidad_no_pisa_la_cita(client):
    client.patch("/api/perfil", json={"cita_texto": "una cita", "cita_fuente": "un fic"})
    client.patch("/api/perfil", json={"nombre_usuario": "mafe"})

    body = client.get("/api/perfil").json()
    assert body["nombre_usuario"] == "mafe"
    assert body["cita_texto"] == "una cita"
    assert body["cita_fuente"] == "un fic"


def test_actualizar_cita_no_pisa_la_identidad(client):
    client.patch("/api/perfil", json={"nombre_usuario": "mafe", "bio": "hola"})
    client.patch("/api/perfil", json={"cita_texto": "una cita", "cita_fuente": "un fic"})

    body = client.get("/api/perfil").json()
    assert body["nombre_usuario"] == "mafe"
    assert body["bio"] == "hola"


def test_favoritos_vacio(client):
    assert client.get("/api/perfil/favoritos").json() == {
        "coleccion_id": None,
        "total": 0,
        "fics": [],
        "todos": [],
        "destacados_ids": [],
    }


def test_agregar_y_listar_favoritos(client, db_session):
    fic = _crear_fic(db_session, ao3_id="1", titulo="Mi favorito")

    r = client.post("/api/perfil/favoritos", json={"fic_id": fic.id})
    assert r.status_code == 201

    body = client.get("/api/perfil/favoritos").json()
    assert body["total"] == 1
    assert body["fics"] == [{"fic_id": fic.id, "titulo": "Mi favorito", "autor": "autora"}]
    assert body["coleccion_id"] is not None


def test_agregar_favorito_usa_coleccion_favoritos_existente(client, db_session):
    """Si ya existe una colección "Favoritos" (ej. de un tag de AO3), se
    reusa esa — no se crea una segunda lista de favoritos separada."""
    coleccion = Coleccion(nombre="Favoritos", tipo="bookmark_tag")
    db_session.add(coleccion)
    db_session.commit()
    fic = _crear_fic(db_session, ao3_id="1", titulo="Ya en AO3")
    coleccion.fics.append(fic)
    db_session.commit()

    nuevo = _crear_fic(db_session, ao3_id="2", titulo="Agregado desde el perfil")
    client.post("/api/perfil/favoritos", json={"fic_id": nuevo.id})

    body = client.get("/api/perfil/favoritos").json()
    assert body["coleccion_id"] == coleccion.id
    assert body["total"] == 2
    assert db_session.query(Coleccion).filter_by(nombre="Favoritos").count() == 1


def test_favoritos_muestra_como_maximo_cuatro_pero_cuenta_el_total(client, db_session):
    for i in range(6):
        fic = _crear_fic(db_session, ao3_id=str(i), titulo=f"Fic {i}")
        client.post("/api/perfil/favoritos", json={"fic_id": fic.id})

    body = client.get("/api/perfil/favoritos").json()
    assert body["total"] == 6
    assert len(body["fics"]) == 4


def test_agregar_favorito_fic_inexistente(client):
    r = client.post("/api/perfil/favoritos", json={"fic_id": 999})
    assert r.status_code == 404


def test_agregar_favorito_duplicado(client, db_session):
    fic = _crear_fic(db_session, ao3_id="1")
    client.post("/api/perfil/favoritos", json={"fic_id": fic.id})

    r = client.post("/api/perfil/favoritos", json={"fic_id": fic.id})
    assert r.status_code == 409


def test_quitar_favorito(client, db_session):
    fic = _crear_fic(db_session, ao3_id="1")
    client.post("/api/perfil/favoritos", json={"fic_id": fic.id})

    r = client.delete(f"/api/perfil/favoritos/{fic.id}")
    assert r.status_code == 204
    assert client.get("/api/perfil/favoritos").json()["total"] == 0


def test_quitar_favorito_inexistente_no_falla(client):
    r = client.delete("/api/perfil/favoritos/999")
    assert r.status_code == 204


def test_destacados_por_defecto_es_fallback_alfabetico(client, db_session):
    for titulo in ["Zeta", "Alfa", "Beta"]:
        fic = _crear_fic(db_session, ao3_id=titulo, titulo=titulo)
        client.post("/api/perfil/favoritos", json={"fic_id": fic.id})

    body = client.get("/api/perfil/favoritos").json()
    assert [f["titulo"] for f in body["fics"]] == ["Alfa", "Beta", "Zeta"]
    assert body["destacados_ids"] == []


def test_elegir_destacados_a_mano(client, db_session):
    fics = [_crear_fic(db_session, ao3_id=str(i), titulo=f"Fic {i}") for i in range(6)]
    for fic in fics:
        client.post("/api/perfil/favoritos", json={"fic_id": fic.id})

    elegidos = [fics[5].id, fics[0].id]
    r = client.put("/api/perfil/favoritos/destacados", json={"fic_ids": elegidos})
    assert r.status_code == 200

    body = client.get("/api/perfil/favoritos").json()
    assert [f["fic_id"] for f in body["fics"]] == elegidos
    assert body["destacados_ids"] == elegidos
    assert body["total"] == 6
    assert len(body["todos"]) == 6


def test_destacados_maximo_cuatro(client, db_session):
    fics = [_crear_fic(db_session, ao3_id=str(i), titulo=f"Fic {i}") for i in range(5)]
    for fic in fics:
        client.post("/api/perfil/favoritos", json={"fic_id": fic.id})

    r = client.put("/api/perfil/favoritos/destacados", json={"fic_ids": [f.id for f in fics]})
    assert r.status_code == 422


def test_destacados_rechaza_fic_fuera_de_favoritos(client, db_session):
    dentro = _crear_fic(db_session, ao3_id="1", titulo="Dentro")
    client.post("/api/perfil/favoritos", json={"fic_id": dentro.id})
    fuera = _crear_fic(db_session, ao3_id="2", titulo="Fuera")

    r = client.put("/api/perfil/favoritos/destacados", json={"fic_ids": [dentro.id, fuera.id]})
    assert r.status_code == 422


def test_destacados_vacio_vuelve_al_fallback(client, db_session):
    fics = [_crear_fic(db_session, ao3_id=str(i), titulo=t) for i, t in enumerate(["Zeta", "Alfa"])]
    for fic in fics:
        client.post("/api/perfil/favoritos", json={"fic_id": fic.id})
    client.put("/api/perfil/favoritos/destacados", json={"fic_ids": [fics[0].id]})

    r = client.put("/api/perfil/favoritos/destacados", json={"fic_ids": []})
    assert r.status_code == 200

    body = client.get("/api/perfil/favoritos").json()
    assert [f["titulo"] for f in body["fics"]] == ["Alfa", "Zeta"]


def test_reemplazar_avatar_actualiza_la_ruta(client, tmp_path):
    client.post("/api/perfil/avatar", files={"archivo": ("uno.jpg", _imagen_falsa(), "image/jpeg")})
    client.post(
        "/api/perfil/avatar",
        files={"archivo": ("dos.png", io.BytesIO(b"otra imagen"), "image/png")},
    )
    r = client.get("/api/perfil/imagen/avatar")
    assert r.content == b"otra imagen"
