"""Sincronización masiva con AO3 (bookmarks, marcados, suscripciones, WIPs,
un fic puntual, un EPUB puntual).

Corre del lado del servidor, en segundo plano: el endpoint `/trigger` solo
anota la tarea y responde al toque, y lo que de verdad scrapea AO3 sigue
corriendo después de mandar la respuesta (ver BackgroundTasks de FastAPI).
Puede tardar bastante (una sincronización de bookmarks completa son muchas
páginas, con el rate limit de siempre entre cada una) — por eso no se espera
a que termine antes de responder.

Antes esto lo hacía un workflow de GitHub Actions, porque el host original
(PythonAnywhere free tier) no tenía salida a AO3. En este servidor sí la
hay, así que ya no hace falta ese salto: se usa la misma lógica de import
que el resto de la app (app/ao3/importer.py), con las credenciales de AO3 y
la base de datos de la cuenta que disparó el sync.
"""

from __future__ import annotations

import smtplib
from email.mime.text import MIMEText
from types import SimpleNamespace

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from app.ao3 import downloader, importer
from app.ao3.client import RequestFailedError, SessionRequestLimitReached
from app.ao3.parser import work_id_from_url
from app.api.ao3_session import build_authenticated_client, resolver_credenciales_ao3
from app.auth import get_cuenta_actual
from app.config import settings
from app.control_models import Cuenta
from app.database import nueva_sesion_para_cuenta
from app.models import Fic, ImportLog

router = APIRouter(prefix="/sync", tags=["sync"])

_MODOS_VALIDOS = {"bookmarks", "bookmarks-rapido", "fic", "epub", "marcados", "suscripciones", "wips"}

TIPO_NOVEDAD_TEXTO = {"capitulo_nuevo": "capítulo nuevo", "completado": "se completó"}


class TriggerRequest(BaseModel):
    modo: str
    url: str | None = None
    ao3_id: str | None = None


@router.post("/trigger")
def disparar_sync(
    payload: TriggerRequest,
    background_tasks: BackgroundTasks,
    cuenta: Cuenta = Depends(get_cuenta_actual),
):
    if payload.modo not in _MODOS_VALIDOS:
        raise HTTPException(status_code=400, detail=f"Modo desconocido: {payload.modo}")
    if payload.modo == "fic" and not payload.url:
        raise HTTPException(status_code=400, detail="Falta 'url' para modo=fic.")
    if payload.modo == "epub" and not payload.ao3_id:
        raise HTTPException(status_code=400, detail="Falta 'ao3_id' para modo=epub.")

    background_tasks.add_task(
        _ejecutar_sync,
        cuenta_id=cuenta.id,
        ao3_username=getattr(cuenta, "ao3_username", None),
        ao3_password_encriptada=getattr(cuenta, "ao3_password_encriptada", None),
        email=getattr(cuenta, "email", None),
        modo=payload.modo,
        url=payload.url,
        ao3_id=payload.ao3_id,
    )
    return {"disparado": True}


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


def _enviar_email_novedades(destinatario: str, novedades: list[dict]) -> None:
    """Silencioso si no están configuradas las credenciales de mail (ver
    app/config.py) — no todo el mundo quiere esta notificación."""
    if not settings.gmail_address or not settings.gmail_app_password:
        return

    lineas = []
    for n in novedades:
        tipos = ", ".join(TIPO_NOVEDAD_TEXTO.get(t, t) for t in n["tipos"])
        lineas.append(f"- {n['titulo']} ({tipos})\n  https://archiveofourown.org/works/{n['ao3_id']}")
    cuerpo = "Novedades en tus WIPs:\n\n" + "\n\n".join(lineas)

    mensaje = MIMEText(cuerpo)
    mensaje["Subject"] = f"Archivum: {len(novedades)} fic(s) actualizado(s)"
    mensaje["From"] = settings.gmail_address
    mensaje["To"] = destinatario

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(settings.gmail_address, settings.gmail_app_password)
        smtp.sendmail(settings.gmail_address, [destinatario], mensaje.as_string())


