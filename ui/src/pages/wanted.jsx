import React, { useState, useEffect, useCallback, useRef } from "react";
import Ic, { Icons, P } from "../icons.jsx";
import { getToken, setToken, getAdvanced, setAdvancedFlag, AUTH_TOKEN_KEY } from "../storage.js";
import { api, TMDB, adultFetch } from "../api.js";
import { PageChrome, PosterTile, LibraryModuleShell, MediaDetailShell, LibraryLegend, LibraryHeader, MediaCard, StatusBadgeStack, libraryStatuses, CollectionProgressWidget, TeachEmpty, AddModal } from "../components/ui.jsx";
import { InteractiveResultsPanel, InteractiveResultsTable, MediaPlayer, HlsVideo } from "../components/media.jsx";

function WantedPage() {
  const [data, setData] = useState({ movies:[], episodes:[], music:[], books:[], audiobooks:[], adult:[], counts:{} });
  const [tab, setTab] = useState('movies');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(null);
  const [msg, setMsg] = useState(null);
  const load = () => { setLoading(true); api.wanted.list().then(setData).catch(e => { console.warn(e); if (typeof setMsg === 'function') setMsg(String(e.message || e)); }).finally(()=>setLoading(false)); };
  useEffect(() => { load(); }, []);
  async function searchOne(kind, id) {
    setBusy(kind+'-'+id); setMsg(null);
    try {
      const fn = {movie:api.wanted.searchMovie, episode:api.wanted.searchEpisode, music:api.wanted.searchMusic, book:api.wanted.searchBook, audiobook:api.wanted.searchAudiobook, adult:api.wanted.searchAdult}[kind];
      const r = await fn(id);
      setMsg(r.found ? ('Grabbed: '+(r.title||'release')+' ('+(r.indexer||'?')+')') : (r.error || 'No release found'));
      load();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(null);
  }
  async function searchAuto(scope) {
    setBusy('auto-'+scope); setMsg(null);
    try {
      const r = await api.wanted.searchAll(scope==='all'?null:scope, 50);
      const parts = Object.entries(r).filter(([k,v])=>typeof v==='number'&&v>0).map(([k,v])=>k+': '+v);
      setMsg(parts.length ? ('Automatic search grabbed — '+parts.join(', ')) : 'Automatic search finished — nothing new grabbed');
      load();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(null);
  }
  const c = data.counts || {};
  const tabs = [
    { key:'movies', label:'Movies ('+(c.movies||0)+')' },
    { key:'episodes', label:'TV ('+(c.episodes||0)+')' },
    { key:'music', label:'Music ('+(c.music||0)+')' },
    { key:'books', label:'Books ('+(c.books||0)+')' },
    { key:'audiobooks', label:'Audiobooks ('+(c.audiobooks||0)+')' },
    { key:'adult', label:'Adult ('+(c.adult||0)+')' },
  ];
  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex flex-wrap justify-between items-start gap-3">
        <div>
          <h1 className="mr-page-title">Wanted</h1>
          <p className="mr-page-sub">Titles you asked for that are not on disk yet</p>
          <p className="text-xs opacity-50 max-w-xl">No results after Search? Simplest fixes: (1) qBittorrent URL in Setup, (2) try a popular title, (3) wait — public indexers can be slow. Advanced: Indexers / Prowlarr.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn btn-sm btn-ghost" onClick={load} disabled={!!busy}>Refresh</button>
          <button type="button" className="btn btn-sm btn-primary" disabled={!!busy} onClick={()=>searchAuto(tab==='episodes'?'tv':tab)}>
            {busy&&String(busy).startsWith('auto')?'Searching…':'Auto-search tab'}
          </button>
          <button type="button" className="btn btn-sm btn-secondary" disabled={!!busy} onClick={()=>searchAuto('all')}>Auto-search all</button>
          <button type="button" className="btn btn-sm btn-accent" disabled={!!busy} onClick={async()=>{
            setBusy('hunt'); setMsg(null);
            try {
              const r = await fetch('/api/hunt/run', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ limit: 40, only_monitored: true }) }).then(x=>x.json());
              setMsg(r.message || `Hunt: processed ${r.processed||0}, grabbed ${r.grabbed||0}`);
              load();
            } catch(e) { setMsg(String(e.message||e)); }
            setBusy(null);
          }}>{busy==='hunt'?'Hunting…':'Run hunt'}</button>
        </div>
      </div>
      {msg && <div className="alert alert-info text-sm py-2"><span>{msg}</span></div>}
      <div className="tabs tabs-boxed w-fit flex-wrap">
        {tabs.map(t=>(<a key={t.key} className={'tab '+(tab===t.key?'tab-active':'')} onClick={()=>setTab(t.key)}>{t.label}</a>))}
      </div>
      {loading ? <span className="loading loading-spinner text-primary"/> : (
        <div className="mr-panel overflow-x-auto">
          {tab==='movies' && <table className="table table-sm"><thead><tr><th>Title</th><th>Year</th><th>Status</th><th>Last search</th><th></th></tr></thead><tbody>
            {(data.movies||[]).length===0?<tr><td colSpan={5} className="opacity-40">No missing movies</td></tr>:
              data.movies.map(m=>(<tr key={m.id}><td className="font-medium">{m.title}</td><td className="text-xs opacity-50">{m.year||'—'}</td><td><span className="badge badge-sm">{m.status}</span></td><td className="text-xs font-mono">{m.last_searched_at?new Date(m.last_searched_at).toLocaleString():'never'}</td>
              <td><button type="button" className="btn btn-xs btn-primary" disabled={!!busy} onClick={()=>searchOne('movie',m.id)}>{busy==='movie-'+m.id?'…':'Search'}</button></td></tr>))}</tbody></table>}
          {tab==='episodes' && <table className="table table-sm"><thead><tr><th>Series</th><th>Ep</th><th>Title</th><th>Air</th><th>Status</th><th></th></tr></thead><tbody>
            {(data.episodes||[]).length===0?<tr><td colSpan={6} className="opacity-40">No missing episodes</td></tr>:
              data.episodes.map(e=>(<tr key={e.id}><td className="font-medium text-sm">{e.series_title}</td><td className="font-mono text-xs">S{String(e.season_number).padStart(2,'0')}E{String(e.episode_number).padStart(2,'0')}</td><td className="text-sm opacity-70">{e.title||'—'}</td><td className="text-xs">{e.air_date||'—'}</td><td><span className="badge badge-sm">{e.status}</span></td>
              <td><button type="button" className="btn btn-xs btn-primary" disabled={!!busy} onClick={()=>searchOne('episode',e.id)}>{busy==='episode-'+e.id?'…':'Search'}</button></td></tr>))}</tbody></table>}
          {tab==='music' && <table className="table table-sm"><thead><tr><th>Artist</th><th>Album</th><th>Year</th><th>Status</th><th></th></tr></thead><tbody>
            {(data.music||[]).length===0?<tr><td colSpan={5} className="opacity-40">No missing albums</td></tr>:
              data.music.map(m=>(<tr key={m.id}><td className="text-sm">{m.artist_name||'—'}</td><td className="font-medium">{m.title}</td><td className="text-xs opacity-50">{m.year||'—'}</td><td><span className="badge badge-sm">{m.status}</span></td>
              <td><button type="button" className="btn btn-xs btn-primary" disabled={!!busy} onClick={()=>searchOne('music',m.id)}>{busy==='music-'+m.id?'…':'Search'}</button></td></tr>))}</tbody></table>}
          {tab==='books' && <table className="table table-sm"><thead><tr><th>Title</th><th>Author</th><th>Status</th><th></th></tr></thead><tbody>
            {(data.books||[]).length===0?<tr><td colSpan={4} className="opacity-40">No missing books</td></tr>:
              data.books.map(b=>(<tr key={b.id}><td className="font-medium">{b.title}</td><td className="text-sm opacity-60">{b.overview||'—'}</td><td><span className="badge badge-sm">{b.status}</span></td>
              <td><button type="button" className="btn btn-xs btn-primary" disabled={!!busy} onClick={()=>searchOne('book',b.id)}>{busy==='book-'+b.id?'…':'Search'}</button></td></tr>))}</tbody></table>}
          {tab==='audiobooks' && <table className="table table-sm"><thead><tr><th>Title</th><th>Author</th><th>Status</th><th></th></tr></thead><tbody>
            {(data.audiobooks||[]).length===0?<tr><td colSpan={4} className="opacity-40">No missing audiobooks</td></tr>:
              data.audiobooks.map(a=>(<tr key={a.id}><td className="font-medium">{a.title}</td><td className="text-sm opacity-60">{a.overview||'—'}</td><td><span className="badge badge-sm">{a.status}</span></td>
              <td><button type="button" className="btn btn-xs btn-primary" disabled={!!busy} onClick={()=>searchOne('audiobook',a.id)}>{busy==='audiobook-'+a.id?'…':'Search'}</button></td></tr>))}</tbody></table>}
          {tab==='adult' && <table className="table table-sm"><thead><tr><th>Title</th><th>Year</th><th>Status</th><th></th></tr></thead><tbody>
            {(data.adult||[]).length===0?<tr><td colSpan={4} className="opacity-40">No missing adult titles</td></tr>:
              data.adult.map(a=>(<tr key={a.id}><td className="font-medium">{a.title}</td><td className="text-sm opacity-60">{a.year||'—'}</td><td><span className="badge badge-sm">{a.status}</span></td>
              <td><button type="button" className="btn btn-xs btn-primary" disabled={!!busy} onClick={()=>searchOne('adult',a.id)}>{busy==='adult-'+a.id?'…':'Search'}</button></td></tr>))}</tbody></table>}
        </div>
      )}
    </div>
  );
}



