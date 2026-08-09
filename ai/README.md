# MediaOS Safe AI Assistant

Local, read-only-by-default AI helper powered by **Ollama**.

## What it can do

- List / search your library  
  - “list all with Matt Smith in”  
  - “list music from the 90s”  
  - “show books by …”
- Check recent activity and error logs
- Propose safe fixes (never applies them until you type **yes**)
- Answer questions about MediaOS settings

## Safety guarantees

- Read-only by default
- No shell commands, no `rm`, no force overwrites
- Any change is only a *proposal* — you must reply `yes` to approve
- Admin-only endpoints (`/api/ai/*`)

## How to start

```bash
# main compose
docker compose --profile ai up -d

# or standalone
docker compose -f docker-compose.standalone.yml --profile ai up -d
```

First start downloads the model (`llama3.2` by default).  
Change model with env:

```env
OLLAMA_MODEL=llama3.1
# or mistral, phi3, etc.
```

## Files added

| Path | Purpose |
|------|---------|
| `ai/system_prompt.txt` | Safety rules the model must follow |
| `app/services/ai_agent.py` | Tool-calling agent (search, logs, health, proposals) |
| `app/routers/ai.py` | `/api/ai/status` + `/api/ai/chat` |
| `ui/src/AiChatPanel.jsx` | Floating chat button + panel |
| docker-compose*.yml | Optional `ollama` service under profile `ai` |

## API

```
GET  /api/ai/status
POST /api/ai/chat
{
  "message": "list music from the 90s",
  "history": []
}
```

Response includes `reply`, any `tool_calls` that ran, and an optional `proposal` that still needs confirmation.
