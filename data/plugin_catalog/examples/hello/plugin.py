"""Minimal MediaOS community plugin example."""
from __future__ import annotations

import logging

log = logging.getLogger("mediaos.plugin.hello")


def register_plugin(register):
    def on_startup():
        log.info("Hello plugin: MediaOS startup hook fired")
        return {"ok": True, "plugin": "community.example-hello"}

    register(
        "community.example-hello",
        name="Example Hello Plugin",
        version="1.0.0",
        hooks={"startup": on_startup},
    )
    log.info("Hello plugin registered")
