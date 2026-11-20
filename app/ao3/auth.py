"""Login a AO3 usando la sesión rate-limitada."""

from __future__ import annotations

from app.ao3.client import RateLimitedClient
from app.ao3.parser import extract_authenticity_token

LOGIN_URL = "https://archiveofourown.org/users/login"
HOME_URL = "https://archiveofourown.org/"

# Cookie de sesión de Rails que usa AO3 — es lo único que hace falta para
# que el cliente quede "logueado" sin pasar por el POST de /users/login.
SESSION_COOKIE_NAME = "_otwarchive_session"

# Marcador de que la cookie sirvió: el header de AO3 trae este link solo
# cuando hay una sesión logueada válida (si la cookie venció, o si justo esa
# página está detrás de un desafío anti-bot como "Shields are up!", este
# link no aparece).
_MARCADOR_LOGUEADA = "/users/logout"


class LoginError(Exception):
    pass


def login(client: RateLimitedClient, username: str, password: str) -> None:
    if not username or not password:
        raise LoginError(
            "Faltan AO3_USERNAME/AO3_PASSWORD. Completalos en .env (nunca los "
            "hardcodees en el código)."
        )

    login_page = client.get(LOGIN_URL)
    token = extract_authenticity_token(login_page.text)
    if token is None:
        snippet = login_page.text[:500].replace("\n", " ")
        raise LoginError(
            "No se encontró el authenticity_token en la página de login de AO3.\n"
            f"  status_code: {login_page.status_code}\n"
            f"  primeros 500 caracteres de la respuesta:\n  {snippet}"
        )

    response = client.post(
        LOGIN_URL,
        params={
            "user[login]": username,
            "user[password]": password,
            "authenticity_token": token,
        },
        allow_redirects=False,
    )
    if response.status_code != 302:
        snippet = response.text[:500].replace("\n", " ")
        raise LoginError(
            "Usuario o contraseña de AO3 inválidos (o AO3 devolvió algo "
            "inesperado).\n"
            f"  status_code: {response.status_code}\n"
            f"  primeros 500 caracteres de la respuesta:\n  {snippet}"
        )


def login_with_cookie(client: RateLimitedClient, session_cookie: str) -> None:
    """Alternativa a login() cuando el POST a /users/login está bloqueado
    (ej. AO3 puso un desafío anti-bot tipo "Shields are up!" justo en esa
    página): en vez de loguearse con usuario/contraseña, reusa la cookie de
    sesión de un login ya hecho a mano en un navegador de verdad (que sí
    puede resolver ese desafío). La cookie vence — cuando eso pase, hay que
    volver a copiarla."""
    if not session_cookie:
        raise LoginError(
            "Falta AO3_SESSION_COOKIE. Completala en .env con el valor de la "
            f"cookie '{SESSION_COOKIE_NAME}' de tu navegador, después de "
            "loguearte en AO3 ahí."
        )

    client.http_session.cookies.set(SESSION_COOKIE_NAME, session_cookie, domain="archiveofourown.org")

    response = client.get(HOME_URL)
    if _MARCADOR_LOGUEADA not in response.text:
        raise LoginError(
            "La cookie de sesión de AO3 no sirvió (venció, está mal copiada, "
            "o AO3 está bloqueando la página). Volvé a loguearte en tu "
            f"navegador y pegá la cookie '{SESSION_COOKIE_NAME}' de nuevo.\n"
            f"  status_code: {response.status_code}"
        )
