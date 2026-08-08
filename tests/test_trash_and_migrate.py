
import json
from pathlib import Path
from app.services.trash_import import parse_trash_payload, _load_json

def test_parse_trash_list():
    data = [{"name": "x265", "score": 10, "specifications": []}]
    cfs = parse_trash_payload(data)
    assert cfs[0]["name"] == "x265"
    assert cfs[0]["score"] == 10

def test_bundled_movie_pack():
    p = Path("data/trash/movie-basic.json")
    if not p.exists():
        p = Path("/app/data/trash/movie-basic.json")
    if p.exists():
        data = json.loads(p.read_text())
        cfs = parse_trash_payload(data)
        assert len(cfs) >= 1

def test_anime_absolute_parser():
    from app.services.quality.parser import parse_anime_absolute
    assert parse_anime_absolute("Show Title - 12 [Group]") == 12
