"""Runner que corre en GitHub Actions: scrapea AO3 y manda el resultado a Archivum.

Existe porque Hetzner no le llega de forma confiable a AO3 (ver docstring de
app/api/routers/sync.py), pero GitHub Actions sí. Reusa el mismo cliente
rate-limitado y parser que el CLI local (app/ao3/*) — la única diferencia es
que en vez de escribir en una base SQLite local, manda lo que scrapeó por
HTTP a los endpoints /api/sync/* de la app, que hacen el guardado real.

A diferencia de la versión de un solo tenant, esto corre "a nombre de" una
cuenta puntual (--cuenta-id): las credenciales de AO3 nunca viajan como
secreto de GitHub (el repo es público, y además son por cuenta) — este
script se las pide al propio servidor de Archivum al arrancar.

Uso (variables de entorno, seteadas como GitHub Secrets en el workflow):
    AO3_CONTACT_EMAIL, ARCHIVUM_BASE_URL, ARCHIVUM_SYNC_SECRET

    python scripts/gh_action_sync.py --cuenta-id 1 --modo fic --url https://archiveofourown.org/works/123
    python scripts/gh_action_sync.py --cuenta-id 1 --modo epub --ao3-id 123
    python scripts/gh_action_sync.py --cuenta-id 1 --modo bookmarks
    python scripts/gh_action_sync.py --cuenta-id 1 --modo marcados
    python scripts/gh_action_sync.py --cuenta-id 1 --modo suscripciones
    python scripts/gh_action_sync.py --cuenta-id 1 --modo wips
"""

from __future__ import annotations

import argparse
import base64
import os
import random
import sys
import time

import requests

from app.ao3 import auth
from app.ao3.client import RateLimitedClient, RequestFailedError, SessionRequestLimitReached
from app.ao3.importer import (
    HISTORY_MARKED_URL,
    SUBSCRIPTIONS_URL,
    WORK_URL,
    _walk_bookmark_items,
    _walk_listing_work_ids,
)
from app.ao3.parser import parse_history_page, parse_subscriptions_page, parse_work_page, work_id_from_url

# Tope de tiempo total para los modos que recorren varias páginas de listado
# (bookmarks, marcados): AO3 a veces devuelve 429/503/525 sostenido durante
# un rato — reintentamos con pausas en vez de morir de una. Antes esto
# llegaba a los 50 min del runner, lo que en la práctica significaba
# machacar a AO3 con reintentos cada 5 min durante casi una hora seguida sin
# lograr nada (ver corridas de prueba de octubre 2026) — probablemente lo
# contrario de lo que conviene si el bloqueo es por reputación de IP. Ahora
# se corta antes y, si sigue fallando, es mejor volver a correrlo más tarde
# (corrida nueva, con su propia sesión) que insistir en la misma ventana.
PRESUPUESTO_TOTAL_SEGUNDOS = 15 * 60
ESPERA_ENTRE_REINTENTOS_SEGUNDOS = 3 * 60
# Margen aleatorio sumado a la espera entre reintentos, para no repetir
# siempre el mismo intervalo exacto.
JITTER_REINTENTOS_SEGUNDOS = 60

# Nombre de la colección donde caen los fics de "Marked for Later" — mismo
# mecanismo que cualquier otro tag de bookmark (ver reading_status.py), pero
# a diferencia de "por leer" no se interpreta como estado de lectura: es
# solo una etiqueta, para no pisar el estado real si la usuaria ya lo leyó
# por otro lado.
TAG_MARCADOS = "Marked for Later"

# Mismo mecanismo que TAG_MARCADOS, para los fics a los que estás suscripta
# en AO3 (que pueden no estar bookmarkeados) — así quedan agrupados en una
# colección y, al quedar en la biblioteca, "Revisar WIPs" también los chequea.
TAG_SUSCRIPCIONES = "Suscripciones AO3"


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


