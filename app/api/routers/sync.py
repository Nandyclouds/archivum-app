"""Sincronización masiva con AO3 (bookmarks, marcados, suscripciones, WIPs,
un fic puntual, un EPUB puntual) — corre en GitHub Actions, no en este
servidor.

Hetzner no le llega de forma confiable a AO3 (pruebas directas desde la
terminal del servidor dan 525/timeout en cualquier página que no sea la
portada, de forma persistente, con o sin IPv6 — algo de la ruta de red
entre el datacenter y AO3, no un bloqueo por "parecer bot" que se destrabe
solo). GitHub Actions sí le llegaba bien durante años, así que:

1. El frontend llama a `POST /sync/trigger`, que dispara un workflow de
   GitHub Actions vía la API de GitHub, pasándole qué cuenta disparó el
   sync (`cuenta_id`).
2. Ese workflow corre `scripts/gh_action_sync.py`, que primero le pide a
   este mismo servidor las credenciales de AO3 de ESA cuenta (nunca viajan
   como secreto de GitHub: el repo es público, y además son por cuenta, no
   un valor fijo) y después scrapea AO3 con la misma lógica de siempre
   (app/ao3/*), mandando el resultado de vuelta acá.
3. Los endpoints `ingest-*`/`known-ids`/`incompletos` reciben eso y hacen
   los mismos guardados que haría un import local, en la base de datos de
   la cuenta correspondiente.

Autenticación: estas rutas (menos `trigger`) nunca las habla el frontend,
así que no usan el token de usuario — usan ARCHIVUM_SYNC_SECRET por header
(ver main.py), más `?cuenta_id=` para saber de quién es cada pedido.
"""

from __future__ import annotations

import base64
import datetime
import smtplib
from email.mime.text import MIMEText

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ao3.downloader import guardar_epub
from app.ao3.importer import apply_bookmark_tags, guardar_snapshot_html, upsert_fic
from app.ao3.parser import parse_work_page
from app.auth import get_cuenta_actual
from app.config import settings
from app.control_db import get_control_session
from app.control_models import Cuenta
from app.crypto import desencriptar
from app.database import get_session
from app.models import Fic

router = APIRouter(prefix="/sync", tags=["sync"])

_MODOS_VALIDOS = {"bookmarks", "bookmarks-rapido", "fic", "epub", "marcados", "suscripciones", "wips"}

TIPO_NOVEDAD_TEXTO = {"capitulo_nuevo": "capítulo nuevo", "completado": "se completó"}


# ---------------------------------------------------------------------------
# Disparo del workflow (lo llama el frontend)
# ---------------------------------------------------------------------------


class TriggerRequest(BaseModel):
    modo: str
    url: str | None = None
    ao3_id: str | None = None


@router.post("/trigger")
def disparar_sync(payload: TriggerRequest, cuenta: Cuenta = Depends(get_cuenta_actual)):
    if not settings.github_pat or not settings.github_repo:
        raise HTTPException(
            status_code=503,
            detail="GITHUB_PAT/GITHUB_REPO no configurados en el .env de este servidor.",
        )
    if payload.modo not in _MODOS_VALIDOS:
        raise HTTPException(status_code=400, detail=f"Modo desconocido: {payload.modo}")
    if payload.modo == "fic" and not payload.url:
        raise HTTPException(status_code=400, detail="Falta 'url' para modo=fic.")
    if payload.modo == "epub" and not payload.ao3_id:
        raise HTTPException(status_code=400, detail="Falta 'ao3_id' para modo=epub.")
    if not getattr(cuenta, "ao3_username", None) or not getattr(cuenta, "ao3_password_encriptada", None):
        raise HTTPException(status_code=409, detail="Todavía no configuraste tus credenciales de AO3 en Ajustes.")

    dispatch_url = (
        f"https://api.github.com/repos/{settings.github_repo}/actions/workflows/"
        f"{settings.github_workflow_file}/dispatches"
    )
    inputs = {"modo": payload.modo, "cuenta_id": str(cuenta.id)}
    if payload.url:
        inputs["url"] = payload.url
    if payload.ao3_id:
        inputs["ao3_id"] = payload.ao3_id

    response = requests.post(
        dispatch_url,
        headers={
            "Authorization": f"Bearer {settings.github_pat}",
            "Accept": "application/vnd.github+json",
        },
        json={"ref": "main", "inputs": inputs},
        timeout=15,
    )
    if response.status_code != 204:
        raise HTTPException(
            status_code=502,
            detail=f"GitHub rechazó el disparo del workflow ({response.status_code}): {response.text[:300]}",
        )
    return {"disparado": True}


