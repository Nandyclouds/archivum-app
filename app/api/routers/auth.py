from __future__ import annotations

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.auth import crear_sesion, get_cuenta_admin, get_cuenta_actual, hashear_password, hash_token, verificar_password
from app.config import settings
from app.control_db import get_control_session
from app.control_models import Cuenta, Invitacion, Sesion
from app.crypto import encriptar
from app.database import Base

router = APIRouter(prefix="/auth", tags=["auth"])


def _email_valido(v: str) -> str:
    v = v.strip().lower()
    if "@" not in v or v.startswith("@") or v.endswith("@"):
        raise ValueError("Email inválido.")
    return v


class RegistroRequest(BaseModel):
    email: str
    password: str
    codigo_invitacion: str

    _normalizar_email = field_validator("email")(_email_valido)


class LoginRequest(BaseModel):
    email: str
    password: str

    _normalizar_email = field_validator("email")(_email_valido)


def _crear_base_de_datos_nueva(cuenta_id: int) -> None:
    path = settings.user_db_path(cuenta_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    engine.dispose()


@router.post("/registro")
def registro(payload: RegistroRequest, db: Session = Depends(get_control_session)):
    if len(payload.password) < 8:
        raise HTTPException(status_code=422, detail="La contraseña tiene que tener al menos 8 caracteres.")
    if db.query(Cuenta).filter_by(email=payload.email).one_or_none():
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese email.")

    invitacion = db.query(Invitacion).filter_by(codigo=payload.codigo_invitacion).one_or_none()
    if invitacion is None or invitacion.usada_por_id is not None:
        raise HTTPException(status_code=422, detail="Código de invitación inválido o ya usado.")

    cuenta = Cuenta(email=payload.email, password_hash=hashear_password(payload.password))
    db.add(cuenta)
    db.flush()

    invitacion.usada_por_id = cuenta.id
    invitacion.usada_en = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(cuenta)

    _crear_base_de_datos_nueva(cuenta.id)

    token = crear_sesion(db, cuenta)
    return {"token": token, "email": cuenta.email, "es_admin": cuenta.es_admin}


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_control_session)):
    cuenta = db.query(Cuenta).filter_by(email=payload.email).one_or_none()
    if cuenta is None or not cuenta.activa or not verificar_password(payload.password, cuenta.password_hash):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos.")
    token = crear_sesion(db, cuenta)
    return {"token": token, "email": cuenta.email, "es_admin": cuenta.es_admin}


@router.post("/logout", status_code=204)
def logout(request: Request, db: Session = Depends(get_control_session)):
    token = request.headers.get("x-archivum-token") or request.query_params.get("token")
    if token:
        db.query(Sesion).filter_by(token_hash=hash_token(token)).delete()
        db.commit()


@router.get("/yo")
def yo(cuenta: Cuenta = Depends(get_cuenta_actual)):
    return {
        "email": cuenta.email,
        "es_admin": cuenta.es_admin,
        "ao3_username": getattr(cuenta, "ao3_username", None),
    }


class Ao3CredencialesUpdate(BaseModel):
    ao3_username: str
    ao3_password: str


@router.put("/ao3-credenciales")
def actualizar_ao3_credenciales(
    payload: Ao3CredencialesUpdate,
    db: Session = Depends(get_control_session),
    cuenta_actual: Cuenta = Depends(get_cuenta_actual),
):
    if not payload.ao3_username.strip() or not payload.ao3_password:
        raise HTTPException(status_code=422, detail="Faltan el usuario o la contraseña de AO3.")
    cuenta = db.get(Cuenta, cuenta_actual.id)
    if cuenta is None:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada.")
    cuenta.ao3_username = payload.ao3_username.strip()
    cuenta.ao3_password_encriptada = encriptar(payload.ao3_password)
    db.commit()
    return {"ao3_username": cuenta.ao3_username}


@router.delete("/ao3-credenciales", status_code=204)
def borrar_ao3_credenciales(
    db: Session = Depends(get_control_session), cuenta_actual: Cuenta = Depends(get_cuenta_actual)
):
    cuenta = db.get(Cuenta, cuenta_actual.id)
    if cuenta is None:
        return
    cuenta.ao3_username = None
    cuenta.ao3_password_encriptada = None
    db.commit()


@router.post("/invitaciones")
def crear_invitacion(db: Session = Depends(get_control_session), cuenta: Cuenta = Depends(get_cuenta_admin)):
    codigo = secrets.token_urlsafe(9)
    db.add(Invitacion(codigo=codigo, creada_por_id=cuenta.id))
    db.commit()
    return {"codigo": codigo}


@router.get("/invitaciones")
def listar_invitaciones(db: Session = Depends(get_control_session), cuenta: Cuenta = Depends(get_cuenta_admin)):
    invitaciones = db.query(Invitacion).order_by(Invitacion.creada_en.desc()).all()
    return [
        {
            "codigo": i.codigo,
            "creada_en": i.creada_en,
            "usada": i.usada_por_id is not None,
            "usada_por_email": i.usada_por.email if i.usada_por else None,
        }
        for i in invitaciones
    ]
