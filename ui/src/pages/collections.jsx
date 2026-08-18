import { useState, useEffect } from "react";
function CollectionsPage() {
  const [rows, setRows] = useState([]);
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [selected, setSelected] = useState(null);

  const load = () =>
    fetch("/api/collections")
      .then((r) => r.json())
      .then((d) => setRows(Array.isArray(d) ? d : d.items || d.collections || []))
      .catch((e) => setMsg(String(e)));

  useEffect(() => {
    load();
  }, []);

  const search = () => {
    if (!q.trim()) return;
    setBusy(true);
    fetch("/api/collections/search?query=" + encodeURIComponent(q.trim()))
      .then((r) => r.json())
      .then((d) => setResults(Array.isArray(d) ? d : d.results || []))
      .catch((e) => setMsg(String(e)))
      .finally(() => setBusy(false));
  };

  const add = async (r) => {
    setBusy(true);
    setMsg("");
    try {
      await fetch("/api/collections", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tmdb_id: r.id || r.tmdb_id, add_all: true }),
      }).then(async (x) => {
        if (!x.ok) throw new Error((await x.json().catch(() => ({}))).detail || x.statusText);
      });
      setResults([]);
      setQ("");
      load();
      setMsg("Collection tracked");
    } catch (e) {
      setMsg(String(e.message || e));
    }
    setBusy(false);
  };

  const remove = async (id) => {
    if (!confirm("Remove this collection from tracking?")) return;
    await fetch("/api/collections/" + id, { method: "DELETE" }).catch(e => { try { setMsg(String(e.message||e)); } catch(_) { console.warn(e); } });
    if (selected?.id === id) setSelected(null);
    load();
  };

  return (
    <div className="p-4 space-y-4 max-w-5xl">
      <div>
        <h1 className="mr-page-title">Movie Collections</h1>
        <p className="text-sm opacity-60">Track TMDb collections and see how much of each saga you own.</p>
      </div>
      {msg && <div className="alert alert-info text-xs py-2">{msg}</div>}
      <div className="flex gap-2 flex-wrap">
        <input
          className="input input-bordered input-sm flex-1 min-w-[12rem]"
          placeholder="Search TMDb collections…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
        />
        <button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={search}>
          {busy ? "…" : "Search"}
        </button>
        <button type="button" className="btn btn-sm btn-ghost" onClick={load}>
          Refresh
        </button>
      </div>
      {results.length > 0 && (
        <div className="card bg-base-200 border border-base-content/10">
          <div className="card-body p-3 gap-2">
            <h2 className="text-sm font-semibold">Search results</h2>
            {results.map((r, i) => (
              <div key={i} className="flex justify-between items-center gap-2 p-2 bg-base-300 rounded">
                <div className="min-w-0">
                  <div className="font-medium text-sm truncate">{r.name || r.title}</div>
                  {r.overview && <div className="text-[10px] opacity-50 line-clamp-2">{r.overview}</div>}
                </div>
                <button type="button" className="btn btn-xs btn-primary shrink-0" disabled={busy} onClick={() => add(r)}>
                  Track
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        {rows.map((c) => {
          const total = c.total_parts || c.parts || 0;
          const owned = c.owned || c.owned_count || 0;
          const pct = total ? Math.round((100 * owned) / total) : 0;
          return (
            <div
              key={c.id}
              className={
                "p-3 bg-base-200 rounded border cursor-pointer " +
                (selected?.id === c.id ? "border-primary" : "border-transparent")
              }
              onClick={() => setSelected(c)}
            >
              <div className="flex justify-between gap-2">
                <div className="font-medium">{c.name}</div>
                <button
                  type="button"
                  className="btn btn-ghost btn-xs"
                  onClick={(e) => {
                    e.stopPropagation();
                    remove(c.id);
                  }}
                >
                  ×
                </button>
              </div>
              <div className="text-xs opacity-60 mt-1">
                {c.progress_label || `${owned} / ${total} owned`}
              </div>
              <progress className="progress progress-primary h-2 w-full mt-2" value={pct} max="100" />
              <div className="text-[10px] opacity-40 mt-1">{pct}%</div>
            </div>
          );
        })}
      </div>
      {!rows.length && (
        <p className="text-sm opacity-50">No collections yet — search TMDb and click Track.</p>
      )}
      {selected && (
        <div className="card bg-base-200 border border-primary/30">
          <div className="card-body p-4 gap-2">
            <h2 className="card-title text-base">{selected.name}</h2>
            <p className="text-xs opacity-60">{selected.overview || selected.progress_label || ""}</p>
            <p className="text-xs">
              TMDb id: {selected.tmdb_id || selected.external_id || "—"} · id: {selected.id}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

export { CollectionsPage };