function TrashImportPanel() {
  const [url, setUrl] = useState('');
  const [name, setName] = useState('TRaSH Imported');
  const [mediaType, setMediaType] = useState('movie');
  const [msg, setMsg] = useState('');
  const [presets, setPresets] = useState(null);
  useEffect(()=>{ fetch('/api/migrate/trash/presets').then(r=>r.json()).then(setPresets).catch(e => { console.warn(e); if (typeof setMsg === 'function') setMsg(String(e.message || e)); }); }, []);
  async function run() {
    setMsg('Importing…');
    try {
      const r = await fetch('/api/migrate/trash', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ url, profile_name: name, media_type: mediaType, replace_formats: true })
      }).then(x=>x.json());
      setMsg(r.ok ? `Imported ${r.custom_formats} formats → profile "${r.profile_name}"` : (r.detail || r.error || 'failed'));
    } catch(e){ setMsg(String(e.message||e)); }
  }
  return (
    <div className="card mr-panel border-0"><div className="card-body gap-2 text-sm">
      <h2 className="font-semibold">TRaSH Guides import</h2>
      <p className="text-xs opacity-60">Import custom formats JSON (URL or paste TRaSH export) into a quality profile.</p>
      {presets && (
        <div className="flex flex-wrap gap-1">
          <button type="button" className="btn btn-xs" onClick={()=>setUrl(presets.movie_hd_bluray_web||'')}>Preset: Movie HD</button>
          <button type="button" className="btn btn-xs" onClick={()=>setUrl(presets.tv_hd_bluray_web||'')}>Preset: TV HD</button>
        </div>
      )}
      <input className="input input-bordered input-sm w-full" placeholder="https://…/custom-formats.json" value={url} onChange={e=>setUrl(e.target.value)} />
      <div className="flex gap-2 flex-wrap">
        <input className="input input-bordered input-sm" value={name} onChange={e=>setName(e.target.value)} placeholder="Profile name" />
        <select className="select select-bordered select-sm" value={mediaType} onChange={e=>setMediaType(e.target.value)}>
          <option value="movie">movie</option>
          <option value="tv">tv</option>
        </select>
        <button type="button" className="btn btn-sm btn-primary" onClick={run}>Import</button>
      </div>
      {msg && <p className="text-xs opacity-70">{msg}</p>}
    </div></div>
  );
}

