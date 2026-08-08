"""VPN / Gluetun health + provider credential helpers."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger("mediaos.vpn")

# Gluetun-supported commercial providers (common ones)
PROVIDER_PRESETS: list[dict[str, Any]] = [
    {
        "id": "protonvpn",
        "label": "ProtonVPN",
        "gluetun": "protonvpn",
        "auth": "user_pass",
        "notes": "Use OpenVPN/WireGuard credentials from Proton account → Downloads",
        "env": ["VPN_SERVICE_PROVIDER=protonvpn", "OPENVPN_USER", "OPENVPN_PASSWORD"],
    },
    {
        "id": "surfshark",
        "label": "Surfshark",
        "gluetun": "surfshark",
        "auth": "user_pass",
        "notes": "Service credentials from Surfshark → VPN → Manual setup",
        "env": ["VPN_SERVICE_PROVIDER=surfshark", "OPENVPN_USER", "OPENVPN_PASSWORD"],
    },
    {
        "id": "mullvad",
        "label": "Mullvad",
        "gluetun": "mullvad",
        "auth": "wireguard_or_account",
        "notes": "Account number as user; WireGuard preferred",
        "env": ["VPN_SERVICE_PROVIDER=mullvad", "OPENVPN_USER", "WIREGUARD_PRIVATE_KEY"],
    },
    {
        "id": "nordvpn",
        "label": "NordVPN",
        "gluetun": "nordvpn",
        "auth": "user_pass",
        "notes": "Service credentials (not regular login) from Nord account",
        "env": ["VPN_SERVICE_PROVIDER=nordvpn", "OPENVPN_USER", "OPENVPN_PASSWORD"],
    },
    {
        "id": "private internet access",
        "label": "Private Internet Access",
        "gluetun": "private internet access",
        "auth": "user_pass",
        "notes": "PIA username/password; enable port forwarding if needed",
        "env": ["VPN_SERVICE_PROVIDER=private internet access", "OPENVPN_USER", "OPENVPN_PASSWORD", "VPN_PORT_FORWARDING"],
    },
    {
        "id": "expressvpn",
        "label": "ExpressVPN",
        "gluetun": "expressvpn",
        "auth": "user_pass",
        "notes": "OpenVPN credentials from ExpressVPN setup page",
        "env": ["VPN_SERVICE_PROVIDER=expressvpn", "OPENVPN_USER", "OPENVPN_PASSWORD"],
    },
    {
        "id": "custom",
        "label": "Custom / WireGuard file",
        "gluetun": "custom",
        "auth": "wireguard",
        "notes": "Mount wg0.conf or set WireGuard keys manually",
        "env": ["VPN_SERVICE_PROVIDER=custom", "WIREGUARD_PRIVATE_KEY", "WIREGUARD_ADDRESSES"],
    },
]


def list_providers() -> list[dict[str, Any]]:
    return PROVIDER_PRESETS


def gluetun_compose_snippet() -> str:
    """Example env block for docker-compose gluetun service."""
    user = settings.vpn_username or settings.vpn_opvn_user or "YOUR_USER"
    password = settings.vpn_password or settings.vpn_opvn_password or "YOUR_PASSWORD"
    provider = settings.vpn_service_provider or settings.vpn_provider or "protonvpn"
    countries = settings.vpn_server_countries or "Netherlands"
    return f"""# Gluetun example — attach qBittorrent to this network
services:
  gluetun:
    image: qmcgaw/gluetun
    cap_add: [NET_ADMIN]
    devices: [/dev/net/tun:/dev/net/tun]
    environment:
      - VPN_SERVICE_PROVIDER={provider}
      - OPENVPN_USER={user}
      - OPENVPN_PASSWORD={password}
      - SERVER_COUNTRIES={countries}
      - HTTP_CONTROL_SERVER_ADDRESS=:8000
      - FIREWALL_OUTBOUND_SUBNETS=172.16.0.0/12,192.168.0.0/16,10.0.0.0/8
    ports:
      - 8888:8888/tcp   # HTTP proxy optional
      - 8388:8388/tcp   # Shadowsocks optional
    volumes:
      - gluetun:/gluetun

  qbittorrent:
    network_mode: service:gluetun
    # ... rest of qB config; no ports here — publish on gluetun if needed
