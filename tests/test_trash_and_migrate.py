import json
from pathlib import Path
from app.services.trash_import import import_trash_payload


def test_import_trash_custom_formats():
    data = {
        "custom_formats": [
            {"name": "x265", "score": 10, "specifications": []},
        ]
    }
    result = import_trash_payload(data)
    assert result["ok"] is True
    assert result["applied"]["custom_formats"] == 1


def test_import_trash_scores():
    data = {
        "scores": {
            "resolution": {"2160p": 20000, "1080p": 1000},
        }
    }
    result = import_trash_payload(data)
    assert result["ok"] is True
    assert "resolution" in result["applied"]["matrices"]


def test_bundled_movie_pack():
    p = Path("data/trash/movie-basic.json")
    if not p.exists():
        p = Path("/app/data/trash/movie-basic.json")
    if p.exists():
        data = json.loads(p.read_text())
        if isinstance(data, list):
            data = {"custom_formats": data}
        result = import_trash_payload(data)
        assert result["ok"] is True


def test_anime_absolute_parser():
    from app.services.quality.parser import parse_anime_absolute
    assert parse_anime_absolute("Show Title - 12 [Group]") == 12