function ArrDbMigratePanel() {
  const [kind, setKind] = useState('radarr');
  const [path, setPath] = useState('');
  const [pg, setPg] = useState('');
  const [msg, setMsg] = useState('');
  async function run() {
    setMsg('Importing…');
    try {
      const body = path ? { path, kind } : { postgres_url: pg, kind };
      const r = await fetch('/api/migrate/db', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) }).then(x=>x.json());
      setMsg(JSON.stringify(r));
    } catch(e){ setMsg(String(e.message||e)); }
  }
  return (
    <div className="card mr-panel border-0"><div className="card-body gap-2 text-sm">
      <h2 className="font-semibold">DB migrator (SQLite / Postgres)</h2>
      <p className="text-xs opacity-60">Point at a Sonarr/Radarr .db file path inside the container, or a Postgres URL to a restored *arr database.</p>
      <select className="select select-bordered select-sm w-40" value={kind} onChange={e=>setKind(e.target.value)}>
        <option value="radarr">Radarr</option><option value="sonarr">Sonarr</option>
      </select>
      <input className="input input-bordered input-sm w-full" placeholder="/config/radarr/radarr.db" value={path} onChange={e=>setPath(e.target.value)} />
      <input className="input input-bordered input-sm w-full" placeholder="postgres://user:pass@host:5432/radarr" value={pg} onChange={e=>setPg(e.target.value)} />
      <button type="button" className="btn btn-sm btn-primary" onClick={run}>Import from DB</button>
      {msg && <pre className="text-xs opacity-70 overflow-auto max-h-24">{msg}</pre>}
    </div></div>
  );
}

