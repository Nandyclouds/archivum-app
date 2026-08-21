import pytest
import responses
from requests.exceptions import ConnectionError as RequestsConnectionError

from app.ao3.client import RateLimitedClient, RequestFailedError, SessionRequestLimitReached


class FakeClock:
    """Reloj falso: cada sleep() avanza el tiempo en vez de bloquear el test."""

    def __init__(self):
        self.now = 0.0
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture()
def clock():
    return FakeClock()


def make_client(clock, **overrides):
    kwargs = dict(
        contact_email="test@example.com",
        min_delay_seconds=4.0,
        max_requests_per_session=500,
        max_backoff_retries=6,
        backoff_base_seconds=2.0,
        sleep_fn=clock.sleep,
        time_fn=clock.time,
    )
    kwargs.update(overrides)
    return RateLimitedClient(**kwargs)


def test_user_agent_incluye_contacto(clock):
    client = make_client(clock)
    assert "test@example.com" in client.http_session.headers["User-Agent"]


def test_contact_email_obligatorio(clock):
    with pytest.raises(ValueError):
        make_client(clock, contact_email="")


@responses.activate
def test_respeta_delay_minimo_entre_peticiones(clock):
    responses.add(responses.GET, "https://example.com/a", status=200)
    responses.add(responses.GET, "https://example.com/b", status=200)

    client = make_client(clock)
    client.get("https://example.com/a")
    client.get("https://example.com/b")

    assert clock.sleeps == [4.0]


@responses.activate
def test_no_espera_antes_de_la_primera_peticion(clock):
    responses.add(responses.GET, "https://example.com/a", status=200)
    client = make_client(clock)
    client.get("https://example.com/a")
    assert clock.sleeps == []


@responses.activate
def test_backoff_exponencial_en_429(clock):
    responses.add(responses.GET, "https://example.com/x", status=429)
    responses.add(responses.GET, "https://example.com/x", status=429)
    responses.add(responses.GET, "https://example.com/x", status=200)

    client = make_client(clock, backoff_base_seconds=2.0, min_delay_seconds=1.0)
    resp = client.get("https://example.com/x")

    assert resp.status_code == 200
    # primer retry: max(2*2^0, 1) = 2 ; segundo retry: max(2*2^1, 1) = 4
    assert clock.sleeps == [2.0, 4.0]


@responses.activate
def test_backoff_respeta_el_piso_del_delay_minimo(clock):
    responses.add(responses.GET, "https://example.com/x", status=503)
    responses.add(responses.GET, "https://example.com/x", status=200)

    client = make_client(clock, backoff_base_seconds=0.1, min_delay_seconds=4.0)
    client.get("https://example.com/x")

    assert clock.sleeps == [4.0]


@responses.activate
def test_agota_reintentos_y_levanta_excepcion(clock):
    for _ in range(4):
        responses.add(responses.GET, "https://example.com/x", status=429)

    client = make_client(clock, max_backoff_retries=3, backoff_base_seconds=0.01, min_delay_seconds=0.01)
    with pytest.raises(RequestFailedError):
        client.get("https://example.com/x")


@responses.activate
def test_reintenta_errores_5xx_de_cloudflare(clock):
    responses.add(responses.GET, "https://example.com/x", status=525)
    responses.add(responses.GET, "https://example.com/x", status=200)

    client = make_client(clock, backoff_base_seconds=0.01, min_delay_seconds=0.01)
    resp = client.get("https://example.com/x")

    assert resp.status_code == 200


@responses.activate
def test_reintenta_timeouts_y_errores_de_conexion(clock):
    responses.add(responses.GET, "https://example.com/x", body=RequestsConnectionError("boom"))
    responses.add(responses.GET, "https://example.com/x", status=200)

    client = make_client(clock, backoff_base_seconds=0.01, min_delay_seconds=0.01)
    resp = client.get("https://example.com/x")

    assert resp.status_code == 200


@responses.activate
def test_agota_reintentos_de_conexion_y_levanta_excepcion(clock):
    for _ in range(4):
        responses.add(responses.GET, "https://example.com/x", body=RequestsConnectionError("boom"))

    client = make_client(clock, max_backoff_retries=3, backoff_base_seconds=0.01, min_delay_seconds=0.01)
    with pytest.raises(RequestFailedError):
        client.get("https://example.com/x")


@responses.activate
def test_limite_de_peticiones_por_sesion(clock):
    responses.add(responses.GET, "https://example.com/a", status=200)
    client = make_client(clock, max_requests_per_session=1)
    client.get("https://example.com/a")
    with pytest.raises(SessionRequestLimitReached):
        client.get("https://example.com/b")
