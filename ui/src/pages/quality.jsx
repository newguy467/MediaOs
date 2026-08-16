import React, { useState, useEffect, useCallback, useRef } from "react";
import Ic, { Icons, P } from "../icons.jsx";
import { getToken, setToken, getAdvanced, setAdvancedFlag, AUTH_TOKEN_KEY } from "../storage.js";
import { api, TMDB, adultFetch } from "../api.js";
import { PageChrome, PosterTile, LibraryModuleShell, MediaDetailShell, LibraryLegend, LibraryHeader, MediaCard, StatusBadgeStack, libraryStatuses, CollectionProgressWidget, TeachEmpty, AddModal } from "../components/ui.jsx";
import { InteractiveResultsPanel, InteractiveResultsTable, MediaPlayer, HlsVideo } from "../components/media.jsx";

function QualityPacksRow() {
  const [packs, setPacks] = React.useState([]);
  const [busy, setBusy] = React.useState(null);
  const [msg, setMsg] = React.useState("");
  React.useEffect(() => {
    fetch("/api/quality-ui/presets").then(r=>r.json()).then(d=>setPacks(d.packs||[])).catch(()=>{});
  }, []);
  async function apply(id) {
    setBusy(id); setMsg("");
    try {
      const r = await fetch(`/api/quality-ui/presets/${id}/apply`, { method: "POST" }).then(async x=>{
        const j = await x.json().catch(()=>({}));
        if (!x.ok) throw new Error(j.detail||x.statusText);
        return j;
      });
      setMsg(`Applied ${r.pack?.label || id}`);
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(null);
  }
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        {packs.map(p => (
          <button key={p.id} type="button" className="btn btn-sm" disabled={busy===p.id} onClick={()=>apply(p.id)} title={p.help||p.description}>
            {busy===p.id ? "…" : p.label}
          </button>
        ))}
      </div>
      {msg && <p className="text-xs opacity-70">{msg}</p>}
    </div>
  );
}

