import React, { useState, useEffect, useCallback } from "react";
import { api } from "../api.js";
import { MediaDetailShell, LibraryLegend } from "../components/ui.jsx";
import { InteractiveResultsPanel, grabPayload } from "../components/media.jsx";
function AudiobooksPage({ setPage }) {
  const [items, setItems] = useState([]);
  const [detailId, setDetailId] = useState(null);
  const [q, setQ] = useState('');
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState({});
  const load = () => api.audiobooks.list().then(setItems).catch(()=>[]);
  useEffect(()=>{ load(); }, []);
  const selectedIds = Object.keys(selected);

  if (detailId) return <AudiobookDetailPage id={detailId} onBack={()=>{ setDetailId(null); load(); }} />;

  async function searchMissing() {
    setBusy(true); setMsg(null);
    try {
      const r = await api.audiobooks.searchMissing();
      setMsg(`Searched ${r.searched||0}   grabbed ${r.grabbed||0}`);
      load();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  async function bulkMonitor(monitored) {
    setBusy(true); setMsg(null);
    try {
      await api.audiobooks.bulk({ ids: selectedIds.map(Number), monitored });
      setSelected({}); load();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  async function bulkSearchSelected() {
    setBusy(true); setMsg(null);
    try {
      for (const id of selectedIds) { await api.audiobooks.searchNow(Number(id)); }
      setMsg('Search queued for selected'); load();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }

  const filtered = (items||[]).filter(a => !q || (a.title||'').toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="mr-page-title flex-1">Audiobooks</h1>
        <button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={searchMissing}>Search missing</button>
      </div>
      {msg && <div className="alert alert-info text-xs py-2">{msg}</div>}
      {selectedIds.length > 0 && (
        <div className="card bg-base-200">
          <div className="card-body p-3 gap-2">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs opacity-60">{selectedIds.length} selected</span>
              {filtered.length > 0 && (
                <button type="button" className="btn btn-xs btn-ghost" disabled={busy} onClick={()=>{
                  const n={}; filtered.forEach(a=>{ n[a.id]=true; }); setSelected(n);
                }}>Select all visible</button>
              )}
              <button type="button" className="btn btn-xs" disabled={busy} onClick={()=>bulkMonitor(true)}>Monitor selected</button>
              <button type="button" className="btn btn-xs" disabled={busy} onClick={()=>bulkMonitor(false)}>Unmonitor selected</button>
              <button type="button" className="btn btn-xs btn-primary" disabled={busy} onClick={bulkSearchSelected}>Search selected</button>
              <button type="button" className="btn btn-xs btn-ghost" disabled={busy} onClick={()=>setSelected({})}>Clear</button>
            </div>
          </div>
        </div>
      )}
      <input className="input input-bordered input-sm" placeholder="Filter…" value={q} onChange={e=>setQ(e.target.value)} />
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
        {filtered.map(a => (
          <div key={a.id} className="relative group rounded-lg overflow-hidden bg-base-200 shadow-sm hover:ring-2 hover:ring-primary/40">
            <label className={`absolute top-2 left-2 z-10 transition-opacity ${selected[a.id] ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`} onClick={e=>e.stopPropagation()}>
              <input type="checkbox" className="checkbox checkbox-xs checkbox-primary" checked={!!selected[a.id]}
                onChange={e=>{ setSelected(prev=>{ const n={...prev}; if(e.target.checked) n[a.id]=true; else delete n[a.id]; return n; }); }} />
            </label>
            <div className="aspect-[2/3] bg-base-300 relative flex items-center justify-center cursor-pointer" onClick={()=>setDetailId(a.id)}>
              {a.poster_path
                ? <img src={a.poster_path} className="w-full h-full object-cover" alt="" loading="lazy" />
                : <span className="text-xs opacity-30">AB</span>}
              <div className={"absolute bottom-0 left-0 right-0 h-1.5 "+(a.status==='downloaded'?'bg-success':a.monitored?'bg-warning':'bg-base-content/20')} />
            </div>
            <div className="p-2 space-y-0.5">
              <div className="text-xs font-semibold line-clamp-2 min-h-[2rem]">{a.title}</div>
              <div className="text-[10px] opacity-50 truncate">{a.artist_name || a.series_name || a.status}</div>
              <span className={"badge badge-xs "+(a.monitored?'badge-success':'badge-ghost')}>{a.monitored?'Monitored':'Off'}</span>
            </div>
          </div>
        ))}
      </div>
      {!filtered.length && <div className="opacity-50 text-sm p-8 text-center">No audiobooks yet</div>}
      <LibraryLegend showTv={false} showSeries={true} />
    </div>
  );
}

function AudiobookDetailPage({ id, onBack }) {
  const [item, setItem] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const [ixResults, setIxResults] = useState(null);
  const [ixLoading, setIxLoading] = useState(false);
  const load = React.useCallback(() => { api.audiobooks.get(id).then(setItem).catch(e=>setMsg(String(e.message||e))); }, [id]);
  useEffect(()=>{ load(); }, [load]);

  
  async function setTrackStatus(status) {
    setBusy(true); setMsg(null);
    try {
      const r = await fetch('/api/tracking', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ media_item_id: id, status }),
      });
      if (!r.ok) throw new Error((await r.json().catch(()=>({}))).detail || 'Track failed');
      setMsg('Tracking: ' + String(status).replace(/_/g, ' '));
    } catch (e) { setMsg(String(e.message || e)); }
    finally { setBusy(false); }
  }

  async function autoSearch() {
    setBusy(true);
    try {
      const r = await api.audiobooks.searchNow(id);
      setMsg(r?.title ? `Grabbed: ${r.title}` : (r?.found===false ? 'No release found' : JSON.stringify(r)));
      load();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  async function openIx() {
    setIxLoading(true); setIxResults([]);
    try { const d = await api.audiobooks.interactive(id); setIxResults(d && !Array.isArray(d) ? d : { results: Array.isArray(d)?d:(d?.results||[]), rejected: d?.rejected||[] }); }
    catch(e) { setMsg(String(e.message||e)); }
    setIxLoading(false);
  }
  async function grabRel(rel) {
    setBusy(true);
    try {
      await api.audiobooks.grab(id, grabPayload(rel));
      setMsg('Grabbed: '+rel.title); setIxResults(null); load();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  async function toggleMon() {
    setBusy(true);
    try { await api.audiobooks.update(id, { monitored: !item.monitored }); load(); }
    catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  if (!item) return <div className="p-6 opacity-50">Loading…</div>;
  return (
    <MediaDetailShell
      title={item.title} year={item.year} poster={item.poster_path}
      status={item.status} monitored={item.monitored} overview={item.overview}
      filePath={item.file_path} qualityProfile={item.quality_profile}
      msg={msg} busy={busy} onBack={onBack}
      actions={<>
        <button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={autoSearch}>Search & grab</button>
        <button type="button" className="btn btn-sm btn-accent" disabled={busy} title="Add top result as stream"
          onClick={async ()=>{
            setBusy(true);
            try {
              const rows = typeof openIx==='function' ? null : null;
              const data = await api.audiobooks.interactive(id);
              const list = data.results || data || [];
              const first = Array.isArray(list)?list[0]:null;
              if (first) {
                await fetch('/api/overhaul/streams',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:first.title||'stream',stream_url:first.download_url||first.magnet||'',provider:first.indexer||'search'})});
                setMsg('Stream link added');
              } else setMsg('No release for stream');
            } catch(e){ setMsg(String(e.message||e)); }
            setBusy(false);
          }}>Stream</button>
        <button type="button" className="btn btn-sm btn-secondary" disabled={busy||ixLoading} onClick={openIx}>Interactive search</button>
        <button type="button" className="btn btn-sm" disabled={busy} onClick={toggleMon}>{item.monitored?'Unmonitor':'Monitor'}</button>
        <select className="select select-bordered select-sm" defaultValue="" disabled={busy}
          onChange={e=>{ if(e.target.value) { setTrackStatus(e.target.value); e.target.value=''; } }} title="Unified tracking">
          <option value="">Track…</option>
          <option value="planned">Planned</option>
          <option value="in_progress">In progress</option>
          <option value="completed">Completed</option>
          <option value="on_hold">On hold</option>
          <option value="dropped">Dropped</option>
        </select>
        <button type="button" className="btn btn-sm btn-ghost text-error" onClick={async()=>{ await api.audiobooks.remove(id); onBack(); }}>Delete</button>
      </>}
    >
      {(ixLoading || ixResults) && (
        <InteractiveResultsPanel data={Array.isArray(ixResults) ? { results: ixResults, rejected: [] } : (ixResults || { results: [], rejected: [] })} loading={ixLoading} busy={busy} onGrab={grabRel} onClose={()=>setIxResults(null)} />
      )}
    </MediaDetailShell>
  );
}




export { AudiobooksPage, AudiobookDetailPage };
