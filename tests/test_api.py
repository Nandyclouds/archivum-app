import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_session
from app.main import app
from app.models import Archivo, Fandom, Fic, Lectura, Personaje, Resena, Ship, TagAdicional


@pytest.fixture()
def db_session():
    # StaticPool: el TestClient corre los requests en otro hilo, y una DB
    # ":memory:" es por conexión -> sin esto, ese hilo ve una DB vacía sin
    # tablas. StaticPool fuerza que todos los hilos compartan una sola
    # conexión/DB real.
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
    yield session
    app.dependency_overrides.clear()
    session.close()


@pytest.fixture()
def client(db_session):
    return TestClient(app)


def _crear_fic(db: Session, *, ao3_id="1", titulo="Un fic", fandom="Fandom A", complete=True, ship=None) -> Fic:
    fandom_obj = db.query(Fandom).filter_by(nombre=fandom).one_or_none()
    if fandom_obj is None:
        fandom_obj = Fandom(nombre=fandom)
        db.add(fandom_obj)
    fic = Fic(
        ao3_id=ao3_id,
        titulo=titulo,
        autor="autora",
        url=f"https://archiveofourown.org/works/{ao3_id}",
        word_count=1000,
        chapters_published=1,
        chapters_total=1,
        complete=complete,
        restricted=False,
    )
    fic.fandoms.append(fandom_obj)
    if ship:
        ship_obj = db.query(Ship).filter_by(nombre=ship).one_or_none()
        if ship_obj is None:
            ship_obj = Ship(nombre=ship, tipo="romantico")
            db.add(ship_obj)
        fic.ships.append(ship_obj)
    db.add(fic)
    db.commit()
    db.refresh(fic)
    return fic


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_listar_fics_vacio(client):
    r = client.get("/api/fics")
    assert r.status_code == 200
    assert r.json() == []


def test_listar_y_obtener_fic(client, db_session):
    fic = _crear_fic(db_session)

    r = client.get("/api/fics")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["titulo"] == "Un fic"
    assert data[0]["fandoms"][0]["nombre"] == "Fandom A"

    r = client.get(f"/api/fics/{fic.id}")
    assert r.status_code == 200
    assert r.json()["ao3_id"] == "1"


def test_obtener_fic_404(client):
    r = client.get("/api/fics/999")
    assert r.status_code == 404


def test_listar_fics_orden_recientes(client, db_session):
    viejo = _crear_fic(db_session, ao3_id="1", titulo="Viejo")
    viejo.fecha_primer_import = datetime.datetime(2024, 1, 1)
    nuevo = _crear_fic(db_session, ao3_id="2", titulo="Nuevo")
    nuevo.fecha_primer_import = datetime.datetime(2026, 1, 1)
    db_session.commit()

    r = client.get("/api/fics", params={"orden": "recientes"})
    assert [f["titulo"] for f in r.json()] == ["Nuevo", "Viejo"]


def test_listar_fics_orden_ultima_lectura(client, db_session):
    leido_hace_poco = _crear_fic(db_session, ao3_id="1", titulo="Leído hace poco")
    leido_hace_mucho = _crear_fic(db_session, ao3_id="2", titulo="Leído hace mucho")
    sin_leer = _crear_fic(db_session, ao3_id="3", titulo="Sin leer")
    db_session.add_all(
        [
            Lectura(fic_id=leido_hace_poco.id, estado="leido", fecha_fin=datetime.date(2026, 1, 1)),
            Lectura(fic_id=leido_hace_mucho.id, estado="leido", fecha_fin=datetime.date(2020, 1, 1)),
        ]
    )
    db_session.commit()

    r = client.get("/api/fics", params={"orden": "ultima_lectura"})
    assert [f["titulo"] for f in r.json()] == ["Leído hace poco", "Leído hace mucho", "Sin leer"]


def test_categorias_warnings_se_parsean_como_lista(client, db_session):
    fic = _crear_fic(db_session)
    fic.categorias = "F/M|Multi"
    fic.warnings = "No Archive Warnings Apply"
    db_session.commit()

    r = client.get(f"/api/fics/{fic.id}")
    body = r.json()
    assert body["categorias"] == ["F/M", "Multi"]
    assert body["warnings"] == ["No Archive Warnings Apply"]


