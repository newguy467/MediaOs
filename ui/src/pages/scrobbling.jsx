import React, { useState, useEffect, useCallback } from "react";
import { LibraryModuleShell, TeachEmpty, SkeletonLoader } from "../components/ui.jsx";

export default function ScrobblingPage() {
  const [tab, setTab] = useState("continue");
  const [cont, setCont] = useState([]);
  const [hist, setHist] = useState([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setMsg(null);
    Promise.all([
      fetch("/api/scrobble/continue?limit=30").then(r => { if (!r.ok) throw new Error("Continue load failed"); return r.json(); }),
      fetch("/api/scrobble/history?limit=80").then(r => { if (!r.ok) throw new Error("History load failed"); return r.json(); }),
    ])
      .then(([c, h]) => {
        setCont(c.items || []);
        setHist(h.items || []);
      })
      .catch(e => setMsg(String(e.message || e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <LibraryModuleShell
      title="History & Scrobbles"
      active={tab}
      onNav={setTab}
      nav={[
        { id: "continue", label: "Continue" },
        { id: "history", label: "History" },
      ]}
      tools={<button type="button" className="btn btn-sm btn-ghost" onClick={load}>Refresh</button>}
    >
      {msg && <div className="alert alert-warning text-xs py-2 mb-3">{msg}</div>}
      {loading && <SkeletonLoader kind="table" rows={8} />}

      {tab === "continue" && !loading && (
        <>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
            {(cont || []).map((row, i) => (
              <div key={i} className="card bg-base-200 p-3">
                <div className="font-medium text-sm">{row.title || (row.media_item_id ? `Media #${row.media_item_id}` : `Game #${row.game_id}`)}</div>
                <div className="text-xs opacity-50 mb-2">{row.media_type || ""} · {row.source || ""}</div>
                <progress className="progress progress-primary w-full" value={row.progress_percent || 0} max="100" />
                <div className="text-xs mt-1">{Math.round(row.progress_percent || 0)}%</div>
              </div>
            ))}
          </div>
          {!cont.length && (
            <TeachEmpty title="Nothing in progress" actionLabel="Open Movies" onAction={() => window.location.hash = "#movies"}>
              <p>Continue watching / playing appears here from local scrobbles or Jellyfin/Plex/Emby webhooks.</p>
              <p>Enable the Scrobbling module and point your media server at MediaOS webhooks.</p>
            </TeachEmpty>
          )}
        </>
      )}

      {tab === "history" && !loading && (
        <div className="overflow-x-auto">
          <table className="table table-sm">
            <thead><tr><th>When</th><th>Title</th><th>Type</th><th>Event</th><th>%</th><th>Source</th></tr></thead>
            <tbody>
              {(hist || []).map((row, i) => (
                <tr key={i}>
                  <td className="text-xs opacity-60">{row.created_at ? new Date(row.created_at).toLocaleString() : "—"}</td>
                  <td className="text-sm">{row.title || row.media_item_id || row.game_id || "—"}</td>
                  <td className="text-xs">{row.media_type || "—"}</td>
                  <td><span className="badge badge-xs">{row.event_type || "—"}</span></td>
                  <td>{Math.round(row.progress_percent || 0)}%</td>
                  <td className="text-xs opacity-50">{row.source || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!hist.length && (
            <TeachEmpty title="No scrobble history yet" actionLabel="Refresh" onAction={load}>
              <p>Play events from MediaOS player or external servers show up here.</p>
            </TeachEmpty>
          )}
        </div>
      )}
    </LibraryModuleShell>
  );
}
