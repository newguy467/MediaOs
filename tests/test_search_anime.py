
from types import SimpleNamespace
from app.services.search import find_best_episode_release

def test_anime_query_uses_absolute(monkeypatch):
    series = SimpleNamespace(title="Test Anime", series_type="anime", quality_profile=None, episodes=[])
    ep = SimpleNamespace(season_number=1, episode_number=5, absolute_episode_number=12, monitored=True, status=SimpleNamespace(value="wanted"))
    seen = {}
    def fake_find(query, cat, profile, db=None, media=None):
        seen["q"] = query
        return {"title": "x"}
    monkeypatch.setattr("app.services.search._find_best", fake_find)
    monkeypatch.setattr("app.services.search._profile_for_item", lambda *a, **k: None)
    find_best_episode_release(series, ep, db=None)
    assert "12" in seen["q"]
