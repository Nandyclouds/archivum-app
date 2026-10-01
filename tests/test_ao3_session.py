from pathlib import Path
from types import SimpleNamespace

import pytest
import responses
from cryptography.fernet import Fernet
from fastapi import HTTPException

from app.api import ao3_session
from app.crypto import encriptar

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _mock_login():
    responses.add(responses.GET, "https://archiveofourown.org/users/login", body=_read("login_page.html"), status=200)
    responses.add(responses.POST, "https://archiveofourown.org/users/login", status=302)


@pytest.fixture(autouse=True)
def _config_base(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ao3_contact_email", "test@example.com")
    monkeypatch.setattr(settings, "archivum_encryption_key", Fernet.generate_key().decode())


@responses.activate
def test_usa_las_credenciales_propias_de_la_cuenta(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "archivum_auth_token", "en-produccion")
    monkeypatch.setattr(settings, "ao3_username", "")
    monkeypatch.setattr(settings, "ao3_password", "")
    _mock_login()

    cuenta = SimpleNamespace(ao3_username="mi-usuario-ao3", ao3_password_encriptada=encriptar("mi-secreta"))
    ao3_session.build_authenticated_client(cuenta, sleep_fn=lambda s: None)

    post_request = responses.calls[1].request
    assert "user%5Blogin%5D=mi-usuario-ao3" in post_request.url


@responses.activate
def test_sin_login_real_cae_a_las_del_env(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "archivum_auth_token", "")
    monkeypatch.setattr(settings, "ao3_username", "usuaria-del-env")
    monkeypatch.setattr(settings, "ao3_password", "secreta-del-env")
    _mock_login()

    cuenta = SimpleNamespace(ao3_username=None, ao3_password_encriptada=None)
    ao3_session.build_authenticated_client(cuenta, sleep_fn=lambda s: None)

    post_request = responses.calls[1].request
    assert "user%5Blogin%5D=usuaria-del-env" in post_request.url


def test_cuenta_real_sin_credenciales_propias_no_usa_las_del_env(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "archivum_auth_token", "en-produccion")
    monkeypatch.setattr(settings, "ao3_username", "usuaria-del-env")
    monkeypatch.setattr(settings, "ao3_password", "secreta-del-env")

    cuenta = SimpleNamespace(ao3_username=None, ao3_password_encriptada=None)
    with pytest.raises(HTTPException) as exc:
        ao3_session.build_authenticated_client(cuenta, sleep_fn=lambda s: None)
    assert exc.value.status_code == 409
