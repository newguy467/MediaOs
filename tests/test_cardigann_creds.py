
def test_search_cardigann_accepts_db():
    from app.services import search as S
    assert "db" in S._search_cardigann.__code__.co_varnames
