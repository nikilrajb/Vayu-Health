"""Safe network diagnostics: python -m app.diagnostics. Never prints credentials."""

import json
import os
import socket
import sys
import time

import httpx

from app.config import get_settings


def check_dns(host):
    try:
        records = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        return {"ok": True, "addresses": sorted({r[4][0] for r in records})}
    except OSError:
        return {
            "ok": False,
            "next_step": "DNS lookup failed. Check your network and its DNS service; compare with the same command on a permitted alternative network.",
        }


def check_https(url, headers=None):
    started = time.monotonic()
    try:
        with httpx.Client(timeout=httpx.Timeout(15, connect=8)) as client:
            response = client.get(url, headers=headers or {})
        status = response.status_code
        result = {
            "http_status": status,
            "seconds": round(time.monotonic() - started, 2),
        }
        if status == 200:
            result["result"] = "HTTPS request succeeded."
        elif status == 401:
            result["result"] = (
                "HTTPS works; authentication failed. Check OPENAQ_API_KEY in .env, then restart the backend."
            )
        elif status == 403:
            result["result"] = (
                "HTTPS works; access was denied. Check account permissions or contact the provider."
            )
        elif status == 429:
            result["result"] = (
                "HTTPS works; rate limited. Wait until the quota resets. Do not repeatedly retry."
            )
            result["quota_reset"] = response.headers.get("x-ratelimit-reset")
        else:
            result["result"] = (
                "An HTTP response was received; inspect the status code rather than changing network timeouts."
            )
        return result
    except httpx.ConnectTimeout:
        message = "Connection timed out before an HTTP response. Compare this command on another permitted network. Ask your administrator to check outbound HTTPS (443) to this hostname. A new API key will not repair the connection path."
        kind = "connect_timeout"
    except httpx.ReadTimeout:
        message = "Connection established, but response data arrived too slowly. Retry later; if repeatable, increase PROVIDER_READ_TIMEOUT_SECONDS to 45 and restart the backend."
        kind = "read_timeout"
    except httpx.ProxyError:
        message = "Proxy connection failed. Check the approved proxy address and authentication with your administrator. Do not remove a required proxy."
        kind = "proxy_error"
    except httpx.ConnectError as exc:
        certificate = "CERTIFICATE_VERIFY_FAILED" in str(exc)
        message = (
            "TLS certificate verification failed. Check system time and your organization's approved CA configuration. Keep certificate verification enabled."
            if certificate
            else "DNS, TCP or TLS connection failed. Use the DNS result above, then compare HTTPS reachability from another permitted network."
        )
        kind = "certificate_error" if certificate else "connect_error"
    except httpx.RequestError:
        message = "Request failed without a usable response. Check provider availability and the network/proxy configuration."
        kind = "request_error"
    return {
        "error": kind,
        "seconds": round(time.monotonic() - started, 2),
        "next_step": message,
    }


def main():
    settings = get_settings()
    key = settings.openaq_api_key.strip()
    report = {
        "python": sys.version.split()[0],
        "openaq_key_configured": bool(key),
        "proxy_environment_present": {
            name: bool(os.environ.get(name))
            for name in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"]
        },
        "openaq_dns": check_dns("api.openaq.org"),
        "openaq_https": (
            check_https(
                "https://api.openaq.org/v3/parameters?limit=1", {"X-API-Key": key}
            )
            if key
            else {
                "next_step": "Set OPENAQ_API_KEY in the project .env. The key stays on the server."
            }
        ),
        "weather_dns": check_dns("api.open-meteo.com"),
        "weather_https": check_https(
            "https://api.open-meteo.com/v1/forecast?latitude=28.6139&longitude=77.2090&current=temperature_2m"
        ),
    }
    print(json.dumps(report, indent=2))
    return (
        0
        if report["openaq_https"].get("http_status") == 200
        and report["weather_https"].get("http_status") == 200
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