# ---------------------------------------------------------------------------
# Lo que habla el workflow de GitHub Actions (nunca el frontend)
# ---------------------------------------------------------------------------


@router.get("/cuentas-activas")
def cuentas_activas(db: Session = Depends(get_control_session)):
    """Para la corrida diaria programada (ver .github/workflows/ao3-sync.yml):
    qué cuentas tienen AO3 conectado, para recorrerlas una por una."""
    cuentas = (
        db.query(Cuenta.id)
        .filter(Cuenta.activa.is_(True), Cuenta.ao3_username.isnot(None), Cuenta.ao3_password_encriptada.isnot(None))
        .all()
    )
    return {"cuenta_ids": [c.id for c in cuentas]}


@router.get("/credenciales-ao3")
def credenciales_ao3(cuenta: Cuenta = Depends(get_cuenta_actual)):
    username = getattr(cuenta, "ao3_username", None)
    password_encriptada = getattr(cuenta, "ao3_password_encriptada", None)
    if not username or not password_encriptada:
        raise HTTPException(status_code=409, detail="Esta cuenta no tiene credenciales de AO3 configuradas.")
    return {"ao3_username": username, "ao3_password": desencriptar(password_encriptada), "email": cuenta.email}


@router.get("/known-ids")
def known_ids(db: Session = Depends(get_session)):
    """IDs de fics que ya tenemos, para que el sync de bookmarks se salte los conocidos."""
    ids = [row[0] for row in db.query(Fic.ao3_id).all()]
    return {"ao3_ids": ids}


@router.get("/incompletos")
def fics_incompletos(stale_days: int = 3, db: Session = Depends(get_session)):
    """IDs de fics marcados 'complete=False' que conviene volver a pedirle a
    AO3 (para detectar capítulos nuevos o que se haya completado — ver
    Novedad). `stale_days` evita re-chequear el mismo WIP en cada corrida:
    solo entran los que no se revisaron en esa cantidad de días (o nunca)."""
    limite = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(
        days=stale_days
    )
    query = db.query(Fic.ao3_id).filter(
        Fic.complete.is_(False),
        Fic.deleted_detected_at.is_(None),
        (Fic.ultima_revision.is_(None)) | (Fic.ultima_revision < limite),
    )
    return {"ao3_ids": [row[0] for row in query.all()]}


class IngestFicRequest(BaseModel):
    ao3_id: str
    # Opcional a propósito: para un fic que YA está en la biblioteca, el
    # runner de GitHub Actions manda solo los tags actualizados del
    # bookmark, sin re-pedir ni re-mandar el HTML entero (no hace falta:
    # nada del fic en sí cambió, solo cómo lo tiene taggeado la usuaria en
    # AO3 — y eso ya lo sabe de haber listado la página de bookmarks, sin
    # gastar otra petición). Si el fic todavía no existe, html es
    # obligatorio (si no, no hay de dónde sacar título/fandoms/etc.).
    html: str | None = None
    bookmark_tags: list[str] | None = None
    bookmarked_at: str | None = None
    # Ausente a propósito (no un simple None) para el sync de "Marked for
    # Later"/WIPs, que llama a este mismo endpoint pero nunca vio la página
    # de bookmarks — no tiene que borrar una nota que ya estaba guardada.
    # Ver apply_bookmark_tags/_SIN_INFO_DE_NOTA.
    nota: str | None = None


