import React, { useState, useEffect, useCallback } from "react";
import { LibraryModuleShell, TeachEmpty, SkeletonLoader } from "../components/ui.jsx";

function SmartListsPage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState(null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    fetch("/api/smartlists")
      .then(r => { if (!r.ok) throw new Error("Failed to load smart lists"); return r.json(); })
      .then(d => setItems(d.items || d || []))
      .catch(e => setMsg(String(e.message || e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const create = async () => {
    if (!name.trim()) return;
    setBusy(true); setMsg(null);
    try {
      const r = await fetch("/api/smartlists", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim() }),
      });
      if (!r.ok) throw new Error("Create failed");
      setName("");
      load();
    } catch (e) { setMsg(String(e.message || e)); }
    finally { setBusy(false); }
  };

  return (
    <LibraryModuleShell
      title="Smart lists"
      active="all"
      onNav={() => {}}
      nav={[{ id: "all", label: "Lists" }]}
      tools={<>
        <input className="mr-search" placeholder="New list name…" value={name} onChange={e => setName(e.target.value)} onKeyDown={e => e.key === "Enter" && create()} />
        <button type="button" className="btn btn-sm btn-primary" disabled={busy || !name.trim()} onClick={create}>Create</button>
        <button type="button" className="btn btn-sm btn-ghost" onClick={load}>Refresh</button>
      </>}
    >
      {msg && <div className="alert alert-info text-xs py-2 mb-3">{msg}</div>}
      {loading && <SkeletonLoader kind="table" rows={5} />}
      {!loading && (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
          {(items || []).map(it => (
            <div key={it.id} className="card bg-base-200 shadow-sm">
              <div className="card-body p-4 gap-1">
                <div className="font-medium">{it.name}</div>
                <div className="text-xs opacity-50">{it.item_count ?? it.count ?? 0} items · {it.media_type || "mixed"}</div>
              </div>
            </div>
          ))}
        </div>
      )}
      {!loading && !items.length && (
        <TeachEmpty title="No smart lists yet" actionLabel="Create one" onAction={create}>
          <p>Smart lists group library items by rules (genre, year, status, tracking).</p>
        </TeachEmpty>
      )}
    </LibraryModuleShell>
  );
}
export default SmartListsPage;
export { SmartListsPage };