function QualityProfilesPage() {
  const empty = () => ({
    name: '', media_type: 'movie', is_default: false, cutoff: '1080p', min_seeders: 3,
    resolutions: ['2160p','1080p','720p','480p'],
    preferred_sources: ['bluray','webdl','webrip','hdtv'],
    custom_formats: [],
    retention_policy: 'best_only',
    keep_n: 2,
  });
  const [profiles, setProfiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [edit, setEdit] = useState(null); // null | {id?, ...form}
  const [msg, setMsg] = useState(null);
  const [scoreTitle, setScoreTitle] = useState('');
  const [scoreResult, setScoreResult] = useState(null);
  const [movieCfg, setMovieCfg] = useState(null);

  const load = () => {
    setLoading(true);
    Promise.all([
      api.settings.profiles(),
      api.settings.movies().catch(()=>null),
    ]).then(([p, m]) => { setProfiles(p||[]); setMovieCfg(m); })
      .catch(e => { console.warn(e); if (typeof setMsg === 'function') setMsg(String(e.message || e)); }).finally(()=>setLoading(false));
  };
  useEffect(() => { load(); }, []);

  const [trashStatus, setTrashStatus] = useState(null);
  const [trashBusy, setTrashBusy] = useState(false);
  const [trashUrl, setTrashUrl] = useState('');
  const loadTrash = () => fetch('/api/quality-ui/trash/status').then(r=>r.json()).then(setTrashStatus).catch(e => { console.warn(e); if (typeof setMsg === 'function') setMsg(String(e.message || e)); });
  useEffect(()=>{ loadTrash(); }, []);
  async function runTrashSync() {
    setTrashBusy(true); setMsg(null);
    try {
      const q = trashUrl ? ('?url='+encodeURIComponent(trashUrl)) : '';
      const r = await fetch('/api/quality-ui/trash/sync'+q, { method:'POST' }).then(x=>x.json());
      setMsg(r.ok ? `TRaSH synced from ${r.source} (${r.custom_formats||0} formats)` : `TRaSH sync failed: ${(r.errors||[]).join(', ')}`);
      loadTrash(); load();
    } catch(e) { setMsg(String(e.message||e)); }
    setTrashBusy(false);
  }

  async function save() {
    setMsg(null);
    try {
      await api.settings.saveProfile(edit.id || null, edit);
      setEdit(null); load(); setMsg('Saved');
    } catch(e) { setMsg(String(e.message||e)); }
  }
  async function remove(id) {
    if (!confirm('Delete this profile?')) return;
    try { await api.settings.deleteProfile(id); load(); } catch(e) { setMsg(String(e.message||e)); }
  }
  async function makeDefault(id) {
    try { await api.settings.setDefaultProfile(id); load(); } catch(e) { setMsg(String(e.message||e)); }
  }
  async function testScore() {
    try {
      const r = await fetch('/api/quality/score', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ title: scoreTitle, media_type: edit?.media_type || 'movie' }),
      }).then(x=>x.json());
      setScoreResult(r);
    } catch(e) { setScoreResult({ error: String(e.message||e) }); }
  }

  function toggleList(key, val) {
    const list = edit[key] || [];
    setEdit({ ...edit, [key]: list.includes(val) ? list.filter(x=>x!==val) : [...list, val] });
  }

  const RES = ['2160p','1080p','720p','480p'];
  const SRC = ['bluray','webdl','webrip','hdtv','hdtv','dvd','cam','ts'];

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex justify-between items-start flex-wrap gap-2">
        <div>
          <h1 className="mr-page-title">Quality Profiles</h1>
          <p className="text-base-content/50 text-sm mt-1">TRaSH-style scoring for movie (and TV) grabs — Radarr replacement core</p>
        </div>
        <button type="button" className="btn btn-sm btn-primary" onClick={()=>setEdit(empty())}>New profile</button>
      </div>

      {movieCfg && (
        <div className="alert text-sm py-2">
          <span>
            Movie mode: <b>{movieCfg.download_mode}</b>
            {movieCfg.download_mode==='strm' ? ' (writes .strm, no torrent)' : ' (qBittorrent download)'}
            {'   '}Upgrades: {movieCfg.upgrade_enabled ? `on (gap ${movieCfg.upgrade_min_score_gap})` : 'off'}
            {'   '}Set <code className="text-xs">MOVIE_DOWNLOAD_MODE=strm</code> for stream-without-download
          </span>
        </div>
      )}
      {msg && <div className="alert alert-info text-sm py-2">{msg}</div>}

      <div className="card bg-base-200 border border-primary/20 shadow-sm">
        <div className="card-body p-4 gap-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="font-semibold text-sm">Live TRaSH Guides</h2>
              <p className="text-xs opacity-50">Sync custom formats &amp; scores from TRaSH (Recyclarr-style). Offline builtin fallback always available.</p>
            </div>
            <button type="button" className="btn btn-sm btn-primary" disabled={trashBusy} onClick={runTrashSync}>
              {trashBusy ? 'Syncing…' : 'Sync now'}
            </button>
          </div>
          <div className="flex flex-wrap gap-2 items-center">
            <input className="input input-bordered input-sm flex-1 min-w-[200px]" placeholder="Optional guide URL (leave blank for default/builtin)"
              value={trashUrl} onChange={e=>setTrashUrl(e.target.value)} />
          </div>
          {trashStatus && (
            <div className="text-[11px] opacity-60 flex flex-wrap gap-3">
              <span>Auto-sync: {trashStatus.auto_sync ? 'on' : 'off'}</span>
              <span>URL configured: {trashStatus.configured_url ? 'yes' : 'no'}</span>
              <span className="opacity-80">{trashStatus.message}</span>
            </div>
          )}
        </div>
      </div>

      <div className="card mr-panel border-0">
        <div className="card-body p-4 gap-2">
          <h2 className="font-semibold text-sm">Quality packs</h2>
          <p className="text-xs opacity-50">One-click HD / 4K / Anime preference packs (stored as active preset).</p>
          <QualityPacksRow />
        </div>
      </div>

      {loading ? <span className="loading loading-spinner"/> : (
        <div className="space-y-3">
          {profiles.map(p => (
            <div key={p.id} className="card mr-panel border-0">
              <div className="card-body p-4 gap-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <h2 className="font-semibold">{p.name}</h2>
                  <span className="badge badge-sm">{p.media_type}</span>
                  {p.is_default && <span className="badge badge-sm badge-primary">default</span>}
                  <div className="flex-1"/>
                  <button type="button" className="btn btn-ghost btn-xs" onClick={()=>setEdit({...p, id:p.id})}>Edit</button>
                  {!p.is_default && <button type="button" className="btn btn-ghost btn-xs" onClick={()=>makeDefault(p.id)}>Set default</button>}
                  {!p.is_default && <button type="button" className="btn btn-ghost btn-xs text-error" onClick={()=>remove(p.id)}>Del</button>}
                </div>
                <div className="text-xs opacity-60">Cutoff {p.cutoff} · Retention {p.retention_policy||'best_only'}   Min seeders {p.min_seeders}   {(p.preferred_sources||[]).join(', ')}</div>
                <div className="flex flex-wrap gap-1">
                  {(p.custom_formats||[]).slice(0,16).map(cf => (
                    <span key={cf.name} className={`badge badge-sm ${cf.reject?'badge-error':'badge-ghost'}`}>
                      {cf.name}{cf.score?` ${cf.score>0?'+':''}${cf.score}`:''}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {edit && (
        <div className="card mr-panel border border-primary/40">
          <div className="card-body gap-3">
            <h2 className="font-semibold text-lg">{edit.id?'Edit':'New'} profile</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <input className="input input-bordered input-sm" placeholder="Name" value={edit.name} onChange={e=>setEdit({...edit, name:e.target.value})}/>
              <select className="select select-bordered select-sm" value={edit.media_type} onChange={e=>setEdit({...edit, media_type:e.target.value})}>
                <option value="movie">movie</option>
                <option value="tv">tv</option>
              </select>
              <select className="select select-bordered select-sm" value={edit.cutoff} onChange={e=>setEdit({...edit, cutoff:e.target.value})}>
                {RES.map(r=><option key={r} value={r}>Cutoff {r}</option>)}
              </select>
              <input className="input input-bordered input-sm" type="number" placeholder="Min seeders" value={edit.min_seeders}
                onChange={e=>setEdit({...edit, min_seeders:Number(e.target.value)})}/>
              <select className="select select-bordered select-sm" value={edit.retention_policy||'best_only'}
                onChange={e=>setEdit({...edit, retention_policy:e.target.value})} title="Bobarr multi-quality retention">
                <option value="best_only">Keep best only</option>
                <option value="keep_all_matching">Keep all matching qualities</option>
                <option value="keep_until_cutoff">Keep until cutoff</option>
                <option value="keep_n_best">Keep N best</option>
              </select>
              {(edit.retention_policy==='keep_n_best') && (
                <input className="input input-bordered input-sm" type="number" min={1} max={10} placeholder="Keep N"
                  value={edit.keep_n??2} onChange={e=>setEdit({...edit, keep_n:Number(e.target.value)})}/>
              )}
            </div>
            <label className="label cursor-pointer justify-start gap-2">
              <input type="checkbox" className="checkbox checkbox-sm" checked={!!edit.is_default} onChange={e=>setEdit({...edit, is_default:e.target.checked})}/>
              <span className="label-text text-sm">Default for {edit.media_type}</span>
            </label>
            <div>
              <div className="text-xs font-medium mb-1">Resolutions</div>
              <div className="flex flex-wrap gap-2">{RES.map(r=>(
                <label key={r} className="label cursor-pointer gap-1 py-0">
                  <input type="checkbox" className="checkbox checkbox-xs" checked={(edit.resolutions||[]).includes(r)} onChange={()=>toggleList('resolutions', r)}/>
                  <span className="label-text text-xs">{r}</span>
                </label>
              ))}</div>
            </div>
            <div>
              <div className="text-xs font-medium mb-1">Preferred sources</div>
              <div className="flex flex-wrap gap-2">{['bluray','webdl','webrip','hdtv','dvd'].map(r=>(
                <label key={r} className="label cursor-pointer gap-1 py-0">
                  <input type="checkbox" className="checkbox checkbox-xs" checked={(edit.preferred_sources||[]).includes(r)} onChange={()=>toggleList('preferred_sources', r)}/>
                  <span className="label-text text-xs">{r}</span>
                </label>
              ))}</div>
            </div>
            <div>
              <div className="text-xs font-medium mb-1">Custom formats ({(edit.custom_formats||[]).length}) — edit via API for full TRaSH sets; defaults seeded</div>
              <div className="flex flex-wrap gap-1 max-h-24 overflow-y-auto">
                {(edit.custom_formats||[]).map(cf=>(
                  <span key={cf.name} className={`badge badge-sm ${cf.reject?'badge-error':'badge-ghost'}`}>{cf.name} {cf.score||0}</span>
                ))}
              </div>
            </div>
            <div className="flex gap-2">
              <button type="button" className="btn btn-sm btn-primary" onClick={save} disabled={!edit.name}>Save</button>
              <button type="button" className="btn btn-sm btn-ghost" onClick={()=>setEdit(null)}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      <div className="card mr-panel border-0">
        <div className="card-body gap-2">
          <h2 className="font-semibold">Score tester (soak / debug)</h2>
          <div className="flex gap-2">
            <input className="input input-bordered input-sm flex-1" placeholder="Release title…" value={scoreTitle} onChange={e=>setScoreTitle(e.target.value)}/>
            <button type="button" className="btn btn-sm" onClick={testScore}>Score</button>
          </div>
          {scoreResult && (
            <pre className="text-xs bg-base-300 p-2 rounded overflow-x-auto">{JSON.stringify(scoreResult, null, 2)}</pre>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Activity Page ───────────────────────────────────────────────────────── */

function QualityMatrixPage({ setPage }) {
  const families = [
    { id: 'resolution', label: 'Resolution', hint: '2160p / 1080p / 720p …' },
    { id: 'source', label: 'Source', hint: 'Remux, BluRay, WEB-DL …' },
    { id: 'codec', label: 'Codec', hint: 'AV1, x265, x264 …' },
    { id: 'hdr', label: 'HDR', hint: 'DV, HDR10+, HDR …' },
    { id: 'audio', label: 'Audio', hint: 'Atmos, TrueHD, DTS …' },
    { id: 'groups', label: 'Release groups', hint: 'Editable reputation table' },
    { id: 'edition', label: 'Edition', hint: 'IMAX, Director\'s Cut …' },
  ];
  const [family, setFamily] = useState('groups');
  const [cells, setCells] = useState({});
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState(null);
  const [filter, setFilter] = useState('');
  const [newName, setNewName] = useState('');
  const [newScore, setNewScore] = useState(100);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    fetch(`/api/quality-ui/matrix/${family}`)
      .then(r => r.json())
      .then(d => setCells(d.cells || {}))
      .catch(e => setMsg(String(e)))
      .finally(() => setLoading(false));
  }, [family]);
  useEffect(() => { load(); }, [load]);

  const rows = Object.entries(cells)
    .filter(([k]) => !filter || k.toLowerCase().includes(filter.toLowerCase()))
    .sort((a,b) => b[1] - a[1] || a[0].localeCompare(b[0]));

  async function saveCell(name, score) {
    setBusy(true); setMsg(null);
    try {
      await fetch(`/api/quality-ui/matrix/${family}/${encodeURIComponent(name)}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, score: Number(score) }),
      }).then(async r => { if (!r.ok) throw new Error((await r.json()).detail || r.statusText); return r.json(); });
      setMsg(`Saved ${name} = ${score}`);
      load();
    } catch (e) { setMsg(String(e.message || e)); }
    setBusy(false);
  }
  async function removeCell(name) {
    if (!confirm(`Remove override for "${name}"?`)) return;
    setBusy(true);
    try {
      await fetch(`/api/quality-ui/matrix/${family}/${encodeURIComponent(name)}`, { method: 'DELETE' });
      load();
    } catch (e) { setMsg(String(e.message || e)); }
    setBusy(false);
  }
  async function addCell() {
    if (!newName.trim()) return;
    await saveCell(newName.trim().toLowerCase(), newScore);
    setNewName('');
  }
  async function resetFamily() {
    if (!confirm(`Reset ${family} overrides to built-in defaults?`)) return;
    setBusy(true);
    try {
      await fetch(`/api/quality-ui/matrix/reset?family=${family}`, { method: 'POST' });
      setMsg('Reset — restart app for full factory defaults on built-in keys');
      load();
    } catch (e) { setMsg(String(e.message || e)); }
    setBusy(false);
  }

  return (
    <div className="p-4 max-w-5xl mx-auto space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setPage && setPage('settings-hub')}>← Settings</button>
        <h1 className="mr-page-title flex-1">Quality matrices</h1>
        <button type="button" className="btn btn-sm" disabled={busy} onClick={async()=>{
          setBusy(true); setMsg('Fetching guide…');
          try {
            const r = await fetch('/api/overhaul/trash/fetch',{method:'POST'}).then(x=>x.json());
            setMsg('Guide: ' + (r.source||'?') + ' ' + JSON.stringify(r.applied||{}));
            load();
          } catch(e) { setMsg(String(e)); }
          setBusy(false);
        }}>Fetch TRaSH / guide</button>
        <button type="button" className="btn btn-sm" disabled={busy} onClick={resetFamily}>Reset family</button>
      </div>
      <p className="text-sm opacity-60">Every scoring cell is editable. Groups is the release-group reputation table used by interactive search and auto-grab.</p>
      <div className="tabs tabs-boxed flex-wrap w-fit gap-1">
        {families.map(f => (
          <a key={f.id} className={'tab ' + (family === f.id ? 'tab-active' : '')} onClick={() => setFamily(f.id)} title={f.hint}>{f.label}</a>
        ))}
      </div>
      {msg && <div className="alert alert-info text-xs py-2">{msg}</div>}
      <div className="flex flex-wrap gap-2 items-end">
        <label className="form-control">
          <span className="label-text text-xs">Filter</span>
          <input className="input input-bordered input-sm" value={filter} onChange={e => setFilter(e.target.value)} placeholder="name…" />
        </label>
        <label className="form-control">
          <span className="label-text text-xs">Add name</span>
          <input className="input input-bordered input-sm" value={newName} onChange={e => setNewName(e.target.value)} placeholder={family === 'groups' ? 'ctrlhd' : 'key'} />
        </label>
        <label className="form-control">
          <span className="label-text text-xs">Score</span>
          <input type="number" className="input input-bordered input-sm w-24" value={newScore} onChange={e => setNewScore(e.target.value)} />
        </label>
        <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={addCell}>Add / update</button>
      </div>
      {loading ? <span className="loading loading-spinner" /> : (
        <div className="overflow-x-auto border border-base-300 rounded-lg">
          <table className="table table-sm">
            <thead><tr><th>Key</th><th className="w-32">Score</th><th className="w-40"></th></tr></thead>
            <tbody>
              {rows.map(([name, score]) => (
                <MatrixRow key={name} name={name} score={score} busy={busy} onSave={saveCell} onRemove={removeCell} />
              ))}
              {!rows.length && <tr><td colSpan={3} className="opacity-50">No cells</td></tr>}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-xs opacity-50">{rows.length} cells in <code>{family}</code></p>
    </div>
  );
}

function MatrixRow({ name, score, busy, onSave, onRemove }) {
  const [val, setVal] = useState(score);
  useEffect(() => { setVal(score); }, [score]);
  return (
    <tr>
      <td className="font-mono text-xs">{name}</td>
      <td>
        <input type="number" className="input input-bordered input-xs w-28" value={val} onChange={e => setVal(e.target.value)} />
      </td>
      <td className="flex gap-1">
        <button type="button" className="btn btn-xs btn-primary" disabled={busy || Number(val) === score} onClick={() => onSave(name, val)}>Save</button>
        <button type="button" className="btn btn-xs btn-ghost" disabled={busy} onClick={() => onRemove(name)}>Del</button>
      </td>
    </tr>
  );
}


function QualityLabPage() {
  const [factors, setFactors] = useState(null);
  const [title, setTitle] = useState('Movie.Title.2024.2160p.BluRay.REMUX.HDR.Atmos-FRAMESTOR');
  const [result, setResult] = useState(null);
  useEffect(()=>{ fetch('/api/quality-ui/factors').then(r=>r.json()).then(setFactors).catch(e => { console.warn(e); if (typeof setMsg === 'function') setMsg(String(e.message || e)); }); }, []);
  async function score() {
    const r = await fetch('/api/quality-ui/score',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title})}).then(r=>r.json());
    setResult(r);
  }
  return (
    <div className="space-y-6 max-w-3xl">
      <div><h1 className="mr-page-title">Quality Lab</h1>
      <p className="mr-page-sub">Dictionarry-class factors   score tester   language profiles</p></div>
      <div className="mr-panel p-4 space-y-2">
        <input className="input input-bordered input-sm w-full font-mono text-xs" value={title} onChange={e=>setTitle(e.target.value)} />
        <button type="button" className="btn btn-sm btn-primary" onClick={score}>Score release</button>
        {result && <pre className="text-xs opacity-80 overflow-auto">{JSON.stringify(result,null,2)}</pre>}
      </div>
      {factors && (
        <div className="mr-panel p-4">
          <h2 className="font-semibold mb-2">Factor families (~{factors.factor_families})</h2>
          <div className="grid sm:grid-cols-2 gap-3 text-xs">
            {['resolution','source','codec','hdr','audio'].map(k=>(
              <div key={k}><div className="font-mono opacity-60 mb-1">{k}</div>
              <pre className="opacity-70 overflow-auto max-h-32">{JSON.stringify(factors[k],null,1)}</pre></div>
            ))}
          </div>
          <h3 className="font-semibold mt-4 mb-1">Language profiles</h3>
          <ul className="text-sm">{(factors.language_profiles||[]).map(p=>(
            <li key={p.id}>{p.name}: {(p.languages||[]).join(', ')}   HI {p.hearing_impaired}</li>
          ))}</ul>
        </div>
      )}
    </div>
  );
}


/* ── Tdarr-style Converter ───────────────────────────────────────────────── */



export { QualityProfilesPage, QualityMatrixPage, MatrixRow, QualityLabPage };
