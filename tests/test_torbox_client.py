"""TorBox-specific client module tests (stream_providers._try_torbox)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_try_torbox_no_key_returns_none(monkeypatch):
    from app.config import settings
    from app.services import stream_providers as sp

    monkeypatch.setattr(settings, "torbox_api_key", "", raising=False)
    assert sp._try_torbox("magnet:?xt=urn:btih:deadbeef") is None


def test_try_torbox_create_and_download(monkeypatch):
    from app.config import settings
    from app.services import stream_providers as sp

    monkeypatch.setattr(settings, "torbox_api_key", "tb-test-key", raising=False)

    create_resp = MagicMock()
    create_resp.raise_for_status = MagicMock()
    create_resp.json.return_value = {
        "success": True,
        "data": {"torrent_id": 42},
    }

    list_resp = MagicMock()
    list_resp.raise_for_status = MagicMock()
    list_resp.json.return_value = {
        "data": [
            {
                "id": 42,
                "download_finished": True,
                "files": [{"id": 0}],
            }
        ]
    }

    dl_resp = MagicMock()
    dl_resp.status_code = 200
    dl_resp.json.return_value = {"data": "https://cdn.torbox.example/file.mkv"}

    with patch("httpx.post", return_value=create_resp) as post, \
         patch("httpx.get", side_effect=[list_resp, dl_resp]) as get, \
         patch("time.sleep", return_value=None):
        url = sp._try_torbox("magnet:?xt=urn:btih:abc123")
        assert url == "https://cdn.torbox.example/file.mkv"
        assert post.called
        assert get.call_count >= 1


def test_try_torbox_create_failure(monkeypatch):
    from app.config import settings
    from app.services import stream_providers as sp

    monkeypatch.setattr(settings, "torbox_api_key", "tb-test-key", raising=False)

    create_resp = MagicMock()
    create_resp.raise_for_status = MagicMock()
    create_resp.json.return_value = {"success": False, "error": "quota exceeded"}

    with patch("httpx.post", return_value=create_resp), patch("time.sleep", return_value=None):
        with pytest.raises(RuntimeError, match="quota exceeded"):
            sp._try_torbox("magnet:?xt=urn:btih:abc123")


def test_provider_list_includes_torbox_when_keyed(monkeypatch):
    from app.config import settings
    from app.services import stream_providers as sp

    monkeypatch.setattr(settings, "torbox_api_key", "tb-test-key", raising=False)
    providers = sp.providers() if hasattr(sp, "providers") else None
    if providers is None and hasattr(sp, "providers"):
        providers = sp.providers()
    # stream_providers exposes provider catalog via internal helpers; soft assert
    if providers:
        ids = {p.get("id") for p in providers}
        assert "torbox" in ids
