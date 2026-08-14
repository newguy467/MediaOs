import React, { useState, useEffect, useCallback } from "react";
import { LibraryModuleShell, TeachEmpty, PageChrome } from "../components/ui.jsx";


function ExternalArrPage() {
  const [items, setItems] = useState([]);
  const [live, setLive] = useState({});
  const [name, setName] = useState('');
  const [kind, setKind] = useState('sonarr');
  const [url, setUrl] = useState('');
  const [key, setKey] = useState('');
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);
  const load = () => fetch('/api/overhaul/external-arr').then(r=>r.json()).then(d=>setItems(d.items||[])).catch(e => { console.warn(e); if (typeof setMsg === 'function') setMsg(String(e.message || e)); });
  useEffect(()=>{ load(); }, []);
  const add = async () => {
    const r = await fetch('/api/overhaul/external-arr', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ name, kind, base_url: url, api_key: key }) }).then(r=>r.json());
    setMsg(r.ok ? 'Added' : JSON.stringify(r)); load();
  };
  const refreshLive = async () => {
    setBusy(true);
    try {
      const d = await fetch('/api/overhaul/external-arr/status-all').then(r=>r.json());
      const map = {};
      (d.items||[]).forEach(x => { map[x.id] = x; });
      setLive(map);
      setMsg('Live status refreshed');
    } catch(e) { setMsg(String(e)); }
    setBusy(false);
  };
  return (
    <div className="page-shell space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="mr-page-title mb-0">External *arr</h1>
        <button type="button" className="btn btn-sm btn-secondary" disabled={busy} onClick={refreshLive}>Refresh live status</button>
      </div>
      <p className="text-sm opacity-60">Remote Sonarr/Radarr/Lidarr — queue + calendar live pull.</p>
      {msg && <div className="alert alert-info text-xs py-2">{msg}</div>}
      <div className="flex flex-wrap gap-2">
        <input className="input input-bordered input-sm" placeholder="Name" value={name} onChange={e=>setName(e.target.value)} />
        <select className="select select-bordered select-sm" value={kind} onChange={e=>setKind(e.target.value)}>
          <option value="sonarr">Sonarr</option><option value="radarr">Radarr</option><option value="lidarr">Lidarr</option>
        </select>
        <input className="input input-bordered input-sm flex-1 min-w-[160px]" placeholder="Base URL" value={url} onChange={e=>setUrl(e.target.value)} />
        <input className="input input-bordered input-sm" placeholder="API key" value={key} onChange={e=>setKey(e.target.value)} />
        <button type="button" className="btn btn-sm btn-primary" onClick={add}>Add</button>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        {(items||[]).map(a=>{
          const st = live[a.id];
          return (
            <div key={a.id} className="card bg-base-200 p-3 space-y-1">
              <div className="font-semibold text-sm flex items-center gap-2">
                {a.name} <span className="badge badge-xs">{a.kind}</span>
                {st && <span className={"badge badge-xs "+(st.ok?'badge-success':'badge-error')}>{st.ok?'Online':'Error'}</span>}
              </div>
              <div className="text-xs opacity-50 truncate">{a.base_url}</div>
              {st && st.version && <div className="text-[10px] opacity-40">v{st.version}</div>}
              {st && st.queue && (
                <div className="text-xs mt-1">
                  <div className="font-medium opacity-70">Queue ({st.queue.length})</div>
                  {st.queue.slice(0,3).map((q,i)=>(<div key={i} className="truncate opacity-60">{q.title||'—'} · {q.status}</div>))}
                </div>
              )}
              {st && st.calendar && st.calendar.length>0 && (
                <div className="text-xs mt-1">
                  <div className="font-medium opacity-70">Upcoming</div>
                  {st.calendar.slice(0,3).map((c,i)=>(<div key={i} className="truncate opacity-60">{c.title}</div>))}
                </div>
              )}
              {st && st.error && <div className="text-xs text-error">{st.error}</div>}
            </div>
          );
        })}
        {!items.length && <p className="text-sm opacity-50">No external instances yet.</p>}
      </div>
    </div>
  );
}

export default ExternalArrPage;
