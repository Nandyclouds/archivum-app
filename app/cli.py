from __future__ import annotations

import sys

import typer

from app import stats as stats_module
from app.ao3 import auth, downloader, importer
from app.ao3.client import RateLimitedClient
from app.ao3.parser import work_id_from_url
from app.config import BASE_DIR, settings
from app.database import SessionLocal
from app.models import Fic, ImportLog

ARCHIVO_DIR = BASE_DIR / "data" / "archivo"

app = typer.Typer(help="Archivum: tracker local de fanfics de AO3.")
import_app = typer.Typer(help="Importar datos desde AO3.")
app.add_typer(import_app, name="import")


def _build_client(max_requests: int | None = None) -> RateLimitedClient:
    if not settings.ao3_contact_email:
        typer.secho(
            "AO3_CONTACT_EMAIL no está configurado en .env. Es obligatorio: "
            "AO3 necesita un User-Agent identificable para no tratarte como bot.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)
    return RateLimitedClient(
        contact_email=settings.ao3_contact_email,
        min_delay_seconds=settings.ao3_min_delay_seconds,
        max_requests_per_session=max_requests or settings.ao3_max_requests_per_session,
    )


def _login_or_exit(client: RateLimitedClient) -> None:
    try:
        auth.login(client, settings.ao3_username, settings.ao3_password)
    except auth.LoginError as exc:
        typer.secho(f"Error de login en AO3: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


def _persist_log(db, result: importer.ImportRunResult) -> None:
    db.add(
        ImportLog(
            tipo=result.tipo,
            fics_nuevos=result.fics_nuevos,
            fics_actualizados=result.fics_actualizados,
            errores=result.errores,
            errores_detalle="\n".join(result.detalles_error) or None,
        )
    )
    db.commit()


def _print_result(result: importer.ImportRunResult) -> None:
    typer.echo(
        f"Nuevos: {result.fics_nuevos}  Actualizados: {result.fics_actualizados}  "
        f"Sin cambios: {result.fics_sin_cambios}  Errores: {result.errores}"
    )
    for detalle in result.detalles_error:
        typer.secho(f"  ! {detalle}", fg=typer.colors.YELLOW)
    if result.detenido_por_limite:
        typer.secho(
            "Se cortó el import antes de terminar (ver detalle arriba). Volvé "
            "a correr el mismo comando para continuar: los fics ya importados "
            "no se vuelven a pedir.",
            fg=typer.colors.YELLOW,
        )


@import_app.command("bookmarks")
def import_bookmarks(
    force: bool = typer.Option(False, help="Ignora la caché y re-descarga todo."),
    stale_days: int = typer.Option(
        importer.DEFAULT_STALE_DAYS, help="Días desde el último check para considerar un fic desactualizado."
    ),
    start_page: int = typer.Option(1, help="Página de bookmarks por la que empezar."),
    max_pages: int = typer.Option(None, help="Máximo de páginas a recorrer en esta corrida."),
    max_requests: int = typer.Option(None, help="Sobrescribe AO3_MAX_REQUESTS_PER_SESSION."),
):
    """Importa tus fics marcados (bookmarks) de AO3."""
    client = _build_client(max_requests)
    _login_or_exit(client)
    db = SessionLocal()
    try:
        result = importer.run_bulk_import(
            db,
            client,
            tipo="bookmarks",
            username=settings.ao3_username,
            force=force,
            stale_days=stale_days,
            start_page=start_page,
            max_pages=max_pages,
        )
        _persist_log(db, result)
        _print_result(result)
    finally:
        db.close()


@import_app.command("history")
def import_history(
    force: bool = typer.Option(False, help="Ignora la caché y re-descarga todo."),
    stale_days: int = typer.Option(
        importer.DEFAULT_STALE_DAYS, help="Días desde el último check para considerar un fic desactualizado."
    ),
    start_page: int = typer.Option(1, help="Página de historial por la que empezar."),
    max_pages: int = typer.Option(None, help="Máximo de páginas a recorrer en esta corrida."),
    max_requests: int = typer.Option(None, help="Sobrescribe AO3_MAX_REQUESTS_PER_SESSION."),
):
    """Importa tu historial de lectura (visitas) de AO3.

    Nota: esto solo agrega/actualiza fics al catálogo. AO3 no distingue
    'leído' de 'abandonado' de 'en progreso' en su historial, así que ese
    estado seguís completándolo vos en la app.
    """
    client = _build_client(max_requests)
    _login_or_exit(client)
    db = SessionLocal()
    try:
        result = importer.run_bulk_import(
            db,
            client,
            tipo="history",
            username=settings.ao3_username,
            force=force,
            stale_days=stale_days,
            start_page=start_page,
            max_pages=max_pages,
        )
        _persist_log(db, result)
        _print_result(result)
    finally:
        db.close()


@import_app.command("fic")
def import_fic_cmd(
    url: str = typer.Argument(..., help="URL o ao3_id del fic (ej: https://archiveofourown.org/works/12345)"),
    force: bool = typer.Option(False, help="Ignora la caché y re-descarga aunque esté reciente."),
):
    """Importa un único fic por URL o id."""
    ao3_id = work_id_from_url(url)
    if ao3_id is None:
        typer.secho(f"No pude reconocer un id de fic en '{url}'.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    client = _build_client()
    _login_or_exit(client)
    db = SessionLocal()
    try:
        try:
            _, estado = importer.import_single_fic(db, client, ao3_id, force=force)
            db.commit()
        except importer.FicNotFoundError as exc:
            db.commit()
            typer.secho(str(exc), fg=typer.colors.RED)
            raise typer.Exit(code=1)
        result = importer.ImportRunResult(
            tipo="fic",
            fics_nuevos=1 if estado == "nuevo" else 0,
            fics_actualizados=1 if estado == "actualizado" else 0,
            fics_sin_cambios=1 if estado == "cacheado" else 0,
        )
        _persist_log(db, result)
        typer.echo(f"Fic {ao3_id}: {estado}")
    finally:
        db.close()


@app.command("check-deleted")
def check_deleted_cmd(
    stale_days: int = typer.Option(
        None, help="Solo revisa fics no chequeados en al menos N días. Por defecto revisa todos."
    ),
    max_requests: int = typer.Option(None, help="Sobrescribe AO3_MAX_REQUESTS_PER_SESSION."),
):
    """Revisita cada fic no marcado como borrado; marca deleted_detected_at en los que dan 404."""
    client = _build_client(max_requests)
    _login_or_exit(client)
    db = SessionLocal()
    try:
        result = importer.check_deleted(db, client, stale_days=stale_days)
        _persist_log(db, result)
        _print_result(result)
    finally:
        db.close()


@app.command("stats")
def stats_cmd():
    """Muestra un resumen rápido de la biblioteca en la terminal."""
    db = SessionLocal()
    try:
        resumen = stats_module.resumen_general(db)
        typer.echo(f"Fics en la biblioteca: {resumen['total_fics']}")
        typer.echo(f"Palabras leídas: {resumen['total_palabras_leidas']:,}")
        typer.echo(f"Fandoms: {resumen['total_fandoms']}   Ships: {resumen['total_ships']}")
        typer.echo("")
        typer.echo("Top fandoms:")
        for nombre, total in stats_module.top_fandoms(db, limite=5):
            typer.echo(f"  {nombre}: {total}")
        typer.echo("")
        ratio = stats_module.ratio_wip_vs_completos(db)
        typer.echo(f"Completos: {ratio['completos']}   WIP: {ratio['wip']}")
    finally:
        db.close()


@app.command("download")
def download_cmd(
    fic_id: str = typer.Argument(None, help="ao3_id o URL del fic a descargar."),
    all_unarchived: bool = typer.Option(
        False, "--all-unarchived", help="Descarga el EPUB de todos los fics que todavía no tienen uno guardado."
    ),
    max_requests: int = typer.Option(None, help="Sobrescribe AO3_MAX_REQUESTS_PER_SESSION."),
):
    """Descarga el EPUB de un fic (o de todos los que falten) a data/archivo/."""
    if bool(fic_id) == all_unarchived:
        typer.secho(
            "Especificá un fic_id o pasá --all-unarchived (no ambos, no ninguno).", fg=typer.colors.RED
        )
        raise typer.Exit(code=1)

    client = _build_client(max_requests)
    _login_or_exit(client)
    db = SessionLocal()
    try:
        if all_unarchived:
            result = downloader.download_all_unarchived(db, client, ARCHIVO_DIR)
            typer.echo(f"Descargados: {result.descargados}  Errores: {result.errores}")
            for detalle in result.detalles_error:
                typer.secho(f"  ! {detalle}", fg=typer.colors.YELLOW)
            if result.detenido_por_limite:
                typer.secho(
                    "Se llegó al límite de peticiones de la sesión. Volvé a correr "
                    "el mismo comando para continuar.",
                    fg=typer.colors.YELLOW,
                )
        else:
            ao3_id = work_id_from_url(fic_id)
            if ao3_id is None:
                typer.secho(f"No pude reconocer un id de fic en '{fic_id}'.", fg=typer.colors.RED)
                raise typer.Exit(code=1)
            fic = db.query(Fic).filter_by(ao3_id=ao3_id).one_or_none()
            if fic is None:
                typer.secho(
                    f"El fic {ao3_id} todavía no está importado. Corré 'import fic' primero.",
                    fg=typer.colors.RED,
                )
                raise typer.Exit(code=1)
            try:
                archivo = downloader.download_fic_epub(db, client, fic, ARCHIVO_DIR)
                db.commit()
                typer.echo(f"Guardado en {archivo.ruta_local} ({archivo.tamano:,} bytes)")
            except downloader.DownloadError as exc:
                db.rollback()
                typer.secho(str(exc), fg=typer.colors.RED)
                raise typer.Exit(code=1)
    finally:
        db.close()


if __name__ == "__main__":
    app()
