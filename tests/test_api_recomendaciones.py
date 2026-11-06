import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_session
from app.main import app
from app.models import Archivo, Fic


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


def _crear_fic(db, *, ao3_id="1", titulo="Un fic", resumen="Un resumen") -> Fic:
    fic = Fic(
        ao3_id=ao3_id,
        titulo=titulo,
        autor="autora",
        url=f"https://archiveofourown.org/works/{ao3_id}",
        word_count=1234,
        chapters_published=1,
        chapters_total=1,
        complete=True,
        restricted=False,
        summary=resumen,
        rating="Teen And Up Audiences",
    )
    db.add(fic)
    db.commit()
    db.refresh(fic)
    return fic


def test_crear_lista_y_obtenerla_por_token(client, db_session):
    f1 = _crear_fic(db_session, ao3_id="1", titulo="Primero")
    f2 = _crear_fic(db_session, ao3_id="2", titulo="Segundo")

    r = client.post(
        "/api/recomendaciones",
        json={"titulo": "Para vos", "nota": "espero que te gusten", "fic_ids": [f2.id, f1.id]},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["cantidad_fics"] == 2
    token = body["token"]

    r = client.get(f"/api/recomendaciones/{token}")
    assert r.status_code == 200
    detalle = r.json()
    assert detalle["titulo"] == "Para vos"
    # respeta el orden pasado (f2 antes que f1), no el orden de id
    assert [f["titulo"] for f in detalle["fics"]] == ["Segundo", "Primero"]
    # campos públicos presentes, nada de biblioteca personal
    assert detalle["fics"][0]["url"] == f2.url
    assert detalle["fics"][0]["summary"] == "Un resumen"
    assert "estado_actual" not in detalle["fics"][0]
    assert "nota_bookmark" not in detalle["fics"][0]


def test_crear_lista_sin_fics_validos_falla(client, db_session):
    r = client.post("/api/recomendaciones", json={"fic_ids": [9999]})
    assert r.status_code == 400


def test_obtener_lista_con_token_inexistente_da_404(client):
    r = client.get("/api/recomendaciones/no-existe")
    assert r.status_code == 404


def test_listar_y_borrar_listas(client, db_session):
    fic = _crear_fic(db_session)
    creada = client.post("/api/recomendaciones", json={"fic_ids": [fic.id]}).json()

    r = client.get("/api/recomendaciones")
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.delete(f"/api/recomendaciones/{creada['id']}")
    assert r.status_code == 204

    assert client.get("/api/recomendaciones").json() == []
    assert client.get(f"/api/recomendaciones/{creada['token']}").status_code == 404


def test_detalle_marca_si_un_fic_tiene_copia_archivada(client, db_session):
    con_copia = _crear_fic(db_session, ao3_id="1", titulo="Con copia")
    sin_copia = _crear_fic(db_session, ao3_id="2", titulo="Sin copia")
    db_session.add(
        Archivo(
            fic_id=con_copia.id,
            formato="html",
            ruta_local="/no/existe.html",
            hash_sha256="x",
            tamano=0,
        )
    )
    db_session.commit()

    r = client.post("/api/recomendaciones", json={"fic_ids": [con_copia.id, sin_copia.id]})
    token = r.json()["token"]

    detalle = client.get(f"/api/recomendaciones/{token}").json()
    por_titulo = {f["titulo"]: f for f in detalle["fics"]}
    assert por_titulo["Con copia"]["tiene_copia_html"] is True
    assert por_titulo["Con copia"]["id"] == con_copia.id
    assert por_titulo["Sin copia"]["tiene_copia_html"] is False


def test_copia_archivada_publica_sirve_el_html_en_modo_lectura(client, db_session, tmp_path):
    fic = _crear_fic(db_session)
    ruta = tmp_path / "1.html"
    ruta.write_text("<html><body><p>Hola</p></body></html>", encoding="utf-8")
    db_session.add(
        Archivo(fic_id=fic.id, formato="html", ruta_local=str(ruta), hash_sha256="x", tamano=10)
    )
    db_session.commit()

    token = client.post("/api/recomendaciones", json={"fic_ids": [fic.id]}).json()["token"]

    r = client.get(f"/api/recomendaciones/{token}/fics/{fic.id}/contenido")
    assert r.status_code == 200
    assert "Hola" in r.text
    assert "<style>" in r.text  # modo lectura inyectado


def test_copia_archivada_publica_404_si_el_fic_no_esta_en_la_lista(client, db_session):
    de_la_lista = _crear_fic(db_session, ao3_id="1")
    otro = _crear_fic(db_session, ao3_id="2")
    token = client.post("/api/recomendaciones", json={"fic_ids": [de_la_lista.id]}).json()["token"]

    r = client.get(f"/api/recomendaciones/{token}/fics/{otro.id}/contenido")
    assert r.status_code == 404


def test_copia_archivada_publica_404_si_no_hay_copia(client, db_session):
    fic = _crear_fic(db_session)
    token = client.post("/api/recomendaciones", json={"fic_ids": [fic.id]}).json()["token"]

    r = client.get(f"/api/recomendaciones/{token}/fics/{fic.id}/contenido")
    assert r.status_code == 404


def test_copia_archivada_publica_no_trae_el_bookmark_ni_el_comentario_de_quien_la_guardo(
    client, db_session, tmp_path
):
    fic = _crear_fic(db_session)
    ruta = tmp_path / "1.html"
    ruta.write_text(
        """<html><body>
        <p>Hola</p>
        <div id="bookmark_form_placement" class="wrapper toggled">
          <div class="post bookmark" id="bookmark-form">
            <input value="Leidos 2024" name="bookmark[tag_string]" />
          </div>
        </div>
        <div id="add_comment_placeholder">
          <div id="add_comment">Comment as FerAsdfgh</div>
        </div>
        </body></html>""",
        encoding="utf-8",
    )
    db_session.add(
        Archivo(fic_id=fic.id, formato="html", ruta_local=str(ruta), hash_sha256="x", tamano=10)
    )
    db_session.commit()

    token = client.post("/api/recomendaciones", json={"fic_ids": [fic.id]}).json()["token"]

    r = client.get(f"/api/recomendaciones/{token}/fics/{fic.id}/contenido")
    assert r.status_code == 200
    assert "Hola" in r.text
    assert "Leidos 2024" not in r.text
    assert "FerAsdfgh" not in r.text
    assert "bookmark_form_placement" not in r.text
    assert "add_comment_placeholder" not in r.text


def test_quitar_fic_de_lista_publicada(client, db_session):
    f1 = _crear_fic(db_session, ao3_id="1", titulo="Primero")
    f2 = _crear_fic(db_session, ao3_id="2", titulo="Segundo")
    creada = client.post("/api/recomendaciones", json={"fic_ids": [f1.id, f2.id]}).json()

    r = client.delete(f"/api/recomendaciones/{creada['id']}/fics/{f1.id}")
    assert r.status_code == 204

    detalle = client.get(f"/api/recomendaciones/{creada['token']}").json()
    assert [f["titulo"] for f in detalle["fics"]] == ["Segundo"]


def test_quitar_fic_que_no_esta_en_la_lista_da_404(client, db_session):
    f1 = _crear_fic(db_session, ao3_id="1")
    f2 = _crear_fic(db_session, ao3_id="2")
    creada = client.post("/api/recomendaciones", json={"fic_ids": [f1.id]}).json()

    r = client.delete(f"/api/recomendaciones/{creada['id']}/fics/{f2.id}")
    assert r.status_code == 404


def test_quitar_fic_de_lista_inexistente_da_404(client, db_session):
    fic = _crear_fic(db_session)
    r = client.delete(f"/api/recomendaciones/9999/fics/{fic.id}")
    assert r.status_code == 404
