from types import SimpleNamespace

import httpx
import pytest

from app.data import openaq


def configure(monkeypatch):
    monkeypatch.setattr(
        openaq, "get_settings", lambda: SimpleNamespace(provider_retries=1)
    )
    monkeypatch.setattr(openaq.time, "sleep", lambda _: None)


def test_transient_connection_failure_is_retried(monkeypatch):
    configure(monkeypatch)
    attempts = []

    def handler(req):
        attempts.append(req)
        if len(attempts) == 1:
            raise httpx.ConnectTimeout("timeout", request=req)
        return httpx.Response(200, json={"results": []})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert openaq.request(client, "https://api.openaq.org/v3/locations") == {
            "results": []
        }
    assert len(attempts) == 2


@pytest.mark.parametrize("status", [401, 403, 429])
def test_auth_and_rate_limit_are_not_retried(monkeypatch, status):
    configure(monkeypatch)
    attempts = []

    def handler(req):
        attempts.append(req)
        return httpx.Response(status)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(openaq.DataUnavailable):
            openaq.request(client, "https://api.openaq.org/v3/locations")
    assert len(attempts) == 1


@pytest.mark.parametrize(
    "error, message",
    [
        (httpx.ConnectTimeout, "connection timed out"),
        (httpx.ReadTimeout, "response data"),
        (httpx.ConnectError, "DNS"),
    ],
)
def test_failures_are_bounded_and_actionable(monkeypatch, error, message):
    configure(monkeypatch)
    attempts = []

    def handler(req):
        attempts.append(req)
        raise error("do not expose internals or secrets", request=req)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(openaq.DataUnavailable, match=message) as caught:
            openaq.request(client, "https://api.openaq.org/v3/locations")
    assert "secrets" not in str(caught.value)
    assert len(attempts) == 2


def test_weather_failure_is_not_mislabeled_openaq(monkeypatch):
    configure(monkeypatch)
    with httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(503))
    ) as client:
        with pytest.raises(
            openaq.DataUnavailable, match="Weather provider returned HTTP 503"
        ):
            openaq.request(client, "https://api.open-meteo.com/v1/forecast")
