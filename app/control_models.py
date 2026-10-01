"""Modelos de la base de control (ver app/control_db.py): quién puede
entrar, no qué hay en su biblioteca."""

import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.control_db import ControlBase


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class Cuenta(ControlBase):
    __tablename__ = "cuentas"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    es_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow)

    # Credenciales de AO3 (etapa 2): ao3_password queda encriptada, nunca en
    # texto plano. Ninguna de las dos es obligatoria para tener cuenta.
    ao3_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ao3_password_encriptada: Mapped[str | None] = mapped_column(String(500), nullable=True)


class Invitacion(ControlBase):
    __tablename__ = "invitaciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    creada_por_id: Mapped[int] = mapped_column(ForeignKey("cuentas.id"))
    usada_por_id: Mapped[int | None] = mapped_column(ForeignKey("cuentas.id"), nullable=True)
    creada_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow)
    usada_en: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)

    creada_por: Mapped[Cuenta] = relationship(foreign_keys=[creada_por_id])
    usada_por: Mapped[Cuenta | None] = relationship(foreign_keys=[usada_por_id])


class Sesion(ControlBase):
    __tablename__ = "sesiones"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    cuenta_id: Mapped[int] = mapped_column(ForeignKey("cuentas.id"))
    creada_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow)

    cuenta: Mapped[Cuenta] = relationship()
