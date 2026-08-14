import React, { useState, useEffect, useCallback, useRef } from "react";
import Ic, { Icons, P } from "../icons.jsx";
import { getToken, setToken, getAdvanced, setAdvancedFlag, AUTH_TOKEN_KEY } from "../storage.js";
import { api, TMDB, adultFetch } from "../api.js";
import { PageChrome, PosterTile, LibraryModuleShell, MediaDetailShell, LibraryLegend, LibraryHeader, MediaCard, StatusBadgeStack, libraryStatuses, CollectionProgressWidget, TeachEmpty, AddModal } from "../components/ui.jsx";
import { InteractiveResultsPanel, InteractiveResultsTable, MediaPlayer, HlsVideo } from "../components/media.jsx";

function ImportPage({ movies, series }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(null);
  const [msg, setMsg] = useState(null);
  const [err, setErr] = useState(null);
  const [mode, setMode] = useState({}); // path -> { type:'movie'|'episode', mediaId, season, episode, title, year }

  const refresh = useCallback(() => {
    setLoading(true); setErr(null);
    api.import.scan().then(setItems).catch(e=>setErr(String(e.message||e))).finally(()=>setLoading(false));
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  function setModeField(path, field, value) {
    setMode(m => ({ ...m, [path]: { type:'movie', ...(m[path]||{}), [field]: value } }));
  }

  async function doImport(item) {
    const m = mode[item.path] || { type: 'movie' };
    setBusy(item.path); setMsg(null); setErr(null);
    try {
      let res;
      if (m.type === 'episode') {
        res = await api.import.episode({
          source_path: item.path,
          episode_id: m.episodeId ? Number(m.episodeId) : undefined,
          series_id: m.seriesId ? Number(m.seriesId) : undefined,
          season: m.season != null && m.season !== '' ? Number(m.season) : (item.parsed?.season ?? undefined),
          episode: m.episode != null && m.episode !== '' ? Number(m.episode) : (item.parsed?.episode ?? undefined),
        });
      } else {
        res = await api.import.movie({
          source_path: item.path,
          media_item_id: m.mediaId ? Number(m.mediaId) : undefined,
          title: m.title || undefined,
          year: m.year ? Number(m.year) : (item.parsed?.year || undefined),
        });
      }
      setMsg(`Imported → ${res.dest}`);
      refresh();
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setBusy(null);
    }
  }

  function fmtSize(n) {
    if (!n) return '—';
    if (n > 1e9) return (n/1e9).toFixed(1) + ' GB';
    if (n > 1e6) return (n/1e6).toFixed(0) + ' MB';
    return n + ' B';
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="mr-page-title">Manual Import</h1>
          <p className="text-base-content/50 text-sm mt-1">Scan downloads and move files into your library</p>
        </div>
        <button type="button" className="btn btn-primary btn-sm" onClick={refresh} disabled={loading}>
          {loading ? 'Scanning…' : 'Rescan'}
        </button>
      </div>

      {msg && <div className="alert alert-success text-sm"><span>{msg}</span></div>}
      {err && <div className="alert alert-error text-sm"><span>{err}</span></div>}

      {loading ? (
        <div className="flex justify-center py-16"><span className="loading loading-spinner loading-lg text-primary"/></div>
      ) : items.length === 0 ? (
        <div className="text-center py-16 text-base-content/40">
          <div className="w-16 h-16 mx-auto mb-4 opacity-30"><Ic.Folder /></div>
          <p>No video files found in downloads</p>
          <p className="text-xs mt-2">Drop files into the downloads folder mounted at /downloads</p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map(item => {
            const m = mode[item.path] || { type: item.parsed?.season != null ? 'episode' : 'movie' };
            return (
              <div key={item.path} className="card mr-panel border-0">
                <div className="card-body p-4 gap-3">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="font-medium font-mono text-sm break-all">{item.name}</div>
                      <div className="text-xs text-base-content/50 mt-1 flex flex-wrap gap-2">
                        <span>{fmtSize(item.size)}</span>
                        {item.parsed?.resolution && <span className="badge badge-sm badge-ghost">{item.parsed.resolution}</span>}
                        {item.parsed?.source && <span className="badge badge-sm badge-ghost">{item.parsed.source}</span>}
                        {item.parsed?.codec && <span className="badge badge-sm badge-ghost">{item.parsed.codec}</span>}
                        {item.parsed?.season != null && <span className="badge badge-sm badge-secondary">S{String(item.parsed.season).padStart(2,'0')}E{String(item.parsed.episode||0).padStart(2,'0')}</span>}
                      </div>
                    </div>
                    <div className="flex gap-2 items-center">
                      <select className="select select-bordered select-sm" value={m.type||'movie'}
                        onChange={e=>setModeField(item.path,'type',e.target.value)}>
                        <option value="movie">Movie</option>
                        <option value="episode">TV episode</option>
                      </select>
                      <button type="button" className="btn btn-primary btn-sm" disabled={busy===item.path} onClick={()=>doImport(item)}>
                        {busy===item.path ? <span className="loading loading-spinner loading-xs"/> : 'Import'}
                      </button>
                    </div>
                  </div>

                  {m.type === 'movie' ? (
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                      <select className="select select-bordered select-sm" value={m.mediaId||''}
                        onChange={e=>setModeField(item.path,'mediaId',e.target.value)}>
                        <option value="">— link to library movie (optional) —</option>
                        {movies.map(mv => <option key={mv.id} value={mv.id}>{mv.title}{mv.year?` (${mv.year})`:''}</option>)}
                      </select>
                      <input className="input input-bordered input-sm" placeholder="Title if untracked"
                        value={m.title||''} onChange={e=>setModeField(item.path,'title',e.target.value)} />
                      <input className="input input-bordered input-sm" placeholder="Year" type="number"
                        value={m.year||item.parsed?.year||''} onChange={e=>setModeField(item.path,'year',e.target.value)} />
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                      <select className="select select-bordered select-sm" value={m.seriesId||''}
                        onChange={e=>setModeField(item.path,'seriesId',e.target.value)}>
                        <option value="">— select series —</option>
                        {series.map(s => <option key={s.id} value={s.id}>{s.title}</option>)}
                      </select>
                      <input className="input input-bordered input-sm" placeholder="Season"
                        type="number" value={m.season??item.parsed?.season??''}
                        onChange={e=>setModeField(item.path,'season',e.target.value)} />
                      <input className="input input-bordered input-sm" placeholder="Episode"
                        type="number" value={m.episode??item.parsed?.episode??''}
                        onChange={e=>setModeField(item.path,'episode',e.target.value)} />
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ── Quality Profiles (full editor) ─────────────────────────────────────── */


export { ImportPage };
