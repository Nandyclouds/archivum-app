import hashlib
from pathlib import Path

import pytest
import responses
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.ao3 import downloader, importer
from app.ao3.client import RateLimitedClient
from app.database import Base
from app.models import Archivo, Fic

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _archivo_dir_temporal(tmp_path, monkeypatch):
    """Evita que los tests escriban snapshots HTML en el data/archivo/ real."""
    from app.config import Settings

    monkeypatch.setattr(Settings, "archivo_dir", property(lambda self: tmp_path / "html_snapshots"))


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture()
def client():
    return RateLimitedClient(contact_email="test@example.com", min_delay_seconds=0, sleep_fn=lambda s: None)


@pytest.fixture()
def archivo_dir(tmp_path):
    return tmp_path / "archivo"


def _importar_fic_1(db, client):
    responses.add(
        responses.GET,
        "https://archiveofourown.org/works/1?view_adult=true&view_full_work=true",
        body=_read("work_page.html"),
        status=200,
    )
    fic, _ = importer.import_single_fic(db, client, "1")
    db.commit()
    return fic


@responses.activate
def test_download_fic_epub_guarda_archivo_y_hash(db, client, archivo_dir):
    fic = _importar_fic_1(db, client)

    responses.add(
        responses.GET,
        "https://archiveofourown.org/works/1?view_adult=true&view_full_work=true",
        body=_read("work_page.html"),
        status=200,
    )
    epub_bytes = b"contenido falso de un epub"
    responses.add(
        responses.GET,
        "https://archiveofourown.org/downloads/1/El_Peso_de_las_Estrellas.epub?updated_at=123",
        body=epub_bytes,
        status=200,
        content_type="application/epub+zip",
    )

    archivo = downloader.download_fic_epub(db, client, fic, archivo_dir)

    assert Path(archivo.ruta_local).read_bytes() == epub_bytes
    assert archivo.hash_sha256 == hashlib.sha256(epub_bytes).hexdigest()
    assert archivo.tamano == len(epub_bytes)
    assert archivo.formato == "epub"


@responses.activate
def test_download_fic_epub_re_descarga_actualiza_la_misma_fila(db, client, archivo_dir):
    fic = _importar_fic_1(db, client)

    for content in (b"version 1", b"version 2 mas larga"):
        responses.add(
            responses.GET,
            "https://archiveofourown.org/works/1?view_adult=true&view_full_work=true",
            body=_read("work_page.html"),
            status=200,
        )
        responses.add(
            responses.GET,
            "https://archiveofourown.org/downloads/1/El_Peso_de_las_Estrellas.epub?updated_at=123",
            body=content,
            status=200,
        )
        downloader.download_fic_epub(db, client, fic, archivo_dir)
        db.commit()

    assert db.query(Archivo).filter_by(fic_id=fic.id, formato="epub").count() == 1
    archivo = db.query(Archivo).filter_by(fic_id=fic.id, formato="epub").one()
    assert Path(archivo.ruta_local).read_bytes() == b"version 2 mas larga"


@responses.activate
def test_download_fic_epub_fic_borrado_no_se_descarga(db, client, archivo_dir):
    fic = _importar_fic_1(db, client)
    fic.deleted_detected_at = importer._utcnow()
    db.commit()

    with pytest.raises(downloader.DownloadError):
        downloader.download_fic_epub(db, client, fic, archivo_dir)


@responses.activate
def test_download_all_unarchived_salta_los_ya_descargados(db, client, archivo_dir):
    fic1 = _importar_fic_1(db, client)

    responses.add(
        responses.GET,
        "https://archiveofourown.org/works/2?view_adult=true&view_full_work=true",
        body=_read("work_page_wip_restricted.html"),
        status=200,
    )
    fic2, _ = importer.import_single_fic(db, client, "2")
    db.commit()

    # fic1 ya tiene un epub archivado
    responses.add(
        responses.GET,
        "https://archiveofourown.org/works/1?view_adult=true&view_full_work=true",
        body=_read("work_page.html"),
        status=200,
    )
    responses.add(
        responses.GET,
        "https://archiveofourown.org/downloads/1/El_Peso_de_las_Estrellas.epub?updated_at=123",
        body=b"ya archivado",
        status=200,
    )
    downloader.download_fic_epub(db, client, fic1, archivo_dir)
    db.commit()

    # Ahora --all-unarchived solo debería tocar a fic2
    responses.add(
        responses.GET,
        "https://archiveofourown.org/works/2?view_adult=true&view_full_work=true",
        body=_read("work_page_wip_restricted.html"),
        status=200,
    )
    responses.add(
        responses.GET,
        "https://archiveofourown.org/downloads/2/Frecuencia_Nocturna.epub?updated_at=456",
        body=b"contenido fic 2",
        status=200,
    )

    result = downloader.download_all_unarchived(db, client, archivo_dir)

    assert result.descargados == 1
    assert result.errores == 0
    archivo2 = db.query(Archivo).filter_by(fic_id=fic2.id, formato="epub").one()
    assert Path(archivo2.ruta_local).read_bytes() == b"contenido fic 2"