def _obtener_credenciales(base_url: str, headers: dict, cuenta_id: int) -> tuple[str, str, str]:
    """(ao3_username, ao3_password, email) de la cuenta, pedidas al propio
    servidor — ver GET /api/sync/credenciales-ao3."""
    response = requests.get(
        f"{base_url}/api/sync/credenciales-ao3", headers=headers, params={"cuenta_id": cuenta_id}, timeout=15
    )
    if response.status_code == 409:
        print(f"La cuenta {cuenta_id} no tiene credenciales de AO3 configuradas.", file=sys.stderr)
        sys.exit(1)
    response.raise_for_status()
    data = response.json()
    return data["ao3_username"], data["ao3_password"], data["email"]


def _build_client() -> RateLimitedClient:
    contact_email = os.environ.get("AO3_CONTACT_EMAIL", "")
    if not contact_email:
        print("Falta AO3_CONTACT_EMAIL.", file=sys.stderr)
        sys.exit(1)
    # Delay más largo y con jitter (8 a 14s entre pedidos, en vez de 6s fijos
    # siempre iguales): más lento, pero un patrón menos reconocible como bot
    # para la mitigación de Cloudflare.
    return RateLimitedClient(contact_email=contact_email, min_delay_seconds=8.0, jitter_seconds=6.0)


def _login(client: RateLimitedClient, username: str, password: str) -> None:
    try:
        auth.login(client, username, password)
    except auth.LoginError as exc:
        print(f"Login a AO3 falló: {exc}", file=sys.stderr)
        sys.exit(1)


_SIN_NOTA = object()  # sentinel: no mandar la clave "nota" en absoluto (ver IngestFicRequest)


