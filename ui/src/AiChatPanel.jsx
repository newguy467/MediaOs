/**
 * MediaOS Safe AI Chat Panel
 * Minimal floating assistant that talks to /api/ai/chat
 * Read-only by default — any proposed fix requires typing "yes"
 */
import { useState, useRef, useEffect } from "react";
import { getToken } from "./storage.js";

const authHeaders = () => {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
};

export default function AiChatPanel() {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "Hi — I’m the MediaOS Safe Assistant (local Ollama).\n\nI can list media (e.g. “list all with Matt Smith”, “music from the 90s”), check error logs, and propose safe fixes. I never change anything without you typing **yes**.",
    },
  ]);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState(null);
  const bottomRef = useRef(null);

  useEffect(() => {
    if (open && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, open]);

  useEffect(() => {
    if (!open) return;
    fetch("/api/ai/status", { headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setStatus(d))
      .catch(() => setStatus({ ok: false, ollama: "unreachable" }));
  }, [open]);

  // Allow sidebar (or anything) to open the panel via custom event
  useEffect(() => {
    const openAi = () => setOpen(true);
    window.addEventListener("mediaos-open-ai", openAi);
    return () => window.removeEventListener("mediaos-open-ai", openAi);
  }, []);

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    const history = messages
      .filter((m) => m.role === "user" || m.role === "assistant")
      .map((m) => ({ role: m.role, content: m.content }));
    setMessages((m) => [...m, { role: "user", content: text }]);
    setBusy(true);
    try {
      const r = await fetch("/api/ai/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ message: text, history }),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error(err.detail || r.statusText || "Request failed");
      }
      const data = await r.json();
      let reply = data.reply || "(empty reply)";
      if (data.needs_confirmation && data.proposal) {
        reply +=
          "\n\n---\n**Proposed fix (not applied yet)**\n" +
          `Problem: ${data.proposal.problem}\n` +
          `Action: ${data.proposal.suggested_action}\n` +
          `Reply with **yes** to approve.`;
      }
      setMessages((m) => [...m, { role: "assistant", content: reply }]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: `Could not reach the Safe AI.\n${e.message}\n\nIs the ollama profile running?\n  docker compose --profile ai up -d`,
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      {/* Floating toggle button */}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        title="Safe AI Assistant"
        className="fixed bottom-5 right-5 z-50 btn btn-circle btn-primary shadow-lg"
        style={{ width: 52, height: 52 }}
      >
        {open ? "✕" : "AI"}
      </button>

      {open && (
        <div
          className="fixed bottom-20 right-5 z-50 flex flex-col rounded-xl shadow-2xl border border-base-300 bg-base-100"
          style={{ width: 380, maxWidth: "94vw", height: 480, maxHeight: "70vh" }}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-3 py-2 border-b border-base-300 bg-base-200 rounded-t-xl">
            <div className="font-semibold text-sm">MediaOS Safe AI</div>
            <div className="text-xs opacity-70">
              {status?.ollama === "ok" ? (
                <span className="text-success">● local</span>
              ) : status ? (
                <span className="text-warning">○ offline</span>
              ) : (
                "…"
              )}
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-3 space-y-3 text-sm">
            {messages.map((m, i) => (
              <div
                key={i}
                className={
                  m.role === "user"
                    ? "chat chat-end"
                    : "chat chat-start"
                }
              >
                <div
                  className={
                    "chat-bubble whitespace-pre-wrap " +
                    (m.role === "user" ? "chat-bubble-primary" : "chat-bubble-secondary")
                  }
                  style={{ maxWidth: "95%" }}
                >
                  {m.content}
                </div>
              </div>
            ))}
            {busy && (
              <div className="chat chat-start">
                <div className="chat-bubble chat-bubble-secondary">Thinking…</div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="p-2 border-t border-base-300 flex gap-2">
            <input
              className="input input-bordered input-sm flex-1"
              placeholder='e.g. "list music from the 90s"'
              value={input}
              disabled={busy}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send()}
            />
            <button type="button"
              className="btn btn-sm btn-primary"
              disabled={busy || !input.trim()}
              onClick={send}
            >
              Send
            </button>
          </div>
        </div>
      )}
    </>
  );
}
