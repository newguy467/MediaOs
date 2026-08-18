import { useState, useEffect } from "react";
import { api } from "../api.js";
function WantedPage() {
  const [data, setData] = useState({ movies:[], episodes:[], music:[], books:[], audiobooks:[], adult:[], counts:{} });
  const [tab, setTab] = useState('movies');
  const [loading, setLoading] = useState(true);
  const [checked, setChecked] = useState({}); // { "movie-12": true }
  const [busy, setBusy] = useState(null);
  const [msg, setMsg] = useState(null);
  const load = () => { setLoading(true); api.wanted.list().then(setData).catch(e => { console.warn(e); if (typeof setMsg === 'function') setMsg(String(e.message || e)); }).finally(()=>setLoading(false)); };
  useEffect(() => { load(); }, []);
  
  async function searchSelected() {
    const keys = Object.keys(checked);
    if (!keys.length) return;
    setBusy('bulk');
    setMsg(null);
    let ok = 0, fail = 0;
    for (const key of keys) {
      const [kind, id] = key.split('-');
      try {
        await searchOne(kind, Number(id));
        ok += 1;
      } catch {
        fail += 1;
      }
    }
    setChecked({});
    setBusy(null);
    setMsg(`Searched ${ok}` + (fail ? `, ${fail} failed` : ''));
  }

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
    { key:'import-tools', label:'Import tools' },
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
          <button type="button" className="btn btn-sm btn-primary" disabled={!!busy || tab==='import-tools'} onClick={()=>searchAuto(tab==='episodes'?'tv':tab)}>
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
      {Object.keys(checked).length > 0 && (
        <div className="card bg-base-200 mb-3">
          <div className="card-body p-3">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs opacity-60">{Object.keys(checked).length} selected</span>
              <button type="button" className="btn btn-xs btn-primary" disabled={!!busy} onClick={searchSelected}>Search selected</button>
              <button type="button" className="btn btn-xs btn-ghost" onClick={()=>setChecked({})}>Clear</button>
            </div>
          </div>
        </div>
      )}
      {msg && <div className="alert alert-info text-sm py-2"><span>{msg}</span></div>}
      <div className="tabs tabs-boxed w-fit flex-wrap">
        {tabs.map(t=>(<a key={t.key} className={'tab '+(tab===t.key?'tab-active':'')} onClick={()=>setTab(t.key)}>{t.label}</a>))}
      </div>
      {tab==='import-tools' ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <TrashImportPanel />
          <ArrDbMigratePanel />
          <ArrMigratePanel />
        </div>
      ) : loading ? <span className="loading loading-spinner text-primary"/> : (
        <div className="mr-panel overflow-x-auto">
          {tab==='movies' && <table className="table table-sm"><thead><tr><th className="w-8"></th><th>Title</th><th>Year</th><th>Status</th><th>Last search</th><th></th></tr></thead><tbody>
            {(data.movies||[]).length===0?<tr><td colSpan={5} className="opacity-40">No missing movies</td></tr>:
              data.movies.map(m=>(<tr key={m.id}><td><input type="checkbox" className="checkbox checkbox-xs" checked={!!checked['movie-'+m.id]} onChange={e=>{ setChecked(prev=>{ const n={...prev}; const k='movie-'+m.id; if(e.target.checked) n[k]=true; else delete n[k]; return n; }); }} /></td><td className="font-medium">{m.title}</td><td className="text-xs opacity-50">{m.year||'—'}</td><td><span className="badge badge-sm">{m.status}</span></td><td className="text-xs font-mono">{m.last_searched_at?new Date(m.last_searched_at).toLocaleString():'never'}</td>
              <td><button type="button" className="btn btn-xs btn-primary" disabled={!!busy} onClick={()=>searchOne('movie',m.id)}>{busy==='movie-'+m.id?'…':'Search'}</button></td></tr>))}</tbody></table>}
          {tab==='episodes' && <table className="table table-sm"><thead><tr><th className="w-8"></th><th>Series</th><th>Ep</th><th>Title</th><th>Air</th><th>Status</th><th></th></tr></thead><tbody>
            {(data.episodes||[]).length===0?<tr><td colSpan={6} className="opacity-40">No missing episodes</td></tr>:
              data.episodes.map(e=>(<tr key={e.id}><td><input type="checkbox" className="checkbox checkbox-xs" checked={!!checked['episode-'+e.id]} onChange={ev=>{ setChecked(prev=>{ const n={...prev}; const k='episode-'+e.id; if(ev.target.checked) n[k]=true; else delete n[k]; return n; }); }} /></td><td className="font-medium text-sm">{e.series_title}</td><td className="font-mono text-xs">S{String(e.season_number).padStart(2,'0')}E{String(e.episode_number).padStart(2,'0')}</td><td className="text-sm opacity-70">{e.title||'—'}</td><td className="text-xs">{e.air_date||'—'}</td><td><span className="badge badge-sm">{e.status}</span></td>
              <td><button type="button" className="btn btn-xs btn-primary" disabled={!!busy} onClick={()=>searchOne('episode',e.id)}>{busy==='episode-'+e.id?'…':'Search'}</button></td></tr>))}</tbody></table>}
          {tab==='music' && <table className="table table-sm"><thead><tr><th>Artist</th><th>Album</th><th>Year</th><th>Status</th><th></th></tr></thead><tbody>
            {(data.music||[]).length===0?<tr><td colSpan={5} className="opacity-40">No missing albums</td></tr>:
              data.music.map(m=>(<tr key={m.id}><td className="text-sm">{m.artist_name||'—'}</td><td className="font-medium">{m.title}</td><td className="text-xs opacity-50">{m.year||'—'}</td><td><span className="badge badge-sm">{m.status}</span></td>
              <td><button type="button" className="btn btn-xs btn-primary" disabled={!!busy} onClick={()=>searchOne('music',m.id)}>{busy==='music-'+m.id?'…':'Search'}</button></td></tr>))}</tbody></table>}
          {tab==='books' && <table className="table table-sm"><thead><tr><th className="w-8"></th><th>Title</th><th>Author</th><th>Status</th><th></th></tr></thead><tbody>
            {(data.books||[]).length===0?<tr><td colSpan={4} className="opacity-40">No missing books</td></tr>:
              data.books.map(b=>(<tr key={b.id}><td><input type="checkbox" className="checkbox checkbox-xs" checked={!!checked['book-'+b.id]} onChange={e=>{ setChecked(prev=>{ const n={...prev}; const k='book-'+b.id; if(e.target.checked) n[k]=true; else delete n[k]; return n; }); }} /></td><td className="font-medium">{b.title}</td><td className="text-sm opacity-60">{b.overview||'—'}</td><td><span className="badge badge-sm">{b.status}</span></td>
              <td><button type="button" className="btn btn-xs btn-primary" disabled={!!busy} onClick={()=>searchOne('book',b.id)}>{busy==='book-'+b.id?'…':'Search'}</button></td></tr>))}</tbody></table>}
          {tab==='audiobooks' && <table className="table table-sm"><thead><tr><th className="w-8"></th><th>Title</th><th>Author</th><th>Status</th><th></th></tr></thead><tbody>
            {(data.audiobooks||[]).length===0?<tr><td colSpan={4} className="opacity-40">No missing audiobooks</td></tr>:
              data.audiobooks.map(a=>(<tr key={a.id}><td><input type="checkbox" className="checkbox checkbox-xs" checked={!!checked['audiobook-'+a.id]} onChange={e=>{ setChecked(prev=>{ const n={...prev}; const k='audiobook-'+a.id; if(e.target.checked) n[k]=true; else delete n[k]; return n; }); }} /></td><td className="font-medium">{a.title}</td><td className="text-sm opacity-60">{a.overview||'—'}</td><td><span className="badge badge-sm">{a.status}</span></td>
              <td><button type="button" className="btn btn-xs btn-primary" disabled={!!busy} onClick={()=>searchOne('audiobook',a.id)}>{busy==='audiobook-'+a.id?'…':'Search'}</button></td></tr>))}</tbody></table>}
          {tab==='adult' && <table className="table table-sm"><thead><tr><th className="w-8"></th><th>Title</th><th>Year</th><th>Status</th><th></th></tr></thead><tbody>
            {(data.adult||[]).length===0?<tr><td colSpan={4} className="opacity-40">No missing adult titles</td></tr>:
              data.adult.map(a=>(<tr key={a.id}><td><input type="checkbox" className="checkbox checkbox-xs" checked={!!checked['adult-'+a.id]} onChange={e=>{ setChecked(prev=>{ const n={...prev}; const k='adult-'+a.id; if(e.target.checked) n[k]=true; else delete n[k]; return n; }); }} /></td><td className="font-medium">{a.title}</td><td className="text-sm opacity-60">{a.year||'—'}</td><td><span className="badge badge-sm">{a.status}</span></td>
              <td><button type="button" className="btn btn-xs btn-primary" disabled={!!busy} onClick={()=>searchOne('adult',a.id)}>{busy==='adult-'+a.id?'…':'Search'}</button></td></tr>))}</tbody></table>}
        </div>
      )}
    </div>
  );
}



