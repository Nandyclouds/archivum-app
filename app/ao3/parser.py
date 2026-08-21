"""Parsers de HTML de AO3. Funciones puras: reciben texto/soup, devuelven datos.

Nada de I/O acá — así se pueden probar con fixtures estáticos sin pegarle a
la web real. Los selectores están calcados de la estructura real de
`<dl class="work meta group">` que usa AO3 en la página de cada fic.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup


class UnexpectedPageError(Exception):
    """La página no tiene la forma que esperábamos (AO3 cambió el HTML, o dio un error)."""


@dataclass
class ParsedFic:
    ao3_id: str
    titulo: str
    autor: str
    autor_url: str | None
    word_count: int
    chapters_published: int
    chapters_total: int | None
    complete: bool
    restricted: bool
    rating: str | None
    categorias: list[str]
    warnings: list[str]
    summary: str | None
    fecha_publicacion: str | None  # "YYYY-MM-DD"
    fecha_actualizacion: str | None  # "YYYY-MM-DD"
    fandoms: list[str]
    ships: list[str]
    personajes: list[str]
    tags_adicionales: list[str]
    epub_url: str | None = None


@dataclass
class ListingPage:
    """Una página de bookmarks o de historial: solo lo suficiente para saber
    qué fics existen y si hay más páginas. El detalle completo de cada fic
    se pide aparte, a su propia página (ver ParsedFic)."""

    work_ids: list[str] = field(default_factory=list)
    total_pages: int = 1


@dataclass
class BookmarkItem:
    work_id: str
    tags: list[str] = field(default_factory=list)
    bookmarked_at: str | None = None  # "YYYY-MM-DD" si se pudo parsear


@dataclass
class BookmarksPage:
    items: list[BookmarkItem] = field(default_factory=list)
    total_pages: int = 1


def _work_id_from_href(href: str) -> str | None:
    match = re.search(r"/works/(\d+)", href)
    return match.group(1) if match else None


def work_id_from_url(url: str) -> str | None:
    """Acepta tanto un ao3_id suelto ('12345') como una URL completa."""
    if url.isdigit():
        return url
    return _work_id_from_href(url)


def _text_list(dl, css_class: str) -> list[str]:
    # OJO: en el HTML real de AO3 el <dt> (la etiqueta, ej. "Fandom:") suele
    # compartir las mismas clases CSS que su <dd> (el valor). Sin restringir
    # el selector a "dd" específicamente, select_one agarra el <dt> primero
    # (aparece antes en el documento) y devuelve texto vacío/la etiqueta en
    # vez del valor real. Bug real encontrado importando una biblioteca real.
    selector = "dd." + ".".join(css_class.split())
    dd = dl.select_one(selector)
    if dd is None:
        return []
    return [a.get_text(strip=True) for a in dd.find_all("a", class_="tag")] or [
        li.get_text(strip=True) for li in dd.find_all("li")
    ]


def parse_work_page(html: str, ao3_id: str) -> ParsedFic:
    soup = BeautifulSoup(html, "html.parser")

    preface = soup.find("div", class_="preface group")
    if preface is None:
        raise UnexpectedPageError(f"No se encontró 'preface group' para el fic {ao3_id}")

    title_el = preface.find("h2", class_="title")
    titulo = title_el.get_text(strip=True) if title_el else ""

    byline = preface.find("h3", class_="byline")
    autor = "Anónimo"
    autor_url = None
    if byline is not None:
        author_link = byline.find("a", rel="author")
        if author_link is not None:
            autor = author_link.get_text(strip=True)
            autor_url = "https://archiveofourown.org" + author_link.get("href", "")

    meta = soup.find("dl", class_="work meta group")
    if meta is None:
        raise UnexpectedPageError(f"No se encontró 'work meta group' para el fic {ao3_id}")

    rating_dd = meta.select_one("dd.rating.tags")
    rating = rating_dd.get_text(strip=True) if rating_dd else None

    categorias = _text_list(meta, "category tags")
    warnings = _text_list(meta, "warning tags")
    fandoms = _text_list(meta, "fandom tags")
    ships = _text_list(meta, "relationship tags")
    personajes = _text_list(meta, "character tags")
    tags_adicionales = _text_list(meta, "freeform tags")

    words_dd = meta.find("dd", class_="words")
    word_count = int(words_dd.get_text(strip=True).replace(",", "")) if words_dd else 0

    chapters_dd = meta.find("dd", class_="chapters")
    chapters_published, chapters_total = 1, 1
    if chapters_dd is not None:
        raw = chapters_dd.get_text(strip=True).replace(",", "")
        published_str, _, total_str = raw.partition("/")
        chapters_published = int(published_str) if published_str.isdigit() else 1
        chapters_total = int(total_str) if total_str.isdigit() else None

    complete = chapters_total is not None and chapters_published >= chapters_total

    published_dd = meta.find("dd", class_="published")
    fecha_publicacion = published_dd.get_text(strip=True) if published_dd else None

    status_dd = meta.find("dd", class_="status")
    fecha_actualizacion = status_dd.get_text(strip=True) if status_dd else fecha_publicacion

    summary_block = preface.find("blockquote", class_="userstuff")
    summary = summary_block.get_text("\n", strip=True) if summary_block else None

    restricted = soup.find("img", title="Restricted") is not None

    epub_url = None
    download_li = soup.find("li", class_="download")
    if download_li is not None:
        for item in download_li.find_all("li"):
            link = item.find("a")
            if link is not None and link.get_text(strip=True).upper() == "EPUB":
                href = link.get("href", "")
                epub_url = href if href.startswith("http") else "https://archiveofourown.org" + href
                break

    return ParsedFic(
        ao3_id=ao3_id,
        titulo=titulo,
        autor=autor,
        autor_url=autor_url,
        word_count=word_count,
        chapters_published=chapters_published,
        chapters_total=chapters_total,
        complete=complete,
        restricted=restricted,
        rating=rating,
        categorias=categorias,
        warnings=warnings,
        summary=summary,
        fecha_publicacion=fecha_publicacion,
        fecha_actualizacion=fecha_actualizacion,
        fandoms=fandoms,
        ships=ships,
        personajes=personajes,
        tags_adicionales=tags_adicionales,
        epub_url=epub_url,
    )


def infer_ship_tipo(nombre_ship: str) -> str | None:
    """AO3 usa '/' para pairings románticos y '&' para relaciones platónicas."""
    tiene_romantico = "/" in nombre_ship
    tiene_platonico = "&" in nombre_ship
    if tiene_romantico and not tiene_platonico:
        return "romantico"
    if tiene_platonico and not tiene_romantico:
        return "platonico"
    return None


def _work_ids_from_items(items) -> list[str]:
    work_ids: list[str] = []
    for item in items:
        heading = item.find("h4")
        if heading is None:
            continue
        for link in heading.find_all("a"):
            href = link.get("href", "")
            if href.startswith("/works/"):
                work_id = _work_id_from_href(href)
                if work_id and work_id not in work_ids:
                    work_ids.append(work_id)
                break
    return work_ids


def _total_pages(soup) -> int:
    # Bug real encontrado importando una biblioteca real: el <ol> de
    # paginación de AO3 no tiene title="pagination" (lo que yo había
    # asumido), tiene class="pagination actions pagy". Sin esto, siempre se
    # detectaba una sola página aunque hubiera 35.
    total_pages = 1
    pagination = soup.find("ol", class_="pagination")
    if pagination is not None:
        for li in pagination.find_all("li"):
            text = li.get_text(strip=True)
            if text.isdigit():
                total_pages = max(total_pages, int(text))
    return total_pages


def _bookmark_tags_and_date(item) -> tuple[list[str], str | None]:
    """Extrae los 'Bookmarker's Tags' y la fecha de bookmarkeo de un item.

    OJO: a diferencia del resto de este módulo (calcado de la página de un
    fic, que sí pudimos verificar contra una librería probada), esto está
    reconstruido de memoria de cómo AO3 arma el bloque de un bookmark. No se
    pudo confirmar contra HTML real. Matchea por texto visible ("Bookmarker's
    Tags") en vez de por clase CSS exacta, para ser más tolerante a que me
    haya equivocado en el nombre de alguna clase. Si en un import real no
    aparecen tags que deberían, revisar esta función primero.
    """
    tags: list[str] = []
    tags_heading = item.find(
        lambda tag: tag.name in ("h6", "h5", "dt")
        and "tag" in tag.get_text(strip=True).lower()
        and "bookmarker" in tag.get_text(strip=True).lower()
    )
    if tags_heading is not None:
        tags_list = tags_heading.find_next_sibling(["ul", "ol"])
        if tags_list is not None:
            tags = [a.get_text(strip=True) for a in tags_list.find_all("a")]

    bookmarked_at = None
    datetime_els = item.find_all("p", class_="datetime")
    if datetime_els:
        raw = datetime_els[-1].get_text(strip=True)
        try:
            bookmarked_at = datetime.datetime.strptime(raw, "%d %b %Y").date().isoformat()
        except ValueError:
            bookmarked_at = None

    return tags, bookmarked_at


def parse_bookmarks_page(html: str) -> BookmarksPage:
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find("ol", class_="bookmark")
    items_html = container.find_all("li", class_="bookmark") if container else []

    items: list[BookmarkItem] = []
    for item in items_html:
        heading = item.find("h4")
        if heading is None:
            continue
        work_id = None
        for link in heading.find_all("a"):
            href = link.get("href", "")
            if href.startswith("/works/"):
                work_id = _work_id_from_href(href)
                break
        if work_id is None:
            continue
        tags, bookmarked_at = _bookmark_tags_and_date(item)
        items.append(BookmarkItem(work_id=work_id, tags=tags, bookmarked_at=bookmarked_at))

    return BookmarksPage(items=items, total_pages=_total_pages(soup))


def parse_history_page(html: str) -> ListingPage:
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find("ol", class_="reading")
    items = container.find_all("li", {"role": "article"}) if container else []
    return ListingPage(work_ids=_work_ids_from_items(items), total_pages=_total_pages(soup))


def extract_authenticity_token(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    token_input = soup.find("input", {"name": "authenticity_token"})
    return token_input.get("value") if token_input else None