def _ingest_fic(
    base_url: str,
    headers: dict,
    cuenta_id: int,
    ao3_id: str,
    html: str | None = None,
    *,
    tags=None,
    bookmarked_at=None,
    nota=_SIN_NOTA,
) -> dict:
    payload = {"ao3_id": ao3_id}
    if html:
        payload["html"] = html
    if tags:
        payload["bookmark_tags"] = tags
    if bookmarked_at:
        payload["bookmarked_at"] = bookmarked_at
    if nota is not _SIN_NOTA:
        payload["nota"] = nota
    response = requests.post(
        f"{base_url}/api/sync/ingest-fic",
        json=payload,
        headers=headers,
        params={"cuenta_id": cuenta_id},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    print(f"  ingest-fic {ao3_id}: {data}")
    return data


def _notificar_novedades(base_url: str, headers: dict, cuenta_id: int, novedades: list[dict]) -> None:
    """El mail de aviso lo arma y manda el servidor, no este script — ver
    POST /sync/notificar-novedades."""
    response = requests.post(
        f"{base_url}/api/sync/notificar-novedades",
        json={"novedades": novedades},
        headers=headers,
        params={"cuenta_id": cuenta_id},
        timeout=15,
    )
    response.raise_for_status()
    print(f"  aviso de novedades: {response.json()}")


def modo_fic(client: RateLimitedClient, base_url: str, headers: dict, cuenta_id: int, username: str, url: str) -> None:
    """Importa un fic puntual por URL. Si está bookmarkeado, también le
    trae la nota y los tags de ESE bookmark exacto — AO3 no los expone en
    la página del fic, solo en el listado de bookmarks, así que hay que
    recorrerlo buscando el que coincida (se corta apenas lo encuentra; en
    el peor caso, si el bookmark es viejo, tarda lo mismo que "Actualizar
    bookmarks" completo)."""
    ao3_id = work_id_from_url(url)
    if ao3_id is None:
        print(f"No reconozco un id de fic en '{url}'.", file=sys.stderr)
        sys.exit(1)

    response = client.get(WORK_URL.format(ao3_id=ao3_id))
    response.raise_for_status()

    tags, bookmarked_at, nota = None, None, _SIN_NOTA
    print(f"Buscando el bookmark de {ao3_id} en tu listado de bookmarks...")
    try:
        for item in _walk_bookmark_items(client, username):
            if item.work_id == ao3_id:
                tags, bookmarked_at, nota = item.tags, item.bookmarked_at, item.nota
                print(f"  encontrado — tags: {tags}, nota: {'sí' if nota else 'no'}")
                break
        else:
            print("  no está bookmarkeado (o no lo encontré), lo importo sin nota/tags.")
    except (RequestFailedError, SessionRequestLimitReached, requests.exceptions.RequestException) as exc:
        print(f"  no pude terminar de buscarlo en bookmarks ({exc}), lo importo sin nota/tags.", file=sys.stderr)

    _ingest_fic(base_url, headers, cuenta_id, ao3_id, response.text, tags=tags, bookmarked_at=bookmarked_at, nota=nota)


def modo_epub(client: RateLimitedClient, base_url: str, headers: dict, cuenta_id: int, ao3_id: str) -> None:
    page_response = client.get(WORK_URL.format(ao3_id=ao3_id))
    page_response.raise_for_status()
    parsed = parse_work_page(page_response.text, ao3_id)
    if parsed.epub_url is None:
        print(f"AO3 no ofrece EPUB para el fic {ao3_id}.", file=sys.stderr)
        sys.exit(1)

    epub_response = client.get(parsed.epub_url)
    epub_response.raise_for_status()

    payload = {"ao3_id": ao3_id, "content_base64": base64.b64encode(epub_response.content).decode()}
    response = requests.post(
        f"{base_url}/api/sync/ingest-epub", json=payload, headers=headers, params={"cuenta_id": cuenta_id}, timeout=60
    )
    response.raise_for_status()
    print(f"  ingest-epub {ao3_id}: {response.json()}")


# Cuántos bookmarks YA conocidos seguidos hacen falta para que el modo
# rápido asuma "de acá para atrás es todo viejo" y corte — AO3 lista los
# bookmarks del más reciente al más viejo por defecto, así que una racha
# larga de conocidos sin cortes es buena señal de que no queda nada nuevo.
# Una página de bookmarks trae 20, así que esto es ~2 páginas de margen.
RAPIDO_CORTE_CONSECUTIVOS = 40


def modo_bookmarks(
    client: RateLimitedClient, base_url: str, headers: dict, cuenta_id: int, username: str, *, rapido: bool = False
) -> None:
    """Con rapido=True corta apenas ve una racha larga de bookmarks ya
    conocidos seguidos, en vez de recorrer TODAS las páginas siempre — mucho
    más rápido cuando lo único que cambió desde la última vez son un puñado
    de bookmarks nuevos. La contra: si editaste el tag/nota de un bookmark
    viejo (que ya quedó "atrás" en el listado), el modo rápido no se entera
    hasta que corras el sync completo."""
    response = requests.get(
        f"{base_url}/api/sync/known-ids", headers=headers, params={"cuenta_id": cuenta_id}, timeout=30
    )
    response.raise_for_status()
    conocidos = set(response.json()["ao3_ids"])
    print(f"Fics ya conocidos en Archivum: {len(conocidos)}")

    inicio = time.monotonic()
    start_page = 1
    progreso = {"pagina": start_page}
    nuevos = 0
    consecutivos_conocidos = 0
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
                            cuenta_id,
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
                            cuenta_id,
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

                if rapido:
                    consecutivos_conocidos = consecutivos_conocidos + 1 if ya_conocido else 0
                    if consecutivos_conocidos >= RAPIDO_CORTE_CONSECUTIVOS:
                        print(
                            f"Modo rápido: {consecutivos_conocidos} bookmarks conocidos seguidos, "
                            "asumo que ya no queda nada nuevo y corto acá."
                        )
                        break
            break  # terminó de recorrer todas las páginas, o cortó por rapido — ninguno es una falla
        except SessionRequestLimitReached as exc:
            print(f"Límite de sesión alcanzado: {exc}. Terminando esta corrida.")
            break
        except RequestFailedError as exc:
            transcurrido = time.monotonic() - inicio
            if transcurrido + ESPERA_ENTRE_REINTENTOS_SEGUNDOS > PRESUPUESTO_TOTAL_SEGUNDOS:
                print(f"AO3 sigue fallando y se acabó el presupuesto de tiempo: {exc}")
                break
            espera = ESPERA_ENTRE_REINTENTOS_SEGUNDOS + random.uniform(0, JITTER_REINTENTOS_SEGUNDOS)
            print(f"AO3 falló listando páginas ({exc}). Esperando {espera / 60:.1f} min antes de reintentar...")
            time.sleep(espera)
            # Reanudar desde la página donde se cortó (progreso["pagina"]),
            # no desde la 1: volver a pedir todas las páginas ya vistas cuesta
            # una petición rate-limitada c/u, y con AO3 fallando seguido eso
            # se come el presupuesto de tiempo antes de llegar a las páginas
            # nuevas — que es justo lo que hacía que algunos bookmarks (y sus
            # notas) nunca se terminaran de sincronizar.
            start_page = progreso["pagina"]
            continue

    print(f"Bookmarks nuevos importados: {nuevos}")


def _sync_listado_con_tag(
    client: RateLimitedClient,
    base_url: str,
    headers: dict,
    cuenta_id: int,
    username: str,
    *,
    url_template: str,
    parse_page,
    tag: str,
    etiqueta_log: str,
) -> None:
    """Recorre un listado de AO3 (Marked for Later, Suscripciones...) y le
    pone `tag` a cada fic encontrado en Archivum. A los ya conocidos solo se
    les agrega el tag (sin re-pedir la página); a los nuevos se los importa
    entero, igual que un bookmark nuevo. Compartido por modo_marcados y
    modo_suscripciones — misma forma de recorrer páginas, solo cambia de
    dónde vienen los work_ids y qué tag les pone."""
    response = requests.get(
        f"{base_url}/api/sync/known-ids", headers=headers, params={"cuenta_id": cuenta_id}, timeout=30
    )
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
                client, url_template, username, parse_page,
                start_page=start_page, progreso=progreso,
            ):
                try:
                    if work_id in conocidos:
                        _ingest_fic(base_url, headers, cuenta_id, work_id, tags=[tag])
                        etiquetados += 1
                    else:
                        fic_response = client.get(WORK_URL.format(ao3_id=work_id))
                        fic_response.raise_for_status()
                        _ingest_fic(base_url, headers, cuenta_id, work_id, fic_response.text, tags=[tag])
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
            espera = ESPERA_ENTRE_REINTENTOS_SEGUNDOS + random.uniform(0, JITTER_REINTENTOS_SEGUNDOS)
            print(f"AO3 falló listando páginas ({exc}). Esperando {espera / 60:.1f} min antes de reintentar...")
            time.sleep(espera)
            # Igual que en modo_bookmarks: reanudar desde progreso["pagina"]
            # en vez de la página 1, para no quemar el presupuesto de tiempo
            # re-pidiendo páginas de listado ya vistas.
            start_page = progreso["pagina"]
            continue

    print(f"{etiqueta_log} — nuevos importados: {nuevos}, ya conocidos etiquetados: {etiquetados}")


