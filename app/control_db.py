"""Base de datos de control: cuentas, invitaciones y sesiones — separada de
la base de datos de cada usuaria (ver app/database.py), que vive en su
propio archivo por cuenta."""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

settings.control_db_path.parent.mkdir(parents=True, exist_ok=True)

control_engine = create_engine(
    f"sqlite:///{settings.control_db_path}",
    connect_args={"check_same_thread": False},
)

ControlSessionLocal = sessionmaker(bind=control_engine, autoflush=False, autocommit=False)


class ControlBase(DeclarativeBase):
    pass


def get_control_session():
    session = ControlSessionLocal()
    try:
        yield session
    finally:
        session.close()
