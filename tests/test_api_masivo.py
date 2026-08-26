import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_session
from app.main import app
from app.models import Coleccion, EtiquetaPersonal, Fic, Lectura


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
    fic = Fic(ao3_id=ao3_id, titulo=titulo, autor="autora", url=f"https://archiveofourown.org/works/{ao3_id}")
    db.add(fic)
    db.commit()
    db.refresh(fic)
    return fic


def test_lecturas_masivo_crea_y_actualiza(client, db_session):
    con_lectura = _crear_fic(db_session, ao3_id="1", titulo="Con lectura")
    db_session.add(Lectura(fic_id=con_lectura.id, estado="pendiente"))
    sin_lectura = _crear_fic(db_session, ao3_id="2", titulo="Sin lectura")
    db_session.commit()

    r = client.post(
        "/api/masivo/lecturas", json={"fic_ids": [con_lectura.id, sin_lectura.id], "estado": "leido"}
    )
    assert r.status_code == 200
    assert r.json() == {"actualizados": 2}

    body_con = client.get(f"/api/fics/{con_lectura.id}").json()
    assert len(body_con["lecturas"]) == 1
    assert body_con["lecturas"][0]["estado"] == "leido"

    body_sin = client.get(f"/api/fics/{sin_lectura.id}").json()
    assert len(body_sin["lecturas"]) == 1
    assert body_sin["lecturas"][0]["estado"] == "leido"


def test_lecturas_masivo_estado_invalido(client, db_session):
    fic = _crear_fic(db_session)
    r = client.post("/api/masivo/lecturas", json={"fic_ids": [fic.id], "estado": "no-existe"})
    assert r.status_code == 200
    assert r.json() == {"actualizados": 0}


def test_etiquetas_masivo_reutiliza_case_insensitive(client, db_session):
    a = _crear_fic(db_session, ao3_id="1", titulo="A")
    b = _crear_fic(db_session, ao3_id="2", titulo="B")
    db_session.add(EtiquetaPersonal(nombre="fluff"))
    db_session.commit()

    r = client.post("/api/masivo/etiquetas", json={"fic_ids": [a.id, b.id], "nombre": "Fluff"})
    assert r.status_code == 200
    assert r.json() == {"actualizados": 2}
    assert client.get("/api/etiquetas").json() == [{"id": 1, "nombre": "fluff"}]
    assert len(client.get(f"/api/fics/{a.id}").json()["etiquetas_personales"]) == 1
    assert len(client.get(f"/api/fics/{b.id}").json()["etiquetas_personales"]) == 1


def test_colecciones_masivo(client, db_session):
    a = _crear_fic(db_session, ao3_id="1", titulo="A")
    b = _crear_fic(db_session, ao3_id="2", titulo="B")
    coleccion = Coleccion(nombre="Favoritos", tipo="personalizada")
    db_session.add(coleccion)
    db_session.commit()

    r = client.post("/api/masivo/colecciones", json={"fic_ids": [a.id, b.id], "coleccion_id": coleccion.id})
    assert r.status_code == 200
    assert r.json() == {"actualizados": 2}
    assert len(client.get(f"/api/fics/{a.id}").json()["colecciones"]) == 1
    assert len(client.get(f"/api/fics/{b.id}").json()["colecciones"]) == 1
