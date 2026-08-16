from app.services.release_enrichment import rank_releases_stream_first, _looks_streamable


def test_looks_streamable_http():
    assert _looks_streamable({"download_url": "https://cdn.example/file.mp4"})
    assert not _looks_streamable({"magnet": "magnet:?xt=urn:btih:abc"})


def test_rank_stream_first_force():
    rows = [
        {"title": "a", "magnet": "magnet:?xt=urn:btih:1"},
        {"title": "b", "download_url": "https://x/y"},
    ]
    out = rank_releases_stream_first(rows, force=True)
    assert out[0]["title"] == "b"
