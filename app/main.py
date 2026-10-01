"""App FastAPI.

Dev (con hot-reload del backend, frontend aparte con `npm run dev`):
    uvicorn app.main:app --reload

Para usar desde el celular (Tailscale/misma WiFi), servir todo desde acá:
    1. cd frontend && npm run build
    2. uvicorn app.main:app --host 0.0.0.0 --port 8000
    3. entrar desde el celular a http://<tu-ip-o-nombre-tailscale>:8000

Toda la API vive bajo /api — a propósito, para que nunca colisione con una
ruta de React Router. Sin el prefijo, /fics/14 sería AMBIGUO: ¿la pantalla
del fic en el frontend, o el endpoint JSON del backend? Con rutas de backend
registradas antes que el catch-all del SPA, el backend siempre ganaba, así
que entrar directo a /fics/14 (recargar la página, o Android reabriendo la
app en esa URL) mostraba el JSON crudo en vez de la app. Bug real.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routers import (
    ao3_import,
    archivos,
    auth,
    colecciones,
    emojis,
    etiquetas,
    fics,
    import_log,
    masivo,
    novedades,
    perfil,
    recomendaciones,
    stats,
    sync,
)
from app.auth import resolver_cuenta_por_token
from app.config import settings
from app.control_db import ControlBase, ControlSessionLocal, control_engine
from app.control_models import Cuenta, Invitacion, Sesion  # noqa: F401 — registran las tablas en ControlBase

app = FastAPI(title="Archivum API", version="0.1.0")

# Tablas de cuentas/invitaciones/sesiones: esquema chico y estable, sin
# migraciones propias por ahora (a diferencia de la base de cada cuenta,
# que sí usa Alembic — ver migrations/).
ControlBase.metadata.create_all(control_engine)

# CORS abierto a propósito: el control de acceso real es el login (ver
# abajo), no CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cuenta fija que se usa cuando no hay login real (ver más abajo) — mismo
# comportamiento que tenía el ARCHIVUM_AUTH_TOKEN vacío antes de que
# existieran las cuentas: todo pega contra una única biblioteca.
_CUENTA_UNICA = SimpleNamespace(
    id=1, es_admin=True, email="cuenta-unica@archivum.local", ao3_username=None, ao3_password_encriptada=None
)

# Rutas /api que no piden ningún token: health check, y login/registro (que
# por definición corren antes de tener una sesión).
_RUTAS_PUBLICAS = {"/api/health", "/api/auth/login", "/api/auth/registro"}

# Rutas que habla el workflow de GitHub Actions (nunca el frontend): piden
# ARCHIVUM_SYNC_SECRET por header en vez del token de usuario. Ver
# app/api/routers/sync.py. Hasta que el sync sea multi-cuenta, siempre
# sincronizan la cuenta 1.
_RUTAS_SYNC = {"/api/sync/known-ids", "/api/sync/ingest-fic", "/api/sync/ingest-epub", "/api/sync/incompletos"}


@app.middleware("http")
async def exigir_token(request: Request, call_next):
    """Controla acceso a /api/* y deja la cuenta resuelta en
    request.state.cuenta para el resto de las dependencias (ver
    app/database.py, app/auth.py).

    ARCHIVUM_AUTH_TOKEN vacío (default local/tests) = sin login real, todo
    pega contra la misma cuenta única — así sigue funcionando el desarrollo
    local y la suite de tests sin tocarlos. Con un valor puesto (producción),
    el token tiene que resolver a una sesión real creada por /auth/login o
    /auth/registro.

    Acepta el token por header (llamadas normales del frontend) o por query
    param `?token=` (el link de "ver copia archivada" se abre directo en el
    navegador/otra app, sin forma de mandar headers custom).
    """
    path = request.url.path
    if request.method == "OPTIONS" or not path.startswith("/api") or path in _RUTAS_PUBLICAS:
        return await call_next(request)

    # Una lista de recomendaciones puntual (/api/recomendaciones/<token>) es
    # pública a propósito: es un link para mandarle a alguien que no tiene
    # (ni debería necesitar) una cuenta. Sin el trailing slash no matchea
    # /api/recomendaciones (el listado completo, ese sí pide login).
    if (
        request.method == "GET"
        and path.startswith("/api/recomendaciones/")
        and path != "/api/recomendaciones/"
    ):
        return await call_next(request)

    if path in _RUTAS_SYNC:
        secret = request.headers.get("x-sync-secret")
        if not settings.archivum_sync_secret or secret != settings.archivum_sync_secret:
            return JSONResponse({"detail": "No autorizado"}, status_code=401)
        request.state.cuenta = _CUENTA_UNICA
        return await call_next(request)

    if not settings.archivum_auth_token:
        request.state.cuenta = _CUENTA_UNICA
        return await call_next(request)

    token = request.headers.get("x-archivum-token") or request.query_params.get("token")
    with ControlSessionLocal() as db:
        cuenta = resolver_cuenta_por_token(db, token)
    if cuenta is None:
        return JSONResponse({"detail": "No autorizado"}, status_code=401)
    request.state.cuenta = cuenta
    return await call_next(request)


@app.middleware("http")
async def sin_cache_en_api(request: Request, call_next):
    """Evita que el navegador (sobre todo Chrome en Android) sirva una
    respuesta de /api vieja desde su caché HTTP para la misma URL, en vez de
    pedirla de nuevo — causaba que stats/gráficos mostraran datos que ya
    habían cambiado en el server hasta hacer un hard refresh.
    """
    response = await call_next(request)
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store"
    return response

app.include_router(fics.router, prefix="/api")
app.include_router(colecciones.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
app.include_router(archivos.router, prefix="/api")
app.include_router(import_log.router, prefix="/api")
app.include_router(ao3_import.router, prefix="/api")
app.include_router(etiquetas.router, prefix="/api")
app.include_router(sync.router, prefix="/api")
app.include_router(perfil.router, prefix="/api")
app.include_router(novedades.router, prefix="/api")
app.include_router(recomendaciones.router, prefix="/api")
app.include_router(emojis.router, prefix="/api")
app.include_router(masivo.router, prefix="/api")
app.include_router(auth.router, prefix="/api")


@app.get("/api/health", tags=["health"])
def health():
    return {"status": "ok"}


FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets")

    # Catch-all al final: cualquier ruta que no sea /api ni un asset conocido
    # (manifest, iconos, service worker) cae a index.html para que React
    # Router la resuelva del lado del cliente. Tiene que ser la ÚLTIMA ruta
    # registrada — si no, se comería las rutas de la API.
    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        candidato = FRONTEND_DIST / full_path
        if full_path and candidato.is_file():
            return FileResponse(candidato)
        return FileResponse(FRONTEND_DIST / "index.html")
