import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_session
from app.main import app
from app.models import Fic, Novedad


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


def test_listar_novedades_vacio(client):
    assert client.get("/api/novedades").json() == []


def test_listar_novedades_por_defecto_solo_no_leidas(client, db_session):
    fic = _crear_fic(db_session)
    db_session.add_all(
        [
            Novedad(fic_id=fic.id, tipo="capitulo_nuevo", capitulos_publicados=5, leida=False),
            Novedad(fic_id=fic.id, tipo="completado", capitulos_publicados=10, leida=True),
        ]
    )
    db_session.commit()

    body = client.get("/api/novedades").json()
    assert len(body) == 1
    assert body[0]["tipo"] == "capitulo_nuevo"
    assert body[0]["fic_titulo"] == "Un fic"


def test_listar_novedades_incluye_leidas_si_se_pide(client, db_session):
    fic = _crear_fic(db_session)
    db_session.add(Novedad(fic_id=fic.id, tipo="completado", capitulos_publicados=10, leida=True))
    db_session.commit()

    body = client.get("/api/novedades", params={"solo_no_leidas": False}).json()
    assert len(body) == 1


def test_marcar_leida(client, db_session):
    fic = _crear_fic(db_session)
    novedad = Novedad(fic_id=fic.id, tipo="capitulo_nuevo", capitulos_publicados=5)
    db_session.add(novedad)
    db_session.commit()

    response = client.post(f"/api/novedades/{novedad.id}/marcar-leida")
    assert response.status_code == 200
    assert response.json()["leida"] is True
    assert client.get("/api/novedades").json() == []


def test_marcar_leida_inexistente(client):
    assert client.post("/api/novedades/999/marcar-leida").status_code == 404


def test_marcar_todas_leidas(client, db_session):
    fic = _crear_fic(db_session)
    db_session.add_all(
        [
            Novedad(fic_id=fic.id, tipo="capitulo_nuevo", capitulos_publicados=5),
            Novedad(fic_id=fic.id, tipo="completado", capitulos_publicados=10),
        ]
    )
    db_session.commit()

    response = client.post("/api/novedades/marcar-todas-leidas")
    assert response.status_code == 200
    assert client.get("/api/novedades").json() == []
