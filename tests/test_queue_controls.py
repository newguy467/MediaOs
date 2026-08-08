
from app.services.download_clients import pause_torrent, resume_torrent, recheck_torrent

def test_pause_returns_dict():
    # Without a live client this should still return a structured dict
    r = pause_torrent("deadbeef")
    assert "ok" in r and "client" in r
