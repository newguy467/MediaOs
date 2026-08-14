import React, { useState, useEffect, useCallback } from "react";
import { LibraryModuleShell, TeachEmpty, SkeletonLoader, PosterTile } from "../components/ui.jsx";
import { InteractiveResultsPanel, grabPayload } from "../components/media.jsx";

/**
 * Manga module — library view is /api/comics/manga (comics tagged quality_profile=manga).
 * Search prefers MangaDex via comics search source=mangadex.
 */
export default function MangaPage({ setPage }) {
  const [items, setItems] = useState([]);
  const [results, setResults] = useState([]);
  const [q, setQ] = useState("");
  const [tab, setTab] = useState("library");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const [source, setSource] = useState("mangadex");
  const [ixResults, setIxResults] = useState(null);
  const [ixLoading, setIxLoading] = useState(false);
  const [ixId, setIxId] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    fetch("/api/comics/manga")
      .then((r) => {
        if (!r.ok) throw new Error("Failed to load manga library");
        return r.json();
      })
      .then((d) => setItems(Array.isArray(d) ? d : d.items || d.results || []))
      .catch((e) => setMsg(String(e.message || e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const search = async () => {
    if (!q.trim()) return;
    setBusy(true);
    setMsg(null);
    try {
      const r = await fetch(
        "/api/comics/search?query=" + encodeURIComponent(q.trim()) + "&source=" + encodeURIComponent(source)
      );
      if (!r.ok) throw new Error("Search failed");
      const d = await r.json();
      const rows = Array.isArray(d) ? d : d.results || d.items || [];
      setResults(rows);
      setTab("search");
      if (!rows.length) setMsg("No results — try another source or query");
    } catch (e) {
      setMsg(String(e.message || e));
    } finally {
      setBusy(false);
    }
  };

  const add = async (row) => {
    setBusy(true);
    setMsg(null);
    try {
      const body = {
        title: row.title || row.name,
        external_id: row.external_id || row.comicvine_id || row.id,
        year: row.year,
        monitored: true,
        overview: row.overview || row.description,
        poster_path: row.poster_path || row.image,
      };
      const r = await fetch("/api/comics", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.detail || "Add failed");
      if (j.id) {
        await fetch(`/api/comics/${j.id}/tag-manga`, { method: "PATCH" }).catch(() => {});
      }
      setMsg(`Added to manga library: ${body.title}`);
      load();
      setTab("library");
    } catch (e) {
      setMsg(String(e.message || e));
    } finally {
      setBusy(false);
    }
  };

  const searchMissing = async (id) => {
    setBusy(true);
    setMsg(null);
    try {
      const r = await fetch(`/api/comics/${id}/search`, { method: "POST" });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.detail || "Search failed");
      setMsg("Search queued");
    } catch (e) {
      setMsg(String(e.message || e));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id) => {
    if (!window.confirm("Remove this title from the library?")) return;
    setBusy(true);
    try {
      await fetch(`/api/comics/${id}`, { method: "DELETE" });
      load();
    } catch (e) {
      setMsg(String(e.message || e));
    } finally {
      setBusy(false);
    }
  };


  const openInteractive = async (id) => {
    setIxId(id);
    setIxLoading(true);
    setIxResults(null);
    try {
      const r = await fetch(`/api/comics/${id}/interactive-search`);
      const d = await r.json();
      setIxResults(d && !Array.isArray(d) ? d : { results: d?.results || d || [], rejected: [] });
    } catch (e) {
      setMsg(String(e.message || e));
      setIxResults({ results: [], rejected: [] });
    } finally {
      setIxLoading(false);
    }
  };
  const grabRel = async (rel) => {
    if (!ixId) return;
    setBusy(true);
    try {
      const r = await fetch(`/api/comics/${ixId}/grab`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(grabPayload(rel)),
      });
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        throw new Error(j.detail || "Grab failed");
      }
      setMsg("Grabbed: " + (rel.title || "release"));
      setIxResults(null);
      setIxId(null);
    } catch (e) {
      setMsg(String(e.message || e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <LibraryModuleShell
      title="Manga"
      active={tab}
      onNav={setTab}
      nav={[
        { id: "library", label: "Library" },
        { id: "search", label: "Search" },
      ]}
      tools={
        <>
          <select
            className="select select-bordered select-sm"
            value={source}
            onChange={(e) => setSource(e.target.value)}
            title="Metadata source"
          >
            <option value="mangadex">MangaDex</option>
            <option value="comicvine">ComicVine</option>
            <option value="all">All sources</option>
          </select>
          <input
            className="mr-search"
            placeholder="Search manga…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && search()}
          />
          <button type="button" className="btn btn-sm btn-primary" disabled={busy || !q.trim()} onClick={search}>
            Search
          </button>
          <button type="button" className="btn btn-sm btn-ghost" onClick={load}>
            Refresh
          </button>
          <button type="button" className="btn btn-sm btn-ghost" onClick={() => setPage && setPage("comics")}>
            Comics
          </button>
        </>
      }
    >
      <p className="text-xs opacity-50 mb-3">
        Manga titles live in the comics library with profile <code className="text-xs">manga</code>. Path: Settings → Library / Setup → manga folder.
      </p>
      {msg && <div className="alert alert-info text-xs py-2 mb-3">{msg}</div>}
      {loading && <SkeletonLoader rows={8} />}
      {tab === "library" && !loading && (
        <>
          <div className="poster-grid">
            {(items || []).map((item) => (
              <div key={item.id} className="relative group">
                <PosterTile
                  title={item.title || item.name}
                  year={item.year}
                  poster={item.poster_path || item.cover_url}
                  status={item.status}
                />
                <div className="absolute bottom-1 left-1 right-1 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    type="button"
                    className="btn btn-xs btn-primary flex-1"
                    disabled={busy}
                    onClick={() => searchMissing(item.id)}
                  >
                    Search
                  </button>
                  <button
                    type="button"
                    className="btn btn-xs btn-secondary"
                    disabled={busy || ixLoading}
                    onClick={() => openInteractive(item.id)}
                  >
                    IX
                  </button>
                  <button type="button" className="btn btn-xs btn-error" disabled={busy} onClick={() => remove(item.id)}>
                    ×
                  </button>
                </div>
              </div>
            ))}
          </div>
          {!items.length && (
            <TeachEmpty title="No manga yet" actionLabel="Search MangaDex" onAction={() => setTab("search")}>
              <p>
                Search MangaDex (or ComicVine), add a series, and it is tagged as manga. Releases use the same grab pipeline as comics.
              </p>
            </TeachEmpty>
          )}
        </>
      )}
      {tab === "search" && (
        <div className="space-y-2">
          {(results || []).map((row, i) => (
            <div key={i} className="flex gap-3 items-center bg-base-200 rounded-lg p-3">
              {(row.poster_path || row.image) && (
                <img src={row.poster_path || row.image} alt="" className="w-12 h-16 object-cover rounded" />
              )}
              <div className="flex-1 min-w-0">
                <div className="font-medium text-sm">{row.title || row.name}</div>
                <div className="text-xs opacity-50">{[row.year, row.publisher, row.source].filter(Boolean).join(" · ")}</div>
              </div>
              <button type="button" className="btn btn-xs btn-primary" disabled={busy} onClick={() => add(row)}>
                Add as manga
              </button>
            </div>
          ))}
          {!results.length && (
            <TeachEmpty title="Search manga" actionLabel="Search" onAction={search}>
              <p>Default source is MangaDex. Switch to ComicVine or All if needed.</p>
            </TeachEmpty>
          )}
        </div>
      )}
      {(ixLoading || ixResults) && (
        <InteractiveResultsPanel
          data={ixResults}
          loading={ixLoading}
          busy={busy}
          onGrab={grabRel}
          onClose={() => { setIxResults(null); setIxId(null); }}
        />
      )}
    </LibraryModuleShell>
  );
}


export { MangaPage };
