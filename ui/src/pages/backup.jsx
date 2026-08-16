import React, { useState, useEffect } from "react";

function BackupPage() {
  const [items, setItems] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const [includeDb, setIncludeDb] = useState(true);
  const [includeConfig, setIncludeConfig] = useState(true);
  const [note, setNote] = useState('');

  const load = () => fetch('/api/system/backup').then(r=>r.json()).then(d=>setItems(d.items||[])).catch(() =>
    fetch('/api/backup').then(r=>r.json()).then(d=>setItems(d.items||[])).catch(e=>setMsg(String(e)))
  );
  useEffect(()=>{ load(); }, []);

  const create = async () => {
    setBusy(true); setMsg('');
    try {
      let r = await fetch('/api/system/backup', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ include_db: includeDb, include_config: includeConfig, note }),
      }).then(async res => ({ ok: res.ok, status: res.status, body: await res.json().catch(()=>({})) }));
      if (r.status === 404) {
        r = await fetch('/api/backup', { method:'POST' }).then(async res => ({ ok: res.ok, body: await res.json().catch(()=>({})) }));
      }
      setMsg(r.body?.path || r.body?.ok ? `Created ${r.body.path || 'backup'}` : JSON.stringify(r.body));
      load();
    } catch(e) { setMsg(String(e)); }
    setBusy(false);
  };

  return (
    <div className="page-shell space-y-4 max-w-2xl">
      <h1 className="mr-page-title">Backup wizard</h1>
      <p className="text-sm opacity-60">Create config + database snapshot zips. Schedule via host cron calling the API if needed.</p>
      {msg && <div className="alert alert-info text-xs py-2">{msg}</div>}

      <div className="card bg-base-200">
        <div className="card-body p-4 gap-2">
          <h2 className="font-semibold text-sm">What to include</h2>
          <label className="label cursor-pointer justify-start gap-2">
            <input type="checkbox" className="checkbox checkbox-sm" checked={includeDb} onChange={e=>setIncludeDb(e.target.checked)} />
            <span className="label-text text-sm">Database</span>
          </label>
          <label className="label cursor-pointer justify-start gap-2">
            <input type="checkbox" className="checkbox checkbox-sm" checked={includeConfig} onChange={e=>setIncludeConfig(e.target.checked)} />
            <span className="label-text text-sm">Config / settings</span>
          </label>
          <input className="input input-bordered input-sm" placeholder="Optional note" value={note} onChange={e=>setNote(e.target.value)} />
          <button type="button" className="btn btn-sm btn-primary w-fit" disabled={busy || (!includeDb && !includeConfig)} onClick={create}>
            {busy?'Working…':'Create backup'}
          </button>
          <p className="text-[10px] opacity-50">Example cron: <code>0 3 * * * curl -X POST -H "X-Api-Key: …" http://localhost:8787/api/system/backup</code></p>
        </div>
      </div>

      <h2 className="font-semibold text-sm">Existing backups</h2>
      <ul className="space-y-1">
        {(items||[]).map(b=>(
          <li key={b.name||b.path} className="flex gap-3 text-sm p-2 rounded bg-base-200 items-center">
            <span className="font-mono text-xs flex-1 truncate">{b.name||b.path}</span>
            <span className="text-xs opacity-50">{Math.round((b.size_bytes||0)/1024)} KB</span>
            <span className="text-xs opacity-40">{(b.modified_at||b.created_at||'').slice(0,19)}</span>
            <button type="button" className="btn btn-xs btn-warning" disabled={busy} onClick={async()=>{
              if(!window.confirm('Restore this backup? Restart recommended after.')) return;
              setBusy(true);
              try {
                const r = await fetch('/api/system/backup/restore',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:b.path||b.name})}).then(async x=>({ok:x.ok, body:await x.json().catch(()=>({}))}));
                const r2 = r.ok ? r : await fetch('/api/backup/restore',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:b.path||b.name})}).then(async x=>({ok:x.ok, body:await x.json().catch(()=>({}))}));
                setMsg(r2.body?.ok?('Restored: '+(r2.body.restored||[]).join(', ')):JSON.stringify(r2.body));
              } catch(e){ setMsg(String(e)); }
              setBusy(false);
            }}>Restore</button>
          </li>
        ))}
        {!items.length && <p className="text-sm opacity-50">No backups yet.</p>}
      </ul>
    </div>
  );
}

export default BackupPage;
