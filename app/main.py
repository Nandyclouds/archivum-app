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

from app.api.routers import ao3_import, archivos, colecciones, etiquetas, fics, import_log, stats
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

# Rutas /api que no piden token: health check (para monitoreo) y nada más.
_RUTAS_PUBLICAS = {"/api/health"}


@app.middleware("http")
async def exigir_token(request: Request, call_next):
    """Si ARCHIVUM_AUTH_TOKEN está seteado, todo /api/* lo exige.

    Vacío (default local) = sin auth, como antes. Se pone un valor real en
    cuanto la app se expone en un dominio público (PythonAnywhere) — ahí sí
    cualquiera con la URL podría leer/escribir en la biblioteca sin esto.

    Acepta el token por header (llamadas normales del frontend) o por query
    param `?token=` (el link de "ver copia archivada" se abre directo en el
    navegador/otra app, sin forma de mandar headers custom).
    """
    if settings.archivum_auth_token and request.url.path.startswith("/api"):
        # El preflight de CORS nunca lleva headers custom (el navegador lo
        # arma solo) — dejarlo pasar para que CORSMiddleware lo responda, o
        # el browser nunca llega a mandar la petición real con el token.
        if request.method != "OPTIONS" and request.url.path not in _RUTAS_PUBLICAS:
            token = request.headers.get("x-archivum-token") or request.query_params.get("token")
            if token != settings.archivum_auth_token:
                return JSONResponse({"detail": "No autorizado"}, status_code=401)
    return await call_next(request)

app.include_router(fics.router, prefix="/api")
app.include_router(colecciones.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
app.include_router(archivos.router, prefix="/api")
app.include_router(import_log.router, prefix="/api")
app.include_router(ao3_import.router, prefix="/api")
app.include_router(etiquetas.router, prefix="/api")


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
