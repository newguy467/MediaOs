import React, { useState, useEffect } from "react";
import { LibraryModuleShell, PosterTile, TeachEmpty } from "../components/ui.jsx";

export function LibraryBrowserPage({ movies = [], series = [], music = [], books = [], setMiniPlayer, setPage }) {
  const [tab, setTab] = useState("movies");
  const [q, setQ] = useState("");
  const [tool, setTool] = useState("play"); // play | duplicates | paths | metadata
  const [dups, setDups] = useState([]);
  const [paths, setPaths] = useState([]);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [pathForm, setPathForm] = useState({ name: "default", container_prefix: "/data", host_prefix: "/mnt/media" });
  const [dryPath, setDryPath] = useState("");
  const [dryResult, setDryResult] = useState(null);
  const [metaIds, setMetaIds] = useState("");
  const [metaProgress, setMetaProgress] = useState(null);

  const loadDups = () => fetch("/api/library/duplicates").then(r => r.json()).then(d => setDups(d.items || [])).catch(() => setDups([]));
  const loadPaths = () => fetch("/api/library/path-maps").then(r => r.json()).then(d => setPaths(d.items || [])).catch(() => setPaths([]));

  useEffect(() => {
    if (tool === "duplicates") loadDups();
    if (tool === "paths") loadPaths();
  }, [tool]);

  const downloaded = (list) => (list || []).filter(x => x.file_path || x.status === "downloaded");
  let items = [];
  if (tab === "movies") items = downloaded(movies);
  else if (tab === "tv") items = series || [];
  else if (tab === "music") items = downloaded(music);
  else if (tab === "books") items = downloaded(books);
  if (q.trim()) {
    const f = q.toLowerCase();
    items = items.filter(x => (x.title || "").toLowerCase().includes(f));
  }

  async function mergeDup(keepId, dropIds) {
    setBusy(true); setMsg(null);
    try {
      const r = await fetch("/api/library/duplicates/merge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keep_id: keepId, drop_ids: dropIds }),
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.detail || "merge failed");
      setMsg(`Merged into #${keepId}, dropped ${j.dropped?.length || 0}`);
      loadDups();
    } catch (e) { setMsg(String(e.message || e)); }
    finally { setBusy(false); }
  }

  async function addPathMap() {
    setBusy(true); setMsg(null);
    try {
      const r = await fetch("/api/library/path-maps", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(pathForm),
      });
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || "save failed");
      setMsg("Path map saved");
      loadPaths();
    } catch (e) { setMsg(String(e.message || e)); }
    finally { setBusy(false); }
  }

  async function runDry() {
    const r = await fetch("/api/library/path-maps/dry-run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: dryPath }),
    }).then(x => x.json());
    setDryResult(r);
  }

  async function bulkRefresh() {
    const ids = metaIds.split(/[\s,]+/).map(Number).filter(Boolean);
    if (!ids.length) { setMsg("Enter media item ids"); return; }
    setBusy(true); setMetaProgress({ done: 0, total: ids.length, errors: [], jobId: null });
    try {
      const enq = await fetch("/api/library/metadata/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ item_ids: ids }),
      }).then(r => r.json());
      if (!enq.ok && !enq.job_id) {
        // Fallback: sequential single refreshes if job API unavailable
        for (let i = 0; i < ids.length; i++) {
          try {
            const r = await fetch(`/api/library/metadata/refresh/${ids[i]}`, { method: "POST" });
            if (!r.ok) throw new Error(String(ids[i]));
          } catch (e) {
            setMetaProgress(p => ({ ...p, errors: [...(p?.errors || []), String(e.message || e)] }));
          }
          setMetaProgress(p => ({ ...p, done: i + 1, total: ids.length }));
        }
        setMsg("Bulk refresh finished (legacy)");
        setBusy(false);
        return;
      }
      const jobId = enq.job_id;
      setMetaProgress(p => ({ ...p, jobId, total: enq.total || ids.length }));
      setMsg(`Job ${jobId} queued`);
      // Poll until complete (SSE also available on metadata_job channel)
      for (let n = 0; n < 600; n++) {
        await new Promise(r => setTimeout(r, 500));
        const st = await fetch(`/api/library/metadata/jobs/${jobId}`).then(r => r.json()).catch(() => null);
        if (!st) continue;
        setMetaProgress({
          done: st.done || 0,
          total: st.total || ids.length,
          errors: (st.results || []).filter(x => !x.ok).map(x => String(x.id) + (x.error ? `: ${x.error}` : "")),
          jobId,
        });
        if (st.status === "completed" || st.status === "failed") {
          setMsg(st.status === "completed" ? `Job ${jobId} done (${st.ok||0} ok, ${st.failed||0} failed)` : `Job ${jobId} failed`);
          break;
        }
      }
    } catch (e) {
      setMsg(String(e));
    }
    setBusy(false);
  }

  return (
    <LibraryModuleShell
      title="Library"
      active={tab}
      onNav={setTab}
      nav={[
        { id: "movies", label: "Movies" },
        { id: "tv", label: "TV" },
        { id: "music", label: "Music" },
        { id: "books", label: "Books" },
      ]}
      tools={
        <div className="flex flex-wrap gap-2 items-center">
          <div className="join">
            {["play", "duplicates", "paths", "metadata"].map(t => (
              <button key={t} type="button" className={"btn btn-xs join-item " + (tool === t ? "btn-primary" : "")}
                onClick={() => setTool(t)}>{t}</button>
            ))}
          </div>
          {tool === "play" && <input className="mr-search" placeholder="Filter…" value={q} onChange={e => setQ(e.target.value)} />}
        </div>
      }
    >
      {msg && <div className="alert alert-info text-xs py-2 mb-2">{msg}</div>}

      {tool === "play" && (
        <>
          <p className="text-xs opacity-60 mb-3">Play downloaded items in the built-in player without Jellyfin.</p>
          <div className="poster-grid">
            {items.map(item => (
              <PosterTile
                key={item.id}
                title={item.title}
                year={item.year}
                poster={item.poster_path}
                status={item.status}
                onClick={() => {
                  if (setMiniPlayer && item.file_path) {
                    setMiniPlayer({ title: item.title, path: item.file_path, itemId: item.id });
                  } else if (tab === "tv" && setPage) {
                    setPage("tv");
                  }
                }}
              />
            ))}
          </div>
          {!items.length && (
            <TeachEmpty title="Nothing playable here" actionLabel="Open Movies" onAction={() => setPage && setPage("movies")}>
              <p>Downloaded items with a file path appear here.</p>
            </TeachEmpty>
          )}
        </>
      )}

      {tool === "duplicates" && (
        <div className="space-y-3">
          <p className="text-xs opacity-60">Groups sharing external id or title+year. Keep one row; others are deleted after merging empty fields.</p>
          <button type="button" className="btn btn-xs" onClick={loadDups}>Refresh</button>
          {(dups || []).map((g, i) => (
            <div key={i} className="card bg-base-200">
              <div className="card-body p-3 gap-1">
                <div className="text-xs opacity-50">{g.reason}: {g.key}</div>
                <div className="text-sm">{(g.titles || []).join(" · ")}</div>
                <div className="flex gap-2 flex-wrap items-center">
                  <span className="text-xs font-mono">ids: {(g.ids || []).join(", ")}</span>
                  {(g.ids || []).length >= 2 && (
                    <button type="button" className="btn btn-xs btn-primary" disabled={busy}
                      onClick={() => mergeDup(g.ids[0], g.ids.slice(1))}>
                      Keep #{g.ids[0]}, drop rest
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
          {!dups.length && <p className="text-sm opacity-50">No duplicate groups found.</p>}
        </div>
      )}

      {tool === "paths" && (
        <div className="space-y-4 max-w-xl">
          <p className="text-xs opacity-60">Map container paths to host paths for organize/stream dry-runs.</p>
          <div className="grid gap-2">
            <input className="input input-bordered input-sm" placeholder="Name" value={pathForm.name}
              onChange={e => setPathForm(f => ({ ...f, name: e.target.value }))} />
            <input className="input input-bordered input-sm font-mono" placeholder="Container prefix" value={pathForm.container_prefix}
              onChange={e => setPathForm(f => ({ ...f, container_prefix: e.target.value }))} />
            <input className="input input-bordered input-sm font-mono" placeholder="Host prefix" value={pathForm.host_prefix}
              onChange={e => setPathForm(f => ({ ...f, host_prefix: e.target.value }))} />
            <button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={addPathMap}>Save path map</button>
          </div>
          <ul className="text-sm space-y-1">
            {(paths || []).map(m => (
              <li key={m.id} className="font-mono text-xs bg-base-200 p-2 rounded">
                #{m.id} {m.name}: {m.container_prefix} → {m.host_prefix}
              </li>
            ))}
          </ul>
          <div className="flex gap-2">
            <input className="input input-bordered input-sm flex-1 font-mono" placeholder="/data/movies/x" value={dryPath}
              onChange={e => setDryPath(e.target.value)} />
            <button type="button" className="btn btn-sm" onClick={runDry}>Dry-run</button>
          </div>
          {dryResult && <pre className="text-xs bg-base-300 p-2 rounded">{JSON.stringify(dryResult, null, 2)}</pre>}
        </div>
      )}

      {tool === "metadata" && (
        <div className="space-y-3 max-w-lg">
          <p className="text-xs opacity-60">Bulk metadata refresh by media item id (comma or space separated).</p>
          <textarea className="textarea textarea-bordered w-full font-mono text-xs" rows={3} value={metaIds}
            onChange={e => setMetaIds(e.target.value)} placeholder="101 102 103" />
          <button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={bulkRefresh}>
            {busy ? "Refreshing…" : "Refresh selected"}
          </button>
          {metaProgress && (
            <div className="text-xs">
              Progress: {metaProgress.done}/{metaProgress.total}
              {metaProgress.errors?.length > 0 && <div className="text-error">Errors: {metaProgress.errors.join(", ")}</div>}
            </div>
          )}
        </div>
      )}
    </LibraryModuleShell>
  );
}

export default LibraryBrowserPage;
