import React, { useState, useEffect, useCallback, useRef } from "react";
import Ic, { Icons, P } from "../icons.jsx";
import { getToken, setToken, getAdvanced, setAdvancedFlag, AUTH_TOKEN_KEY } from "../storage.js";
import { api, TMDB, adultFetch } from "../api.js";
import { PageChrome, PosterTile, LibraryModuleShell, MediaDetailShell, LibraryLegend, LibraryHeader, MediaCard, StatusBadgeStack, libraryStatuses, CollectionProgressWidget, TeachEmpty, AddModal } from "../components/ui.jsx";
import { InteractiveResultsPanel, InteractiveResultsTable, MediaPlayer, HlsVideo } from "../components/media.jsx";

function LogsPage() {
  const [files, setFiles] = useState([]);
  const [file, setFile] = useState('mediaos.log');
  const [lines, setLines] = useState([]);
  const [level, setLevel] = useState('');
  const [q, setQ] = useState('');
  const [auto, setAuto] = useState(true);
  const [err, setErr] = useState('');
  const [dir, setDir] = useState('');
  const bottomRef = React.useRef(null);

  const loadFiles = () => fetch('/api/logs').then(r=>r.json()).then(d=>{
    setFiles(d.files||[]); setDir(d.dir||'');
    if ((d.files||[]).length && !file) setFile(d.files[0].name);
  }).catch(e=>setErr(String(e)));

  const loadTail = () => {
    const params = new URLSearchParams({ file, lines: '300' });
    if (level) params.set('level', level);
    fetch('/api/logs/tail?' + params.toString()).then(r=>r.json()).then(d=>{
      setLines(d.lines||[]);
      if (d.error) setErr(d.error); else setErr('');
    }).catch(e=>setErr(String(e.message||e)));
  };

  const doSearch = async () => {
    if (!q.trim()) return loadTail();
    const params = new URLSearchParams({ file, q, limit: '200' });
    const d = await fetch('/api/logs/search?' + params.toString()).then(r=>r.json());
    setLines(d.matches||[]);
  };

  useEffect(() => { loadFiles(); }, []);
  useEffect(() => {
    loadTail();
    if (!auto) return;
    const id = setInterval(loadTail, 4000);
    return () => clearInterval(id);
  }, [file, level, auto]);

  useEffect(() => {
    if (auto && bottomRef.current) bottomRef.current.scrollIntoView({ behavior: 'smooth' });
  }, [lines, auto]);

  function colorize(line) {
    if (line.includes('| ERROR') || line.includes('| CRITICAL')) return 'text-error';
    if (line.includes('| WARNING') || line.includes('| WARN')) return 'text-warning';
    if (line.includes('| DEBUG')) return 'opacity-50';
    if (line.includes('| INFO')) return 'text-base-content/80';
    return '';
  }

  return (
    <div className="space-y-3 max-w-6xl">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h1 className="mr-page-title">Logs</h1>
          <p className="text-xs opacity-50 font-mono">{dir || '/config/logs'}</p>
        </div>
        <div className="flex flex-wrap gap-1.5 items-center">
          <select className="select select-bordered select-xs" value={file} onChange={e=>setFile(e.target.value)}>
            {(files.length?files:[{name:'mediaos.log'},{name:'mediaos-error.log'},{name:'mediaos-access.log'}]).map(f=>(
              <option key={f.name} value={f.name}>{f.name}{f.size!=null?` (${Math.round(f.size/1024)}KB)`:''}</option>
            ))}
          </select>
          <select className="select select-bordered select-xs" value={level} onChange={e=>setLevel(e.target.value)}>
            <option value="">All levels</option>
            <option value="DEBUG">DEBUG</option>
            <option value="INFO">INFO</option>
            <option value="WARNING">WARNING</option>
            <option value="ERROR">ERROR</option>
          </select>
          <input className="input input-bordered input-xs w-40" placeholder="Search…" value={q} onChange={e=>setQ(e.target.value)}
            onKeyDown={e=>e.key==='Enter'&&doSearch()} />
          <button type="button" className="btn btn-xs" onClick={doSearch}>Search</button>
          <button type="button" className="btn btn-xs" onClick={loadTail}>Refresh</button>
          <label className="label cursor-pointer gap-1 py-0">
            <input type="checkbox" className="toggle toggle-xs" checked={auto} onChange={e=>setAuto(e.target.checked)} />
            <span className="label-text text-xs">Live</span>
          </label>
          <select className="select select-bordered select-xs" defaultValue="INFO"
            onChange={async e=>{ await fetch('/api/logs/level?level='+e.target.value,{method:'POST'}); }}>
            <option value="DEBUG">Set DEBUG</option>
            <option value="INFO">Set INFO</option>
            <option value="WARNING">Set WARNING</option>
          </select>
        </div>
      </div>
      {err && <div className="alert alert-warning text-xs py-1">{err}</div>}
      <div className="bg-base-300 rounded-lg border border-base-content/10 p-2 font-mono text-[11px] leading-relaxed max-h-[70vh] overflow-auto">
        {lines.length===0 ? <div className="opacity-40 p-4">No log lines — generate traffic or wait for jobs</div> :
          lines.map((line,i)=>(
            <div key={i} className={'whitespace-pre-wrap break-all '+colorize(line)}>{line}</div>
          ))}
        <div ref={bottomRef} />
      </div>
      <p className="text-[10px] opacity-40">Files rotate at ~10MB (app/access) and ~5MB (error). Mount <code>/config/logs</code> to persist. Env: <code>LOG_LEVEL</code>, <code>MEDIAOS_LOG_DIR</code>.</p>
    </div>
  );
}

