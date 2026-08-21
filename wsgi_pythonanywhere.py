"""Adaptador para PythonAnywhere (gratis solo corre WSGI; la app es ASGI).

En el tab "Web" de PythonAnywhere, configurar el "WSGI configuration file"
para que importe `application` desde acá:

    import sys
    path = '/home/tu-usuario/archivum-app'
    if path not in sys.path:
        sys.path.append(path)
    from wsgi_pythonanywhere import application

No correr esto localmente — para desarrollo normal seguí usando
`uvicorn app.main:app --reload`, que es más rápido y no necesita a2wsgi.
"""

from a2wsgi import ASGIMiddleware

from app.main import app as _asgi_app

application = ASGIMiddleware(_asgi_app)
