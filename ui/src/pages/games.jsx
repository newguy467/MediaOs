import React, { useState, useEffect, useCallback } from "react";
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
  const [selectedId, setSelectedId] = useState(null);

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
      ]}
      tools={<>
        <input className="mr-search" placeholder="Search IGDB / Steam…" value={q}
          onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === "Enter" && searchMeta()} />
        <button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={searchMeta}>Search</button>
        <button type="button" className="btn btn-sm btn-ghost" disabled={loading} onClick={load}>Refresh</button>
      </>}
    >
      {msg && <div className="alert alert-info text-xs py-2 mb-3">{msg}</div>}
      {loading && <SkeletonLoader rows={12} />}

      {tab === "library" && !loading && (
        <>
          <div className="poster-grid">
            {(games || []).map(g => (
              <PosterTile
                key={g.id}
                title={g.title}
                year={g.year}
                poster={g.poster_path}
                status={g.status}
                onClick={() => searchReleases(g.id)}
              />
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
        <div className="overflow-x-auto">
          <table className="table table-sm">
            <thead><tr><th>Title</th><th>Year</th><th>Status</th><th></th></tr></thead>
            <tbody>
              {(wanted || []).map(g => (
                <tr key={g.id}>
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
      )}
    </LibraryModuleShell>
  );
}
