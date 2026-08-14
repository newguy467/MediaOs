# VPN Setup — Gluetun Kill-Switch

MediaOS Next routes all download traffic through a VPN tunnel using [Gluetun](https://github.com/qdm12/gluetun). This is a **kill-switch** architecture: qBittorrent shares Gluetun's network namespace, so if the VPN tunnel drops, qBittorrent loses all connectivity and nothing leaks your real IP.

* * *

## How the kill-switch works

```
┌──────────┐     ┌──────────┐     ┌────────────┐     ┌──────────┐
│  Indexer │────►│ MediaOS  │────►│qBittorrent │────►│ Gluetun  │──VPN──►Internet
│  search  │     │  (grab)  │     │network_mode│     │ (tunnel) │
└──────────┘     └──────────┘     │service:    │     └──────────┘
                                  │  gluetun   │
                                  └────────────┘
```

In `docker-compose.yml`:

```yaml
qbittorrent:
  network_mode: "service:gluetun"   # ← shares Gluetun's network namespace
  depends_on:
    gluetun:
      condition: service_healthy     # ← won't start until VPN is up
```

Because qBittorrent has **no network interface of its own**, it physically cannot send traffic outside the tunnel. If Gluetun's tunnel breaks, qBittorrent goes dark. This is the kill-switch — no iptables rules to maintain, no race conditions, just network namespace isolation.

MediaOS monitors Gluetun's control server and reports VPN status in the UI (Settings → VPN). If the public IP doesn't match the expected VPN exit country, MediaOS flags a warning.

* * *

## Configuration

### 1\. Choose your VPN protocol

Set `VPN_TYPE` in `.env` (default: `wireguard`):

```bash
VPN_TYPE=wireguard   # or: openvpn
```

### 2\. Provide VPN credentials in `.env`

#### WireGuard (recommended)

```bash
VPN_SERVICE_PROVIDER=mullvad          # or: custom, pia, nordvpn, surfshark, …
VPN_TYPE=wireguard
VPN_WIREGUARD_PRIVATE_KEY=<your-private-key>
VPN_WIREGUARD_ADDRESSES=10.64.0.2/32  # your WireGuard address
VPN_WIREGUARD_PRESHARED_KEY=<optional-preshared-key>
```

For a **custom** WireGuard config (any provider not in Gluetun's built-in list), set `VPN_SERVICE_PROVIDER=custom` and provide the full endpoint:

```bash
VPN_SERVICE_PROVIDER=custom
VPN_WIREGUARD_PRIVATE_KEY=<key>
VPN_WIREGUARD_ADDRESSES=10.0.0.2/32
VPN_WIREGUARD_ENDPOINT_IP=<vpn-server-ip>
VPN_WIREGUARD_ENDPOINT_PORT=51820
```

#### OpenVPN

```bash
VPN_SERVICE_PROVIDER=mullvad
VPN_TYPE=openvpn
VPN_USERNAME=<your-username>
VPN_PASSWORD=<your-password>
VPN_OPENVPN_CUSTOM_CONFIG=<optional-path-to-.ovpn>
```

### 3\. (Optional) Verify the exit country

MediaOS can check that your VPN exit IP matches an expected country:

```bash
VPN_EXPECTED_COUNTRY=Netherlands   # ISO country name; empty = skip check
```

If set, MediaOS queries Gluetun's `/v1/publicip` endpoint and flags a warning when the country doesn't match.

### 4\. Restart the stack

```bash
docker compose down
docker compose up -d
```

Check that Gluetun becomes healthy:

```bash
docker compose ps gluetun
# STATUS: Up (healthy)

docker compose logs gluetun | tail -20
# Look for: "INFO ... IP is: <vpn-ip> ..."
```

* * *

## Supported VPN providers

Gluetun ships with built-in support for 40+ providers. Set `VPN_SERVICE_PROVIDER` to one of:

`custom`, `mullvad`, `pia` (Private Internet Access), `nordvpn`, `surfshark`, `windscribe`, `protonvpn`, `purevpn`, `torguard`, `vyprvpn`, `ipvanish`, `fastvpn`, `cyberghost`, `expressvpn`, `hidemyass`, `ivpn`, `le-vpn`, `vpn-unlimited`, `wevpn`, `kaspersky`, `norton`, `privatevpn`, `perfect-privacy`, `privacy-network`, `tunnelbear`, `bulletvpn`, `cafelinux`, `cubevpn`, `fastestvpn`, `flowvpn`, `ghostpath`, `ghostvpn`, `hybridvpn`, \`ipo \[...\]

Check the [Gluetun wiki](https://github.com/qdm12/gluetun/wiki) for the full, current list and provider-specific requirements.

* * *

## Verifying the kill-switch

### Test 1: Gluetun healthy → qBittorrent works

```bash
docker compose ps        # gluetun: healthy, qbittorrent: up
curl -u admin:password http://localhost:8080/api/v2/app/version
# → qBittorrent responds
```

### Test 2: Stop Gluetun → qBittorrent goes dark

```bash
docker compose stop gluetun
# qBittorrent loses its network namespace → all downloads stall
# No traffic leaks because there's no interface to leak through
docker compose start gluetun
# Gluetun reconnects → qBittorrent resumes (after healthcheck passes)
```

### Test 3: Check your public IP through the tunnel

```bash
docker compose exec gluetun wget -qO- https://api.ipify.org
# → should show your VPN exit IP, NOT your ISP IP
```

* * *

## MediaOS VPN monitoring

MediaOS exposes VPN status via the API and UI:

-   **API:** `GET /api/settings/vpn/status` — returns `enabled`, `provider`, `service_provider`, `kill_switch`, `expected_country`, and current status
-   **UI:** Settings → VPN — shows live Gluetun status, exit IP, expected vs. actual country, and kill-switch state
-   **Health endpoint:** `GET /api/health` includes a `vpn` object summarizing the configuration

MediaOS queries Gluetun's control server at the URL configured in `VPN_GLUETUN_URL` (default: `http://gluetun:8000`).

* * *

## Troubleshooting

### Gluetun won't become healthy

-   Check `docker compose logs gluetun` for auth errors (wrong key / password)
-   Verify `VPN_SERVICE_PROVIDER` is spelled exactly as Gluetun expects
-   For WireGuard: ensure `VPN_WIREGUARD_ADDRESSES` includes the `/32` (or `/128` for IPv6) suffix
-   For custom WireGuard: you must provide `VPN_WIREGUARD_ENDPOINT_IP` and `VPN_WIREGUARD_ENDPOINT_PORT`

### qBittorrent can't connect

-   If Gluetun isn't healthy, qBittorrent won't start (`depends_on: healthy`)
-   qBittorrent's Web UI is published **through Gluetun** on `QBIT_HOST_PORT` (default 8080). If you can't reach it, Gluetun may be down.
-   MediaOS connects to qBittorrent at `QBIT_URL=http://gluetun:8080` (the in-network address through Gluetun's published port)

### Downloads stall but Gluetun is up

-   The torrent ports (`6881` TCP/UDP) are published through Gluetun — verify `QBIT_TORRENT_PORT` matches your qBittorrent settings
-   Some VPN providers block P2P traffic — use a provider/port that allows it (Mullvad, PIA, and most Gluetun-supported providers do)

### "VPN country mismatch" warning in MediaOS

-   Your VPN exited through a different country than `VPN_EXPECTED_COUNTRY`
-   Either fix the server selection in your VPN config, or clear `VPN_EXPECTED_COUNTRY` to disable the check

* * *

## Disabling VPN (not recommended)

If you must run without VPN (e.g. for testing on a seedbox that's already protected):

1.  Set `VPN_ENABLED=false` in `.env`
2.  Remove the `network_mode: "service:gluetun"` line from qBittorrent in `docker-compose.yml` and give qBittorrent its own `ports` mapping
3.  Remove qBittorrent's `depends_on: gluetun` condition

**Warning:** This removes the kill-switch. Only do this if your network is already protected by other means. MediaOS will show VPN as disabled in the UI.