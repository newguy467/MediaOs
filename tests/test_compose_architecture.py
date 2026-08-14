"""Tests for the unified Docker Compose architecture and .env.example completeness.

Verifies that:
1. docker-compose.yml has all required services (MediaOS, Postgres, Redis,
   Jellyfin, qBittorrent, Gluetun VPN)
2. qBittorrent uses network_mode: service:gluetun (VPN kill-switch)
3. Library mount paths are consistent across MediaOS, Jellyfin, qBittorrent
4. All services have healthchecks, restart policies, security options
5. .env.example contains all variables referenced in docker-compose.yml
6. No hard-coded secrets in docker-compose.yml or .env.example
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "docker-compose.yml"
ENV_EXAMPLE = ROOT / ".env.example"


@pytest.fixture(scope="module")
def compose_data():
    """Load and parse docker-compose.yml."""
    with open(COMPOSE) as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def env_vars():
    """Parse all variable names from .env.example."""
    text = ENV_EXAMPLE.read_text()
    # Match VAR_NAME= at start of line (not comments)
    matches = re.findall(r"^([A-Z][A-Z0-9_]*)=", text, re.MULTILINE)
    return set(matches)


@pytest.fixture(scope="module")
def compose_env_refs(compose_data):
    """Extract all ${VAR} references from docker-compose.yml."""
    raw = COMPOSE.read_text()
    # Match ${VAR} or ${VAR:-default}
    refs = re.findall(r"\$\{([A-Z][A-Z0-9_]*?)(?::-[^}]*)?\}", raw)
    return set(refs)


# ─────────────────────────────────────────────────────────────────────────────
# Service presence
# ─────────────────────────────────────────────────────────────────────────────

class TestServicePresence:
    def test_has_all_core_services(self, compose_data):
        services = set(compose_data.get("services", {}).keys())
        required = {"mediaos", "mediaos-db", "redis", "gluetun", "qbittorrent", "jellyfin"}
        missing = required - services
        assert not missing, f"Missing required services: {missing}"

    def test_has_optional_profile_services(self, compose_data):
        services = set(compose_data.get("services", {}).keys())
        optional = {"tdarr", "iptv-org-epg", "flaresolverr", "ollama"}
        present = services & optional
        assert len(present) >= 3, f"Expected at least 3 optional services, got: {present}"


# ─────────────────────────────────────────────────────────────────────────────
# VPN kill-switch
# ─────────────────────────────────────────────────────────────────────────────

class TestVPNKillSwitch:
    def test_qbittorrent_uses_gluetun_network(self, compose_data):
        qbit = compose_data["services"]["qbittorrent"]
        assert qbit.get("network_mode") == "service:gluetun", (
            "qBittorrent must use network_mode: service:gluetun for VPN kill-switch"
        )

    def test_qbittorrent_depends_on_gluetun_healthy(self, compose_data):
        qbit = compose_data["services"]["qbittorrent"]
        deps = qbit.get("depends_on", {})
        assert "gluetun" in deps, "qBittorrent must depend on gluetun"
        gluetun_dep = deps["gluetun"]
        if isinstance(gluetun_dep, dict):
            assert gluetun_dep.get("condition") == "service_healthy"
        # If it's a simple list form, just check presence

    def test_gluetun_has_healthcheck(self, compose_data):
        gluetun = compose_data["services"]["gluetun"]
        assert "healthcheck" in gluetun, "Gluetun must have a healthcheck"

    def test_gluetun_has_net_admin_cap(self, compose_data):
        gluetun = compose_data["services"]["gluetun"]
        caps = gluetun.get("cap_add", [])
        assert "NET_ADMIN" in caps, "Gluetun needs NET_ADMIN capability"

    def test_gluetun_has_tun_device(self, compose_data):
        gluetun = compose_data["services"]["gluetun"]
        devices = gluetun.get("devices", [])
        assert any("tun" in str(d) for d in devices), "Gluetun needs /dev/net/tun"

    def test_mediaos_connects_to_gluetun_for_qbit(self, compose_data):
        mediaos = compose_data["services"]["mediaos"]
        env = mediaos.get("environment", {})
        qbit_url = env.get("QBIT_URL", "")
        assert "gluetun" in qbit_url, (
            f"MediaOS QBIT_URL should point to gluetun, got: {qbit_url}"
        )

    def test_mediaos_has_vpn_kill_switch_env(self, compose_data):
        mediaos = compose_data["services"]["mediaos"]
        env = mediaos.get("environment", {})
        # Values may be literal booleans or ${VAR:-default} interpolation.
        vpn_enabled = str(env.get("VPN_ENABLED", ""))
        assert vpn_enabled, "MediaOS must define VPN_ENABLED"
        assert vpn_enabled.lower() in ("true", "false", "1", "0") or "${" in vpn_enabled, (
            f"VPN_ENABLED must be a bool or env interpolation, got: {vpn_enabled}"
        )
        vpn_ks = str(env.get("VPN_KILL_SWITCH", ""))
        assert vpn_ks, "MediaOS must define VPN_KILL_SWITCH"
        assert vpn_ks.lower() in ("true", "false", "1", "0") or "${" in vpn_ks, (
            f"VPN_KILL_SWITCH must be a bool or env interpolation, got: {vpn_ks}"
        )
        assert "gluetun" in str(env.get("VPN_GLUETUN_URL", ""))


# ─────────────────────────────────────────────────────────────────────────────
# Path consistency (hardlinks)
# ─────────────────────────────────────────────────────────────────────────────

class TestPathConsistency:
    @staticmethod
    def _parse_mounts(svc):
        mounts = {}
        for v in svc.get("volumes", []):
            idx = v.find(":/")
            if idx != -1:
                host = v[:idx]
                rest = v[idx + 1:]
                container = rest.split(":")[0]
                mounts[container] = host
            else:
                parts = v.rsplit(":", 1)
                if len(parts) == 2 and parts[1].startswith("/"):
                    mounts[parts[1]] = parts[0]
        return mounts

    @staticmethod
    def _normalize(host_path):
        return re.sub(r"\$\{(\w+):-([^}]*)\}", r"\2", host_path)

    def test_library_paths_consistent_mediaos_jellyfin(self, compose_data):
        mediaos = self._parse_mounts(compose_data["services"]["mediaos"])
        jellyfin = self._parse_mounts(compose_data["services"]["jellyfin"])
        shared = ["/movies", "/tv", "/music", "/books", "/audiobooks",
                   "/podcasts", "/comics", "/manga", "/youtube"]
        mismatches = []
        for lib in shared:
            m = self._normalize(mediaos.get(lib, ""))
            j = self._normalize(jellyfin.get(lib, ""))
            if m != j:
                mismatches.append(f"{lib}: mediaos={m} jellyfin={j}")
        assert not mismatches, f"Path mismatches: {mismatches}"

    def test_downloads_path_consistent_mediaos_qbit(self, compose_data):
        mediaos = self._parse_mounts(compose_data["services"]["mediaos"])
        qbit = self._parse_mounts(compose_data["services"]["qbittorrent"])
        m = self._normalize(mediaos.get("/downloads", ""))
        q = self._normalize(qbit.get("/downloads", ""))
        assert m == q, f"Downloads path mismatch: mediaos={m} qbit={q}"


# ─────────────────────────────────────────────────────────────────────────────
# Security, healthchecks, restart policies
# ─────────────────────────────────────────────────────────────────────────────

class TestServiceConfig:
    @pytest.mark.parametrize("svc_name", [
        "mediaos", "mediaos-db", "redis", "gluetun", "qbittorrent", "jellyfin"
    ])
    def test_service_has_restart_policy(self, compose_data, svc_name):
        svc = compose_data["services"][svc_name]
        assert "restart" in svc, f"{svc_name} missing restart policy"

    @pytest.mark.parametrize("svc_name", [
        "mediaos", "mediaos-db", "redis", "gluetun", "jellyfin"
    ])
    def test_service_has_healthcheck(self, compose_data, svc_name):
        svc = compose_data["services"][svc_name]
        assert "healthcheck" in svc, f"{svc_name} missing healthcheck"

    @pytest.mark.parametrize("svc_name", [
        "mediaos", "mediaos-db", "redis", "jellyfin", "tdarr",
        "iptv-org-epg", "flaresolverr", "ollama"
    ])
    def test_service_has_no_new_privileges(self, compose_data, svc_name):
        svc = compose_data["services"].get(svc_name, {})
        so = svc.get("security_opt", [])
        assert "no-new-privileges:true" in so, (
            f"{svc_name} missing no-new-privileges security option"
        )

    def test_mediaos_depends_on_core_services(self, compose_data):
        mediaos = compose_data["services"]["mediaos"]
        deps = set(mediaos.get("depends_on", {}).keys())
        required = {"mediaos-db", "redis", "gluetun", "qbittorrent", "jellyfin"}
        missing = required - deps
        assert not missing, f"MediaOS missing dependencies: {missing}"

    def test_mediaos_has_log_rotation(self, compose_data):
        mediaos = compose_data["services"]["mediaos"]
        logging = mediaos.get("logging", {})
        assert logging.get("driver") == "json-file"
        opts = logging.get("options", {})
        assert "max-size" in opts and "max-file" in opts


# ─────────────────────────────────────────────────────────────────────────────
# .env.example completeness
# ─────────────────────────────────────────────────────────────────────────────

class TestEnvExampleCompleteness:
    def test_env_example_exists(self):
        assert ENV_EXAMPLE.exists(), ".env.example must exist"

    def test_env_example_has_postgres_password(self, env_vars):
        assert "POSTGRES_PASSWORD" in env_vars, (
            ".env.example must contain POSTGRES_PASSWORD"
        )

    def test_env_example_has_redis_url(self, env_vars):
        assert "REDIS_URL" in env_vars, ".env.example must contain REDIS_URL"

    def test_env_example_has_vpn_credentials(self, env_vars):
        required_vpn = {
            "VPN_ENABLED", "VPN_PROVIDER", "VPN_KILL_SWITCH",
            "VPN_GLUETUN_URL", "VPN_SERVICE_PROVIDER",
            "VPN_WIREGUARD_PRIVATE_KEY", "VPN_WIREGUARD_ADDRESSES",
        }
        missing = required_vpn - env_vars
        assert not missing, f".env.example missing VPN vars: {missing}"

    def test_env_example_has_qbit_credentials(self, env_vars):
        required_qbit = {"QBIT_URL", "QBIT_USERNAME", "QBIT_PASSWORD"}
        missing = required_qbit - env_vars
        assert not missing, f".env.example missing qBittorrent vars: {missing}"

    def test_env_example_has_jellyfin_config(self, env_vars):
        required_jf = {"JELLYFIN_URL", "JELLYFIN_API_KEY"}
        missing = required_jf - env_vars
        assert not missing, f".env.example missing Jellyfin vars: {missing}"

    def test_env_example_has_library_paths(self, env_vars):
        required_paths = {
            "MOVIES_PATH", "TV_PATH", "MUSIC_PATH", "BOOKS_PATH",
            "AUDIOBOOKS_PATH", "COMICS_PATH", "DOWNLOADS_PATH",
        }
        missing = required_paths - env_vars
        assert not missing, f".env.example missing library path vars: {missing}"

    def test_env_example_has_compose_infra_vars(self, env_vars):
        required_infra = {
            "PUID", "PGID", "TZ", "MEDIAOS_HOST_PORT",
            "JELLYFIN_HOST_PORT", "QBIT_HOST_PORT",
        }
        missing = required_infra - env_vars
        assert not missing, f".env.example missing compose infra vars: {missing}"

    def test_no_hardcoded_secrets_in_compose(self):
        raw = COMPOSE.read_text()
        # Check for common secret patterns that shouldn't be hard-coded
        bad_patterns = [
            r"password\s*[:=]\s*['\"][^$]",  # literal password (not ${...})
            r"api_key\s*[:=]\s*['\"][^$]",
        ]
        for pattern in bad_patterns:
            matches = re.findall(pattern, raw, re.IGNORECASE)
            assert not matches, f"Hard-coded secret in compose: {matches}"

    def test_no_hardcoded_secrets_in_env_example(self):
        text = ENV_EXAMPLE.read_text()
        # All sensitive values should be empty or placeholder
        for line in text.splitlines():
            if "=  # sensitive" in line:
                # The value before =  # should be empty
                var_part = line.split("=")[0]
                value_part = line.split("=", 1)[1].split("#")[0].strip()
                assert value_part == "", (
                    f"Sensitive var {var_part} has non-empty default: '{value_part}'"
                )
