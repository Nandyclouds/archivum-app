from app.ao3.reading_status import clasificar_tags


def test_tag_leidos_anio():
    r = clasificar_tags(["Leídos 2026"])
    assert r.anios_leido == [2026]
    assert r.tags_coleccion == []


def test_variantes_de_leidos():
    for tag in ["leídos 2025", "Leído 2025", "LEIDAS 2025", "leido 2025"]:
        r = clasificar_tags([tag])
        assert r.anios_leido == [2025], tag


def test_varios_anios_son_relecturas():
    r = clasificar_tags(["Leídos 2024", "Leídos 2026"])
    assert r.anios_leido == [2024, 2026]


def test_por_leer_es_pendiente():
    r = clasificar_tags(["por leer"])
    assert r.pendiente is True
    assert r.anios_leido == []
    assert r.tags_coleccion == []


def test_tags_desconocidos_van_a_coleccion():
    r = clasificar_tags(["Favoritos", "andreil favs", "HR", "joquis", "aftg", "Merlin"])
    assert r.tags_coleccion == ["Favoritos", "andreil favs", "HR", "joquis", "aftg", "Merlin"]
    assert r.anios_leido == []
    assert r.pendiente is False
    assert r.abandonado is False


def test_mezcla_de_tags():
    r = clasificar_tags(["Leídos 2026", "Favoritos"])
    assert r.anios_leido == [2026]
    assert r.tags_coleccion == ["Favoritos"]


def test_relectura_explicita():
    r = clasificar_tags(["Leídos 2026", "relectura"])
    assert r.marca_relectura is True
    assert r.tags_coleccion == []