function ActivityPage({ movies, setPage }) {
  const [tab, setTab] = useState('history'); // queue | history | blocklist
  const [events, setEvents] = useState([]);
  const [blocklist, setBlocklist] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [mediaFilter, setMediaFilter] = useState('all');
  const [q, setQ] = useState('');
  const [dateRange, setDateRange] = useState('all'); // all | 24h | 7d | 30d
  const active = (movies||[]).filter(m=>m.status==='downloading');

  const loadHistory = () => {
    const params = new URLSearchParams({ limit: '250' });
    if (filter !== 'all') params.set('event', filter);
    if (mediaFilter !== 'all') params.set('media_type', mediaFilter);
    fetch('/api/activity?' + params.toString()).then(r=>r.json())
      .then(setEvents).catch(()=>setEvents([])).finally(()=>setLoading(false));
  };
  const loadBlocklist = () => {
    fetch('/api/blocklist').then(r=>r.json()).then(setBlocklist).catch(()=>setBlocklist([]));
  };

  useEffect(() => {
    if (tab === 'history') loadHistory();
    if (tab === 'blocklist') loadBlocklist();
    const id = setInterval(() => {
      if (tab === 'history') loadHistory();
    }, 15000);
    return () => clearInterval(id);
  }, [tab, filter, mediaFilter]);

  const kindMeta = {
    grabbed:   { label: 'Grabbed',   cls: 'badge-info',    icon: '↓' },
    imported:  { label: 'Imported',  cls: 'badge-success', icon: '✓' },
    organized: { label: 'Organized', cls: 'badge-success', icon: '✓' },
    upgraded:  { label: 'Upgraded',  cls: 'badge-warning', icon: '↑' },
    failed:    { label: 'Failed',    cls: 'badge-error',   icon: '✕' },
    blocked:   { label: 'Blocked',   cls: 'badge-error',   icon: '⊘' },
    searched:  { label: 'Searched',  cls: 'badge-ghost',   icon: '⌕' },
    deleted:   { label: 'Deleted',   cls: 'badge-ghost',   icon: '⌫' },
    renamed:   { label: 'Renamed',   cls: 'badge-ghost',   icon: '✎' },
    event:     { label: 'Event',     cls: 'badge-ghost',   icon: ' ' },
  };

  function relTime(iso) {
    if (!iso) return '—';
    const t = new Date(iso).getTime();
    if (isNaN(t)) return iso;
    const s = Math.floor((Date.now() - t) / 1000);
    if (s < 60) return s + 's ago';
    if (s < 3600) return Math.floor(s/60) + 'm ago';
    if (s < 86400) return Math.floor(s/3600) + 'h ago';
    if (s < 86400*7) return Math.floor(s/86400) + 'd ago';
    return new Date(iso).toLocaleString();
  }

  function withinRange(iso) {
    if (dateRange === 'all' || !iso) return true;
    const t = new Date(iso).getTime();
    if (isNaN(t)) return true;
    const age = Date.now() - t;
    if (dateRange === '24h') return age <= 86400000;
    if (dateRange === '7d') return age <= 86400000 * 7;
    if (dateRange === '30d') return age <= 86400000 * 30;
    return true;
  }

  let rows = events;
  if (q.trim()) {
    const qq = q.toLowerCase();
    rows = rows.filter(e =>
      (e.release_title||'').toLowerCase().includes(qq) ||
      (e.message||'').toLowerCase().includes(qq) ||
      (e.media_type||'').toLowerCase().includes(qq)
    );
  }
  rows = rows.filter(e => withinRange(e.created_at || e.date || e.added_at));

  const filteredBlocklist = (blocklist||[]).filter(b => {
    if (!q.trim()) return true;
    const qq = q.toLowerCase();
    return (b.release_title||'').toLowerCase().includes(qq) || (b.reason||'').toLowerCase().includes(qq);
  });

  return (
    <div className="space-y-4 max-w-6xl">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="mr-page-title">History</h1>
          <p className="text-sm opacity-50">Sonarr/Radarr-style — grabs, imports, failures, blocklist</p>
        </div>
        <div className="tabs tabs-boxed tabs-sm">
          <a className={'tab '+(tab==='queue'?'tab-active':'')} onClick={()=>setTab('queue')}>Queue ({active.length})</a>
          <a className={'tab '+(tab==='history'?'tab-active':'')} onClick={()=>setTab('history')}>History</a>
          <a className={'tab '+(tab==='blocklist'?'tab-active':'')} onClick={()=>setTab('blocklist')}>Blocklist</a>
        </div>
      </div>

      {tab==='queue' && (
        <div className="space-y-3">
          <div className="flex justify-between items-center flex-wrap gap-2">
            <h2 className="font-semibold text-sm">Downloading now</h2>
            <button type="button" className="btn btn-xs btn-primary" onClick={()=>setPage&&setPage('queue')}>Open full Queue</button>
          </div>
          {active.length===0 ? (
            <p className="text-sm opacity-40">Queue is empty</p>
          ) : (
            <table className="table table-sm">
              <thead><tr><th>Title</th><th>Type</th><th>Status</th><th></th></tr></thead>
              <tbody>
                {active.map(m=>(
                  <tr key={m.id}>
                    <td className="font-medium">{m.title}</td>
                    <td><span className="badge badge-outline badge-sm">{m.media_type||'movie'}</span></td>
                    <td><span className="badge badge-info badge-sm">Downloading</span></td>
                    <td><button type="button" className="btn btn-ghost btn-xs" onClick={()=>setPage&&setPage('queue')}>Details</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {tab==='history' && (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2 items-center">
            <select className="select select-bordered select-xs" value={filter} onChange={e=>setFilter(e.target.value)}>
              <option value="all">All events</option>
              <option value="grab">Grabbed</option>
              <option value="import">Imported</option>
              <option value="fail">Failed</option>
              <option value="block">Blocked</option>
              <option value="upgrade">Upgraded</option>
              <option value="search">Searched</option>
            </select>
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
            <select className="select select-bordered select-xs" value={dateRange} onChange={e=>setDateRange(e.target.value)}>
              <option value="all">Any time</option>
              <option value="24h">Last 24h</option>
              <option value="7d">Last 7 days</option>
              <option value="30d">Last 30 days</option>
            </select>
            <input className="input input-bordered input-xs w-48" placeholder="Filter title / message…" value={q} onChange={e=>setQ(e.target.value)} />
            <button type="button" className="btn btn-xs" onClick={loadHistory}>Refresh</button>
            <span className="text-xs opacity-40">{rows.length} records</span>
          </div>

          {loading ? <span className="loading loading-spinner text-primary"/> : rows.length===0 ? (
            <div className="text-sm opacity-40 py-8">No history yet — grabs and imports appear here</div>
          ) : (
            <div className="overflow-x-auto border border-base-content/10 rounded-lg">
              <table className="table table-sm table-pin-rows">
                <thead>
                  <tr className="bg-base-300">
                    <th className="w-28">Event</th>
                    <th>Source Title</th>
                    <th className="w-20">Type</th>
                    <th className="w-36">Date</th>
                    <th className="w-28">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map(e=>{
                    const kind = e.event_kind || e.event || 'event';
                    const meta = kindMeta[kind] || kindMeta.event;
                    return (
                      <tr key={e.id} className="hover">
                        <td>
                          <span className={'badge badge-sm gap-1 border-0 '+meta.cls}>
                            <span className="opacity-70">{meta.icon}</span> {meta.label}
                          </span>
                        </td>
                        <td>
                          <div className="font-medium text-sm truncate max-w-md" title={e.release_title||e.message}>
                            {e.release_title || e.message || '—'}
                          </div>
                          {e.message && e.release_title && e.message !== e.release_title && (
                            <div className="text-xs opacity-50 truncate max-w-md">{e.message}</div>
                          )}
                        </td>
                        <td><span className="badge badge-outline badge-sm">{e.media_type||'—'}</span></td>
                        <td className="text-xs font-mono whitespace-nowrap">{relTime(e.created_at || e.date)}</td>
                        <td className="flex gap-1">
                          <button type="button" className="btn btn-ghost btn-xs" title="Blocklist this release"
                            onClick={async()=>{
                              const title = e.release_title || e.message;
                              if (!title) return;
                              await fetch('/api/blocklist',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({release_title:title,reason:'manual from history'})});
                              if (tab==='blocklist') loadBlocklist();
                            }}>Block</button>
                          {(kind==='failed' || kind==='fail') && (
                            <button type="button" className="btn btn-ghost btn-xs" title="Re-run wanted search"
                              onClick={async()=>{
                                await fetch('/api/search-all-missing',{method:'POST'}).catch(e => console.warn(e));
                              }}>Search</button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab==='blocklist' && (
        <div className="space-y-3">
          <div className="flex flex-wrap justify-between items-center gap-2">
            <p className="text-sm opacity-50">Permanently skipped releases</p>
            <div className="flex gap-2">
              <input className="input input-bordered input-xs w-48" placeholder="Filter blocklist…" value={q} onChange={e=>setQ(e.target.value)} />
              <button type="button" className="btn btn-xs" onClick={loadBlocklist}>Refresh</button>
            </div>
          </div>
          <div className="overflow-x-auto border border-base-content/10 rounded-lg">
            <table className="table table-sm">
              <thead>
                <tr className="bg-base-300">
                  <th>Release Title</th>
                  <th>Reason</th>
                  <th>Hash</th>
                  <th>Added</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filteredBlocklist.map(b=>(
                  <tr key={b.id} className="hover">
                    <td className="text-sm font-medium max-w-sm truncate" title={b.release_title}>{b.release_title}</td>
                    <td className="text-xs opacity-60">{b.reason||'—'}</td>
                    <td className="font-mono text-[10px] opacity-40">{(b.torrent_hash||'—').toString().slice(0,12)}</td>
                    <td className="text-xs">{b.added_at ? relTime(b.added_at) : '—'}</td>
                    <td>
                      <button type="button" className="btn btn-ghost btn-xs text-error" onClick={async()=>{
                        await fetch('/api/blocklist/'+b.id,{method:'DELETE'}).catch(e => console.warn(e));
                        loadBlocklist();
                      }}>Remove</button>
                    </td>
                  </tr>
                ))}
                {!filteredBlocklist.length && <tr><td colSpan={5} className="opacity-40 text-sm">Blocklist empty</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}





export { LogsPage, ActivityPage };
