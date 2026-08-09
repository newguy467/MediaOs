"""
MediaOS Safe AI Agent  (v4.12.0)
================================
Local Ollama-powered helper. Model defaults to llama3.2 (required for
reliable tool use). Read-only by default; any change is only a proposal
that needs the user to type "yes".
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import or_, and_, func, text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import (
    MediaItem,
    Activity,
    Indexer,
    Download,
    Blocklist,
    QualityProfileRecord,
)

log = logging.getLogger("mediaos.ai")

# ---------------------------------------------------------------------------
# Configuration — llama3.2 is the required default for tool calling
# ---------------------------------------------------------------------------

OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
REQUIRED_MODEL_HINT = "llama3.2"

SYSTEM_PROMPT_PATH = Path(__file__).resolve().parents[2] / "ai" / "system_prompt.txt"
MAX_LIST = 40


def _load_system_prompt() -> str:
    try:
        return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return (
            "You are a safe, read-only MediaOS assistant. "
            "Never delete or change anything without explicit user confirmation (the word yes)."
        )


def _db() -> Session:
    return SessionLocal()


# ===========================================================================
# SAFE TOOLS
# ===========================================================================

def tool_search_media(
    query: str = "",
    media_type: str | None = None,
    actor: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    artist: str | None = None,
    limit: int = 25,
) -> dict[str, Any]:
    """Search the local library (title, actor, year range, artist)."""
    limit = min(max(1, limit), MAX_LIST)
    db = _db()
    try:
        q = db.query(MediaItem)
        if media_type:
            q = q.filter(MediaItem.media_type == media_type.lower())

        clauses = []
        if query:
            like = f"%{query}%"
            clauses.append(MediaItem.title.ilike(like))
            if hasattr(MediaItem, "original_title"):
                clauses.append(MediaItem.original_title.ilike(like))
        if actor:
            like = f"%{actor}%"
            for col in ("cast", "actors", "people", "overview", "description"):
                if hasattr(MediaItem, col):
                    clauses.append(getattr(MediaItem, col).ilike(like))
            clauses.append(MediaItem.title.ilike(like))
        if year_from is not None and hasattr(MediaItem, "year"):
            clauses.append(MediaItem.year >= year_from)
        if year_to is not None and hasattr(MediaItem, "year"):
            clauses.append(MediaItem.year <= year_to)
        if artist:
            like = f"%{artist}%"
            if hasattr(MediaItem, "artist_name"):
                clauses.append(MediaItem.artist_name.ilike(like))
            clauses.append(MediaItem.title.ilike(like))

        if clauses:
            q = q.filter(or_(*clauses))

        rows = q.order_by(MediaItem.title).limit(limit).all()
        items = [
            {
                "id": r.id,
                "title": getattr(r, "title", None),
                "media_type": getattr(r, "media_type", None),
                "year": getattr(r, "year", None),
                "status": str(getattr(r, "status", None) or ""),
                "monitored": getattr(r, "monitored", None),
                "path": getattr(r, "file_path", None) or getattr(r, "path", None),
            }
            for r in rows
        ]
        return {"ok": True, "count": len(items), "items": items}
    except Exception as e:
        log.exception("search_media")
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


def tool_show_wanted(media_type: str | None = None, limit: int = 30) -> dict[str, Any]:
    """List wanted / missing items (monitored but not on disk)."""
    limit = min(max(1, limit), MAX_LIST)
    db = _db()
    try:
        q = db.query(MediaItem).filter(
            MediaItem.status.in_(["wanted", "missing", "failed"])
        )
        if hasattr(MediaItem, "monitored") and hasattr(MediaItem, "file_path"):
            q = db.query(MediaItem).filter(
                or_(
                    MediaItem.status.in_(["wanted", "missing", "failed"]),
                    and_(
                        MediaItem.monitored.is_(True),
                        or_(MediaItem.file_path.is_(None), MediaItem.file_path == ""),
                    ),
                )
            )
        if media_type:
            q = q.filter(MediaItem.media_type == media_type.lower())
        rows = q.order_by(MediaItem.title).limit(limit).all()
        items = [
            {
                "id": r.id,
                "title": r.title,
                "media_type": r.media_type,
                "year": getattr(r, "year", None),
                "status": str(getattr(r, "status", "")),
                "monitored": getattr(r, "monitored", None),
            }
            for r in rows
        ]
        return {"ok": True, "count": len(items), "wanted": items}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


def tool_library_stats() -> dict[str, Any]:
    """Counts per media type + monitored total."""
    db = _db()
    try:
        rows = (
            db.query(MediaItem.media_type, func.count(MediaItem.id))
            .group_by(MediaItem.media_type)
            .all()
        )
        by_type = {str(t or "unknown"): c for t, c in rows}
        total = sum(by_type.values())
        monitored = 0
        if hasattr(MediaItem, "monitored"):
            monitored = db.query(func.count(MediaItem.id)).filter(MediaItem.monitored.is_(True)).scalar() or 0
        return {"ok": True, "total_items": total, "by_type": by_type, "monitored": monitored}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


def tool_check_indexer_health(limit: int = 40) -> dict[str, Any]:
    """Read-only snapshot of indexers (enabled, last error, fail streak)."""
    limit = min(max(1, limit), 80)
    db = _db()
    try:
        rows = db.query(Indexer).order_by(Indexer.priority).limit(limit).all()
        out, enabled, with_error = [], 0, 0
        for r in rows:
            creds = {}
            if getattr(r, "credentials_json", None):
                try:
                    creds = json.loads(r.credentials_json)
                except Exception:
                    pass
            item = {
                "id": r.id,
                "name": r.name,
                "kind": getattr(r, "kind", None),
                "enabled": bool(r.enabled),
                "priority": getattr(r, "priority", None),
                "last_ok_at": r.last_ok_at.isoformat() if getattr(r, "last_ok_at", None) else None,
                "last_error": (getattr(r, "last_error", None) or "")[:300] or None,
                "fail_streak": int(creds.get("fail_streak") or 0),
            }
            if item["enabled"]:
                enabled += 1
            if item["last_error"]:
                with_error += 1
            out.append(item)
        return {"ok": True, "total": len(out), "enabled": enabled, "with_error": with_error, "indexers": out}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


def tool_list_quality_profiles() -> dict[str, Any]:
    """List quality profiles."""
    db = _db()
    try:
        rows = db.query(QualityProfileRecord).order_by(QualityProfileRecord.name).all()
        profiles = []
        for r in rows:
            profiles.append({
                "id": r.id,
                "name": r.name,
                "media_type": getattr(r, "media_type", None) or getattr(r, "type", None),
                "cutoff": getattr(r, "cutoff", None),
            })
        return {"ok": True, "count": len(profiles), "profiles": profiles}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


def tool_suggest_quality_profile(media_type: str = "movie", goal: str = "balanced") -> dict[str, Any]:
    """Propose a quality-profile strategy. Does NOT apply anything."""
    suggestions = {
        "balanced": {
            "name": f"Balanced ({media_type})",
            "cutoff": "Bluray-1080p",
            "notes": "Prefer 1080p BluRay / WEB-DL; allow 720p fallback. Good default.",
        },
        "quality": {
            "name": f"Quality ({media_type})",
            "cutoff": "Bluray-2160p",
            "notes": "Prefer Remux / 2160p / 1080p BluRay. Higher disk use.",
        },
        "space": {
            "name": f"Space-saver ({media_type})",
            "cutoff": "WEBDL-720p",
            "notes": "Prefer smaller WEB-DL / x265 720p-1080p. Best when disk is limited.",
        },
        "anime": {
            "name": f"Anime ({media_type})",
            "cutoff": "Bluray-1080p",
            "notes": "Prefer fansub groups + official BDs; score release group heavily.",
        },
        "4k": {
            "name": f"4K ({media_type})",
            "cutoff": "Bluray-2160p",
            "notes": "Only keep 2160p / Remux. Needs large storage and 4K player.",
        },
    }
    pick = suggestions.get(goal.lower(), suggestions["balanced"])
    return {
        "ok": True,
        "type": "proposal",
        "media_type": media_type,
        "goal": goal,
        "suggested_profile": pick,
        "requires_confirmation": True,
        "confirm_phrase": "yes",
        "note": "No profile created or changed. Reply 'yes' for steps to apply in Settings > Quality.",
    }


def tool_queue_status(limit: int = 25) -> dict[str, Any]:
    """Current download queue."""
    limit = min(max(1, limit), 50)
    db = _db()
    try:
        rows = db.query(Download).order_by(Download.id.desc()).limit(limit).all()
        items = [
            {
                "id": r.id,
                "title": getattr(r, "release_title", None),
                "status": str(getattr(r, "status", "")),
                "progress": getattr(r, "progress", None),
                "error": (getattr(r, "last_error", None) or "")[:200] or None,
                "media_item_id": getattr(r, "media_item_id", None),
            }
            for r in rows
        ]
        return {"ok": True, "count": len(items), "queue": items}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


def tool_list_recent_activity(limit: int = 20, event_filter: str | None = None) -> dict[str, Any]:
    """Recent Activity feed."""
    limit = min(max(1, limit), 50)
    db = _db()
    try:
        q = db.query(Activity)
        if event_filter:
            q = q.filter(Activity.event.ilike(f"%{event_filter}%"))
        rows = q.order_by(Activity.created_at.desc()).limit(limit).all()
        out = [
            {
                "event": r.event,
                "message": r.message,
                "media_type": r.media_type,
                "release_title": r.release_title,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
        return {"ok": True, "count": len(out), "activity": out}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


def tool_get_recent_errors(hours: int = 24, limit: int = 30) -> dict[str, Any]:
    """Failures / errors / stalls."""
    limit = min(max(1, limit), 50)
    hours = min(max(1, hours), 168)
    db = _db()
    try:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        q = db.query(Activity).filter(
            Activity.created_at >= since,
            or_(
                Activity.event.ilike("%fail%"),
                Activity.event.ilike("%error%"),
                Activity.event.ilike("%stall%"),
                Activity.message.ilike("%error%"),
                Activity.message.ilike("%fail%"),
            ),
        )
        rows = q.order_by(Activity.created_at.desc()).limit(limit).all()
        out = [
            {
                "event": r.event,
                "message": r.message,
                "media_type": r.media_type,
                "release_title": r.release_title,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
        return {"ok": True, "count": len(out), "errors": out, "window_hours": hours}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


def tool_blocklist_overview(limit: int = 20) -> dict[str, Any]:
    """Recent blocklist entries."""
    limit = min(max(1, limit), 40)
    db = _db()
    try:
        rows = db.query(Blocklist).order_by(Blocklist.added_at.desc()).limit(limit).all()
        items = [
            {
                "id": r.id,
                "title": getattr(r, "release_title", None),
                "reason": getattr(r, "reason", None),
                "added_at": r.added_at.isoformat() if getattr(r, "added_at", None) else None,
            }
            for r in rows
        ]
        return {"ok": True, "count": len(items), "blocklist": items}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


def tool_system_health() -> dict[str, Any]:
    """DB + Ollama + model presence."""
    info: dict[str, Any] = {
        "ok": True,
        "ollama_base": OLLAMA_BASE,
        "model": OLLAMA_MODEL,
        "required_model_hint": REQUIRED_MODEL_HINT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        db = _db()
        db.execute(text("SELECT 1"))
        info["database"] = "ok"
        db.close()
    except Exception as e:
        info["database"] = f"error: {e}"
        info["ok"] = False

    try:
        with httpx.Client(timeout=3.0) as client:
            r = client.get(f"{OLLAMA_BASE}/api/tags")
            if r.status_code == 200:
                models = [m.get("name", "") for m in r.json().get("models", [])]
                info["ollama"] = "ok"
                info["available_models"] = models
                has_preferred = any(REQUIRED_MODEL_HINT in m for m in models)
                info["llama32_present"] = has_preferred
                if not has_preferred:
                    info["hint"] = (
                        f"Pull the required model: "
                        f"docker compose exec ollama ollama pull {REQUIRED_MODEL_HINT}"
                    )
            else:
                info["ollama"] = f"status {r.status_code}"
                info["ok"] = False
    except Exception as e:
        info["ollama"] = f"unreachable: {e}"
        info["ok"] = False
    return info


def tool_settings_summary() -> dict[str, Any]:
    """Non-secret settings overview."""
    safe_keys = [
        "movies_library_path", "tv_library_path", "music_library_path",
        "books_library_path", "audiobooks_library_path", "downloads_path",
        "search_interval_minutes", "min_seeders", "upgrade_enabled",
        "cleanup_enabled", "cleanup_max_strikes", "movie_download_mode",
        "allow_usenet", "torrent_client",
    ]
    out = {}
    for k in safe_keys:
        try:
            out[k] = getattr(settings, k, None)
        except Exception:
            pass
    return {"ok": True, "settings": out}


def tool_propose_safe_fix(problem_summary: str, suggested_action: str) -> dict[str, Any]:
    """Structured fix proposal. Never executes."""
    return {
        "ok": True,
        "type": "proposal",
        "problem": problem_summary,
        "suggested_action": suggested_action,
        "requires_confirmation": True,
        "confirm_phrase": "yes",
        "note": "No change has been made. Reply with 'yes' to approve.",
    }


SAFE_TOOLS = {
    "search_media": tool_search_media,
    "show_wanted": tool_show_wanted,
    "library_stats": tool_library_stats,
    "check_indexer_health": tool_check_indexer_health,
    "list_quality_profiles": tool_list_quality_profiles,
    "suggest_quality_profile": tool_suggest_quality_profile,
    "queue_status": tool_queue_status,
    "list_recent_activity": tool_list_recent_activity,
    "get_recent_errors": tool_get_recent_errors,
    "blocklist_overview": tool_blocklist_overview,
    "system_health": tool_system_health,
    "settings_summary": tool_settings_summary,
    "propose_safe_fix": tool_propose_safe_fix,
}


TOOL_DESCRIPTIONS = """
You have these tools. Call one by outputting exactly:

