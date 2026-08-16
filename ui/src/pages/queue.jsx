import React, { useState, useEffect, useCallback, useRef } from "react";
import Ic, { Icons, P } from "../icons.jsx";
import { getToken, setToken, getAdvanced, setAdvancedFlag, AUTH_TOKEN_KEY } from "../storage.js";
import { api, TMDB, adultFetch } from "../api.js";
import { PageChrome, PosterTile, LibraryModuleShell, MediaDetailShell, LibraryLegend, LibraryHeader, MediaCard, StatusBadgeStack, libraryStatuses, CollectionProgressWidget, TeachEmpty, AddModal } from "../components/ui.jsx";
import { InteractiveResultsPanel, InteractiveResultsTable, MediaPlayer, HlsVideo } from "../components/media.jsx";

function QueuePage() {
  async function torrentAction(hash, action) {
    if (!hash) return;
    await fetch(`/api/queue/torrent/${encodeURIComponent(hash)}/${action}`, {method:'POST'}).catch(e => { console.warn(e); if (typeof setMsg === 'function') setMsg(String(e.message || e)); });
  }
  function TorrentControls({ hash, category }) {
    if (!hash) return null;
    async function setPrio(p) {
      await fetch(`/api/queue/torrent/${encodeURIComponent(hash)}/priority?priority=${p}`, {method:'POST'}).catch(e => { console.warn(e); if (typeof setMsg === 'function') setMsg(String(e.message || e)); });
    }
    async function setCat(c) {
      await fetch(`/api/queue/torrent/${encodeURIComponent(hash)}/category?category=${encodeURIComponent(c)}`, {method:'POST'}).catch(e => { console.warn(e); if (typeof setMsg === 'function') setMsg(String(e.message || e)); });
    }
    async function forceStart() {
      await fetch(`/api/queue/torrent/${encodeURIComponent(hash)}/force-start?value=true`, {method:'POST'}).catch(e => { console.warn(e); if (typeof setMsg === 'function') setMsg(String(e.message || e)); });
    }
    const cats = ['mediaos','mediaos-tv','mediaos-music','mediaos-books','mediaos-audiobooks','mediaos-comics'];
    return (
      <div className="flex flex-wrap gap-1 items-center">
        <div className="join">
          <button type="button" className="btn btn-xs join-item" title="Pause" onClick={()=>torrentAction(hash,'pause')}>Pause</button>
          <button type="button" className="btn btn-xs join-item" title="Resume" onClick={()=>torrentAction(hash,'resume')}>Resume</button>
          <button type="button" className="btn btn-xs join-item" title="Recheck" onClick={()=>torrentAction(hash,'recheck')}>Recheck</button>
          <button type="button" className="btn btn-xs join-item" title="Force start" onClick={forceStart}>Force</button>
        </div>
        <select className="select select-bordered select-xs w-24" defaultValue="" title="Priority"
          onChange={e=>{ if(e.target.value) setPrio(Number(e.target.value)); e.target.value=''; }}>
          <option value="" disabled>Priority</option>
          <option value="1">Top</option>
          <option value="2">High</option>
          <option value="3">Normal</option>
          <option value="4">Low</option>
          <option value="5">Bottom</option>
        </select>
        <select className="select select-bordered select-xs w-32" defaultValue={category||''} title="Category"
          onChange={e=>{ if(e.target.value) setCat(e.target.value); }}>
          <option value="" disabled>Category</option>
          {cats.map(c=><option key={c} value={c}>{c}</option>)}
        </select>
      </div>
    );
  }
  const [items, setItems] = useState([]);
  const [qSel, setQSel] = useState({});
  const qSelIds = Object.keys(qSel);
  const [loading, setLoading] = useState(true);
  const [hist, setHist] = useState({downloads:[], events:[]});
  const [tab, setTab] = useState('queue');
  const [live, setLive] = useState(false);
  const [mediaFilter, setMediaFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [histStatus, setHistStatus] = useState('all');
  const [histQuery, setHistQuery] = useState('');
  const [groupBy, setGroupBy] = useState('none'); // none | media_type | indexer

  const load = () => {
    api.queue.list().then(d=>{ setItems(d); setLoading(false); }).catch(()=>{ setItems([]); setLoading(false); });
    api.queue.history().then(setHist).catch(()=>setHist({downloads:[],events:[]}));
  };
  useEffect(() => {
    load();
    let es;
    try {
      es = new EventSource('/api/sse/events');
      setLive(true);
      es.addEventListener('queue', (ev) => {
        try {
          const data = JSON.parse(ev.data || '{}');
          const incoming = data.items || [];
          if (!incoming.length) { load(); return; }
          setItems(prev => {
            const byId = Object.fromEntries(incoming.map(x => [x.download_id, x]));
            const prevIds = new Set(prev.map(p => p.download_id));
            const newIds = incoming.some(x => !prevIds.has(x.download_id));
            if (newIds || prev.length !== incoming.length) {
              load();
              return prev;
            }
            return prev.map(row => {
              const liveRow = byId[row.download_id];
              if (!liveRow) return row;
              return {
                ...row,
                progress: liveRow.progress != null ? liveRow.progress : row.progress,
                status: liveRow.status || row.status,
                qbit_state: liveRow.qbit_state || row.qbit_state,
              };
            });
          });
        } catch (e) {}
      });
      es.onerror = () => setLive(false);
      es.onopen = () => setLive(true);
    } catch (e) { setLive(false); }
    const i = setInterval(load, 30000);
    return () => { try { es && es.close(); } catch(e){} clearInterval(i); };
  }, []);

  const removeItem = async (id, { blocklist = false, deleteFiles = false } = {}) => {
    const qs = new URLSearchParams();
    if (blocklist) qs.set('blocklist', '1');
    if (deleteFiles) qs.set('delete_files', '1');
    const url = `/api/queue/${id}` + (qs.toString() ? '?' + qs.toString() : '');
    try {
      if (api.queue.remove) await api.queue.remove(id);
      else await fetch(url, { method: 'DELETE' });
      // optional blocklist endpoint
      if (blocklist) {
        await fetch(`/api/queue/${id}/blocklist`, { method: 'POST' }).catch(e => { console.warn(e); if (typeof setMsg === 'function') setMsg(String(e.message || e)); });
      }
    } catch (e) {}
    load();
  };

  const retryFailed = async (d) => {
    try {
      await fetch(`/api/queue/${d.download_id}/retry`, { method: 'POST' });
    } catch (e) {}
    load();
  };

  const filteredQueue = (items || []).filter(q => {
    if (mediaFilter !== 'all' && (q.media_type || '') !== mediaFilter) return false;
    if (statusFilter !== 'all') {
      const st = (q.qbit_state || q.status || '').toLowerCase();
      if (statusFilter === 'active' && !(st.includes('down') || st.includes('grab') || st.includes('meta'))) return false;
      if (statusFilter === 'stalled' && !st.includes('stall')) return false;
      if (statusFilter === 'done' && !(q.progress >= 0.99 || st.includes('up') || st.includes('seed'))) return false;
    }
    return true;
  });

  // group rows
  const groups = (() => {
    if (groupBy === 'none') return { 'All': filteredQueue };
    const map = {};
    for (const q of filteredQueue) {
      const key = groupBy === 'indexer' ? (q.indexer || 'Unknown indexer') : (q.media_type || 'other');
      (map[key] = map[key] || []).push(q);
    }
    return map;
  })();

  const filteredHist = (hist.downloads || []).filter(d => {
    if (histStatus !== 'all' && (d.status || '') !== histStatus) return false;
    if (histQuery) {
      const q = histQuery.toLowerCase();
      const hay = `${d.title||''} ${d.release_title||''} ${d.indexer||''}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  const filteredEvents = (hist.events || []).filter(e => {
    if (histQuery) {
      const q = histQuery.toLowerCase();
      const hay = `${e.event||''} ${e.message||''} ${e.release_title||''}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  function renderQueueRow(q) {
    const pct = q.progress != null ? Math.round(q.progress * 100) : null;
    const st = (q.qbit_state || q.status || '').toLowerCase();
    const isFailed = st.includes('fail') || st.includes('error');
    return (
      <div key={q.download_id} className="card bg-base-200 shadow-sm relative">
          <div className="absolute top-2 left-2 z-10" onClick={e=>e.stopPropagation()}>
            <input type="checkbox" className="checkbox checkbox-xs checkbox-primary" checked={!!qSel[q.download_id||q.hash]}
              onChange={e=>{ setQSel(prev=>{ const n={...prev}; const k=q.download_id||q.hash; if(e.target.checked) n[k]=true; else delete n[k]; return n; }); }} />
          </div>
        <div className="card-body p-3 gap-2">
          <div className="flex justify-between gap-3 items-start">
            <div className="min-w-0">
              <div className="font-medium text-sm truncate">{q.title}</div>
              <div className="text-xs opacity-50 truncate">{q.release_title}</div>
              {q.episode && <div className="text-xs opacity-60">{q.episode}</div>}
            </div>
            <div className="flex flex-wrap items-center gap-2 shrink-0 justify-end">
              <span className="badge badge-sm badge-outline">{q.media_type || '—'}</span>
              {q.indexer && <span className="badge badge-sm badge-ghost">{q.indexer}</span>}
              <span className="text-xs font-mono">{pct != null ? pct + '%' : '—'}</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <progress
              className={"progress h-2 flex-1 " + (pct === 100 ? "progress-success" : isFailed ? "progress-error" : "progress-primary")}
              value={pct != null ? pct : 0}
              max="100"
            />
            <span className="text-xs opacity-60 w-28 text-right truncate">{q.qbit_state || q.status}</span>
            {q.quality_score != null && <span className="text-xs font-mono opacity-50">score {q.quality_score}</span>}
          </div>
          <div className="flex flex-wrap gap-2 items-center">
            <TorrentControls hash={q.torrent_hash} category={q.category} />
            {isFailed && (
              <button type="button" className="btn btn-xs btn-warning" onClick={()=>retryFailed(q)}>Retry search</button>
            )}
            <div className="dropdown dropdown-end ml-auto">
              <label tabIndex={0} className="btn btn-ghost btn-xs text-error">Remove ▾</label>
              <ul tabIndex={0} className="dropdown-content z-20 menu p-2 shadow bg-base-100 rounded-box w-52 text-sm">
                <li><button type="button" onClick={()=>removeItem(q.download_id)}>Remove from queue</button></li>
                <li><button type="button" onClick={()=>removeItem(q.download_id, { deleteFiles: true })}>Remove + delete files</button></li>
                <li><button type="button" onClick={()=>removeItem(q.download_id, { blocklist: true })}>Remove + blocklist release</button></li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4 max-w-5xl">
      <div className="flex flex-wrap justify-between gap-3 items-start">
        <div>
          <h1 className="mr-page-title">Queue &amp; History</h1>
          <p className="text-sm text-base-content/50">
            Live download progress via SSE
            <span className={"ml-2 badge badge-sm " + (live ? "badge-success" : "badge-ghost")}>
              {live ? "LIVE" : "polling"}
            </span>
          </p>
        </div>
        <button type="button" className="btn btn-sm" onClick={load}>Refresh</button>
      </div>
      <div className="tabs tabs-boxed w-fit flex-wrap">
        <a className={`tab ${tab==='queue'?'tab-active':''}`} onClick={()=>setTab('queue')}>Queue ({filteredQueue.length})</a>
        <a className={`tab ${tab==='history'?'tab-active':''}`} onClick={()=>setTab('history')}>History</a>
        <a className={`tab ${tab==='events'?'tab-active':''}`} onClick={()=>setTab('events')}>Events</a>
      </div>

      {tab==='queue' && (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2 items-center">
            <select className="select select-bordered select-xs" value={mediaFilter} onChange={e=>setMediaFilter(e.target.value)}>
              <option value="all">All types</option>
              <option value="movie">Movies</option>
              <option value="tv">TV</option>
              <option value="music">Music</option>
              <option value="book">Books</option>
              <option value="audiobook">Audiobooks</option>
              <option value="comic">Comics</option>
              <option value="manga">Manga</option>
            </select>
            <select className="select select-bordered select-xs" value={statusFilter} onChange={e=>setStatusFilter(e.target.value)}>
              <option value="all">All states</option>
              <option value="active">Active</option>
              <option value="stalled">Stalled</option>
              <option value="done">Done / seeding</option>
            </select>
            <select className="select select-bordered select-xs" value={groupBy} onChange={e=>setGroupBy(e.target.value)}>
              <option value="none">No grouping</option>
              <option value="media_type">Group by type</option>
              <option value="indexer">Group by indexer</option>
            </select>
          </div>
          {filteredQueue.length===0 ? (
            loading ? <div className="opacity-40 text-sm p-4">Loading queue…</div> : <div className="opacity-40 text-sm p-4">Queue empty</div>
          ) : Object.entries(groups).map(([gname, rows]) => (
            <div key={gname} className="space-y-2">
              {groupBy !== 'none' && <div className="text-xs font-semibold opacity-60 uppercase tracking-wide pt-2">{gname} ({rows.length})</div>}
              {rows.map(renderQueueRow)}
            </div>
          ))}
        </div>
      )}

      {tab==='history' && (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <input className="input input-bordered input-xs w-48" placeholder="Search title / release…" value={histQuery} onChange={e=>setHistQuery(e.target.value)} />
            <select className="select select-bordered select-xs" value={histStatus} onChange={e=>setHistStatus(e.target.value)}>
              <option value="all">All statuses</option>
              <option value="grabbed">Grabbed</option>
              <option value="organized">Organized</option>
              <option value="failed">Failed</option>
              <option value="downloading">Downloading</option>
            </select>
          </div>
          <div className="overflow-x-auto">
            <table className="table table-sm">
              <thead><tr><th>When</th><th>Title</th><th>Status</th><th>Indexer</th><th>Score</th><th></th></tr></thead>
              <tbody>
                {filteredHist.length===0 ? (
                  <tr><td colSpan={6} className="opacity-40 text-sm">No history yet</td></tr>
                ) : filteredHist.map(d=>(
                  <tr key={d.download_id}>
                    <td className="text-xs font-mono whitespace-nowrap">{d.added_at?new Date(d.added_at).toLocaleString():''}</td>
                    <td className="text-sm">{d.title}<div className="text-xs opacity-50">{d.release_title}</div></td>
                    <td><span className={"badge badge-sm " + (d.status==='failed'?'badge-error':d.status==='organized'?'badge-success':'')}>{d.status}</span></td>
                    <td className="text-xs">{d.indexer||'—'}</td>
                    <td className="font-mono text-xs">{d.quality_score??'—'}</td>
                    <td>
                      {d.status==='failed' && (
                        <button type="button" className="btn btn-ghost btn-xs" onClick={()=>retryFailed(d)}>Retry</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab==='events' && (
        <div className="space-y-3">
          <input className="input input-bordered input-xs w-64" placeholder="Filter events…" value={histQuery} onChange={e=>setHistQuery(e.target.value)} />
          <div className="overflow-x-auto">
            <table className="table table-sm">
              <thead><tr><th>When</th><th>Event</th><th>Message</th></tr></thead>
              <tbody>
                {filteredEvents.length===0 ? (
                  <tr><td colSpan={3} className="opacity-40 text-sm">No events</td></tr>
                ) : filteredEvents.map(e=>(
                  <tr key={e.id}>
                    <td className="text-xs font-mono whitespace-nowrap">{e.created_at?new Date(e.created_at).toLocaleString():''}</td>
                    <td><span className="badge badge-sm">{e.event}</span></td>
                    <td className="text-sm">{e.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}



export { QueuePage };
