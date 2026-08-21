"""Cliente HTTP hacia AO3 con rate limiting estricto.

Este es el único punto por el que pasan las peticiones a AO3 en todo el
proyecto. Nada más en la app debe usar `requests` directamente contra AO3:
así el límite de velocidad, el backoff y el User-Agent quedan garantizados
en un solo lugar, auditable, en vez de depender de que cada llamador se
acuerde de respetarlos.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import requests

APP_VERSION = "0.1.0"

# 429/503 son rate limiting explícito. 520-527 son errores de Cloudflare
# (el proxy de AO3 no logra hablar con su propio servidor de origen) — en la
# práctica salen seguido y casi siempre se resuelven solos con un reintento
# a los pocos segundos, así que se tratan igual que un rate limit temporal.
RETRIABLE_STATUS_CODES = {429, 503, 520, 521, 522, 523, 524, 525, 526, 527}


class SessionRequestLimitReached(Exception):
    """Se alcanzó el máximo de peticiones configurado para esta sesión."""


class RequestFailedError(Exception):
    """AO3 siguió fallando (429/503/5xx de Cloudflare, o timeouts) después de agotar los reintentos."""


@dataclass
class RateLimitedClient:
    contact_email: str
    min_delay_seconds: float = 4.0
    max_requests_per_session: int = 500
    max_backoff_retries: int = 6
    backoff_base_seconds: float = 2.0
    timeout_seconds: float = 30.0

    # Inyectables para tests: evitan esperas reales de segundos/horas.
    sleep_fn: callable = field(default=time.sleep)
    time_fn: callable = field(default=time.monotonic)
    http_session: requests.Session | None = None

    def __post_init__(self):
        if not self.contact_email:
            raise ValueError(
                "contact_email es obligatorio: AO3 requiere un User-Agent "
                "identificable para no tratarte como bot."
            )
        if self.http_session is None:
            self.http_session = requests.Session()
        self.http_session.headers["User-Agent"] = (
            f"archivum-importer/{APP_VERSION} "
            f"(uso personal, no comercial; contacto: {self.contact_email})"
        )
        self.request_count = 0
        self._last_request_at: float | None = None

    def get(self, url: str, **kwargs) -> requests.Response:
        return self._request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response:
        return self._request("POST", url, **kwargs)

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        attempt = 0
        while True:
            self._enforce_session_limit()
            self._wait_min_delay()

            self.request_count += 1
            self._last_request_at = self.time_fn()
            try:
                response = self.http_session.request(
                    method, url, timeout=self.timeout_seconds, **kwargs
                )
            except requests.exceptions.RequestException as exc:
                if attempt >= self.max_backoff_retries:
                    raise RequestFailedError(
                        f"Fallo de red persistente tras {self.max_backoff_retries} "
                        f"reintentos: {url} ({exc})"
                    ) from exc
                self._backoff_sleep(attempt)
                attempt += 1
                continue

            if response.status_code in RETRIABLE_STATUS_CODES:
                if attempt >= self.max_backoff_retries:
                    raise RequestFailedError(
                        f"AO3 sigue devolviendo {response.status_code} tras "
                        f"{self.max_backoff_retries} reintentos: {url}"
                    )
                self._backoff_sleep(attempt)
                attempt += 1
                continue

            return response

    def _backoff_sleep(self, attempt: int) -> None:
        wait = max(self.backoff_base_seconds * (2**attempt), self.min_delay_seconds)
        self.sleep_fn(wait)

    def _enforce_session_limit(self) -> None:
        if self.request_count >= self.max_requests_per_session:
            raise SessionRequestLimitReached(
                f"Se alcanzó el límite de {self.max_requests_per_session} "
                "peticiones para esta sesión. Volvé a correr el comando "
                "para continuar donde quedó (los fics ya importados no se "
                "vuelven a pedir)."
            )

    def _wait_min_delay(self) -> None:
        if self._last_request_at is None:
            return
        elapsed = self.time_fn() - self._last_request_at
        remaining = self.min_delay_seconds - elapsed
        if remaining > 0:
            self.sleep_fn(remaining)