def test_filtrar_fics_por_fandom(client, db_session):
    _crear_fic(db_session, ao3_id="1", titulo="A", fandom="Fandom A")
    _crear_fic(db_session, ao3_id="2", titulo="B", fandom="Fandom B")

    r = client.get("/api/fics", params={"fandom": "Fandom A"})
    data = r.json()
    assert len(data) == 1
    assert data[0]["titulo"] == "A"


def test_filtrar_fics_por_ship(client, db_session):
    _crear_fic(db_session, ao3_id="1", titulo="A", ship="Ship A/Ship B")
    _crear_fic(db_session, ao3_id="2", titulo="B", ship="Ship C/Ship D")

    r = client.get("/api/fics", params={"ship": "Ship A/Ship B"})
    data = r.json()
    assert len(data) == 1
    assert data[0]["titulo"] == "A"


def test_filtrar_fics_por_varios_ships_a_la_vez(client, db_session):
    a = _crear_fic(db_session, ao3_id="1", titulo="A")
    b = _crear_fic(db_session, ao3_id="2", titulo="B")
    ab = Ship(nombre="A/B", tipo="romantico")
    a.ships.extend([ab, Ship(nombre="A & C", tipo="platonico")])
    b.ships.append(ab)
    db_session.commit()

    r = client.get("/api/fics", params=[("ship", "A/B"), ("ship", "A & C")])
    assert [f["titulo"] for f in r.json()] == ["A"]


def test_filtrar_fics_por_personaje(client, db_session):
    a = _crear_fic(db_session, ao3_id="1", titulo="A")
    _crear_fic(db_session, ao3_id="2", titulo="B")
    a.personajes.append(Personaje(nombre="Frodo Baggins"))
    db_session.commit()

    r = client.get("/api/fics", params={"personaje": "Frodo Baggins"})
    assert [f["titulo"] for f in r.json()] == ["A"]


def test_filtrar_fics_por_tag_adicional(client, db_session):
    a = _crear_fic(db_session, ao3_id="1", titulo="A")
    _crear_fic(db_session, ao3_id="2", titulo="B")
    a.tags_adicionales.append(TagAdicional(nombre="Slow Burn"))
    db_session.commit()

    r = client.get("/api/fics", params={"tag": "Slow Burn"})
    assert [f["titulo"] for f in r.json()] == ["A"]


def test_filtrar_fics_por_varios_personajes_a_la_vez(client, db_session):
    a = _crear_fic(db_session, ao3_id="1", titulo="A")
    b = _crear_fic(db_session, ao3_id="2", titulo="B")
    frodo = Personaje(nombre="Frodo Baggins")
    sam = Personaje(nombre="Samwise Gamgee")
    a.personajes.extend([frodo, sam])
    b.personajes.append(frodo)
    db_session.commit()

    # AND, no OR: solo el fic que tiene AMBOS personajes debe aparecer.
    r = client.get("/api/fics", params=[("personaje", "Frodo Baggins"), ("personaje", "Samwise Gamgee")])
    assert [f["titulo"] for f in r.json()] == ["A"]


def test_filtrar_fics_por_varios_tags_a_la_vez(client, db_session):
    a = _crear_fic(db_session, ao3_id="1", titulo="A")
    b = _crear_fic(db_session, ao3_id="2", titulo="B")
    slow_burn = TagAdicional(nombre="Slow Burn")
    a.tags_adicionales.extend([slow_burn, TagAdicional(nombre="Fluff")])
    b.tags_adicionales.append(slow_burn)
    db_session.commit()

    r = client.get("/api/fics", params=[("tag", "Slow Burn"), ("tag", "Fluff")])
    assert [f["titulo"] for f in r.json()] == ["A"]


def test_filtrar_fics_por_categoria(client, db_session):
    a = _crear_fic(db_session, ao3_id="1", titulo="A")
    a.categorias = "F/F"
    b = _crear_fic(db_session, ao3_id="2", titulo="B")
    b.categorias = "F/M|Multi"
    db_session.commit()

    r = client.get("/api/fics", params={"categoria": "F/F"})
    assert [f["titulo"] for f in r.json()] == ["A"]


def test_filtrar_fics_por_idioma(client, db_session):
    a = _crear_fic(db_session, ao3_id="1", titulo="A")
    a.idioma = "Español"
    b = _crear_fic(db_session, ao3_id="2", titulo="B")
    b.idioma = "English"
    db_session.commit()

    r = client.get("/api/fics", params={"idioma": "Español"})
    assert [f["titulo"] for f in r.json()] == ["A"]