function ArrMigratePanel() {
  const [radarr, setRadarr] = useState({url:'', api_key:''});
  const [sonarr, setSonarr] = useState({url:'', api_key:''});
  const [msg, setMsg] = useState('');
  async function go(kind) {
    setMsg('Migrating…');
    const body = kind==='radarr' ? radarr : sonarr;
    try {
      const r = await fetch('/api/migrate/'+kind, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({...body, monitor:true})
      }).then(x=>x.json());
      setMsg(JSON.stringify(r));
    } catch(e){ setMsg(String(e.message||e)); }
  }
  return (
    <div className="card mr-panel border-0"><div className="card-body gap-2 text-sm">
      <h2 className="font-semibold">Import from Radarr / Sonarr</h2>
      <p className="text-xs opacity-60">Pull library via *arr API (no direct Postgres required). Episodes include absolute numbers when Sonarr provides them.</p>
      <div className="grid sm:grid-cols-2 gap-3">
        <div className="space-y-1">
          <div className="font-medium text-xs">Radarr</div>
          <input className="input input-bordered input-sm w-full" placeholder="http://radarr:7878" value={radarr.url} onChange={e=>setRadarr(s=>({...s,url:e.target.value}))} />
          <input className="input input-bordered input-sm w-full" placeholder="API key" type="password" value={radarr.api_key} onChange={e=>setRadarr(s=>({...s,api_key:e.target.value}))} />
          <button type="button" className="btn btn-xs btn-primary" onClick={()=>go('radarr')}>Import movies</button>
        </div>
        <div className="space-y-1">
          <div className="font-medium text-xs">Sonarr</div>
          <input className="input input-bordered input-sm w-full" placeholder="http://sonarr:8989" value={sonarr.url} onChange={e=>setSonarr(s=>({...s,url:e.target.value}))} />
          <input className="input input-bordered input-sm w-full" placeholder="API key" type="password" value={sonarr.api_key} onChange={e=>setSonarr(s=>({...s,api_key:e.target.value}))} />
          <button type="button" className="btn btn-xs btn-primary" onClick={()=>go('sonarr')}>Import series + episodes</button>
        </div>
      </div>
      {msg && <pre className="text-xs opacity-70 overflow-auto max-h-24">{msg}</pre>}
    </div></div>
  );
}





export { WantedPage, TrashImportPanel, ArrDbMigratePanel, ArrMigratePanel };
