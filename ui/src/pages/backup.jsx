import React, { useState, useEffect, useCallback } from "react";
import { LibraryModuleShell, TeachEmpty, PageChrome } from "../components/ui.jsx";


function BackupPage() {
  const [items, setItems] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const load = () => fetch('/api/backup').then(r=>r.json()).then(d=>setItems(d.items||[])).catch(e=>setMsg(String(e)));
  useEffect(()=>{ load(); }, []);
  const create = async () => {
    setBusy(true); setMsg('');
    try {
      const r = await fetch('/api/backup', { method:'POST' }).then(r=>r.json());
      setMsg(r.ok ? `Created ${r.path}` : JSON.stringify(r));
      load();
    } catch(e) { setMsg(String(e)); }
    setBusy(false);
  };
  return (
    <div className="page-shell space-y-4">
      <h1 className="mr-page-title">Backup</h1>
      <p className="text-sm opacity-60">Config + database snapshot zips.</p>
      {msg && <div className="alert alert-info text-xs py-2">{msg}</div>}
      <button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={create}>{busy?'Working…':'Create backup'}</button>
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
                const r = await fetch('/api/backup/restore',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:b.path||b.name})}).then(x=>x.json());
                setMsg(r.ok?('Restored: '+(r.restored||[]).join(', ')):JSON.stringify(r));
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
