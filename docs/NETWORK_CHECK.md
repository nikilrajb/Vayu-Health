# Provider connectivity check — September 24, 2026

Executed `python -m app.diagnostics` from the project's Python 3.11 environment on this computer.

| Check | Observed result |
| --- | --- |
| OpenAQ key configured | Yes; key value not displayed |
| Standard HTTP/HTTPS proxy environment variables | Not present in this process |
| `api.openaq.org` DNS | Resolved successfully |
| Authenticated OpenAQ parameters request | Connection timeout; no HTTP response |
| `api.open-meteo.com` DNS | Resolved successfully |
| Open-Meteo current-weather request | Connection timeout; no HTTP response |

This result **does not prove which component is responsible**, nor does it validate or reject the OpenAQ key. It shows that both provider connection paths failed in this environment before an HTTP response was available. A missing proxy environment variable also does not prove that the computer has no system-level proxy.

Next useful step: run `./diagnose.ps1` on the other computer and compare on the same network. If permitted, compare this computer on a personal hotspot. Success on another network would narrow the investigation toward the current network's routing/filtering/proxy setup. Have an administrator investigate outbound HTTPS to the affected provider hosts; do not disable the firewall or TLS verification.

See [the run and troubleshooting guide](../RUN_GUIDE.md) for commands, interpretation, and configurable timeouts. The application now reports connection, read, proxy, authentication, and rate-limit failures separately, with a bounded transient retry.
