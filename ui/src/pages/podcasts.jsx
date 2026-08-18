import { useState, useEffect, useCallback } from "react";
import { LibraryModuleShell, TeachEmpty, SkeletonLoader } from "../components/ui.jsx";

function PodcastsPage({ setMiniPlayer }) {
  const [items, setItems] = useState([]);
  const [results, setResults] = useState([]);
  const [episodes, setEpisodes] = useState([]);
  const [selected, setSelected] = useState(null);
  const [q, setQ] = useState("");
  const [tab, setTab] = useState("library");
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [checked, setChecked] = useState({}); // bulk selection (ids)
  const checkedIds = Object.keys(checked);
  const [epChecked, setEpChecked] = useState({});
  const epCheckedIds = Object.keys(epChecked);

  const load = useCallback(() => {
    setLoading(true);
    fetch("/api/podcasts")
      .then((r) => {
        if (!r.ok) throw new Error("Load failed");
        return r.json();
      })
      .then((d) => setItems(Array.isArray(d) ? d : d.items || []))
      .catch((e) => setMsg(String(e.message || e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const bulkMonitor = async (monitored) => {
    setBusy(true); setMsg(null);
    try {
      const r = await fetch('/api/podcasts/bulk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: checkedIds.map(Number), monitored }),
      });
      if (!r.ok) throw new Error((await r.json().catch(()=>({}))).detail || 'Bulk failed');
      setChecked({});
      load();
    } catch (e) {
      setMsg(String(e.message || e));
    } finally {
      setBusy(false);
    }
  };
  const bulkAutoDownload = async (auto_download) => {
    setBusy(true); setMsg(null);
    try {
      const r = await fetch('/api/podcasts/bulk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: checkedIds.map(Number), auto_download }),
      });
      if (!r.ok) throw new Error((await r.json().catch(()=>({}))).detail || 'Bulk failed');
      setChecked({});
      load();
    } catch (e) {
      setMsg(String(e.message || e));
    } finally {
      setBusy(false);
    }
  };
  const selectAllVisible = () => {
    const n = {};
    (items || []).forEach((p) => { n[p.id] = true; });
    setChecked(n);
  };


  const search = async () => {
    if (!q.trim()) return;
    setBusy(true);
    setMsg(null);
    try {
      const r = await fetch("/api/podcasts/search?query=" + encodeURIComponent(q));
      if (!r.ok) throw new Error("Search failed");
      const d = await r.json();
      setResults(Array.isArray(d) ? d : d.results || d.items || []);
      setTab("search");
    } catch (e) {
      setMsg(String(e.message || e));
    } finally {
      setBusy(false);
    }
  };

  const add = async (row) => {
    setBusy(true);
    try {
      const feed_url = row.feed_url || row.url || row.feedUrl;
      if (!feed_url) throw new Error("No feed URL");
      const r = await fetch("/api/podcasts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ feed_url, monitored: true }),
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.detail || "Add failed");
      setMsg("Subscribed");
      load();
      setTab("library");
    } catch (e) {
      setMsg(String(e.message || e));
    } finally {
      setBusy(false);
    }
  };

  const openPodcast = async (p) => {
    setSelected(p);
    setTab("episodes");
    setBusy(true);
    setMsg(null);
    try {
      const r = await fetch(`/api/podcasts/${p.id}/episodes`);
      if (!r.ok) throw new Error("Could not load episodes");
      const d = await r.json();
      setEpisodes(Array.isArray(d) ? d : d.items || []);
    } catch (e) {
      setMsg(String(e.message || e));
      setEpisodes([]);
    } finally {
      setBusy(false);
    }
  };

  const refreshFeed = async (p) => {
    setBusy(true);
    setMsg(null);
    try {
      const r = await fetch(`/api/podcasts/${p.id}/refresh`, { method: "POST" });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.detail || "Refresh failed");
      setMsg("Feed refreshed");
      if (selected && selected.id === p.id) await openPodcast(p);
      load();
    } catch (e) {
      setMsg(String(e.message || e));
    } finally {
      setBusy(false);
    }
  };


  const bulkDownloadEps = async () => {
    if (!selected || !epCheckedIds.length) return;
    setBusy(true); setMsg(null);
    let n = 0;
    try {
      for (const id of epCheckedIds) {
        const ep = (episodes || []).find(e => String(e.id) === String(id));
        if (!ep || ep.file_path || ep.status === 'downloaded') continue;
        const r = await fetch(`/api/podcasts/${selected.id}/episodes/${id}/download`, { method: 'POST' });
        if (r.ok) n += 1;
      }
      setMsg(`Queued download for ${n} episode(s)`);
      setEpChecked({});
      await openPodcast(selected);
    } catch (e) { setMsg(String(e.message || e)); }
    finally { setBusy(false); }
  };

  const downloadEp = async (ep) => {
    if (!selected) return;
    setBusy(true);
    setMsg(null);
    try {
      const r = await fetch(`/api/podcasts/${selected.id}/episodes/${ep.id}/download`, { method: "POST" });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.detail || "Download failed");
      setMsg(`Downloading: ${ep.title}`);
      await openPodcast(selected);
    } catch (e) {
      setMsg(String(e.message || e));
    } finally {
      setBusy(false);
    }
  };

  const playEp = (ep) => {
    if (!setMiniPlayer) {
      setMsg("Player not available");
      return;
    }
    // Prefer episode id so /api/player can resolve file or stream URL server-side
    setMiniPlayer({
      title: ep.title,
      path: ep.file_path || undefined,
      podcastEpisodeId: ep.id,
    });
  };

  const removePodcast = async (p) => {
    if (!window.confirm(`Unsubscribe from “${p.title}”?`)) return;
    setBusy(true);
    try {
      await fetch(`/api/podcasts/${p.id}`, { method: "DELETE" });
      if (selected && selected.id === p.id) {
        setSelected(null);
        setTab("library");
      }
      load();
    } catch (e) {
      setMsg(String(e.message || e));
    } finally {
      setBusy(false);
    }
  };

  const fmtDur = (sec) => {
    if (sec == null) return "";
    const m = Math.floor(Number(sec) / 60);
    const s = Math.floor(Number(sec) % 60);
    return `${m}:${String(s).padStart(2, "0")}`;
  };

  return (
    <LibraryModuleShell
      title="Podcasts"
      active={tab === "episodes" ? "library" : tab}
      onNav={(id) => {
        setTab(id);
        if (id !== "episodes") setSelected(null);
      }}
      nav={[
        { id: "library", label: "Library" },
        { id: "search", label: "Search" },
      ]}
      tools={
        <>
          <input
            className="mr-search"
            placeholder="Search podcasts…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && search()}
          />
          <button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={search}>
            Search
          </button>
          <button type="button" className="btn btn-sm btn-ghost" onClick={load}>
            Refresh
          </button>
        </>
      }
    >
      {msg && <div className="alert alert-info text-xs py-2 mb-3">{msg}</div>}
      {loading && <SkeletonLoader rows={8} />}

      {tab === "library" && !loading && (
        <>
          {checkedIds.length > 0 && (
            <div className="card bg-base-200 mb-3">
              <div className="card-body p-3 gap-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs opacity-60">{checkedIds.length} selected</span>
                  <button type="button" className="btn btn-xs" disabled={busy} onClick={() => bulkMonitor(true)}>Monitor</button>
                  <button type="button" className="btn btn-xs" disabled={busy} onClick={() => bulkMonitor(false)}>Unmonitor</button>
                  <button type="button" className="btn btn-xs" disabled={busy} onClick={() => bulkAutoDownload(true)}>Auto-DL on</button>
                  <button type="button" className="btn btn-xs" disabled={busy} onClick={() => bulkAutoDownload(false)}>Auto-DL off</button>
                  <button type="button" className="btn btn-xs btn-ghost" disabled={busy} onClick={() => setChecked({})}>Clear</button>
                </div>
              </div>
            </div>
          )}
          {(items || []).length > 0 && (
            <div className="flex gap-2 mb-2">
              <button type="button" className="btn btn-xs btn-ghost" onClick={selectAllVisible}>Select all</button>
              <span className="text-xs opacity-40 self-center">{(items || []).length} feeds</span>
            </div>
          )}
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
            {(items || []).map((p) => (
              <div key={p.id} className="card bg-base-200 shadow-sm relative group">
                <label className={`absolute top-2 left-2 z-10 transition-opacity ${checked[p.id] ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`} onClick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    className="checkbox checkbox-xs checkbox-primary"
                    checked={!!checked[p.id]}
                    onChange={(e) => {
                      setChecked((prev) => {
                        const n = { ...prev };
                        if (e.target.checked) n[p.id] = true;
                        else delete n[p.id];
                        return n;
                      });
                    }}
                  />
                </label>
                <div className="card-body p-2 gap-1">
                  <div className="aspect-square bg-base-300 rounded overflow-hidden flex items-center justify-center cursor-pointer" onClick={() => openPodcast(p)}>
                    {p.image || p.artwork_url || p.poster_path ? (
                      <img src={p.image || p.artwork_url || p.poster_path} alt="" className="w-full h-full object-cover" loading="lazy" />
                    ) : (
                      <span className="text-xs opacity-30">Podcast</span>
                    )}
                  </div>
                  <div className="font-medium text-xs line-clamp-2 min-h-[2rem]">{p.title}</div>
                  <div className="text-[10px] opacity-50 truncate">{p.author || ""}</div>
                  <div className="flex flex-wrap gap-1 items-center">
                    <span className={"badge badge-xs " + (p.monitored ? "badge-success" : "badge-ghost")}>{p.monitored ? "Mon" : "Off"}</span>
                    {p.auto_download && <span className="badge badge-xs badge-outline">Auto</span>}
                    {p.episode_count != null && <span className="text-[10px] opacity-40">{p.episode_count} eps</span>}
                  </div>
                  <div className="flex flex-wrap gap-1 mt-0.5">
                    <button type="button" className="btn btn-xs btn-primary" onClick={() => openPodcast(p)}>Eps</button>
                    <button type="button" className="btn btn-xs btn-ghost" disabled={busy} onClick={() => refreshFeed(p)}>Sync</button>
                    <button type="button" className="btn btn-xs btn-ghost text-error" disabled={busy} onClick={() => removePodcast(p)}>Del</button>
                  </div>
                </div>
              </div>
            ))}
          </div>
          {!items.length && (
            <TeachEmpty title="No podcasts yet" actionLabel="Search feeds" onAction={() => setTab("search")}>
              <p>Subscribe to podcast RSS feeds, sync episodes, download, and play in the built-in player.</p>
            </TeachEmpty>
          )}
        </>
      )}

      {tab === "episodes" && selected && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 flex-wrap">
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => { setTab("library"); setSelected(null); setEpChecked({}); }}>
              ← Library
            </button>
            <h2 className="font-semibold text-sm flex-1 truncate">{selected.title}</h2>
            <button type="button" className="btn btn-sm btn-ghost" disabled={busy} onClick={() => refreshFeed(selected)}>
              Sync feed
            </button>
          </div>
          {busy && !episodes.length && <SkeletonLoader rows={6} kind="list" />}
          {epCheckedIds.length > 0 && (
            <div className="flex gap-2 flex-wrap mb-2">
              <span className="text-xs opacity-60 self-center">{epCheckedIds.length} selected</span>
              <button type="button" className="btn btn-xs btn-primary" disabled={busy} onClick={bulkDownloadEps}>Download selected</button>
              <button type="button" className="btn btn-xs btn-ghost" onClick={() => setEpChecked({})}>Clear</button>
              <button type="button" className="btn btn-xs btn-ghost" onClick={() => {
                const n = {}; (episodes || []).forEach(e => { if (e.audio_url && !e.file_path) n[e.id] = true; });
                setEpChecked(n);
              }}>Select downloadable</button>
            </div>
          )}
          <ul className="space-y-1">
            {(episodes || []).map((ep) => (
              <li key={ep.id} className="flex gap-2 items-center p-2 rounded bg-base-200 text-sm">
                <input type="checkbox" className="checkbox checkbox-xs checkbox-primary" checked={!!epChecked[ep.id]}
                  onChange={e => {
                    setEpChecked(prev => {
                      const n = { ...prev };
                      if (e.target.checked) n[ep.id] = true; else delete n[ep.id];
                      return n;
                    });
                  }} />
                <div className="flex-1 min-w-0">
                  <div className="truncate font-medium">{ep.title}</div>
                  <div className="text-[10px] opacity-50">
                    {ep.pub_date || ""} {fmtDur(ep.duration_seconds) ? `· ${fmtDur(ep.duration_seconds)}` : ""} · {ep.status || "unknown"}
                  </div>
                </div>
                {(ep.file_path || ep.status === "downloaded") && (
                  <button type="button" className="btn btn-xs btn-primary" onClick={() => playEp(ep)}>
                    Play
                  </button>
                )}
                {ep.audio_url && !ep.file_path && ep.status !== "downloaded" && (
                  <button type="button" className="btn btn-xs" disabled={busy} onClick={() => downloadEp(ep)}>
                    Download
                  </button>
                )}
                {ep.audio_url && (
                  <button
                    type="button"
                    className="btn btn-xs btn-ghost"
                    onClick={() => setMiniPlayer && setMiniPlayer({ title: ep.title, podcastEpisodeId: ep.id })}
                    title="Stream via player (episode id)"
                  >
                    Stream
                  </button>
                )}
              </li>
            ))}
          </ul>
          {!episodes.length && !busy && (
            <p className="text-sm opacity-50">No episodes yet — try Sync feed.</p>
          )}
        </div>
      )}

      {tab === "search" && (
        <div className="space-y-2">
          {(results || []).map((row, i) => (
            <div key={i} className="flex gap-3 items-center bg-base-200 rounded-lg p-3">
              <div className="flex-1 min-w-0">
                <div className="font-medium text-sm">{row.title}</div>
                <div className="text-xs opacity-50 truncate">{row.feed_url || row.url || ""}</div>
              </div>
              <button type="button" className="btn btn-xs btn-primary" disabled={busy} onClick={() => add(row)}>
                Add
              </button>
            </div>
          ))}
          {!results.length && (
            <TeachEmpty title="Search Apple / RSS" actionLabel="Search" onAction={search}>
              <p>Find podcasts by name, then add the feed to your library.</p>
            </TeachEmpty>
          )}
        </div>
      )}
    </LibraryModuleShell>
  );
}

export { PodcastsPage };
export default PodcastsPage;