def _sync_modo_fic(db, client, archivo_dir, username: str | None, url: str) -> importer.ImportRunResult:
    """Importa un fic puntual. Si está bookmarkeado, de paso le trae la nota
    y los tags de ESE bookmark — AO3 no los expone en la página del fic,
    solo en el listado de bookmarks, así que hay que recorrerlo buscando el
    que coincida (en el peor caso tarda lo mismo que un sync de bookmarks
    completo, pero corta apenas lo encuentra)."""
    result = importer.ImportRunResult(tipo="fic")
    ao3_id = work_id_from_url(url)
    if ao3_id is None:
        result.errores += 1
        result.detalles_error.append(f"No reconozco un id de fic en '{url}'.")
        return result

    try:
        fic, estado = importer.import_single_fic(db, client, ao3_id, archivo_dir=archivo_dir)
    except importer.FicNotFoundError as exc:
        db.commit()
        result.errores += 1
        result.detalles_error.append(str(exc))
        return result

    tags, bookmarked_at, nota_kwargs = [], None, {}
    if username:
        try:
            for item in importer._walk_bookmark_items(client, username):
                if item.work_id == ao3_id:
                    tags, bookmarked_at, nota_kwargs = item.tags, item.bookmarked_at, {"nota": item.nota}
                    break
        except (RequestFailedError, SessionRequestLimitReached):
            pass  # no se pudo terminar de buscarlo en bookmarks: se importa sin nota/tags

    importer.apply_bookmark_tags(db, fic, tags, bookmarked_at, **nota_kwargs)
    db.commit()

    if estado == "nuevo":
        result.fics_nuevos += 1
    elif estado == "actualizado":
        result.fics_actualizados += 1
    else:
        result.fics_sin_cambios += 1
    return result


def _sync_modo_epub(db, client, archivo_dir, ao3_id: str) -> importer.ImportRunResult:
    result = importer.ImportRunResult(tipo="epub")
    fic = db.query(Fic).filter_by(ao3_id=ao3_id).one_or_none()
    if fic is None:
        result.errores += 1
        result.detalles_error.append(f"Fic {ao3_id} no encontrado.")
        return result
    try:
        downloader.download_fic_epub(db, client, fic, archivo_dir)
        db.commit()
        result.fics_actualizados += 1
    except downloader.DownloadError as exc:
        db.rollback()
        result.errores += 1
        result.detalles_error.append(str(exc))
    return result


def _ejecutar_sync(
    *,
    cuenta_id: int,
    ao3_username: str | None,
    ao3_password_encriptada: str | None,
    email: str | None,
    modo: str,
    url: str | None,
    ao3_id: str | None,
) -> None:
    db = nueva_sesion_para_cuenta(cuenta_id)
    try:
        cuenta_ao3 = SimpleNamespace(ao3_username=ao3_username, ao3_password_encriptada=ao3_password_encriptada)
        try:
            # El usuario efectivo puede no ser ao3_username (en modo sin
            # login real, resuelve al del .env) — hay que usar ESTE para
            # recorrer bookmarks/listados, no el campo crudo de la cuenta.
            username, _ = resolver_credenciales_ao3(cuenta_ao3)
            client = build_authenticated_client(cuenta_ao3)
        except HTTPException as exc:
            _persist_log(db, importer.ImportRunResult(tipo=modo, errores=1, detalles_error=[str(exc.detail)]))
            return

        archivo_dir = settings.archivo_dir(cuenta_id)
        novedades_para_mail: list[dict] = []
        if modo == "fic":
            result = _sync_modo_fic(db, client, archivo_dir, username, url)
        elif modo == "epub":
            result = _sync_modo_epub(db, client, archivo_dir, ao3_id)
        elif modo in ("bookmarks", "bookmarks-rapido"):
            result = importer.run_bulk_import(
                db,
                client,
                tipo="bookmarks",
                username=username,
                rapido=(modo == "bookmarks-rapido"),
                archivo_dir=archivo_dir,
            )
        elif modo in ("marcados", "suscripciones"):
            result = importer.run_bulk_import(db, client, tipo=modo, username=username, archivo_dir=archivo_dir)
        elif modo == "wips":
            result, novedades_para_mail = importer.run_wips_import(db, client, archivo_dir=archivo_dir)
        else:
            return

        _persist_log(db, result)
        if novedades_para_mail and email:
            _enviar_email_novedades(email, novedades_para_mail)
    except Exception as exc:  # noqa: BLE001 - una tarea en segundo plano no debe perderse en silencio
        db.rollback()
        _persist_log(db, importer.ImportRunResult(tipo=modo, errores=1, detalles_error=[f"Error inesperado: {exc}"]))
    finally:
        db.close()