function TrashImportPanel() {
  const [raw, setRaw] = useState('');
  const [name, setName] = useState('TRaSH Imported');
  const [mediaType, setMediaType] = useState('movie');
  const [msg, setMsg] = useState('');
  async function run() {
    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch (e) {
      setMsg('Not valid JSON: ' + String(e.message || e));
      return;
    }
    setMsg('Importing…');
    try {
      const r = await fetch('/api/migrate/trash', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ data: parsed, profile_name: name, media_type: mediaType, replace_formats: true })
      }).then(x=>x.json());
      setMsg(r.ok ? `Imported ${r.custom_formats} formats → profile "${r.profile_name}"` : (r.detail || r.error || 'failed'));
    } catch(e){ setMsg(String(e.message||e)); }
  }
  return (
    <div className="card mr-panel border-0"><div className="card-body gap-2 text-sm">
      <h2 className="font-semibold">TRaSH Guides import</h2>
      <p className="text-xs opacity-60">Paste a TRaSH custom-formats JSON export below to import it into a quality profile. (Import by URL isn't supported server-side — fetch the JSON yourself first, e.g. from the TRaSH Guides repo, then paste it here.)</p>
      <textarea className="textarea textarea-bordered textarea-sm w-full font-mono" rows={6} placeholder="{ ...custom formats JSON... }" value={raw} onChange={e=>setRaw(e.target.value)} />
      <div className="flex gap-2 flex-wrap">
        <input className="input input-bordered input-sm" value={name} onChange={e=>setName(e.target.value)} placeholder="Profile name" />
        <select className="select select-bordered select-sm" value={mediaType} onChange={e=>setMediaType(e.target.value)}>
          <option value="movie">movie</option>
          <option value="tv">tv</option>
        </select>
        <button type="button" className="btn btn-sm btn-primary" disabled={!raw.trim()} onClick={run}>Import</button>
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
