# MediaOS Safe AI Assistant (v4.12.0)

Local, optional, **read-only-by-default** AI helper powered by [Ollama](https://ollama.com).  
It lives inside MediaOS, talks only to models running on your machine, and never changes your library or host without an explicit `yes`.

---

## Why this exists

MediaOS is an all-in-one media manager. Users frequently ask:

- “Show me everything with Matt Smith”
- “List music from the 90s”
- “What’s broken in the logs and how do I fix it safely?”

Cloud AIs cannot see your private library. A local agent that *can* see it must still be trustworthy.  
The Safe AI Assistant is designed so that:

1. It is **optional** (Docker profile `ai`)
2. It is **read-only by default**
3. Any write / fix is only a **proposal** until you type `yes`
4. It never runs arbitrary shell commands

---

## Key functions

### 1. Library search (read-only)

| Example prompt | What the agent does |
|----------------|---------------------|
| `list all with Matt Smith in` | Calls `search_media(actor="Matt Smith")` across movies & TV |
| `list music from the 90s` | `search_media(media_type="music", year_from=1990, year_to=1999)` |
| `show books by Stephen King` | Filters by title / author fields |
| `what do I have from 2015` | Year-range search across enabled media types |

Returns title, year, type, path and status. Never modifies the database.

### 2. Error & activity inspection

| Example prompt | Tool used |
|----------------|-----------|
| `show recent errors` | `get_recent_errors(hours=24)` |
| `what failed today` | Filters Activity rows for fail / error / stall |
| `show last grabs` | `list_recent_activity(event_filter="grab")` |

### 3. System health

| Example prompt | Tool used |
|----------------|-----------|
| `is everything healthy?` | `system_health()` — DB + Ollama reachability |
| `is the AI online?` | Same endpoint the UI status light uses |

### 4. Safe fix proposals (confirmation required)

When you ask the agent to *fix* something:

1. It diagnoses using the tools above
2. It calls `propose_safe_fix(problem, suggested_action)`
3. The UI shows the exact proposed steps
4. **Nothing is executed** until you reply with the word `yes`

If you reply anything else, the proposal is discarded.

### 5. Floating chat panel

- Bottom-right **AI** button in the web UI
- Status light (green = Ollama reachable)
- Conversation history kept for the current session
- Works behind the existing MediaOS auth (admin only)

---


### Expanded tool set (v4.12.0)

| Tool | Example prompt | Side effects |
|------|----------------|--------------|
| `search_media` | list all with Matt Smith / music from the 90s | None |
| `show_wanted` | show wanted / missing movies | None |
| `library_stats` | how big is my library | None |
| `check_indexer_health` | check indexer health | None |
| `list_quality_profiles` | list quality profiles | None |
| `suggest_quality_profile` | suggest a space-saving movie profile | Proposal only |
| `queue_status` | what's in the queue | None |
| `list_recent_activity` | show recent grabs | None |
| `get_recent_errors` | show recent errors | None |
| `blocklist_overview` | show blocklist | None |
| `system_health` | is everything healthy | None |
| `settings_summary` | show library paths | None |
| `propose_safe_fix` | fix the stalled download | Proposal only |

**Model:** `llama3.2` is the required default (reliable tool calling).
Pull it once: `docker compose exec ollama ollama pull llama3.2`

## Architecture

```
┌─────────────────┐     HTTP      ┌──────────────────┐
│  AiChatPanel    │ ────────────► │  /api/ai/chat    │
│  (React)        │               │  /api/ai/status  │
└─────────────────┘               └────────┬─────────┘
                                           │
                                           ▼
                                  ┌──────────────────┐
                                  │  ai_agent.py     │
                                  │  (safe tools)    │
                                  └────────┬─────────┘
                                           │
                          ┌────────────────┼────────────────┐
                          ▼                ▼                ▼
                   MediaOS DB        Activity log      Ollama
                   (read-only)       (read-only)     (localhost)
```

### Files

| Path | Role |
|------|------|
| `ai/system_prompt.txt` | Hard safety rules the model must obey |
| `app/services/ai_agent.py` | Tool registry + Ollama chat loop |
| `app/routers/ai.py` | FastAPI endpoints (admin-protected) |
| `ui/src/AiChatPanel.jsx` | Floating chat UI |
| `docker-compose*.yml` | Optional `ollama` service under profile `ai` |

### Tools the model is allowed to call

| Tool | Side effects |
|------|--------------|
| `search_media` | None (read) |
| `list_recent_activity` | None (read) |
| `get_recent_errors` | None (read) |
| `system_health` | None (read) |
| `propose_safe_fix` | None — only returns a proposal object |

No other tools exist. The model cannot invent shell commands.

---

## How to enable

```bash
# Main compose
docker compose --profile ai up -d --build

# Standalone stack
docker compose -f docker-compose.standalone.yml --profile ai up -d --build
```

First start downloads the default model (`llama3.2`).  
Override with environment variables:

```env
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3.1          # or mistral, phi3, gemma2, …
```

Pull a model manually if you prefer:

```bash
docker compose exec ollama ollama pull llama3.2
```

---

## Safety guarantees

1. **Read-only default** — search, logs, health only
2. **No shell access** — the agent never receives a shell tool
3. **Explicit confirmation** — any proposed change requires the user to type `yes`
4. **Admin-only API** — `/api/ai/*` requires an admin token
5. **Optional** — without the `ai` profile the feature is completely inactive
6. **Local only** — conversation and model stay on your machine

---

## Automation scripts (GitHub-friendly)

| Script | Purpose |
|--------|---------|
| `scripts/apply_safe_ai.sh` | Idempotent patch that wires the AI into an existing tree |
| `scripts/build_release.sh` | Produces `MediaOs-v4.12.0.zip` + SHA256 for a GitHub Release |

Typical CI / release flow:

```bash
./scripts/apply_safe_ai.sh
./scripts/build_release.sh
# then: gh release create v4.12.0 release/MediaOs-v4.12.0.zip ...
```

---

## API reference

### `GET /api/ai/status`

Returns Ollama reachability, selected model, and basic health.

### `POST /api/ai/chat`

```json
{
  "message": "list music from the 90s",
  "history": [
    {"role": "user", "content": "…"},
    {"role": "assistant", "content": "…"}
  ]
}
```

Response:

```json
{
  "reply": "Here are the albums from 1990-1999…",
  "tool_calls": [ … ],
  "proposal": null,
  "needs_confirmation": false
}
```

When a fix is proposed, `proposal` is populated and `needs_confirmation` is `true`.

---

## Roadmap notes

Possible future safe tools (still confirmation-gated):

- List wanted / missing items
- Indexer health summary
- Suggest quality-profile tweaks (proposal only)
- Explain a specific Activity row

None of these will gain write power without the same `yes` gate.

---

**MediaOS Safe AI — help without breaking anything.**