def test_filtrar_fics_por_con_nota(client, db_session):
    a = _crear_fic(db_session, ao3_id="1", titulo="A")
    a.nota_bookmark = "qué lindo esto"
    _crear_fic(db_session, ao3_id="2", titulo="B")
    db_session.commit()

    r = client.get("/api/fics", params={"con_nota": True})
    assert [f["titulo"] for f in r.json()] == ["A"]
    assert r.json()[0]["nota_bookmark"] == "qué lindo esto"

    r_todos = client.get("/api/fics")
    assert len(r_todos.json()) == 2


def test_filtrar_fics_por_rating_exacto(client, db_session):
    cinco = _crear_fic(db_session, ao3_id="1", titulo="Cinco")
    cuatro = _crear_fic(db_session, ao3_id="2", titulo="Cuatro")
    db_session.add_all(
        [
            Resena(fic_id=cinco.id, rating=5),
            Resena(fic_id=cuatro.id, rating=4),
        ]
    )
    db_session.commit()

    r = client.get("/api/fics", params={"rating_exacto": 5})
    assert [f["titulo"] for f in r.json()] == ["Cinco"]


def test_filtrar_fics_por_hizo_llorar(client, db_session):
    llore = _crear_fic(db_session, ao3_id="1", titulo="Lloré")
    no_llore = _crear_fic(db_session, ao3_id="2", titulo="No lloré")
    db_session.add_all(
        [
            Resena(fic_id=llore.id, rating=5, hizo_llorar=True),
            Resena(fic_id=no_llore.id, rating=5, hizo_llorar=False),
        ]
    )
    db_session.commit()

    r = client.get("/api/fics", params={"hizo_llorar": True})
    assert [f["titulo"] for f in r.json()] == ["Lloré"]


def test_filtrar_fics_por_es_relectura(client, db_session):
    releido = _crear_fic(db_session, ao3_id="1", titulo="Releído")
    no_releido = _crear_fic(db_session, ao3_id="2", titulo="No releído")
    db_session.add_all(
        [
            Lectura(fic_id=releido.id, estado="leido", es_relectura=True),
            Lectura(fic_id=no_releido.id, estado="leido", es_relectura=False),
        ]
    )
    db_session.commit()

    r = client.get("/api/fics", params={"es_relectura": True})
    assert [f["titulo"] for f in r.json()] == ["Releído"]


def test_filtrar_fics_por_con_resena(client, db_session):
    con = _crear_fic(db_session, ao3_id="1", titulo="Con reseña")
    sin = _crear_fic(db_session, ao3_id="2", titulo="Sin reseña")
    db_session.add(Resena(fic_id=con.id, rating=4))
    db_session.commit()

    r = client.get("/api/fics", params={"con_resena": True})
    assert [f["titulo"] for f in r.json()] == ["Con reseña"]

    r = client.get("/api/fics", params={"con_resena": False})
    assert [f["titulo"] for f in r.json()] == ["Sin reseña"]


def test_filtrar_fics_por_rating(client, db_session):
    a = _crear_fic(db_session, ao3_id="1", titulo="A")
    a.rating = "Explicit"
    b = _crear_fic(db_session, ao3_id="2", titulo="B")
    b.rating = "General Audiences"
    db_session.commit()

    r = client.get("/api/fics", params={"rating": "Explicit"})
    assert [f["titulo"] for f in r.json()] == ["A"]


def test_filtrar_fics_por_warning_no_matchea_subcadena(client, db_session):
    a = _crear_fic(db_session, ao3_id="1", titulo="A")
    a.warnings = "Major Character Death"
    b = _crear_fic(db_session, ao3_id="2", titulo="B")
    # "Character Death" NO debe matchear "Major Character Death" (segmento
    # exacto entre "|", no una subcadena cualquiera).
    b.warnings = "Character Death"
    db_session.commit()

    r = client.get("/api/fics", params={"warning": "Major Character Death"})
    assert [f["titulo"] for f in r.json()] == ["A"]


def test_opciones_filtro(client, db_session):
    fic = _crear_fic(db_session)
    fic.personajes.append(Personaje(nombre="Frodo Baggins"))
    fic.tags_adicionales.append(TagAdicional(nombre="Slow Burn"))
    fic.idioma = "Español"
    db_session.commit()

    r = client.get("/api/fics/opciones-filtro")
    assert r.status_code == 200
    body = r.json()
    assert "Explicit" in body["ratings"]
    assert "Major Character Death" in body["warnings"]
    assert "F/F" in body["categorias"]
    assert body["ships"] == []
    assert body["personajes"] == ["Frodo Baggins"]
    assert body["tags"] == ["Slow Burn"]
    assert body["idiomas"] == ["Español"]


