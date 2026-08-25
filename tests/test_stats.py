import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import stats
from app.database import Base
from app.models import Coleccion, Fandom, Fic, Lectura, Resena, Ship


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _make_fic(session, *, ao3_id, titulo, word_count, complete, fandom, ship=None):
    fandom_obj = session.query(Fandom).filter_by(nombre=fandom).one_or_none()
    if fandom_obj is None:
        fandom_obj = Fandom(nombre=fandom)
        session.add(fandom_obj)

    fic = Fic(
        ao3_id=ao3_id,
        titulo=titulo,
        autor="autora_test",
        url=f"https://archiveofourown.org/works/{ao3_id}",
        word_count=word_count,
        chapters_published=1,
        chapters_total=1,
        complete=complete,
        restricted=False,
        fecha_primer_import=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
    )
    fic.fandoms.append(fandom_obj)
    if ship:
        ship_obj = session.query(Ship).filter_by(nombre=ship).one_or_none()
        if ship_obj is None:
            ship_obj = Ship(nombre=ship, tipo="romantico")
            session.add(ship_obj)
        fic.ships.append(ship_obj)
    session.add(fic)
    session.flush()
    return fic


def test_palabras_leidas_por_mes(session):
    fic = _make_fic(session, ao3_id="1", titulo="Fic A", word_count=10_000, complete=True, fandom="Fandom A")
    session.add(
        Lectura(
            fic_id=fic.id,
            fecha_inicio=datetime.date(2026, 1, 1),
            fecha_fin=datetime.date(2026, 1, 15),
            estado="leido",
            es_relectura=False,
        )
    )
    session.commit()

    resultado = stats.palabras_leidas_por_mes(session)
    assert resultado == [stats.PeriodoPalabras(periodo="2026-01", palabras=10_000, fics=1)]


def test_top_fandoms(session):
    _make_fic(session, ao3_id="1", titulo="Fic A", word_count=1000, complete=True, fandom="Fandom A")
    _make_fic(session, ao3_id="2", titulo="Fic B", word_count=1000, complete=True, fandom="Fandom A")
    _make_fic(session, ao3_id="3", titulo="Fic C", word_count=1000, complete=True, fandom="Fandom B")
    session.commit()

    resultado = stats.top_fandoms(session)
    assert resultado[0] == ("Fandom A", 2)
    assert resultado[1] == ("Fandom B", 1)


def test_top_fandoms_filtrado_por_anio(session):
    fic_a = _make_fic(session, ao3_id="1", titulo="A", word_count=1000, complete=True, fandom="Fandom A")
    fic_b = _make_fic(session, ao3_id="2", titulo="B", word_count=1000, complete=True, fandom="Fandom B")
    session.add_all(
        [
            Lectura(fic_id=fic_a.id, estado="leido", fecha_fin=datetime.date(2025, 6, 1)),
            Lectura(fic_id=fic_b.id, estado="leido", fecha_fin=datetime.date(2026, 6, 1)),
        ]
    )
    session.commit()

    assert stats.top_fandoms(session, anio=2025) == [("Fandom A", 1)]
    assert stats.top_fandoms(session, anio=2026) == [("Fandom B", 1)]
    assert len(stats.top_fandoms(session)) == 2  # sin filtro, trae todo


def test_top_ships_filtrado_por_anio(session):
    fic = _make_fic(session, ao3_id="1", titulo="A", word_count=100, complete=True, fandom="F", ship="A/B")
    session.add(Lectura(fic_id=fic.id, estado="leido", fecha_fin=datetime.date(2025, 6, 1)))
    session.commit()

    assert stats.top_ships(session, anio=2025) == [("A/B", 1)]
    assert stats.top_ships(session, anio=2026) == []


def test_distribucion_longitud(session):
    drabble = _make_fic(session, ao3_id="1", titulo="Drabble", word_count=500, complete=True, fandom="F")
    epico = _make_fic(session, ao3_id="2", titulo="Epico", word_count=200_000, complete=True, fandom="F")
    # Pendiente, con muchas palabras: no debería sumar a ningún bucket, solo
    # lo leído cuenta acá (es un gráfico de "cuánto leíste", no de biblioteca).
    _make_fic(session, ao3_id="3", titulo="Pendiente", word_count=300_000, complete=True, fandom="F")
    session.add(Lectura(fic_id=drabble.id, estado="leido"))
    session.add(Lectura(fic_id=epico.id, estado="leido"))
    session.commit()

    resultado = dict(stats.distribucion_longitud(session))
    assert resultado["drabble (<1k)"] == 1
    assert resultado["epico (100k+)"] == 1
    assert sum(resultado.values()) == 2


