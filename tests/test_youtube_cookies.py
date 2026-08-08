"""YouTube cookies paste endpoint."""
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def test_cookies_status():
    client = TestClient(app)
    r = client.get("/api/youtube/cookies/status")
    assert r.status_code == 200
    data = r.json()
    assert "path" in data
    assert "exists" in data


def test_cookies_paste(tmp_path, monkeypatch):
    from app.config import settings
    dest = tmp_path / "cookies.txt"
    monkeypatch.setattr(settings, "youtube_cookies_path", str(dest), raising=False)
    client = TestClient(app)
    body = {
        "content": "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tFALSE\t0\tTESTID\tabc\n"
    }
    r = client.post("/api/youtube/cookies", json=body)
    assert r.status_code == 200
    assert r.json().get("ok") is True
    assert dest.exists()
    assert "youtube.com" in dest.read_text()
