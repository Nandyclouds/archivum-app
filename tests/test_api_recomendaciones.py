import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_session
from app.main import app
from app.models import Fic


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
