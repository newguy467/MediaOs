"""SSE endpoint — live updates for queue, activity, workers, cleanup."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from app.services.sse import recent, stream
from app.auth import require_permission

router = APIRouter(prefix="/sse", tags=["sse"],
    dependencies=[Depends(require_permission("library.view", "queue.view"))],
)


@router.get("/events")
async def sse_events(request: Request, last_event_id: int = Query(0, alias="lastEventId")):
    async def gen():
        async for chunk in stream(last_id=last_event_id):
            if await request.is_disconnected():
                break
            yield chunk

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/recent")
def sse_recent(limit: int = 50):
    return recent(limit=limit)
