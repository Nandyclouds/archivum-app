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

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routers import (
    ao3_import,
    archivos,
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
from app.config import settings

app = FastAPI(title="Archivum API", version="0.1.0")

# CORS abierto a propósito: esta app es para un máximo de 3 personas, cada
# una con su propia copia (ver Tarea 1), sin cuentas/registro. El control de
# acceso real es ARCHIVUM_AUTH_TOKEN (ver abajo), no CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rutas /api que no piden ningún token: solo el health check (monitoreo).
_RUTAS_PUBLICAS = {"/api/health"}

# Rutas que habla el workflow de GitHub Actions (nunca el frontend): piden
# ARCHIVUM_SYNC_SECRET por header en vez del token de usuario. Ver
# app/api/routers/sync.py — mandan de vuelta lo que scrapearon de AO3 desde
# una máquina que sí tiene salida a internet, a diferencia de PythonAnywhere.
_RUTAS_SYNC = {"/api/sync/known-ids", "/api/sync/ingest-fic", "/api/sync/ingest-epub", "/api/sync/incompletos"}


@app.middleware("http")
async def exigir_token(request: Request, call_next):
    """Controla acceso a /api/*: token de usuario, o secreto de sync para GH Actions.

    ARCHIVUM_AUTH_TOKEN vacío (default local) = sin auth en rutas normales,
    como antes. Se pone un valor real en cuanto la app se expone en un
    dominio público (PythonAnywhere) — ahí sí cualquiera con la URL podría
    leer/escribir en la biblioteca sin esto.

    Acepta el token por header (llamadas normales del frontend) o por query
    param `?token=` (el link de "ver copia archivada" se abre directo en el
    navegador/otra app, sin forma de mandar headers custom).

    Las rutas de sync son distintas: a diferencia del token de usuario, acá
    NO hay default abierto — si ARCHIVUM_SYNC_SECRET no está seteado, esas
    rutas quedan inaccesibles (fail-closed), porque son de escritura y las
    habla una máquina, no una persona con el código de acceso.
    """
    path = request.url.path
    if request.method == "OPTIONS" or not path.startswith("/api") or path in _RUTAS_PUBLICAS:
        return await call_next(request)

    # Una lista de recomendaciones puntual (/api/recomendaciones/<token>) es
    # pública a propósito: es un link para mandarle a alguien que no tiene
    # (ni debería necesitar) el token de acceso a la app. Sin el trailing
    # slash no matchea /api/recomendaciones (el listado completo, ese sí
    # pide el token normal, más abajo).
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
        return await call_next(request)

    if settings.archivum_auth_token:
        token = request.headers.get("x-archivum-token") or request.query_params.get("token")
        if token != settings.archivum_auth_token:
            return JSONResponse({"detail": "No autorizado"}, status_code=401)
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
