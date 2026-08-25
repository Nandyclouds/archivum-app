"""Runner que corre en GitHub Actions: scrapea AO3 y manda el resultado a Archivum.

Existe porque el host donde vive la app (PythonAnywhere free tier) no tiene
salida a AO3, pero GitHub Actions sí. Reusa el mismo cliente rate-limitado y
parser que el CLI local (app/ao3/*) — la única diferencia es que en vez de
escribir en una base SQLite local, manda lo que scrapeó por HTTP a los
endpoints /api/sync/* de la app (ver app/api/routers/sync.py), que hacen el
guardado real.

Uso (variables de entorno, seteadas como GitHub Secrets en el workflow):
    AO3_USERNAME, AO3_PASSWORD, AO3_CONTACT_EMAIL
    ARCHIVUM_BASE_URL   (ej: https://tu-usuario.pythonanywhere.com)
    ARCHIVUM_SYNC_SECRET

    python scripts/gh_action_sync.py --modo fic --url https://archiveofourown.org/works/123
    python scripts/gh_action_sync.py --modo epub --ao3-id 123
    python scripts/gh_action_sync.py --modo bookmarks
    python scripts/gh_action_sync.py --modo marcados
    python scripts/gh_action_sync.py --modo wips
"""

from __future__ import annotations

import argparse
import base64
import os
import sys
import time

import requests

from app.ao3 import auth
from app.ao3.client import RateLimitedClient, RequestFailedError, SessionRequestLimitReached
from app.ao3.importer import HISTORY_MARKED_URL, WORK_URL, _walk_bookmark_items, _walk_listing_work_ids
from app.ao3.parser import parse_history_page, parse_work_page, work_id_from_url

# Tope de tiempo total para los modos que recorren varias páginas de listado
# (bookmarks, marcados): AO3 a veces devuelve 429/503 sostenido durante un
# rato — reintentamos con pausas en vez de morir de una, pero sin pasarnos
# del límite de minutos del runner de GitHub Actions.
PRESUPUESTO_TOTAL_SEGUNDOS = 50 * 60
ESPERA_ENTRE_REINTENTOS_SEGUNDOS = 5 * 60

# Nombre de la colección donde caen los fics de "Marked for Later" — mismo
# mecanismo que cualquier otro tag de bookmark (ver reading_status.py), pero
# a diferencia de "por leer" no se interpreta como estado de lectura: es
# solo una etiqueta, para no pisar el estado real si la usuaria ya lo leyó
# por otro lado.
TAG_MARCADOS = "Marked for Later"


def _base_url() -> str:
    url = os.environ.get("ARCHIVUM_BASE_URL", "").rstrip("/")
    if not url:
        print("Falta ARCHIVUM_BASE_URL.", file=sys.stderr)
        sys.exit(1)
    return url


def _sync_headers() -> dict:
    secret = os.environ.get("ARCHIVUM_SYNC_SECRET", "")
    if not secret:
        print("Falta ARCHIVUM_SYNC_SECRET.", file=sys.stderr)
        sys.exit(1)
    return {"X-Sync-Secret": secret}


def _build_client() -> RateLimitedClient:
    contact_email = os.environ.get("AO3_CONTACT_EMAIL", "")
    if not contact_email:
        print("Falta AO3_CONTACT_EMAIL.", file=sys.stderr)
        sys.exit(1)
    return RateLimitedClient(contact_email=contact_email, min_delay_seconds=6.0)


def _login(client: RateLimitedClient) -> None:
    username = os.environ.get("AO3_USERNAME", "")
    password = os.environ.get("AO3_PASSWORD", "")
    try:
        auth.login(client, username, password)
    except auth.LoginError as exc:
        print(f"Login a AO3 falló: {exc}", file=sys.stderr)
        sys.exit(1)


_SIN_NOTA = object()  # sentinel: no mandar la clave "nota" en absoluto (ver IngestFicRequest)


