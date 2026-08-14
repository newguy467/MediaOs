import React, { useState, useEffect, useCallback } from "react";
import { LibraryModuleShell, TeachEmpty, SkeletonLoader } from "../components/ui.jsx";

export default function TrackingPage() {
  const [items, setItems] = useState([]);
  const [status, setStatus] = useState("");
  const [tab, setTab] = useState("list");
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setMsg(null);
    const q = status ? `?status=${encodeURIComponent(status)}` : "";
    fetch("/api/tracking" + q)
      .then(r => { if (!r.ok) throw new Error("Tracking load failed"); return r.json(); })
      .then(d => setItems(d.items || d || []))
      .catch(e => setMsg(String(e.message || e)))
      .finally(() => setLoading(false));
  }, [status]);

  useEffect(() => { load(); }, [load]);

  const setItemStatus = async (id, newStatus) => {
    setBusy(true); setMsg(null);
    try {
      const r = await fetch(`/api/tracking/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
      });
      if (!r.ok) throw new Error("Update failed");
      load();
    } catch (e) { setMsg(String(e.message || e)); }
    finally { setBusy(false); }
  };

  return (
    <LibraryModuleShell
      title="Tracking"
      active={tab}
      onNav={setTab}
      nav={[
        { id: "list", label: "All" },
        { id: "planned", label: "Planned" },
        { id: "in_progress", label: "In progress" },
        { id: "completed", label: "Completed" },
      ]}
      tools={<>
        <select className="select select-sm select-bordered" value={status} onChange={e => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="planned">Planned</option>
          <option value="in_progress">In progress</option>
          <option value="completed">Completed</option>
          <option value="dropped">Dropped</option>
          <option value="on_hold">On hold</option>
        </select>
        <button type="button" className="btn btn-sm btn-ghost" onClick={load}>Refresh</button>
      </>}
    >
      {msg && <div className="alert alert-warning text-xs py-2 mb-3">{msg}</div>}
      {loading && <SkeletonLoader kind="table" rows={8} />}

      {!loading && (
        <div className="overflow-x-auto">
          <table className="table table-sm">
            <thead><tr><th>Title</th><th>Type</th><th>Status</th><th>Progress</th><th>Rating</th><th></th></tr></thead>
            <tbody>
              {(items || []).map(it => (
                <tr key={it.id}>
                  <td className="text-sm font-medium">{it.title || "—"}</td>
                  <td className="text-xs opacity-60">{it.media_type || "—"}</td>
                  <td><span className="badge badge-sm">{it.status || "—"}</span></td>
                  <td className="text-xs">{Math.round(it.progress_percent || 0)}%</td>
                  <td className="text-xs">{it.rating ?? "—"}</td>
                  <td className="flex gap-1">
                    <button type="button" className="btn btn-xs" disabled={busy} onClick={() => setItemStatus(it.id, "in_progress")}>Play</button>
                    <button type="button" className="btn btn-xs btn-primary" disabled={busy} onClick={() => setItemStatus(it.id, "completed")}>Done</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!items.length && (
            <TeachEmpty title="Nothing tracked yet" actionLabel="Open library" onAction={() => window.location.hash = "#movies"}>
              <p>Track movies, TV, games, books and more with status, progress, and ratings.</p>
              <p>Items appear when you mark them from library pages or import history.</p>
            </TeachEmpty>
          )}
        </div>
      )}
    </LibraryModuleShell>
  );
}
