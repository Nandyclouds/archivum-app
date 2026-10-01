from fastapi import Request
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


def _enable_sqlite_foreign_keys(dbapi_connection, _):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# Un engine por cuenta, creado la primera vez que se la usa y reusado
# después — cada cuenta tiene su propio archivo SQLite (ver
# settings.user_db_path), así que no hay forma de que una consulta vea
# datos de otra cuenta por error de filtro: son bases de datos distintas.
_engines_por_cuenta: dict[int, Engine] = {}


def _engine_para_cuenta(cuenta_id: int) -> Engine:
    if cuenta_id not in _engines_por_cuenta:
        path = settings.user_db_path(cuenta_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
        # El registro (ver app/api/routers/auth.py) ya crea las tablas al
        # crear la cuenta, pero esto cubre también la cuenta 1 en modo sin
        # login (ARCHIVUM_AUTH_TOKEN vacío), que nunca pasa por /auth/registro.
        Base.metadata.create_all(engine)
        _engines_por_cuenta[cuenta_id] = engine
    return _engines_por_cuenta[cuenta_id]


def get_session(request: Request):
    """La cuenta actual la deja request.state.cuenta el middleware de
    auth (ver app/main.py) antes de que corra cualquier dependencia de
    ruta — acá solo se usa para elegir el archivo de base de datos."""
    engine = _engine_para_cuenta(request.state.cuenta.id)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def nueva_sesion_para_cuenta(cuenta_id: int) -> Session:
    """Para código que no puede usar Depends(get_session) — las tareas de
    sync en segundo plano (ver app/api/routers/sync.py) corren DESPUÉS de
    que la respuesta ya se mandó, así que no pueden reusar la sesión de la
    request (esa ya se cerró)."""
    engine = _engine_para_cuenta(cuenta_id)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


# Para app/cli.py (herramienta de desarrollo local, sin cuentas): mismo
# engine de siempre, apuntado a settings.db_path, sin pasar por el
# enrutamiento por cuenta de get_session.
settings.db_path.parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(settings.sqlalchemy_database_url, connect_args={"check_same_thread": False})
event.listen(engine, "connect", _enable_sqlite_foreign_keys)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
