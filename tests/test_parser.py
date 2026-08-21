from pathlib import Path

from app.ao3 import parser

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_work_page_completo():
    fic = parser.parse_work_page(_read("work_page.html"), ao3_id="1")

    assert fic.titulo == "El Peso de las Estrellas"
    assert fic.autor == "nightingale_writes"
    assert fic.autor_url == "https://archiveofourown.org/users/nightingale_writes/pseuds/nightingale_writes"
    assert fic.word_count == 48_200
    assert fic.chapters_published == 18
    assert fic.chapters_total == 18
    assert fic.complete is True
    assert fic.restricted is False
    assert fic.rating == "Teen And Up Audiences"
    assert fic.categorias == ["F/M"]
    assert fic.warnings == ["No Archive Warnings Apply"]
    assert fic.fandoms == ["Star Wars: Original Trilogy"]
    assert fic.ships == ["Leia Organa/Han Solo"]
    assert fic.personajes == ["Leia Organa", "Han Solo"]
    assert fic.tags_adicionales == ["Post-Endor", "Slow Burn"]
    assert fic.fecha_publicacion == "2026-03-02"
    assert fic.fecha_actualizacion == "2026-04-10"
    assert "Endor" in fic.summary
    assert fic.epub_url == "https://archiveofourown.org/downloads/1/El_Peso_de_las_Estrellas.epub?updated_at=123"


def test_parse_work_page_wip_y_restricted():
    fic = parser.parse_work_page(_read("work_page_wip_restricted.html"), ao3_id="2")

    assert fic.restricted is True
    assert fic.chapters_published == 3
    assert fic.chapters_total is None
    assert fic.complete is False
    assert fic.fecha_actualizacion == fic.fecha_publicacion  # no hay dd.status


def test_infer_ship_tipo():
    assert parser.infer_ship_tipo("Leia Organa/Han Solo") == "romantico"
    assert parser.infer_ship_tipo("Wei Wuxian & Lan Wangji") == "platonico"
    assert parser.infer_ship_tipo("Nombre Suelto") is None
    assert parser.infer_ship_tipo("A/B & C") is None


def test_parse_bookmarks_page():
    page = parser.parse_bookmarks_page(_read("bookmarks_page.html"))
    assert [item.work_id for item in page.items] == ["1", "2"]
    assert page.total_pages == 3

    fic1, fic2 = page.items
    assert fic1.tags == ["Leídos 2026", "Favoritos"]
    assert fic1.bookmarked_at == "2026-03-15"
    assert fic2.tags == ["por leer"]
    assert fic2.bookmarked_at == "2026-01-11"


def test_parse_history_page():
    page = parser.parse_history_page(_read("history_page.html"))
    assert page.work_ids == ["1", "3"]
    assert page.total_pages == 1


def test_extract_authenticity_token():
    token = parser.extract_authenticity_token(_read("login_page.html"))
    assert token == "fake-csrf-token-123"
