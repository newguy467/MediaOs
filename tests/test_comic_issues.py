"""Comic issue model + API smoke (no external ComicVine calls)."""
from app.models import ComicIssue, ItemStatus, MediaItem, MediaType


def test_comic_issue_model_fields():
    assert hasattr(ComicIssue, "issue_number")
    assert hasattr(ComicIssue, "monitored")
    assert hasattr(ComicIssue, "status")
    assert MediaType.comic.value == "comic"
    assert ItemStatus.wanted.value == "wanted"


def test_comics_router_import():
    from app.routers import comics
    assert hasattr(comics, "list_issues")
    assert hasattr(comics, "sync_issues")
