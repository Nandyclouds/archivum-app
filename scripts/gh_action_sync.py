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
from app.ao3.importer import WORK_URL, _walk_bookmark_items
from app.ao3.parser import parse_work_page, work_id_from_url

# Tope de tiempo total para el modo bookmarks: AO3 a veces devuelve 429/503
# sostenido durante un rato — reintentamos con pausas en vez de morir de
# una, pero sin pasarnos del límite de minutos del runner de GitHub Actions.
PRESUPUESTO_TOTAL_SEGUNDOS = 50 * 60
ESPERA_ENTRE_REINTENTOS_SEGUNDOS = 5 * 60


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


def _ingest_fic(base_url: str, headers: dict, ao3_id: str, html: str, *, tags=None, bookmarked_at=None) -> None:
    payload = {"ao3_id": ao3_id, "html": html}
    if tags:
        payload["bookmark_tags"] = tags
    if bookmarked_at:
        payload["bookmarked_at"] = bookmarked_at
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
    nuevos = 0
    while True:
        try:
            for item in _walk_bookmark_items(client, username, start_page=start_page):
                if item.work_id in conocidos:
                    continue
                try:
                    fic_response = client.get(WORK_URL.format(ao3_id=item.work_id))
                    fic_response.raise_for_status()
                    _ingest_fic(
                        base_url,
                        headers,
                        item.work_id,
                        fic_response.text,
                        tags=item.tags,
                        bookmarked_at=item.bookmarked_at,
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
            # No sabemos exactamente en qué página se cortó _walk_bookmark_items
            # (es un generador), así que reintentamos desde el principio: las
            # páginas ya vistas son baratas (una petición c/u) y cada fic ya
            # ingresado está en `conocidos`, así que se saltea sin re-pedirlo.
            start_page = 1
            continue

    print(f"Bookmarks nuevos importados: {nuevos}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--modo", required=True, choices=["fic", "epub", "bookmarks"])
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
    else:
        modo_bookmarks(client, base_url, headers)


if __name__ == "__main__":
    main()
