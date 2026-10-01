"""Login multi-cuenta: contraseñas con bcrypt, tokens de sesión opacos
(se guarda el hash, no el token en sí) y la dependencia que resuelve la
cuenta actual. El middleware de app/main.py ya deja la cuenta resuelta en
request.state.cuenta antes de que corra cualquier ruta."""

from __future__ import annotations

import hashlib
import secrets

import bcrypt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.control_models import Cuenta, Sesion


def hashear_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verificar_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def generar_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def crear_sesion(db: Session, cuenta: Cuenta) -> str:
    token = generar_token()
    db.add(Sesion(token_hash=hash_token(token), cuenta_id=cuenta.id))
    db.commit()
    return token


def resolver_cuenta_por_token(db: Session, token: str | None) -> Cuenta | None:
    if not token:
        return None
    sesion = db.query(Sesion).filter_by(token_hash=hash_token(token)).one_or_none()
    if sesion is None:
        return None
    cuenta = db.get(Cuenta, sesion.cuenta_id)
    if cuenta is None or not cuenta.activa:
        return None
    return cuenta


def get_cuenta_actual(request: Request) -> Cuenta:
    cuenta = getattr(request.state, "cuenta", None)
    if cuenta is None:
        raise HTTPException(status_code=401, detail="No autorizado")
    return cuenta


def get_cuenta_admin(cuenta: Cuenta = Depends(get_cuenta_actual)) -> Cuenta:
    if not cuenta.es_admin:
        raise HTTPException(status_code=403, detail="Solo una cuenta administradora puede hacer esto.")
    return cuenta
