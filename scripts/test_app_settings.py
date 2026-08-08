#!/usr/bin/env python3
"""Smoke test for app_settings override layer. Requires DATABASE_URL."""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main() -> int:
    from app.database import Base, SessionLocal, engine
    from app.models import AppSetting
    from app.services import app_settings as svc
    from app.config import settings
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        key = "search_interval_minutes"
        existing = db.get(AppSetting, key)
        if existing: db.delete(existing); db.commit()
        original = int(settings.search_interval_minutes)
        svc.update_group(db, "system", {key: 42})
        assert settings.search_interval_minutes == 42
        object.__setattr__(settings, key, original)
        svc.load_overrides(db)
        assert settings.search_interval_minutes == 42
        row = db.get(AppSetting, key)
        if row: db.delete(row); db.commit()
        object.__setattr__(settings, key, original)
        print("PASS")
        return 0
    except Exception as exc:
        print(f"FAIL: {exc}")
        return 1
    finally:
        db.close()

if __name__ == "__main__":
    raise SystemExit(main())
