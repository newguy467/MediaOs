
def test_epg_grid_importable():
    from app.services.livetv import epg_grid, epg_now_next
    assert callable(epg_grid)
    assert epg_now_next(None) == {"now": None, "next": None}
