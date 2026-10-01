"""Cliente AO3 autenticado, para endpoints que hacen UNA acción rápida
(importar un fic, bajar un EPUB) directo desde la app, sin terminal."""

from __future__ import annotations

from fastapi import HTTPException

from app.ao3 import auth
from app.ao3.client import RateLimitedClient
from app.config import settings
from app.crypto import desencriptar


def resolver_credenciales_ao3(cuenta) -> tuple[str, str]:
    """Usuario/contraseña de AO3 efectivos para esta cuenta: los que
    configuró en Ajustes si los tiene, o los del .env si el servidor corre
    sin login real (ARCHIVUM_AUTH_TOKEN vacío) — nunca los del .env si hay
    cuentas reales, para no mezclar la sesión de AO3 de una cuenta con la
    de otra."""
    username = getattr(cuenta, "ao3_username", None)
    password_encriptada = getattr(cuenta, "ao3_password_encriptada", None)
    if username and password_encriptada:
        return username, desencriptar(password_encriptada)
    if not settings.archivum_auth_token:
        return settings.ao3_username, settings.ao3_password
    raise HTTPException(status_code=409, detail="Todavía no configuraste tus credenciales de AO3 en Ajustes.")


def build_authenticated_client(cuenta, **overrides) -> RateLimitedClient:
    """`**overrides` existe para los tests (inyectar sleep_fn/time_fn falsos
    y no depender del reloj real ni del AO3_MIN_DELAY_SECONDS del .env)."""
    if not settings.ao3_contact_email:
        raise HTTPException(
            status_code=500,
            detail="AO3_CONTACT_EMAIL no está configurado en .env del servidor.",
        )

    username, password = resolver_credenciales_ao3(cuenta)

    kwargs = dict(
        contact_email=settings.ao3_contact_email,
        min_delay_seconds=settings.ao3_min_delay_seconds,
        max_requests_per_session=settings.ao3_max_requests_per_session,
    )
    kwargs.update(overrides)
    client = RateLimitedClient(**kwargs)
    try:
        auth.login(client, username, password)
    except auth.LoginError as exc:
        raise HTTPException(status_code=502, detail=f"No se pudo iniciar sesión en AO3: {exc}") from exc
    return client