def test_ratio_wip_vs_completos(session):
    _make_fic(session, ao3_id="1", titulo="A", word_count=100, complete=True, fandom="F")
    _make_fic(session, ao3_id="2", titulo="B", word_count=100, complete=False, fandom="F")
    _make_fic(session, ao3_id="3", titulo="C", word_count=100, complete=False, fandom="F")
    session.commit()

    resultado = stats.ratio_wip_vs_completos(session)
    assert resultado == {"completos": 1, "wip": 2}


def test_relecturas(session):
    fic = _make_fic(session, ao3_id="1", titulo="A", word_count=100, complete=True, fandom="F")
    session.add_all(
        [
            Lectura(fic_id=fic.id, estado="leido", es_relectura=False),
            Lectura(fic_id=fic.id, estado="leido", es_relectura=True),
            Lectura(fic_id=fic.id, estado="leido", es_relectura=True),
        ]
    )
    session.commit()

    assert stats.total_relecturas(session) == 2
    assert stats.relecturas_por_fic(session) == [("A", 2)]


def test_promedio_rating_por_fandom(session):
    fic_a = _make_fic(session, ao3_id="1", titulo="A", word_count=100, complete=True, fandom="Fandom X")
    fic_b = _make_fic(session, ao3_id="2", titulo="B", word_count=100, complete=True, fandom="Fandom X")
    session.add_all(
        [
            Resena(fic_id=fic_a.id, rating=5.0, fecha=datetime.date.today()),
            Resena(fic_id=fic_b.id, rating=4.0, fecha=datetime.date.today()),
        ]
    )
    session.commit()

    resultado = stats.promedio_rating_por_fandom(session)
    assert resultado == [("Fandom X", 4.5, 2)]


def test_resumen_general(session):
    fic = _make_fic(session, ao3_id="1", titulo="A", word_count=1000, complete=True, fandom="F", ship="Ship A/Ship B")
    session.add(Lectura(fic_id=fic.id, estado="leido"))
    session.commit()

    resumen = stats.resumen_general(session)
    assert resumen["total_fics"] == 1
    assert resumen["total_lecturas_leido"] == 1
    assert resumen["total_palabras_leidas"] == 1000
    assert resumen["total_fandoms"] == 1
    assert resumen["total_ships"] == 1


def test_resumen_general_filtrado_por_anio(session):
    fic_a = _make_fic(session, ao3_id="1", titulo="A", word_count=1000, complete=True, fandom="Fandom A", ship="A/B")
    fic_b = _make_fic(session, ao3_id="2", titulo="B", word_count=500, complete=True, fandom="Fandom B", ship="C/D")
    session.add_all(
        [
            Lectura(fic_id=fic_a.id, estado="leido", fecha_fin=datetime.date(2025, 6, 1)),
            Lectura(fic_id=fic_b.id, estado="leido", fecha_fin=datetime.date(2026, 6, 1)),
        ]
    )
    session.commit()

    resumen_2025 = stats.resumen_general(session, anio=2025)
    assert resumen_2025["total_fics"] == 2  # tamaño de biblioteca: no se filtra por año
    assert resumen_2025["total_lecturas_leido"] == 1
    assert resumen_2025["total_palabras_leidas"] == 1000
    assert resumen_2025["total_fandoms"] == 1
    assert resumen_2025["total_ships"] == 1

    resumen_todos = stats.resumen_general(session)
    assert resumen_todos["total_lecturas_leido"] == 2
    assert resumen_todos["total_palabras_leidas"] == 1500


