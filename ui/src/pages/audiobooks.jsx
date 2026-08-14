import React, { useState, useEffect, useCallback, useRef } from "react";
import Ic, { Icons, P } from "../icons.jsx";
import { getToken, setToken, getAdvanced, setAdvancedFlag, AUTH_TOKEN_KEY } from "../storage.js";
import { api, TMDB, adultFetch } from "../api.js";
import { PageChrome, PosterTile, LibraryModuleShell, MediaDetailShell, LibraryLegend, LibraryHeader, MediaCard, StatusBadgeStack, libraryStatuses, CollectionProgressWidget, TeachEmpty, AddModal } from "../components/ui.jsx";
import { InteractiveResultsPanel, InteractiveResultsTable, MediaPlayer, HlsVideo, grabPayload, releaseDownloadUrl } from "../components/media.jsx";

function AudiobooksPage({ setPage }) {
  const [items, setItems] = useState([]);
  const [detailId, setDetailId] = useState(null);
  const [q, setQ] = useState('');
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = () => api.audiobooks.list().then(setItems).catch(()=>[]);
  useEffect(()=>{ load(); }, []);

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

  const filtered = (items||[]).filter(a => !q || (a.title||'').toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="mr-page-title flex-1">Audiobooks</h1>
        <button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={searchMissing}>Search missing</button>
      </div>
      {msg && <div className="alert alert-info text-xs py-2">{msg}</div>}
      <input className="input input-bordered input-sm" placeholder="Filter…" value={q} onChange={e=>setQ(e.target.value)} />
      <div className="space-y-2 max-w-3xl">
        {filtered.map(a => (
          <div key={a.id} className="mr-row cursor-pointer" onClick={() => setDetailId(a.id)}>
            {a.poster_path
              ? <img className="thumb" src={a.poster_path} alt="" />
              : <div className="thumb flex items-center justify-center text-xs opacity-30">AB</div>}
            <div className="flex-1 min-w-0">
              <div className="font-semibold text-sm truncate">{a.title}</div>
              <div className="text-xs opacity-50 truncate">{a.artist_name || a.series_name || a.status}</div>
            </div>
            <div className="mr-progress"><span style={{ width: a.status==='downloaded' ? '100%' : '40%' }} /></div>
            <span className="text-xs opacity-60 w-10 text-right">{a.status==='downloaded'?'100%':'40%'}</span>
          </div>
        ))}
        {!filtered.length && <div className="opacity-50 text-sm p-8 text-center">No audiobooks yet</div>}
      </div>
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
