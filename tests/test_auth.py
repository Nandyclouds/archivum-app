from pathlib import Path

import pytest
import responses

from app.ao3 import auth
from app.ao3.client import RateLimitedClient

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture()
def client():
    return RateLimitedClient(contact_email="test@example.com", min_delay_seconds=0, sleep_fn=lambda s: None)


@responses.activate
def test_login_exitoso(client):
    responses.add(responses.GET, auth.LOGIN_URL, body=_read("login_page.html"), status=200)
    responses.add(responses.POST, auth.LOGIN_URL, status=302)

    auth.login(client, "lunaescribe", "supersecreta")  # no debe levantar excepción

    post_request = responses.calls[1].request
    assert "user%5Blogin%5D=lunaescribe" in post_request.url or "user[login]=lunaescribe" in post_request.url


@responses.activate
def test_login_credenciales_invalidas(client):
    responses.add(responses.GET, auth.LOGIN_URL, body=_read("login_page.html"), status=200)
    responses.add(responses.POST, auth.LOGIN_URL, status=200)  # sin redirect 302 = fallo

    with pytest.raises(auth.LoginError):
        auth.login(client, "lunaescribe", "mal")


def test_login_sin_credenciales(client):
    with pytest.raises(auth.LoginError):
        auth.login(client, "", "")


@responses.activate
def test_login_con_cookie_exitoso(client):
    responses.add(responses.GET, auth.HOME_URL, body='<a href="/users/logout">Log Out</a>', status=200)

    auth.login_with_cookie(client, "una-cookie-valida")  # no debe levantar excepción

    assert client.http_session.cookies.get(auth.SESSION_COOKIE_NAME) == "una-cookie-valida"


@responses.activate
def test_login_con_cookie_vencida(client):
    responses.add(responses.GET, auth.HOME_URL, body='<a href="/users/login">Log In</a>', status=200)

    with pytest.raises(auth.LoginError):
        auth.login_with_cookie(client, "una-cookie-vencida")


def test_login_con_cookie_vacia(client):
    with pytest.raises(auth.LoginError):
        auth.login_with_cookie(client, "")