def test_listar_fics_orden_palabras(client, db_session):
    _crear_fic(db_session, ao3_id="1", titulo="Corto")
    corto = db_session.query(Fic).filter_by(ao3_id="1").one()
    corto.word_count = 500
    _crear_fic(db_session, ao3_id="2", titulo="Largo")
    largo = db_session.query(Fic).filter_by(ao3_id="2").one()
    largo.word_count = 50_000
    db_session.commit()

    r = client.get("/api/fics", params={"orden": "palabras"})
    assert [f["titulo"] for f in r.json()] == ["Largo", "Corto"]


def test_orden_palabras_combinado_con_estado_leido_excluye_pendientes(client, db_session):
    """Regresión: la pantalla de 'fics leídos por palabras' pedía
    orden=palabras sin estado=leido, así que mostraba fics pendientes/
    abandonados con muchas palabras como si fueran leídos."""
    leido = _crear_fic(db_session, ao3_id="1", titulo="Leído")
    leido_obj = db_session.query(Fic).filter_by(ao3_id="1").one()
    leido_obj.word_count = 100
    pendiente = _crear_fic(db_session, ao3_id="2", titulo="Pendiente")
    pendiente_obj = db_session.query(Fic).filter_by(ao3_id="2").one()
    pendiente_obj.word_count = 999_999
    db_session.add(Lectura(fic_id=leido.id, estado="leido"))
    db_session.add(Lectura(fic_id=pendiente.id, estado="pendiente"))
    db_session.commit()

    r = client.get("/api/fics", params={"orden": "palabras", "estado": "leido"})
    assert [f["titulo"] for f in r.json()] == ["Leído"]


def test_filtrar_fics_por_anio_leido(client, db_session):
    a = _crear_fic(db_session, ao3_id="1", titulo="A")
    b = _crear_fic(db_session, ao3_id="2", titulo="B")
    db_session.add_all(
        [
            Lectura(fic_id=a.id, estado="leido", fecha_fin=datetime.date(2025, 6, 1)),
            Lectura(fic_id=b.id, estado="leido", fecha_fin=datetime.date(2026, 6, 1)),
        ]
    )
    db_session.commit()

    r = client.get("/api/fics", params={"anio": 2025})
    assert [f["titulo"] for f in r.json()] == ["A"]


def test_filtrar_fics_por_anio_no_duplica_por_relectura(client, db_session):
    a = _crear_fic(db_session, ao3_id="1", titulo="A")
    db_session.add_all(
        [
            Lectura(fic_id=a.id, estado="leido", fecha_fin=datetime.date(2025, 1, 1)),
            Lectura(fic_id=a.id, estado="leido", fecha_fin=datetime.date(2025, 6, 1), es_relectura=True),
        ]
    )
    db_session.commit()

    r = client.get("/api/fics", params={"anio": 2025})
    assert len(r.json()) == 1


def test_filtrar_fics_por_completo(client, db_session):
    _crear_fic(db_session, ao3_id="1", titulo="Completo", complete=True)
    _crear_fic(db_session, ao3_id="2", titulo="WIP", complete=False)

    r = client.get("/api/fics", params={"completo": True})
    data = r.json()
    assert [f["titulo"] for f in data] == ["Completo"]

    r = client.get("/api/fics", params={"completo": False})
    data = r.json()
    assert [f["titulo"] for f in data] == ["WIP"]


def test_filtrar_fics_por_busqueda(client, db_session):
    _crear_fic(db_session, ao3_id="1", titulo="El Peso de las Estrellas", fandom="F")
    _crear_fic(db_session, ao3_id="2", titulo="Ley de Gravedad", fandom="F")

    r = client.get("/api/fics", params={"q": "estrellas"})
    data = r.json()
    assert len(data) == 1
    assert data[0]["titulo"] == "El Peso de las Estrellas"


def test_fics_borrados_se_excluyen_por_defecto(client, db_session):
    fic = _crear_fic(db_session)
    fic.deleted_detected_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    db_session.commit()

    assert client.get("/api/fics").json() == []
    assert len(client.get("/api/fics", params={"incluir_borrados": True}).json()) == 1


