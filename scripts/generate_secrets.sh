#!/bin/sh
set -eu

ENV_FILE="${1:-.env}"
umask 077

generate_secret() {
    if command -v openssl >/dev/null 2>&1; then
        openssl rand -hex 32
    elif command -v python3 >/dev/null 2>&1; then
        python3 -c 'import secrets; print(secrets.token_hex(32))'
    else
        echo "ERROR: openssl or python3 is required" >&2
        exit 1
    fi
}

[ -f "$ENV_FILE" ] || cp .env.example "$ENV_FILE"

set_env() {
    key="$1"
    value="$2"
    tmp="${ENV_FILE}.tmp.$$"
    if grep -q "^${key}=" "$ENV_FILE"; then
        sed "s|^${key}=.*|${key}=${value}|" "$ENV_FILE" > "$tmp"
    else
        cat "$ENV_FILE" > "$tmp"
        printf '%s=%s\n' "$key" "$value" >> "$tmp"
    fi
    chmod 600 "$tmp"
    mv "$tmp" "$ENV_FILE"
}

current_db="$(sed -n 's/^POSTGRES_PASSWORD=//p' "$ENV_FILE" | head -n1)"
current_api="$(sed -n 's/^AUTH_API_KEY=//p' "$ENV_FILE" | head -n1)"

case "$current_db" in
    ""|change-me|mediaos|your-*) current_db="$(generate_secret)";;
esac
case "$current_api" in
    ""|change-me|your-*) current_api="$(generate_secret)";;
esac

set_env POSTGRES_PASSWORD "$current_db"
set_env DATABASE_URL "postgresql://mediaos:${current_db}@mediaos-db:5432/mediaos"
set_env AUTH_API_KEY "$current_api"
set_env AUTH_REQUIRE true

printf 'Secrets configured in %s\n' "$ENV_FILE"
printf 'POSTGRES_PASSWORD and AUTH_API_KEY were generated/preserved; AUTH_REQUIRE=true.\n'
printf 'Keep %s private and do not commit it.\n' "$ENV_FILE"
