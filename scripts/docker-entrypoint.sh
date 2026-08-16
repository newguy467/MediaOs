#!/bin/sh
set -eu

# The image is built with a non-root runtime user, but Docker bind mounts can
# arrive owned by root. Fix only application/config data by default; library
# mounts can be very large, so they are opt-in through MEDIAOS_CHOWN_PATHS.
if [ "$(id -u)" = "0" ]; then
    chown_paths="${MEDIAOS_CHOWN_PATHS:-/app/data /config}"
    for path in $chown_paths; do
        if [ -e "$path" ]; then
            chown -R mediaos:mediaos "$path" 2>/dev/null || true
        fi
    done

    # Drop privileges for the actual application process. gosu is installed
    # by the Dockerfile and preserves signal handling with exec.
    exec gosu mediaos "$@"
fi

exec "$@"
