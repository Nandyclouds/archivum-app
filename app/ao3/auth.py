"""Login a AO3 usando la sesión rate-limitada."""

from __future__ import annotations

from app.ao3.client import RateLimitedClient
from app.ao3.parser import extract_authenticity_token

LOGIN_URL = "https://archiveofourown.org/users/login"


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