def test_fic_mas_largo_leido(session):
    corto = _make_fic(session, ao3_id="1", titulo="Corto", word_count=1000, complete=True, fandom="F")
    largo = _make_fic(session, ao3_id="2", titulo="Largo", word_count=50_000, complete=True, fandom="F")
    sin_leer = _make_fic(session, ao3_id="3", titulo="Sin leer", word_count=999_999, complete=True, fandom="F")
    session.add_all(
        [
            Lectura(fic_id=corto.id, estado="leido", fecha_fin=datetime.date(2025, 1, 1)),
            Lectura(fic_id=largo.id, estado="leido", fecha_fin=datetime.date(2026, 1, 1)),
        ]
    )
    session.commit()

    assert stats.fic_mas_largo_leido(session).titulo == "Largo"
    assert stats.fic_mas_largo_leido(session, anio=2025).titulo == "Corto"
    assert stats.fic_mas_largo_leido(session, anio=2099) is None


def test_resumen_general_cuenta_relecturas(session):
    fic = _make_fic(session, ao3_id="1", titulo="A", word_count=1000, complete=True, fandom="F")
    session.add(Lectura(fic_id=fic.id, estado="leido", fecha_fin=datetime.date(2025, 1, 1)))
    session.add(
        Lectura(fic_id=fic.id, estado="leido", fecha_fin=datetime.date(2026, 1, 1), es_relectura=True)
    )
    session.commit()

    resumen = stats.resumen_general(session)
    assert resumen["total_fics"] == 1  # tamaño de biblioteca: 1 fic distinto
    assert resumen["total_lecturas_leido"] == 2  # pero se leyó 2 veces
    assert resumen["total_palabras_leidas"] == 2000


def test_top_ships_separa_romanticos_de_platonicos(session):
    fic = _make_fic(session, ao3_id="1", titulo="A", word_count=100, complete=True, fandom="F")
    ship_romantico = Ship(nombre="A/B", tipo="romantico")
    ship_platonico = Ship(nombre="A & C", tipo="platonico")
    session.add_all([ship_romantico, ship_platonico])
    fic.ships.extend([ship_romantico, ship_platonico])
    session.commit()

    assert stats.top_ships(session, tipo="romantico") == [("A/B", 1)]
    assert stats.top_ships(session, tipo="platonico") == [("A & C", 1)]
    assert len(stats.top_ships(session)) == 2  # sin filtro, trae todo


def test_conteo_por_estado_lectura_usa_la_lectura_mas_reciente(session):
    fic1 = _make_fic(session, ao3_id="1", titulo="A", word_count=100, complete=True, fandom="F")
    fic2 = _make_fic(session, ao3_id="2", titulo="B", word_count=100, complete=False, fandom="F")
    fic3 = _make_fic(session, ao3_id="3", titulo="C", word_count=100, complete=False, fandom="F")
    session.add_all(
        [
            Lectura(fic_id=fic1.id, estado="leido", fecha_fin=datetime.date(2025, 1, 1)),
            Lectura(fic_id=fic1.id, estado="leido", fecha_fin=datetime.date(2026, 1, 1)),  # relectura, misma fic
            Lectura(fic_id=fic2.id, estado="leyendo"),
            Lectura(fic_id=fic3.id, estado="abandonado"),
        ]
    )
    session.commit()

    resultado = stats.conteo_por_estado_lectura(session)
    assert resultado == {"leido": 1, "leyendo": 1, "abandonado": 1}


def test_racha_dias_lectura(session):
    fic = _make_fic(session, ao3_id="1", titulo="A", word_count=100, complete=True, fandom="F")
    session.add_all(
        [
            Lectura(fic_id=fic.id, estado="leido", fecha_fin=datetime.date(2026, 8, 18)),
            Lectura(fic_id=fic.id, estado="leido", fecha_fin=datetime.date(2026, 8, 19)),
            Lectura(fic_id=fic.id, estado="leido", fecha_fin=datetime.date(2026, 8, 20)),
            Lectura(fic_id=fic.id, estado="leido", fecha_fin=datetime.date(2026, 8, 10)),  # corta la racha
        ]
    )
    session.commit()

    assert stats.racha_dias_lectura(session) == 3


def test_racha_dias_lectura_vacia(session):
    assert stats.racha_dias_lectura(session) == 0


def test_coleccion_fics_join(session):
    fic = _make_fic(session, ao3_id="1", titulo="A", word_count=100, complete=True, fandom="F")
    coleccion = Coleccion(nombre="Comfort reads", color="#ff0000", orden=0)
    coleccion.fics.append(fic)
    session.add(coleccion)
    session.commit()

    recargada = session.get(Coleccion, coleccion.id)
    assert [f.titulo for f in recargada.fics] == ["A"]