def _ingest_fic(
    base_url: str, headers: dict, ao3_id: str, html: str | None = None, *, tags=None, bookmarked_at=None, nota=_SIN_NOTA
) -> None:
    payload = {"ao3_id": ao3_id}
    if html:
        payload["html"] = html
    if tags:
        payload["bookmark_tags"] = tags
    if bookmarked_at:
        payload["bookmarked_at"] = bookmarked_at
    if nota is not _SIN_NOTA:
        payload["nota"] = nota
    response = requests.post(f"{base_url}/api/sync/ingest-fic", json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    print(f"  ingest-fic {ao3_id}: {response.json()}")


def modo_fic(client: RateLimitedClient, base_url: str, headers: dict, url: str) -> None:
    ao3_id = work_id_from_url(url)
    if ao3_id is None:
        print(f"No reconozco un id de fic en '{url}'.", file=sys.stderr)
        sys.exit(1)

    response = client.get(WORK_URL.format(ao3_id=ao3_id))
    response.raise_for_status()
    _ingest_fic(base_url, headers, ao3_id, response.text)


def modo_epub(client: RateLimitedClient, base_url: str, headers: dict, ao3_id: str) -> None:
    page_response = client.get(WORK_URL.format(ao3_id=ao3_id))
    page_response.raise_for_status()
    parsed = parse_work_page(page_response.text, ao3_id)
    if parsed.epub_url is None:
        print(f"AO3 no ofrece EPUB para el fic {ao3_id}.", file=sys.stderr)
        sys.exit(1)

    epub_response = client.get(parsed.epub_url)
    epub_response.raise_for_status()

    payload = {"ao3_id": ao3_id, "content_base64": base64.b64encode(epub_response.content).decode()}
    response = requests.post(f"{base_url}/api/sync/ingest-epub", json=payload, headers=headers, timeout=60)
    response.raise_for_status()
    print(f"  ingest-epub {ao3_id}: {response.json()}")


def modo_bookmarks(client: RateLimitedClient, base_url: str, headers: dict) -> None:
    username = os.environ.get("AO3_USERNAME", "")

    response = requests.get(f"{base_url}/api/sync/known-ids", headers=headers, timeout=30)
    response.raise_for_status()
    conocidos = set(response.json()["ao3_ids"])
    print(f"Fics ya conocidos en Archivum: {len(conocidos)}")

    inicio = time.monotonic()
    start_page = 1
    progreso = {"pagina": start_page}
    nuevos = 0
    while True:
        try:
            for item in _walk_bookmark_items(client, username, start_page=start_page, progreso=progreso):
                ya_conocido = item.work_id in conocidos
                try:
                    if ya_conocido:
                        # Ya tenemos el fic — no hace falta re-pedirlo a AO3,
                        # pero SÍ hay que re-mandar los tags: si cambiaste
                        # el tag en AO3 (ej. de "por leer" a "Leídos 2026"),
                        # esto es lo único que se entera de eso.
                        _ingest_fic(
                            base_url,
                            headers,
                            item.work_id,
                            tags=item.tags,
                            bookmarked_at=item.bookmarked_at,
                            nota=item.nota,
                        )
                    else:
                        fic_response = client.get(WORK_URL.format(ao3_id=item.work_id))
                        fic_response.raise_for_status()
                        _ingest_fic(
                            base_url,
                            headers,
                            item.work_id,
                            fic_response.text,
                            tags=item.tags,
                            bookmarked_at=item.bookmarked_at,
                            nota=item.nota,
                        )
                        conocidos.add(item.work_id)
                        nuevos += 1
                except (RequestFailedError, requests.exceptions.RequestException) as exc:
                    print(f"  ! {item.work_id}: {exc}", file=sys.stderr)
            break  # terminó de recorrer todas las páginas sin cortarse
        except SessionRequestLimitReached as exc:
            print(f"Límite de sesión alcanzado: {exc}. Terminando esta corrida.")
            break
        except RequestFailedError as exc:
            transcurrido = time.monotonic() - inicio
            if transcurrido + ESPERA_ENTRE_REINTENTOS_SEGUNDOS > PRESUPUESTO_TOTAL_SEGUNDOS:
                print(f"AO3 sigue fallando y se acabó el presupuesto de tiempo: {exc}")
                break
            print(f"AO3 falló listando páginas ({exc}). Esperando 5 min antes de reintentar...")
            time.sleep(ESPERA_ENTRE_REINTENTOS_SEGUNDOS)
            # Reanudar desde la página donde se cortó (progreso["pagina"]),
            # no desde la 1: volver a pedir todas las páginas ya vistas cuesta
            # una petición rate-limitada c/u, y con AO3 fallando seguido eso
            # se come el presupuesto de tiempo antes de llegar a las páginas
            # nuevas — que es justo lo que hacía que algunos bookmarks (y sus
            # notas) nunca se terminaran de sincronizar.
            start_page = progreso["pagina"]
            continue

    print(f"Bookmarks nuevos importados: {nuevos}")


def modo_marcados(client: RateLimitedClient, base_url: str, headers: dict) -> None:
    """Trae los work_ids marcados 'Marked for Later' (?show=to-read de la
    History) y los etiqueta en Archivum. A los ya conocidos solo se les
    agrega el tag (sin re-pedir la página); a los nuevos se los importa
    entero, igual que un bookmark nuevo."""
    username = os.environ.get("AO3_USERNAME", "")

    response = requests.get(f"{base_url}/api/sync/known-ids", headers=headers, timeout=30)
    response.raise_for_status()
    conocidos = set(response.json()["ao3_ids"])
    print(f"Fics ya conocidos en Archivum: {len(conocidos)}")

    inicio = time.monotonic()
    start_page = 1
    progreso = {"pagina": start_page}
    nuevos = 0
    etiquetados = 0
    while True:
        try:
            for work_id in _walk_listing_work_ids(
                client, HISTORY_MARKED_URL, username, parse_history_page,
                start_page=start_page, progreso=progreso,
            ):
                try:
                    if work_id in conocidos:
                        _ingest_fic(base_url, headers, work_id, tags=[TAG_MARCADOS])
                        etiquetados += 1
                    else:
                        fic_response = client.get(WORK_URL.format(ao3_id=work_id))
                        fic_response.raise_for_status()
                        _ingest_fic(base_url, headers, work_id, fic_response.text, tags=[TAG_MARCADOS])
                        conocidos.add(work_id)
                        nuevos += 1
                except (RequestFailedError, requests.exceptions.RequestException) as exc:
                    print(f"  ! {work_id}: {exc}", file=sys.stderr)
            break
        except SessionRequestLimitReached as exc:
            print(f"Límite de sesión alcanzado: {exc}. Terminando esta corrida.")
            break
        except RequestFailedError as exc:
            transcurrido = time.monotonic() - inicio
            if transcurrido + ESPERA_ENTRE_REINTENTOS_SEGUNDOS > PRESUPUESTO_TOTAL_SEGUNDOS:
                print(f"AO3 sigue fallando y se acabó el presupuesto de tiempo: {exc}")
                break
            print(f"AO3 falló listando páginas ({exc}). Esperando 5 min antes de reintentar...")
            time.sleep(ESPERA_ENTRE_REINTENTOS_SEGUNDOS)
            # Igual que en modo_bookmarks: reanudar desde progreso["pagina"]
            # en vez de la página 1, para no quemar el presupuesto de tiempo
            # re-pidiendo páginas de listado ya vistas.
            start_page = progreso["pagina"]
            continue

    print(f"Marked for Later — nuevos importados: {nuevos}, ya conocidos etiquetados: {etiquetados}")


def modo_wips(client: RateLimitedClient, base_url: str, headers: dict) -> None:
    """Vuelve a pedirle a AO3 los fics incompletos que hace rato no se
    revisan (ver /sync/incompletos), para que _detectar_novedades note si
    sumaron capítulo o se completaron. A diferencia de bookmarks/marcados no
    hay páginas de listado que recorrer — la lista ya viene de nuestra
    propia base — así que el único límite es el presupuesto de tiempo."""
    response = requests.get(f"{base_url}/api/sync/incompletos", headers=headers, timeout=30)
    response.raise_for_status()
    ids = response.json()["ao3_ids"]
    print(f"WIPs a revisar: {len(ids)}")

    inicio = time.monotonic()
    revisados = 0
    for ao3_id in ids:
        if time.monotonic() - inicio > PRESUPUESTO_TOTAL_SEGUNDOS:
            print("Se acabó el presupuesto de tiempo para esta corrida, corto acá.")
            break
        try:
            fic_response = client.get(WORK_URL.format(ao3_id=ao3_id))
            fic_response.raise_for_status()
            _ingest_fic(base_url, headers, ao3_id, fic_response.text)
            revisados += 1
        except (RequestFailedError, requests.exceptions.RequestException) as exc:
            print(f"  ! {ao3_id}: {exc}", file=sys.stderr)

    print(f"WIPs revisados: {revisados}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--modo", required=True, choices=["fic", "epub", "bookmarks", "marcados", "wips"])
    parser.add_argument("--url", default=None)
    parser.add_argument("--ao3-id", default=None)
    args = parser.parse_args()

    base_url = _base_url()
    headers = _sync_headers()
    client = _build_client()
    _login(client)

    if args.modo == "fic":
        if not args.url:
            print("--url es obligatorio para --modo fic", file=sys.stderr)
            sys.exit(1)
        modo_fic(client, base_url, headers, args.url)
    elif args.modo == "epub":
        if not args.ao3_id:
            print("--ao3-id es obligatorio para --modo epub", file=sys.stderr)
            sys.exit(1)
        modo_epub(client, base_url, headers, args.ao3_id)
    elif args.modo == "marcados":
        modo_marcados(client, base_url, headers)
    elif args.modo == "wips":
        modo_wips(client, base_url, headers)
    else:
        modo_bookmarks(client, base_url, headers)


if __name__ == "__main__":
    main()