def test_crear_actualizar_borrar_lectura(client, db_session):
    fic = _crear_fic(db_session)

    r = client.post(f"/api/fics/{fic.id}/lecturas", json={"estado": "leyendo"})
    assert r.status_code == 201
    lectura_id = r.json()["id"]

    r = client.get(f"/api/fics/{fic.id}")
    assert r.json()["estado_actual"] == "leyendo"

    r = client.patch(
        f"/api/fics/{fic.id}/lecturas/{lectura_id}",
        json={"estado": "leido", "fecha_fin": "2026-08-01"},
    )
    assert r.status_code == 200
    assert r.json()["estado"] == "leido"

    r = client.delete(f"/api/fics/{fic.id}/lecturas/{lectura_id}")
    assert r.status_code == 204
    assert client.get(f"/api/fics/{fic.id}").json()["lecturas"] == []


def test_crear_lectura_estado_invalido(client, db_session):
    fic = _crear_fic(db_session)
    r = client.post(f"/api/fics/{fic.id}/lecturas", json={"estado": "en_curso"})
    assert r.status_code == 422


def test_crear_lectura_fic_inexistente(client):
    r = client.post("/api/fics/999/lecturas", json={"estado": "leyendo"})
    assert r.status_code == 404


def test_crear_resena(client, db_session):
    fic = _crear_fic(db_session)
    r = client.post(
        f"/api/fics/{fic.id}/resenas",
        json={"rating": 4.5, "texto": "Muy bueno", "contiene_spoilers": False},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["rating"] == 4.5
    assert body["fecha"] == datetime.date.today().isoformat()
    assert body["hizo_llorar"] is False


def test_crear_resena_rating_fuera_de_rango(client, db_session):
    fic = _crear_fic(db_session)
    r = client.post(f"/api/fics/{fic.id}/resenas", json={"rating": 6})
    assert r.status_code == 422


def test_crear_y_actualizar_resena_hizo_llorar(client, db_session):
    fic = _crear_fic(db_session)
    r = client.post(f"/api/fics/{fic.id}/resenas", json={"rating": 5, "hizo_llorar": True})
    assert r.status_code == 201
    resena_id = r.json()["id"]
    assert r.json()["hizo_llorar"] is True

    r = client.patch(
        f"/api/fics/{fic.id}/resenas/{resena_id}", json={"hizo_llorar": False}
    )
    assert r.status_code == 200
    assert r.json()["hizo_llorar"] is False


def test_colecciones_crud_y_fics(client, db_session):
    fic = _crear_fic(db_session)

    r = client.post("/api/colecciones", json={"nombre": "Comfort reads", "color": "#ff0000"})
    assert r.status_code == 201
    coleccion = r.json()
    assert coleccion["tipo"] == "personalizada"
    assert coleccion["cantidad_fics"] == 0

    r = client.put(f"/api/colecciones/{coleccion['id']}/fics/{fic.id}")
    assert r.status_code == 204

    r = client.get("/api/colecciones")
    assert r.json()[0]["cantidad_fics"] == 1

    # agregar de nuevo no duplica
    client.put(f"/api/colecciones/{coleccion['id']}/fics/{fic.id}")
    assert client.get("/api/colecciones").json()[0]["cantidad_fics"] == 1

    r = client.delete(f"/api/colecciones/{coleccion['id']}/fics/{fic.id}")
    assert r.status_code == 204
    assert client.get("/api/colecciones").json()[0]["cantidad_fics"] == 0

    r = client.patch(f"/api/colecciones/{coleccion['id']}", json={"nombre": "Comfort reads 2"})
    assert r.json()["nombre"] == "Comfort reads 2"

    r = client.delete(f"/api/colecciones/{coleccion['id']}")
    assert r.status_code == 204
    assert client.get("/api/colecciones").json() == []


def test_obtener_coleccion_individual(client, db_session):
    fic = _crear_fic(db_session)
    coleccion = client.post("/api/colecciones", json={"nombre": "Favoritos"}).json()
    client.put(f"/api/colecciones/{coleccion['id']}/fics/{fic.id}")

    r = client.get(f"/api/colecciones/{coleccion['id']}")
    assert r.status_code == 200
    assert r.json()["nombre"] == "Favoritos"
    assert r.json()["cantidad_fics"] == 1

    assert client.get("/api/colecciones/999").status_code == 404


def test_filtrar_fics_por_coleccion(client, db_session):
    fic1 = _crear_fic(db_session, ao3_id="1", titulo="A")
    _crear_fic(db_session, ao3_id="2", titulo="B")
    coleccion = client.post("/api/colecciones", json={"nombre": "Favoritos"}).json()
    client.put(f"/api/colecciones/{coleccion['id']}/fics/{fic1.id}")

    r = client.get("/api/fics", params={"coleccion": coleccion["id"]})
    data = r.json()
    assert [f["titulo"] for f in data] == ["A"]


def test_etiquetas_personales_crear_listar_filtrar_borrar(client, db_session):
    fic1 = _crear_fic(db_session, ao3_id="1", titulo="A")
    fic2 = _crear_fic(db_session, ao3_id="2", titulo="B")

    r = client.post(f"/api/fics/{fic1.id}/etiquetas", json={"nombre": "para releer"})
    assert r.status_code == 201
    etiqueta = r.json()

    # la misma etiqueta en otro fic reutiliza la fila, no duplica
    client.post(f"/api/fics/{fic2.id}/etiquetas", json={"nombre": "para releer"})
    assert client.get("/api/etiquetas").json() == [{"id": etiqueta["id"], "nombre": "para releer"}]

    r = client.get(f"/api/fics/{fic1.id}")
    assert r.json()["etiquetas_personales"] == [etiqueta]

    r = client.get("/api/fics", params={"etiqueta": "para releer"})
    assert {f["titulo"] for f in r.json()} == {"A", "B"}

    # quitar de un fic no la borra del otro
    r = client.delete(f"/api/fics/{fic1.id}/etiquetas/{etiqueta['id']}")
    assert r.status_code == 204
    assert client.get(f"/api/fics/{fic1.id}").json()["etiquetas_personales"] == []
    assert len(client.get(f"/api/fics/{fic2.id}").json()["etiquetas_personales"]) == 1

    # borrar la etiqueta entera la saca de todos lados
    r = client.delete(f"/api/etiquetas/{etiqueta['id']}")
    assert r.status_code == 204
    assert client.get("/api/etiquetas").json() == []
    assert client.get(f"/api/fics/{fic2.id}").json()["etiquetas_personales"] == []


def test_etiqueta_reutiliza_sin_importar_mayusculas(client, db_session):
    fic1 = _crear_fic(db_session, ao3_id="1", titulo="A")
    fic2 = _crear_fic(db_session, ao3_id="2", titulo="B")

    creada = client.post(f"/api/fics/{fic1.id}/etiquetas", json={"nombre": "fluff"}).json()
    reusada = client.post(f"/api/fics/{fic2.id}/etiquetas", json={"nombre": "Fluff"}).json()

    assert reusada["id"] == creada["id"]
    assert client.get("/api/etiquetas").json() == [{"id": creada["id"], "nombre": "fluff"}]


def test_etiqueta_nombre_vacio_rechazado(client, db_session):
    fic = _crear_fic(db_session)
    r = client.post(f"/api/fics/{fic.id}/etiquetas", json={"nombre": "   "})
    assert r.status_code == 422


def test_fic_detail_incluye_colecciones(client, db_session):
    fic = _crear_fic(db_session)
    coleccion = client.post("/api/colecciones", json={"nombre": "Favoritos"}).json()
    client.put(f"/api/colecciones/{coleccion['id']}/fics/{fic.id}")

    r = client.get(f"/api/fics/{fic.id}")
    assert r.json()["colecciones"] == [
        {"id": coleccion["id"], "nombre": "Favoritos", "tipo": "personalizada"}
    ]


def test_stats_resumen(client, db_session):
    fic = _crear_fic(db_session)
    db_session.add(Lectura(fic_id=fic.id, estado="leido", fecha_fin=datetime.date(2026, 8, 1)))
    db_session.commit()

    r = client.get("/api/stats/resumen")
    body = r.json()
    assert body["total_fics"] == 1
    assert body["total_palabras_leidas"] == 1000
    assert body["racha_dias"] == 1

    r = client.get("/api/stats/resumen", params={"anio": 2026})
    assert r.json()["total_palabras_leidas"] == 1000
    r = client.get("/api/stats/resumen", params={"anio": 2020})
    assert r.json()["total_palabras_leidas"] == 0


def test_stats_fic_mas_largo(client, db_session):
    fic = _crear_fic(db_session, ao3_id="1", titulo="El más largo")
    db_session.add(Lectura(fic_id=fic.id, estado="leido", fecha_fin=datetime.date(2026, 8, 1)))
    db_session.commit()

    r = client.get("/api/stats/fic-mas-largo")
    assert r.json() == {"id": fic.id, "titulo": "El más largo", "word_count": 1000}

    r = client.get("/api/stats/fic-mas-largo", params={"anio": 2020})
    assert r.json() is None


def test_stats_estado_lectura(client, db_session):
    fic = _crear_fic(db_session)
    db_session.add(Lectura(fic_id=fic.id, estado="leyendo"))
    db_session.commit()

    r = client.get("/api/stats/estado-lectura")
    assert r.json() == {"leyendo": 1}


def test_import_log_vacio(client):
    r = client.get("/api/import-log")
    assert r.status_code == 200
    assert r.json() == []


def test_archivos_vacio(client):
    r = client.get("/api/archivos")
    assert r.status_code == 200
    assert r.json() == []


def test_listar_archivos_marca_si_falta_en_disco(client, db_session, tmp_path):
    fic = _crear_fic(db_session)
    presente = Archivo(
        fic_id=fic.id, formato="epub", ruta_local=str(tmp_path / "presente.epub"), hash_sha256="x", tamano=1,
    )
    (tmp_path / "presente.epub").write_bytes(b"x")
    faltante = Archivo(
        fic_id=fic.id, formato="html", ruta_local=str(tmp_path / "no-existe.html"), hash_sha256="x", tamano=1,
    )
    db_session.add_all([presente, faltante])
    db_session.commit()

    body = {a["formato"]: a["existe_en_disco"] for a in client.get("/api/archivos").json()}
    assert body == {"epub": True, "html": False}


def test_contenido_archivo_html_se_sirve_inline(client, db_session, tmp_path):
    fic = _crear_fic(db_session)
    ruta = tmp_path / "1.html"
    ruta.write_text("<html><body>copia archivada</body></html>", encoding="utf-8")
    archivo = Archivo(
        fic_id=fic.id, formato="html", ruta_local=str(ruta), hash_sha256="x", tamano=10,
    )
    db_session.add(archivo)
    db_session.commit()

    r = client.get(f"/api/archivos/{archivo.id}/contenido")
    assert r.status_code == 200
    assert "copia archivada" in r.text
    assert "content-disposition" not in {k.lower() for k in r.headers.keys()}


def test_contenido_archivo_epub_se_descarga_como_attachment(client, db_session, tmp_path):
    fic = _crear_fic(db_session)
    ruta = tmp_path / "1.epub"
    ruta.write_bytes(b"contenido epub falso")
    archivo = Archivo(
        fic_id=fic.id, formato="epub", ruta_local=str(ruta), hash_sha256="x", tamano=10,
    )
    db_session.add(archivo)
    db_session.commit()

    r = client.get(f"/api/archivos/{archivo.id}/contenido")
    assert r.status_code == 200
    assert r.content == b"contenido epub falso"
    assert "attachment" in r.headers["content-disposition"]


def test_contenido_archivo_inexistente(client):
    r = client.get("/api/archivos/999/contenido")
    assert r.status_code == 404


def test_contenido_archivo_borrado_del_disco(client, db_session, tmp_path):
    fic = _crear_fic(db_session)
    archivo = Archivo(
        fic_id=fic.id,
        formato="epub",
        ruta_local=str(tmp_path / "no-existe.epub"),
        hash_sha256="x",
        tamano=10,
    )
    db_session.add(archivo)
    db_session.commit()

    r = client.get(f"/api/archivos/{archivo.id}/contenido")
    assert r.status_code == 410


def test_borrar_archivo(client, db_session, tmp_path):
    fic = _crear_fic(db_session)
    ruta = tmp_path / "1.epub"
    ruta.write_bytes(b"contenido epub falso")
    archivo = Archivo(
        fic_id=fic.id, formato="epub", ruta_local=str(ruta), hash_sha256="x", tamano=10,
    )
    db_session.add(archivo)
    db_session.commit()
    archivo_id = archivo.id

    r = client.delete(f"/api/archivos/{archivo_id}")
    assert r.status_code == 204
    assert not ruta.exists()
    assert client.get(f"/api/archivos/{archivo_id}/contenido").status_code == 404


def test_borrar_archivo_inexistente(client):
    r = client.delete("/api/archivos/999")
    assert r.status_code == 404
