"""Cliente AO3 autenticado, para endpoints que hacen UNA acción rápida
(importar un fic, bajar un EPUB) directo desde la app, sin terminal."""

from __future__ import annotations

from fastapi import HTTPException

from app.ao3 import auth
from app.ao3.client import RateLimitedClient
from app.config import settings


def build_authenticated_client(**overrides) -> RateLimitedClient:
    """`**overrides` existe para los tests (inyectar sleep_fn/time_fn falsos
    y no depender del reloj real ni del AO3_MIN_DELAY_SECONDS del .env)."""
    if not settings.ao3_contact_email:
        raise HTTPException(
            status_code=500,
            detail="AO3_CONTACT_EMAIL no está configurado en .env del servidor.",
        )
    kwargs = dict(
        contact_email=settings.ao3_contact_email,
        min_delay_seconds=settings.ao3_min_delay_seconds,
        max_requests_per_session=settings.ao3_max_requests_per_session,
    )
    kwargs.update(overrides)
    client = RateLimitedClient(**kwargs)
    try:
        auth.login(client, settings.ao3_username, settings.ao3_password)
    except auth.LoginError as exc:
        raise HTTPException(status_code=502, detail=f"No se pudo iniciar sesión en AO3: {exc}") from exc
    return client
