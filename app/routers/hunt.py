"""Hunt engine API — aggressive missing / upgrade searches."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.database import get_db
from app.services.hunt import plan_hunt, run_hunt_batch

router = APIRouter(prefix="/hunt", tags=["hunt"])


class HuntPlanBody(BaseModel):
    media_types: list[str] | None = None
    only_monitored: bool = True
    limit: int = Field(default=50, ge=1, le=500)


@router.post("/plan")
def hunt_plan(body: HuntPlanBody, db: Session = Depends(get_db), _=Depends(require_permission("download"))):
    plan = plan_hunt(
        db,
        media_types=body.media_types,
        only_monitored=body.only_monitored,
        limit=body.limit,
    )
    return {"ok": True, "plan": plan, "count": len(plan)}


@router.post("/run")
def hunt_run(body: HuntPlanBody, db: Session = Depends(get_db), _=Depends(require_permission("download"))):
    plan = plan_hunt(
        db,
        media_types=body.media_types,
        only_monitored=body.only_monitored,
        limit=body.limit,
    )
    result = run_hunt_batch(db, plan)
    return {"ok": True, **result, "plan_count": len(plan)}