```tool
{"name": "tool_name", "arguments": {...}}
```

Then wait for the result.

TOOLS:
1. search_media — query, media_type, actor, year_from, year_to, artist, limit
2. show_wanted — media_type (optional), limit
3. library_stats — counts per type
4. check_indexer_health — limit
5. list_quality_profiles
6. suggest_quality_profile — media_type, goal (balanced|quality|space|anime|4k)  [proposal only]
7. queue_status — limit
8. list_recent_activity — limit, event_filter
9. get_recent_errors — hours, limit
10. blocklist_overview — limit
11. system_health
12. settings_summary
13. propose_safe_fix — problem_summary, suggested_action  [proposal only]

RULES:
- Prefer tools over guessing about the library.
- For any change use propose_safe_fix and wait for the user to say "yes".
- Keep answers concise; use bullet lists for media results.
"""


async def call_ollama(messages: list[dict], temperature: float = 0.2) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    async with httpx.AsyncClient(timeout=180.0) as client:
        r = await client.post(f"{OLLAMA_BASE}/api/chat", json=payload)
        r.raise_for_status()
        data = r.json()
        return data.get("message", {}).get("content", "") or ""


def _extract_tool_call(text: str) -> dict | None:
    m = re.search(r"```tool\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if not m:
        m = re.search(r'\{[^{}]*"name"\s*:\s*"[a-z_]+"[^{}]*\}', text)
    if not m:
        return None
    try:
        return json.loads(m.group(1) if m.lastindex else m.group(0))
    except Exception:
        return None


async def run_agent(user_message: str, history: list[dict] | None = None) -> dict[str, Any]:
    history = history or []
    system = _load_system_prompt() + "\n\n" + TOOL_DESCRIPTIONS

    messages = [{"role": "system", "content": system}]
    for h in history[-14:]:
        messages.append(h)
    messages.append({"role": "user", "content": user_message})

    tool_results: list[dict] = []
    proposal = None
    needs_confirmation = False
    content = ""

    for _ in range(4):
        try:
            content = await call_ollama(messages)
        except Exception as e:
            log.exception("Ollama call failed")
            return {
                "reply": (
                    f"Cannot reach the local model ({e}).\n"
                    f"Is Ollama running and is **{REQUIRED_MODEL_HINT}** pulled?\n\n"
                    f"  docker compose --profile ai up -d\\n"
                    f"  docker compose exec ollama ollama pull {REQUIRED_MODEL_HINT}"
                ),
                "tool_calls": [],
                "proposal": None,
                "needs_confirmation": False,
            }

        tool_call = _extract_tool_call(content)
        if not tool_call:
            return {
                "reply": content.strip(),
                "tool_calls": tool_results,
                "proposal": proposal,
                "needs_confirmation": needs_confirmation,
            }

        name = tool_call.get("name")
        args = tool_call.get("arguments") or {}
        if name not in SAFE_TOOLS:
            messages.append({"role": "assistant", "content": content})
            messages.append({
                "role": "user",
                "content": f"Tool '{name}' is not allowed. Only use the listed safe tools.",
            })
            continue

        try:
            result = SAFE_TOOLS[name](**args)
        except TypeError as e:
            result = {"ok": False, "error": f"Bad arguments: {e}"}
        except Exception as e:
            result = {"ok": False, "error": str(e)}

        tool_results.append({"name": name, "arguments": args, "result": result})
        if name in ("propose_safe_fix", "suggest_quality_profile") and result.get("ok"):
            proposal = result
            needs_confirmation = True

        messages.append({"role": "assistant", "content": content})
        messages.append({
            "role": "user",
            "content": f"Tool result for {name}:\n{json.dumps(result, default=str)[:5000]}",
        })

    return {
        "reply": content.strip() if content else "Tool-call limit reached — please rephrase.",
        "tool_calls": tool_results,
        "proposal": proposal,
        "needs_confirmation": needs_confirmation,
    }


async def chat(user_message: str, history: list[dict] | None = None) -> dict[str, Any]:
    return await run_agent(user_message, history)


async def ollama_status() -> dict[str, Any]:
    return tool_system_health()
