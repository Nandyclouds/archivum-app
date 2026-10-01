import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException

from app import crypto


@pytest.fixture(autouse=True)
def _clave_de_prueba(monkeypatch):
    monkeypatch.setattr(crypto.settings, "archivum_encryption_key", Fernet.generate_key().decode())


def test_encriptar_y_desencriptar_da_el_mismo_texto():
    cifrado = crypto.encriptar("mi-contraseña-de-ao3")
    assert cifrado != "mi-contraseña-de-ao3"
    assert crypto.desencriptar(cifrado) == "mi-contraseña-de-ao3"


def test_sin_clave_configurada_levanta_error(monkeypatch):
    monkeypatch.setattr(crypto.settings, "archivum_encryption_key", "")
    with pytest.raises(HTTPException) as exc:
        crypto.encriptar("algo")
    assert exc.value.status_code == 503


def test_desencriptar_algo_invalido_levanta_error():
    with pytest.raises(HTTPException) as exc:
        crypto.desencriptar("no-es-un-token-fernet-valido")
    assert exc.value.status_code == 500