def modo_marcados(client: RateLimitedClient, base_url: str, headers: dict, cuenta_id: int, username: str) -> None:
    """Trae los work_ids marcados 'Marked for Later' (?show=to-read de la
    History) y los etiqueta en Archivum."""
    _sync_listado_con_tag(
        client, base_url, headers, cuenta_id, username,
        url_template=HISTORY_MARKED_URL, parse_page=parse_history_page,
        tag=TAG_MARCADOS, etiqueta_log="Marked for Later",
    )


def modo_suscripciones(client: RateLimitedClient, base_url: str, headers: dict, cuenta_id: int, username: str) -> None:
    """Trae los fics a los que estás suscripta en AO3 (aparte de bookmarks:
    podés suscribirte sin bookmarkear) y los etiqueta en Archivum. Al
    quedar en la biblioteca, "Revisar WIPs" también los va a chequear."""
    _sync_listado_con_tag(
        client, base_url, headers, cuenta_id, username,
        url_template=SUBSCRIPTIONS_URL, parse_page=parse_subscriptions_page,
        tag=TAG_SUSCRIPCIONES, etiqueta_log="Suscripciones",
    )


def modo_wips(client: RateLimitedClient, base_url: str, headers: dict, cuenta_id: int) -> None:
    """Vuelve a pedirle a AO3 los fics incompletos que hace rato no se
    revisan (ver /sync/incompletos), para que _detectar_novedades note si
    sumaron capítulo o se completaron. A diferencia de bookmarks/marcados no
    hay páginas de listado que recorrer — la lista ya viene de nuestra
    propia base — así que el único límite es el presupuesto de tiempo."""
    response = requests.get(
        f"{base_url}/api/sync/incompletos", headers=headers, params={"cuenta_id": cuenta_id}, timeout=30
    )
    response.raise_for_status()
    ids = response.json()["ao3_ids"]
    print(f"WIPs a revisar: {len(ids)}")

    inicio = time.monotonic()
    revisados = 0
    novedades = []
    for ao3_id in ids:
        if time.monotonic() - inicio > PRESUPUESTO_TOTAL_SEGUNDOS:
            print("Se acabó el presupuesto de tiempo para esta corrida, corto acá.")
            break
        try:
            fic_response = client.get(WORK_URL.format(ao3_id=ao3_id))
            fic_response.raise_for_status()
            resultado = _ingest_fic(base_url, headers, cuenta_id, ao3_id, fic_response.text)
            revisados += 1
            if resultado.get("novedades"):
                novedades.append(
                    {"ao3_id": ao3_id, "titulo": resultado.get("titulo") or ao3_id, "tipos": resultado["novedades"]}
                )
        except (RequestFailedError, requests.exceptions.RequestException) as exc:
            print(f"  ! {ao3_id}: {exc}", file=sys.stderr)

    print(f"WIPs revisados: {revisados}")
    if novedades:
        _notificar_novedades(base_url, headers, cuenta_id, novedades)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cuenta-id", required=True, type=int)
    parser.add_argument(
        "--modo",
        required=True,
        choices=["fic", "epub", "bookmarks", "bookmarks-rapido", "marcados", "suscripciones", "wips"],
    )
    parser.add_argument("--url", default=None)
    parser.add_argument("--ao3-id", default=None)
    args = parser.parse_args()

    base_url = _base_url()
    headers = _sync_headers()
    username, password, _email = _obtener_credenciales(base_url, headers, args.cuenta_id)
    client = _build_client()
    _login(client, username, password)

    if args.modo == "fic":
        if not args.url:
            print("--url es obligatorio para --modo fic", file=sys.stderr)
            sys.exit(1)
        modo_fic(client, base_url, headers, args.cuenta_id, username, args.url)
    elif args.modo == "epub":
        if not args.ao3_id:
            print("--ao3-id es obligatorio para --modo epub", file=sys.stderr)
            sys.exit(1)
        modo_epub(client, base_url, headers, args.cuenta_id, args.ao3_id)
    elif args.modo == "marcados":
        modo_marcados(client, base_url, headers, args.cuenta_id, username)
    elif args.modo == "suscripciones":
        modo_suscripciones(client, base_url, headers, args.cuenta_id, username)
    elif args.modo == "wips":
        modo_wips(client, base_url, headers, args.cuenta_id)
    elif args.modo == "bookmarks-rapido":
        modo_bookmarks(client, base_url, headers, args.cuenta_id, username, rapido=True)
    else:
        modo_bookmarks(client, base_url, headers, args.cuenta_id, username)


if __name__ == "__main__":
    main()