@router.post("/ingest-fic")
def ingest_fic(payload: IngestFicRequest, db: Session = Depends(get_session)):
    novedades_detectadas: list[str] = []
    if payload.html:
        parsed = parse_work_page(payload.html, payload.ao3_id)
        fic, es_nuevo, novedades_detectadas = upsert_fic(db, parsed)
        guardar_snapshot_html(db, fic, payload.html)
    else:
        fic = db.query(Fic).filter_by(ao3_id=payload.ao3_id).one_or_none()
        if fic is None:
            raise HTTPException(
                status_code=404,
                detail=f"Fic {payload.ao3_id} no encontrado (mandá 'html' para crearlo).",
            )
        es_nuevo = False

    nota_provista = "nota" in payload.model_fields_set
    if payload.bookmark_tags or nota_provista:
        kwargs = {"nota": payload.nota} if nota_provista else {}
        apply_bookmark_tags(db, fic, payload.bookmark_tags or [], payload.bookmarked_at, **kwargs)
    db.commit()
    return {
        "ao3_id": fic.ao3_id,
        "es_nuevo": es_nuevo,
        "titulo": fic.titulo,
        # Para que el runner de GitHub Actions (modo=wips) sepa qué novedades
        # encontró sin tener que volver a consultar la API, y arme el aviso
        # por mail — ver /sync/notificar-novedades.
        "novedades": novedades_detectadas,
    }


class IngestEpubRequest(BaseModel):
    ao3_id: str
    content_base64: str


@router.post("/ingest-epub")
def ingest_epub(payload: IngestEpubRequest, db: Session = Depends(get_session), cuenta: Cuenta = Depends(get_cuenta_actual)):
    fic = db.query(Fic).filter_by(ao3_id=payload.ao3_id).one_or_none()
    if fic is None:
        raise HTTPException(status_code=404, detail=f"Fic {payload.ao3_id} no encontrado.")
    contenido = base64.b64decode(payload.content_base64)
    guardar_epub(db, fic, contenido, settings.archivo_dir(cuenta.id))
    db.commit()
    return {"ao3_id": fic.ao3_id, "bytes": len(contenido)}


class NovedadItem(BaseModel):
    ao3_id: str
    titulo: str
    tipos: list[str]


class NotificarNovedadesRequest(BaseModel):
    novedades: list[NovedadItem]


@router.post("/notificar-novedades")
def notificar_novedades(payload: NotificarNovedadesRequest, cuenta: Cuenta = Depends(get_cuenta_actual)):
    """Manda el mail de aviso de 'Revisar WIPs' — lo manda este servidor
    (no el runner de GitHub Actions) para no duplicar GMAIL_ADDRESS/
    GMAIL_APP_PASSWORD como secretos de GitHub además de en el .env."""
    if not payload.novedades or not settings.gmail_address or not settings.gmail_app_password:
        return {"enviado": False}

    lineas = []
    for n in payload.novedades:
        tipos = ", ".join(TIPO_NOVEDAD_TEXTO.get(t, t) for t in n.tipos)
        lineas.append(f"- {n.titulo} ({tipos})\n  https://archiveofourown.org/works/{n.ao3_id}")
    cuerpo = "Novedades en tus WIPs:\n\n" + "\n\n".join(lineas)

    mensaje = MIMEText(cuerpo)
    mensaje["Subject"] = f"Archivum: {len(payload.novedades)} fic(s) actualizado(s)"
    mensaje["From"] = settings.gmail_address
    mensaje["To"] = cuenta.email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(settings.gmail_address, settings.gmail_app_password)
        smtp.sendmail(settings.gmail_address, [cuenta.email], mensaje.as_string())
    return {"enviado": True}
