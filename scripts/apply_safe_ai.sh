#!/usr/bin/env bash
# Apply / verify MediaOS Safe AI integration (v4.12.0)
# Safe to re-run. Does not delete or overwrite user data.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> MediaOS Safe AI apply script (v4.12.0)"
echo "    Root: $ROOT"

# 1. Ensure directories
mkdir -p ai app/services app/routers ui/src scripts

# 2. Verify core AI files exist
for f in \
  ai/system_prompt.txt \
  ai/README.md \
  app/services/ai_agent.py \
  app/routers/ai.py \
  ui/src/AiChatPanel.jsx
do
  if [[ ! -f "$f" ]]; then
    echo "ERROR: missing $f — unpack the v4.12.0 release first"
    exit 1
  fi
  echo "  OK  $f"
done

# 3. Ensure main.py registers the router (idempotent)
if ! grep -q 'include_router(ai.router' app/main.py 2>/dev/null; then
  echo "  Patching app/main.py to include ai router..."
  # Add import if missing
  if ! grep -q '^\s*ai,' app/main.py; then
    sed -i 's/^\(\s*hunt,\)$/\1\n    ai,/' app/main.py
  fi
  # Add include_router if missing
  if ! grep -q 'include_router(ai.router' app/main.py; then
    sed -i 's|app.include_router(hunt.router, prefix="/api")|app.include_router(hunt.router, prefix="/api")\napp.include_router(ai.router, prefix="/api")|' app/main.py
  fi
  echo "  Patched main.py"
else
  echo "  OK  app/main.py already includes ai router"
fi

# 4. Ensure UI imports the panel (idempotent)
if [[ -f ui/src/app.jsx ]]; then
  if ! grep -q 'AiChatPanel' ui/src/app.jsx; then
    echo "  Patching ui/src/app.jsx to import AiChatPanel..."
    # Add import after storage import
    sed -i '/from "\.\/storage\.js"/a import AiChatPanel from "./AiChatPanel.jsx";' ui/src/app.jsx
    # Insert component just before the final closing of the App return
    # Look for the drawer-side closing and inject before the fragment end
    if grep -q 'drawer-side' ui/src/app.jsx; then
      sed -i '/<\/div>\s*$/{
        N
        /drawer-side/{
          a\    <AiChatPanel />
        }
      }' ui/src/app.jsx 2>/dev/null || true
      # Fallback: append near the end of the component if sed was too fragile
      if ! grep -q '<AiChatPanel' ui/src/app.jsx; then
        # Insert before the last </div></> of App
        python3 - <<'PY'
from pathlib import Path
p = Path("ui/src/app.jsx")
text = p.read_text()
if "<AiChatPanel" not in text:
    # Find the return of App and inject before the final fragment close
    needle = "    </div>\n    </>\n  );\n}\n\nexport function mount"
    if needle in text:
        text = text.replace(needle, "    </div>\n    <AiChatPanel />\n    </>\n  );\n}\n\nexport function mount")
        p.write_text(text)
        print("  Injected <AiChatPanel /> via Python fallback")
    else:
        print("  WARN: could not auto-inject <AiChatPanel /> — add it manually near the end of App()")
else:
        print("  OK  AiChatPanel already present")
PY
      fi
    fi
  else
    echo "  OK  ui/src/app.jsx already references AiChatPanel"
  fi
else
  echo "  WARN: ui/src/app.jsx not present (UI may be pre-built). Panel will still load if you rebuild UI."
fi

# 5. Dockerfile must copy ai/
if [[ -f Dockerfile ]] && ! grep -q 'COPY ai' Dockerfile; then
  echo "  Patching Dockerfile to COPY ai/..."
  sed -i '/COPY app \.\/app/a COPY ai ./ai' Dockerfile
  echo "  Patched Dockerfile"
else
  echo "  OK  Dockerfile"
fi

# 6. Version stamp
echo "4.12.0" > VERSION
echo "  VERSION → $(cat VERSION)"

echo ""
echo "==> Safe AI apply complete."
echo "    Next:  ./scripts/build_release.sh"
echo "    Or:    docker compose --profile ai up -d --build"
