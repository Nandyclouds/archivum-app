"""Cifra la contraseña de AO3 de cada cuenta antes de guardarla (ver
Cuenta.ao3_password_encriptada en app/control_models.py)."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException

from app.config import settings


def _fernet() -> Fernet:
    if not settings.archivum_encryption_key:
        raise HTTPException(
            status_code=503,
            detail="ARCHIVUM_ENCRYPTION_KEY no está configurado en el .env de este servidor.",
        )
    return Fernet(settings.archivum_encryption_key.encode())


def encriptar(texto: str) -> str:
    return _fernet().encrypt(texto.encode()).decode()


def desencriptar(cifrado: str) -> str:
    try:
        return _fernet().decrypt(cifrado.encode()).decode()
    except InvalidToken as exc:
        raise HTTPException(
            status_code=500, detail="No se pudo leer la contraseña de AO3 guardada."
        ) from exc
