import React, { useState, useEffect, useCallback, useRef } from "react";
import Ic, { Icons, P } from "../icons.jsx";
import { getToken, setToken, getAdvanced, setAdvancedFlag, AUTH_TOKEN_KEY } from "../storage.js";
import { api, TMDB, adultFetch } from "../api.js";
import { PageChrome, PosterTile, LibraryModuleShell, MediaDetailShell, LibraryLegend, LibraryHeader, MediaCard, StatusBadgeStack, libraryStatuses, CollectionProgressWidget, TeachEmpty, AddModal } from "../components/ui.jsx";
import { InteractiveResultsPanel, InteractiveResultsTable, MediaPlayer, HlsVideo, grabPayload, releaseDownloadUrl } from "../components/media.jsx";

function MusicPage({ setPage }) {
  const [items, setItems] = useState([]);
  const [tree, setTree] = useState([]);
  const [view, setView] = useState('hierarchy'); // hierarchy | grid | incomplete
  const [detailId, setDetailId] = useState(null);
  const [expanded, setExpanded] = useState({});
  const [incomplete, setIncomplete] = useState([]);
  const [q, setQ] = useState('');
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = () => {
    api.music.list().then(setItems).catch(()=>[]);
    fetch('/api/music/artists/tree').then(r=>r.json()).then(d=>setTree(d.artists||[])).catch(()=>[]);
  };
  useEffect(()=>{ load(); }, []);
  useEffect(()=>{
    if (view === 'incomplete') {
      fetch('/api/music/incomplete').then(r=>r.json()).then(setIncomplete).catch(()=>setIncomplete([]));
    }
  }, [view]);

  if (detailId) return <MusicDetailPage id={detailId} onBack={()=>{ setDetailId(null); load(); }} />;

  async function searchMissing() {
    setBusy(true); setMsg(null);
    try {
      const r = await api.music.searchMissing();
      setMsg(`Searched ${r.searched||0} · grabbed ${r.grabbed||0}`);
      load();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }

  const filteredTree = (tree||[]).filter(a => {
    if (!q) return true;
    const s = q.toLowerCase();
    if ((a.name||'').toLowerCase().includes(s)) return true;
    return (a.albums||[]).some(al => (al.title||'').toLowerCase().includes(s));
  });

  const filteredGrid = (items||[]).filter(a => {
    if (!q) return true;
    const s = q.toLowerCase();
    return (a.title||'').toLowerCase().includes(s) || (a.artist_name||'').toLowerCase().includes(s);
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex-1 min-w-[160px]">
          <h1 className="mr-page-title">Music</h1>
          <p className="text-xs opacity-50">Artist → album → track hierarchy</p>
        </div>
        <div className="join">
          <button type="button" className={"btn btn-sm join-item "+(view==='hierarchy'?'btn-primary':'')} onClick={()=>setView('hierarchy')}>Hierarchy</button>
          <button type="button" className={"btn btn-sm join-item "+(view==='grid'?'btn-primary':'')} onClick={()=>setView('grid')}>Albums</button>
          <button type="button" className={"btn btn-sm join-item "+(view==='incomplete'?'btn-primary':'')} onClick={()=>setView('incomplete')}>Incomplete</button>
        </div>
        <button type="button" className="btn btn-sm btn-secondary" disabled={busy} onClick={searchMissing}>Search missing</button>
        <button type="button" className="btn btn-sm" onClick={()=>setPage && setPage('discover')}>Discover</button>
      </div>
      {msg && <div className="alert alert-info text-xs py-2">{msg}</div>}
      <input className="input input-bordered input-sm w-full max-w-md" placeholder="Filter artist or album…" value={q} onChange={e=>setQ(e.target.value)} />

      {view === 'hierarchy' && (
        <div className="space-y-1">
          {filteredTree.map(artist => {
            const open = expanded[artist.name];
            const dl = (artist.albums||[]).filter(a=>a.status==='downloaded').length;
            return (
              <div key={artist.name} className="card bg-base-200/80 border border-base-content/5 overflow-hidden">
                <button type="button" className="flex items-center gap-3 p-3 w-full text-left hover:bg-base-300/40"
                  onClick={()=>setExpanded(e=>({...e, [artist.name]: !open}))}>
                  <span className="text-xs opacity-40 w-4">{open?'▼':'▶'}</span>
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-sm truncate">{artist.name}</div>
                    <div className="text-[10px] opacity-50">{artist.album_count} albums · {dl} on disk</div>
                  </div>
                  <span className="badge badge-sm badge-ghost">{artist.album_count}</span>
                </button>
                {open && (
                  <div className="border-t border-base-content/5 divide-y divide-base-content/5">
                    {(artist.albums||[]).map(al => (
                      <button key={al.id} type="button"
                        className="flex items-center gap-3 px-4 py-2 w-full text-left hover:bg-primary/10"
                        onClick={()=>setDetailId(al.id)}>
                        <div className="w-10 h-10 rounded bg-base-300 overflow-hidden shrink-0">
                          {al.poster_path ? <img src={al.poster_path} alt="" className="object-cover w-full h-full"/> : null}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium truncate">{al.title}</div>
                          <div className="text-[10px] opacity-50">{al.year||'—'} · {al.monitored?'monitored':'unmonitored'}</div>
                        </div>
                        <span className={'badge badge-xs '+(al.status==='downloaded'?'badge-success':al.status==='wanted'?'badge-warning':'badge-ghost')}>{al.status}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
          {!filteredTree.length && <div className="opacity-50 text-sm p-6">No artists yet — add albums from Discover or search.</div>}
        </div>
      )}

      {view === 'grid' && (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
          {filteredGrid.map(a=>(
            <div key={a.id} className="card bg-base-200 shadow-sm cursor-pointer hover:ring-1 hover:ring-primary/40" onClick={()=>setDetailId(a.id)}>
              <figure className="aspect-square bg-base-300 overflow-hidden">
                {a.poster_path ? <img src={a.poster_path} alt="" className="object-cover w-full h-full" /> : <div className="flex items-center justify-center h-full opacity-30 text-xs">No art</div>}
              </figure>
              <div className="card-body p-2 gap-0.5">
                <div className="text-xs font-semibold line-clamp-1">{a.title}</div>
                <div className="text-[10px] opacity-60 line-clamp-1">{a.artist_name||''}</div>
                <span className={'badge badge-xs '+(a.status==='downloaded'?'badge-success':'badge-warning')}>{a.status}</span>
              </div>
            </div>
          ))}
          {!filteredGrid.length && <div className="col-span-full opacity-50 text-sm p-6">No albums yet</div>}
        </div>
      )}

      {view === 'incomplete' && (
        <div className="space-y-2">
          {(incomplete||[]).map(c=>(
            <div key={c.album_id} className="card bg-base-200 border border-warning/20">
              <div className="card-body p-3 gap-2">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <div className="font-medium text-sm">{c.title}</div>
                    <div className="text-xs opacity-50">{c.artist}</div>
                  </div>
                  <button type="button" className="btn btn-xs btn-primary" onClick={()=>setDetailId(c.album_id)}>Open</button>
                </div>
                <div className="flex items-center gap-3">
                  <progress className="progress progress-warning w-full" value={c.percent||0} max="100"></progress>
                  <span className="text-xs tabular-nums shrink-0">{c.percent}% · {c.tracks_have}/{c.tracks_total}</span>
                </div>
                {c.missing?.length>0 && (
                  <div className="text-[10px] opacity-60 line-clamp-2">Missing: {c.missing.map(m=>m.title).join(', ')}</div>
                )}
              </div>
            </div>
          ))}
          {!incomplete.length && <div className="opacity-50 text-sm p-6">All monitored albums look complete (or no track data yet).</div>}
        </div>
      )}
    </div>
  );
}

function MusicDetailPage({ id, onBack }) {
  const [item, setItem] = useState(null);
  const [tracks, setTracks] = useState([]);
  const [completeness, setCompleteness] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const [ixResults, setIxResults] = useState(null);
  const [ixLoading, setIxLoading] = useState(false);
  const load = React.useCallback(() => {
    api.music.get(id).then(setItem).catch(e=>setMsg(String(e.message||e)));
    fetch(`/api/music/album/${id}/tracks`).then(r=>r.json()).then(d=>setTracks(Array.isArray(d)?d:[])).catch(()=>[]);
    fetch(`/api/music/album/${id}/completeness`).then(r=>r.json()).then(setCompleteness).catch(()=>setCompleteness(null));
  }, [id]);
  useEffect(()=>{ load(); }, [load]);

  async function autoSearch() {
    setBusy(true);
    try {
      const r = await api.music.searchNow(id);
      const body = r && r.json ? await r.json().catch(()=>null) : r;
      setMsg(body?.title ? `Grabbed: ${body.title}` : 'Search done');
      load();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  async function openIx() {
    setIxLoading(true); setIxResults([]);
    try { const d = await api.music.interactive(id); setIxResults(d && !Array.isArray(d) ? d : { results: Array.isArray(d)?d:(d?.results||[]), rejected: d?.rejected||[] }); }
    catch(e) { setMsg(String(e.message||e)); }
    setIxLoading(false);
  }
  async function grabRel(rel) {
    setBusy(true);
    try {
      await api.music.grab(id, grabPayload(rel));
      setMsg('Grabbed: '+rel.title); setIxResults(null); load();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  async function toggleMon() {
    setBusy(true);
    try { await api.music.update(id, { monitored: !item.monitored }); load(); }
    catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  if (!item) return <div className="p-6 opacity-50">Loading…</div>;
  return (
    <MediaDetailShell
      title={item.title} year={item.year} poster={item.poster_path}
      status={item.status} monitored={item.monitored}
      overview={item.artist_name ? `Artist: ${item.artist_name}` : item.overview}
      filePath={item.file_path} qualityProfile={item.quality_profile}
      msg={msg} busy={busy} onBack={onBack}
      actions={<>
        <button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={autoSearch}>Search & grab</button>
        <button type="button" className="btn btn-sm btn-accent" disabled={busy} title="Add top result as stream"
          onClick={async ()=>{
            setBusy(true);
            try {
              const rows = typeof openIx==='function' ? null : null;
              const data = await api.music.interactive(id);
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
        <button type="button" className="btn btn-sm btn-ghost text-error" onClick={async()=>{ await api.music.remove(id); onBack(); }}>Delete</button>
      </>}
    >
      {(ixLoading || ixResults) && (
        <InteractiveResultsPanel data={Array.isArray(ixResults) ? { results: ixResults, rejected: [] } : (ixResults || { results: [], rejected: [] })} loading={ixLoading} busy={busy} onGrab={grabRel} onClose={()=>setIxResults(null)} />
      )}
      {completeness && (
        <div className="card bg-base-200 border border-base-content/5">
          <div className="card-body p-3 gap-2">
            <div className="flex items-center justify-between text-sm">
              <span className="font-semibold">Album completeness</span>
              <span className="tabular-nums text-xs">{completeness.percent}% · {completeness.tracks_have}/{completeness.tracks_total}</span>
            </div>
            <progress className={"progress w-full "+(completeness.complete?'progress-success':'progress-warning')} value={completeness.percent||0} max="100"></progress>
          </div>
        </div>
      )}
      {(tracks.length>0 || completeness) && (
        <div className="card bg-base-200"><div className="card-body p-4 gap-2">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-sm">Tracks ({tracks.length})</h3>
            <button type="button" className="btn btn-ghost btn-xs" onClick={async()=>{
              try {
                await fetch(`/api/music/album/${id}/tracks/refresh`, {method:'POST'});
                const d = await fetch(`/api/music/album/${id}/tracks`).then(r=>r.json());
                setTracks(Array.isArray(d)?d:[]);
                const c = await fetch(`/api/music/album/${id}/completeness`).then(r=>r.json());
                setCompleteness(c);
              } catch(e) { setMsg(String(e.message||e)); }
            }}>Refresh from MusicBrainz</button>
          </div>
          <div className="overflow-x-auto max-h-64">
            <table className="table table-xs">
              <thead><tr><th>#</th><th>Title</th><th>Disc</th><th>Status</th></tr></thead>
              <tbody>
                {tracks.map((tr,i)=>(
                  <tr key={tr.id||i} className={tr.file_path || tr.status==='downloaded' ? 'opacity-100' : 'opacity-70'}>
                    <td className="tabular-nums opacity-50">{tr.track_number||i+1}</td>
                    <td className="truncate max-w-[220px]">{tr.title||tr.name}</td>
                    <td className="opacity-50">{tr.disc_number||1}</td>
                    <td><span className={'badge badge-xs '+(tr.file_path||tr.status==='downloaded'?'badge-success':'badge-ghost')}>{tr.file_path||tr.status==='downloaded'?'have':(tr.status||'wanted')}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div></div>
      )}
    </MediaDetailShell>
  );
}







export { MusicPage, MusicDetailPage };
