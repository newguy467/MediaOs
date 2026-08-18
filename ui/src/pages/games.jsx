import { useState, useEffect, useCallback } from "react";
import { LibraryModuleShell, PosterTile, TeachEmpty, SkeletonLoader } from "../components/ui.jsx";

export default function GamesPage({ setPage }) {
  const [games, setGames] = useState([]);
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);
  const [wanted, setWanted] = useState([]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState(null);
  const [tab, setTab] = useState("library");
  const [releases, setReleases] = useState([]);
  const [installJobs, setInstallJobs] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [checked, setChecked] = useState({});
  const checkedIds = Object.keys(checked);
  const [platforms, setPlatforms] = useState([]);
  const [platformDrafts, setPlatformDrafts] = useState({});
  const [savingPlatformId, setSavingPlatformId] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setMsg(null);
    Promise.all([
      fetch("/api/games").then(r => { if (!r.ok) throw new Error("Failed to load games"); return r.json(); }),
      fetch("/api/games/wanted").then(r => { if (!r.ok) throw new Error("Failed to load wanted"); return r.json(); }),
    ])
      .then(([g, w]) => {
        setGames(g.items || g.games || (Array.isArray(g) ? g : []));
        setWanted(w.items || []);
      })
      .catch(e => setMsg(String(e.message || e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const loadPlatforms = useCallback(() => {
    fetch("/api/games/platforms/list")
      .then(r => { if (!r.ok) throw new Error("Failed to load platforms"); return r.json(); })
      .then(rows => setPlatforms(Array.isArray(rows) ? rows : []))
      .catch(() => {});
  }, []);

  useEffect(() => { loadPlatforms(); }, [loadPlatforms]);

  // Seed a draft per platform for the emulator-command input, without
  // clobbering text the user is actively editing on a refresh.
  useEffect(() => {
    setPlatformDrafts(prev => {
      const next = { ...prev };
      let changed = false;
      platforms.forEach(p => {
        if (!(p.id in next)) { next[p.id] = p.emulator_command || ""; changed = true; }
      });
      return changed ? next : prev;
    });
  }, [platforms]);

  const bulkMonitor = async (monitored) => {
    setBusy(true); setMsg(null);
    try {
      const r = await fetch('/api/games/bulk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: checkedIds.map(Number), monitored }),
      });
      if (!r.ok) throw new Error((await r.json().catch(()=>({}))).detail || 'Bulk failed');
      setChecked({});
      load();
    } catch (e) { setMsg(String(e.message || e)); }
    finally { setBusy(false); }
  };


  const searchMeta = async () => {
    if (!q.trim()) return;
    setBusy(true); setMsg(null);
    try {
      const r = await fetch("/api/games/metadata/search?q=" + encodeURIComponent(q) + "&limit=25");
      if (!r.ok) throw new Error("Search failed");
      const d = await r.json();
      setResults(d.results || []);
      setTab("search");
      if (!(d.results || []).length) {
        setMsg(d.igdb_configured === false
          ? "IGDB not configured — set IGDB credentials in Settings. Steam search may still work."
          : "No results");
      }
    } catch (e) { setMsg(String(e.message || e)); }
    finally { setBusy(false); }
  };

  const addFromMeta = async (row) => {
    setBusy(true); setMsg(null);
    try {
      const r = await fetch("/api/games/from-metadata", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: row.title, year: row.year, overview: row.overview,
          poster_path: row.poster_path, igdb_id: row.igdb_id,
          steam_appid: row.steam_appid, monitored: true,
        }),
      });
      if (!r.ok) throw new Error("Add failed");
      setMsg(`Added: ${row.title}`);
      load();
      setTab("library");
    } catch (e) { setMsg(String(e.message || e)); }
    finally { setBusy(false); }
  };


  const toggleGameMonitor = async (g) => {
    setBusy(true); setMsg(null);
    try {
      const r = await fetch('/api/games/' + g.id, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ monitored: !g.monitored }),
      });
      if (!r.ok) throw new Error('Update failed');
      load();
    } catch (e) { setMsg(String(e.message || e)); }
    finally { setBusy(false); }
  };



  const setTrackStatus = async (gameId, status) => {
    setBusy(true); setMsg(null);
    try {
      const r = await fetch('/api/tracking', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ game_id: gameId, status }),
      });
      if (!r.ok) throw new Error((await r.json().catch(()=>({}))).detail || 'Track failed');
      setMsg('Tracking: ' + String(status).replace(/_/g, ' '));
    } catch (e) { setMsg(String(e.message || e)); }
    finally { setBusy(false); }
  };


  const loadInstallJobs = () => fetch('/api/games/install-jobs').then(r=>r.json()).then(d=>setInstallJobs(d.items||[])).catch(()=>[]);

  const launchGame = async (gameId) => {
    setBusy(true); setMsg(null);
    try {
      const r = await fetch('/api/games/' + gameId + '/launch', { method: 'POST' });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.detail || 'No launch target');
      const primary = j.primary || (j.targets || [])[0];
      if (primary && primary.url) {
        window.location.href = primary.url;
        setMsg('Launching via ' + (primary.label || primary.kind));
      } else if (primary && primary.kind === 'emulator') {
        setMsg((primary.label || 'Emulator configured') + ' — use the "Launch via emulator" button below to run it.');
      } else if (primary && primary.path) {
        setMsg('Install path: ' + primary.path + ' (open on the host)');
      } else {
        setMsg(JSON.stringify(j));
      }
    } catch (e) { setMsg(String(e.message || e)); }
    finally { setBusy(false); }
  };

  const launchEmulator = async (gameId) => {
    setBusy(true); setMsg(null);
    try {
      const r = await fetch('/api/games/' + gameId + '/launch/emulator', { method: 'POST' });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.detail || 'Emulator launch failed');
      setMsg('Emulator launch queued — job #' + j.job_id + ' (' + j.status + ')');
      loadInstallJobs();
    } catch (e) { setMsg(String(e.message || e)); }
    finally { setBusy(false); }
  };

  const savePlatformEmulatorCommand = async (platformId, command) => {
    setSavingPlatformId(platformId); setMsg(null);
    try {
      const r = await fetch('/api/games/platforms/' + platformId, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ emulator_command: command }),
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.detail || 'Save failed');
      setPlatforms(prev => prev.map(p => p.id === platformId ? { ...p, emulator_command: j.emulator_command } : p));
      setMsg('Saved emulator command for ' + (j.name || 'platform'));
    } catch (e) { setMsg(String(e.message || e)); }
    finally { setSavingPlatformId(null); }
  };

  const searchReleases = async (gameId) => {
    setBusy(true); setMsg(null); setSelectedId(gameId);
    try {
      const r = await fetch(`/api/games/${gameId}/search-grab`, { method: "POST" });
      if (!r.ok) throw new Error("Release search failed");
      const d = await r.json();
      setReleases(d.results || d.items || []);
      setTab("releases");
      if (!(d.results || d.items || []).length) setMsg("No releases found");
    } catch (e) { setMsg(String(e.message || e)); }
    finally { setBusy(false); }
  };

  const releaseDownloadUrl = (r) => (r?.download_url || r?.magnet || r?.link || "").trim();
  const grabRelease = async (rel) => {
    if (!selectedId) return;
    setBusy(true); setMsg(null);
    try {
      const r = await fetch(`/api/games/${selectedId}/grab`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: rel.title, download_url: releaseDownloadUrl(rel), indexer: rel.indexer, size: rel.size || rel.size_bytes, seeders: rel.seeders, protocol: rel.protocol || "torrent" }),
      });
      if (!r.ok) throw new Error("Grab failed");
      setMsg(`Grabbed: ${rel.title || "release"}`);
      load();
    } catch (e) { setMsg(String(e.message || e)); }
    finally { setBusy(false); }
  };

  return (
    <LibraryModuleShell
      title="Games"
      active={tab}
      onNav={(id) => setTab(id)}
      nav={[
        { id: "library", label: "Library" },
        { id: "wanted", label: "Wanted" },
        { id: "search", label: "Search" },
        { id: "releases", label: "Releases" },
        { id: "platforms", label: "Platforms" },
      ]}
      tools={<>
        <input className="mr-search" placeholder="Search IGDB / Steam…" value={q}
          onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === "Enter" && searchMeta()} />
        <button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={searchMeta}>Search</button>
        <button type="button" className="btn btn-sm btn-ghost" disabled={loading} onClick={load}>Refresh</button>
      </>}
    >
      {installJobs.length > 0 && (
        <div className="card bg-base-200 mb-2"><div className="card-body p-3 gap-1">
          <div className="flex justify-between"><span className="text-xs font-semibold">Install jobs</span>
            <button type="button" className="btn btn-ghost btn-xs" onClick={()=>setInstallJobs([])}>Hide</button></div>
          {installJobs.slice(0,8).map(j=>(
            <div key={j.id} className="text-xs font-mono">
              #{j.id} game={j.game_id} <span className="badge badge-xs">{j.status}</span>
              {j.kind && j.kind !== 'install' && <span className="badge badge-xs badge-ghost ml-1">{j.kind}</span>}
              <pre className="text-[10px] opacity-60 max-h-20 overflow-auto whitespace-pre-wrap">{(j.log_text||'').slice(0,400)}</pre>
            </div>
          ))}
        </div></div>
      )}
      {msg && <div className="alert alert-info text-xs py-2 mb-3">{msg}</div>}
      {loading && <SkeletonLoader rows={12} />}

      {tab === "library" && !loading && (
        <>
          {checkedIds.length > 0 && (
            <div className="card bg-base-200 mb-3">
              <div className="card-body p-3 gap-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs opacity-60">{checkedIds.length} selected</span>
                  {(games || []).length > 0 && (
                    <button type="button" className="btn btn-xs btn-ghost" onClick={() => {
                      const n = {}; (games || []).forEach(g => { n[g.id] = true; }); setChecked(n);
                    }}>Select all</button>
                  )}
                  <button type="button" className="btn btn-xs" disabled={busy} onClick={() => bulkMonitor(true)}>Monitor</button>
                  <button type="button" className="btn btn-xs" disabled={busy} onClick={() => bulkMonitor(false)}>Unmonitor</button>
                  <button type="button" className="btn btn-xs btn-ghost" onClick={() => setChecked({})}>Clear</button>
                </div>
              </div>
            </div>
          )}
          <div className="poster-grid">
            {(games || []).map(g => (
              <div key={g.id} className="relative group">
                <label className={`absolute top-2 left-2 z-10 transition-opacity ${checked[g.id] ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`} onClick={e => e.stopPropagation()}>
                  <input type="checkbox" className="checkbox checkbox-xs checkbox-primary" checked={!!checked[g.id]}
                    onChange={e => {
                      setChecked(prev => {
                        const n = { ...prev };
                        if (e.target.checked) n[g.id] = true; else delete n[g.id];
                        return n;
                      });
                    }} />
                </label>
                <PosterTile
                  title={g.title}
                  year={g.year}
                  poster={g.poster_path}
                  status={g.status}
                  onClick={() => searchReleases(g.id)}
                />
              </div>
            ))}
          </div>
          {!games.length && (
            <TeachEmpty title="No games yet" actionLabel="Search metadata" onAction={() => setTab("search")}>
              <p>Add games from IGDB or Steam, then search releases and grab like Movies/TV.</p>
              <p>Enable the Games module in Module Store if this page is empty by design.</p>
            </TeachEmpty>
          )}
        </>
      )}

      {tab === "wanted" && (
        <div className="space-y-3">
          {checkedIds.length > 0 && (
            <div className="card bg-base-200">
              <div className="card-body p-3 gap-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs opacity-60">{checkedIds.length} selected</span>
                  {(wanted || []).length > 0 && (
                    <button type="button" className="btn btn-xs btn-ghost" onClick={() => {
                      const n = {}; (wanted || []).forEach(g => { n[g.id] = true; }); setChecked(n);
                    }}>Select all</button>
                  )}
                  <button type="button" className="btn btn-xs" disabled={busy} onClick={() => bulkMonitor(true)}>Monitor</button>
                  <button type="button" className="btn btn-xs" disabled={busy} onClick={() => bulkMonitor(false)}>Unmonitor</button>
                  <button type="button" className="btn btn-xs btn-ghost" onClick={() => setChecked({})}>Clear</button>
                </div>
              </div>
            </div>
          )}
          <div className="overflow-x-auto">
            <table className="table table-sm">
              <thead><tr><th className="w-8"></th><th>Title</th><th>Year</th><th>Status</th><th></th></tr></thead>
              <tbody>
                {(wanted || []).map(g => (
                  <tr key={g.id}>
                    <td>
                      <input type="checkbox" className="checkbox checkbox-xs checkbox-primary" checked={!!checked[g.id]}
                        onChange={e => {
                          setChecked(prev => {
                            const n = { ...prev };
                            if (e.target.checked) n[g.id] = true; else delete n[g.id];
                            return n;
                          });
                        }} />
                    </td>
                    <td>{g.title}</td>
                    <td>{g.year || "—"}</td>
                    <td><span className="badge badge-sm">{g.status}</span></td>
                    <td><button type="button" className="btn btn-xs btn-primary" disabled={busy} onClick={() => searchReleases(g.id)}>Search</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!wanted.length && (
              <TeachEmpty title="No wanted games" actionLabel="Search to add" onAction={() => setTab("search")}>
                <p>Monitored games missing a download appear here.</p>
              </TeachEmpty>
            )}
          </div>
        </div>
      )}

      {tab === "search" && (
        <div className="space-y-2">
          {(results || []).map((row, i) => (
            <div key={i} className="flex gap-3 items-start bg-base-200 rounded-lg p-3">
              {row.poster_path && <img src={row.poster_path} alt="" className="w-14 h-20 object-cover rounded" />}
              <div className="flex-1 min-w-0">
                <div className="font-medium text-sm">{row.title} {row.year ? `(${row.year})` : ""}</div>
                <div className="text-xs opacity-50 line-clamp-2">{row.overview || ""}</div>
              </div>
              <button type="button" className="btn btn-xs btn-primary" disabled={busy} onClick={() => addFromMeta(row)}>Add</button>
            </div>
          ))}
          {!results.length && (
            <TeachEmpty title="Search for a game" actionLabel="Type above & Search" onAction={searchMeta}>
              <p>Uses IGDB and Steam metadata. Configure IGDB in Settings for best results.</p>
            </TeachEmpty>
          )}
        </div>
      )}

      {tab === "releases" && (
        <div className="space-y-2">
          {selectedId && (
            <div className="flex gap-2 flex-wrap items-center">
              <span className="text-xs opacity-60">Game #{selectedId}</span>
              <button type="button" className="btn btn-xs" disabled={busy} onClick={async () => {
                const g = (games || []).find(x => x.id === selectedId) || (wanted || []).find(x => x.id === selectedId);
                if (g) await toggleGameMonitor(g);
              }}>Toggle monitored</button>
              <button type="button" className="btn btn-xs btn-accent" disabled={busy || !selectedId} onClick={() => launchGame(selectedId)}>Launch</button>
              {(() => {
                const selGame = (games || []).find(x => x.id === selectedId) || (wanted || []).find(x => x.id === selectedId);
                const selPlatform = selGame ? platforms.find(p => p.id === selGame.platform_id) : null;
                if (!selPlatform || !(selPlatform.emulator_command || '').trim()) return null;
                return (
                  <button type="button" className="btn btn-xs btn-accent" disabled={busy || !selectedId}
                    onClick={() => launchEmulator(selectedId)}>
                    Launch via {selPlatform.name} emulator
                  </button>
                );
              })()}
              <button type="button" className="btn btn-xs" disabled={busy || !selectedId} onClick={async ()=>{
                setBusy(true); setMsg(null);
                try {
                  const r = await fetch('/api/games/'+selectedId+'/install',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
                  const j = await r.json().catch(()=>({}));
                  if (!r.ok) throw new Error(j.detail||'Install failed');
                  setMsg('Marked installed: '+(j.install_path||j.path||''));
                  load();
                } catch(e){ setMsg(String(e.message||e)); }
                finally { setBusy(false); }
              }}>Install</button>
              <button type="button" className="btn btn-xs btn-ghost" onClick={()=>{ loadInstallJobs(); setMsg(null); }}>Install jobs</button>
              <select className="select select-bordered select-xs" defaultValue="" disabled={busy || !selectedId}
                onChange={e=>{ if(e.target.value && selectedId) { setTrackStatus(selectedId, e.target.value); e.target.value=''; } }}>
                <option value="">Track…</option>
                <option value="planned">Planned</option>
                <option value="in_progress">In progress</option>
                <option value="completed">Completed</option>
                <option value="dropped">Dropped</option>
              </select>
              <button type="button" className="btn btn-xs btn-primary" disabled={busy} onClick={() => searchReleases(selectedId)}>Search again</button>
              <button type="button" className="btn btn-xs btn-ghost" onClick={() => setTab("library")}>Back to library</button>
            </div>
          )}
          <div className="overflow-x-auto">
          <table className="table table-sm">
            <thead><tr><th>Release</th><th>Indexer</th><th>Size</th><th>Seeders</th><th></th></tr></thead>
            <tbody>
              {(releases || []).map((rel, i) => (
                <tr key={i}>
                  <td className="text-sm">{rel.title}</td>
                  <td className="text-xs opacity-60">{rel.indexer || "—"}</td>
                  <td className="text-xs">{rel.size_bytes ? `${Math.round(rel.size_bytes/1e6)} MB` : "—"}</td>
                  <td>{rel.seeders ?? "—"}</td>
                  <td className="flex gap-1">
                    <button type="button" className="btn btn-xs btn-primary" disabled={busy} onClick={() => grabRelease(rel)}>Grab</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!releases.length && (
            <TeachEmpty title="No releases" actionLabel="Back to library" onAction={() => setTab("library")}>
              <p>Select a game from Library or Wanted and run Search releases.</p>
            </TeachEmpty>
          )}
        </div>
      </div>
      )}

      {tab === "platforms" && (
        <div className="space-y-2">
          <p className="text-xs opacity-60">
            Optional per-platform emulator launch command. Placeholders: <code>{"{rom}"}</code> (install/library path, auto-quoted),{" "}
            <code>{"{title}"}</code>, <code>{"{id}"}</code>. Leave blank to disable emulator launch for a platform.
          </p>
          <div className="overflow-x-auto">
            <table className="table table-sm">
              <thead><tr><th>Platform</th><th>Emulator command</th><th></th></tr></thead>
              <tbody>
                {(platforms || []).map(p => (
                  <tr key={p.id}>
                    <td className="text-sm whitespace-nowrap">{p.name}</td>
                    <td>
                      <input
                        className="input input-bordered input-xs w-full font-mono"
                        placeholder="e.g. retroarch -L /cores/snes9x_libretro.so {rom}"
                        value={platformDrafts[p.id] ?? ""}
                        onChange={e => setPlatformDrafts(prev => ({ ...prev, [p.id]: e.target.value }))}
                      />
                    </td>
                    <td>
                      <button
                        type="button"
                        className="btn btn-xs btn-primary"
                        disabled={savingPlatformId === p.id}
                        onClick={() => savePlatformEmulatorCommand(p.id, platformDrafts[p.id] ?? "")}
                      >
                        {savingPlatformId === p.id ? "Saving…" : "Save"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!platforms.length && (
              <TeachEmpty title="No platforms yet" actionLabel="Seed defaults" onAction={async () => {
                setBusy(true); setMsg(null);
                try {
                  const r = await fetch("/api/games/platforms/seed", { method: "POST" });
                  if (!r.ok) throw new Error("Seed failed");
                  loadPlatforms();
                } catch (e) { setMsg(String(e.message || e)); }
                finally { setBusy(false); }
              }}>
                <p>Seed the default platform list (PC, Steam, GOG, consoles), then set an emulator command per platform here.</p>
              </TeachEmpty>
            )}
          </div>
        </div>
      )}
    </LibraryModuleShell>
  );
}