"""


def _gluetun_status() -> dict[str, Any]:
    url = (settings.vpn_gluetun_url or "").rstrip("/")
    if not url:
        return {"ok": False, "error": "vpn_gluetun_url empty", "source": "gluetun"}
    try:
        with httpx.Client(timeout=settings.vpn_check_timeout_seconds) as client:
            # Gluetun control server endpoints
            ip = None
            country = None
            try:
                r = client.get(f"{url}/v1/publicip/ip")
                if r.status_code == 200:
                    data = r.json() if "json" in r.headers.get("content-type", "") else {"public_ip": r.text.strip()}
                    ip = data.get("public_ip") or data.get("ip") or (data if isinstance(data, str) else None)
            except Exception:
                pass
            try:
                r = client.get(f"{url}/v1/publicip/country")
                if r.status_code == 200:
                    country = r.text.strip().strip('"')
            except Exception:
                pass
            # Fallback status
            if ip is None:
                r = client.get(f"{url}/v1/openvpn/status")
                ok = r.status_code == 200 and "running" in r.text.lower()
                return {"ok": ok, "public_ip": None, "country": country, "source": "gluetun", "raw": r.text[:200]}
            return {"ok": True, "public_ip": ip, "country": country, "source": "gluetun"}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "source": "gluetun"}


def _public_ip_fallback() -> dict[str, Any]:
    try:
        with httpx.Client(timeout=settings.vpn_check_timeout_seconds) as client:
            r = client.get(settings.vpn_public_ip_url or "https://ifconfig.io/ip")
            r.raise_for_status()
            return {"ok": True, "public_ip": r.text.strip(), "country": None, "source": "public_ip_url"}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "source": "public_ip_url"}


def get_vpn_status() -> dict[str, Any]:
    enabled = bool(settings.vpn_enabled)
    result: dict[str, Any] = {
        "enabled": enabled,
        "provider": settings.vpn_provider,
        "service_provider": getattr(settings, "vpn_service_provider", "") or settings.vpn_provider,
        "kill_switch": bool(settings.vpn_kill_switch),
        "expected_country": settings.vpn_expected_country or None,
        "has_credentials": bool(settings.vpn_username or settings.vpn_opvn_user or settings.vpn_wireguard_private_key),
        "healthy": True,
        "public_ip": None,
        "country": None,
        "detail": None,
        "providers": [p["id"] for p in PROVIDER_PRESETS],
    }
    if not enabled:
        result["detail"] = "VPN checks disabled"
        return result

    if settings.vpn_provider == "gluetun" and settings.vpn_gluetun_url:
        detail = _gluetun_status()
    else:
        detail = _public_ip_fallback()

    result["detail"] = detail
    result["public_ip"] = detail.get("public_ip")
    result["country"] = detail.get("country")
    healthy = bool(detail.get("ok"))
    expected = (settings.vpn_expected_country or "").strip().upper()
    if expected and detail.get("country"):
        got = str(detail["country"]).upper()
        if expected not in got and got not in expected:
            healthy = False
            detail["country_mismatch"] = True
    result["healthy"] = healthy
    return result


def vpn_allows_grabs() -> tuple[bool, str]:
    if not settings.vpn_enabled or not settings.vpn_kill_switch:
        return True, "ok"
    status = get_vpn_status()
    if status.get("healthy"):
        return True, "vpn healthy"
    return False, "VPN kill switch: tunnel unhealthy — grabs blocked"


def credentials_summary() -> dict[str, Any]:
    """Safe summary for UI (no raw secrets)."""
    return {
        "service_provider": getattr(settings, "vpn_service_provider", "") or "",
        "has_user": bool(settings.vpn_username or getattr(settings, "vpn_opvn_user", "")),
        "has_password": bool(settings.vpn_password or getattr(settings, "vpn_opvn_password", "")),
        "has_wireguard_key": bool(getattr(settings, "vpn_wireguard_private_key", "")),
        "server_countries": getattr(settings, "vpn_server_countries", "") or "",
        "port_forwarding": bool(getattr(settings, "vpn_port_forwarding", False)),
        "compose_hint": gluetun_compose_snippet(),
        "providers": PROVIDER_PRESETS,
    }
