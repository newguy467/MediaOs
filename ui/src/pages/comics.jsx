import React, { useState, useEffect, useCallback, useRef } from "react";
import Ic, { Icons, P } from "../icons.jsx";
import { getToken, setToken, getAdvanced, setAdvancedFlag, AUTH_TOKEN_KEY } from "../storage.js";
import { api, TMDB, adultFetch } from "../api.js";
import { PageChrome, PosterTile, LibraryModuleShell, MediaDetailShell, LibraryLegend, LibraryHeader, MediaCard, StatusBadgeStack, libraryStatuses, CollectionProgressWidget, TeachEmpty, AddModal } from "../components/ui.jsx";
import { InteractiveResultsPanel, InteractiveResultsTable, MediaPlayer, HlsVideo, grabPayload, releaseDownloadUrl } from "../components/media.jsx";

function ComicsPullPanel() {
  const [rows, setRows] = useState([]);
  const [msg, setMsg] = useState(null);
  const load = () => fetch('/api/overhaul/comics/pull-list').then(r=>r.json()).then(setRows).catch(()=>[]);
  useEffect(()=>{ load(); }, []);
  return (
    <div className="card bg-base-200 mb-4">
      <div className="card-body p-3 gap-2">
        <div className="flex items-center gap-2">
          <h2 className="font-semibold text-sm flex-1">Weekly pull-list</h2>
          <button type="button" className="btn btn-xs" onClick={async()=>{
            setMsg('Syncing…');
            const r = await fetch('/api/overhaul/comics/pull-list/sync',{method:'POST'}).then(x=>x.json()).catch(e=>({error:String(e)}));
            setMsg(JSON.stringify(r));
            load();
          }}>Sync now</button>
        </div>
        {msg && <p className="text-[10px] opacity-60 truncate">{msg}</p>}
        <div className="overflow-x-auto max-h-48">
          <table className="table table-xs">
            <thead><tr><th>Series</th><th>#</th><th>Date</th><th></th></tr></thead>
            <tbody>
              {(rows||[]).map(r=>(
                <tr key={r.id}><td>{r.series_name}</td><td>{r.issue_number||'—'}</td><td>{r.release_date||'—'}</td>
                <td>{r.grabbed?'✓':''}</td></tr>
              ))}
              {!(rows||[]).length && <tr><td colSpan={4} className="opacity-50">Empty — sync or add monitored comics with issue dates</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function ComicsPage({ setPage }) {
  const [items, setItems] = useState([]);
  const [detailId, setDetailId] = useState(null);
  const [tab, setTab] = useState('library'); // library | arcs | pull
  const [arcs, setArcs] = useState([]);
  const [arcDetail, setArcDetail] = useState(null);
  const [pull, setPull] = useState([]);
  const [q, setQ] = useState('');
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [newArcName, setNewArcName] = useState('');
  const [newPull, setNewPull] = useState({ series_name:'', issue_number:'', publisher:'', release_date:'' });

  const load = () => fetch('/api/comics').then(r=>r.json()).then(setItems).catch(()=>[]);
  const loadArcs = () => fetch('/api/comics/arcs').then(r=>r.json()).then(setArcs).catch(()=>[]);
  const loadPull = () => fetch('/api/comics/pull').then(r=>r.json()).then(setPull).catch(()=>[]);
  useEffect(()=>{ load(); }, []);
  useEffect(()=>{ if (tab==='arcs') loadArcs(); if (tab==='pull') loadPull(); }, [tab]);

  if (detailId) {
    return <ComicDetailPage comicId={detailId} onBack={()=>{ setDetailId(null); load(); }} />;
  }

  async function searchMissing() {
    setBusy(true); setMsg(null);
    try {
      const r = await fetch('/api/comics/search-missing',{method:'POST'}).then(x=>x.json());
      setMsg(`Searched ${r.searched||0} · grabbed ${r.grabbed||0}`);
      load();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }

  async function createArc() {
    if (!newArcName.trim()) return;
    setBusy(true);
    try {
      await fetch('/api/comics/arcs', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ name: newArcName.trim() }) });
      setNewArcName(''); loadArcs(); setMsg('Arc created');
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }

  async function openArc(id) {
    const d = await fetch('/api/comics/arcs/'+id).then(r=>r.json());
    setArcDetail(d);
  }

  async function addPull() {
    if (!newPull.series_name.trim()) return;
    setBusy(true);
    try {
      await fetch('/api/comics/pull', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(newPull) });
      setNewPull({ series_name:'', issue_number:'', publisher:'', release_date:'' });
      loadPull(); setMsg('Added to pull list');
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }

  async function togglePull(id, field, value) {
    await fetch('/api/comics/pull/'+id, { method:'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ [field]: value }) });
    loadPull();
  }

  const filtered = (items||[]).filter(c => !q || (c.title||'').toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex-1 min-w-[140px]">
          <h1 className="mr-page-title">Comics</h1>
          <p className="text-xs opacity-50">Library · story arcs · weekly pull list</p>
        </div>
        <div className="join">
          <button type="button" className={"btn btn-sm join-item "+(tab==='library'?'btn-primary':'')} onClick={()=>setTab('library')}>Library</button>
          <button type="button" className={"btn btn-sm join-item "+(tab==='arcs'?'btn-primary':'')} onClick={()=>setTab('arcs')}>Story arcs</button>
          <button type="button" className={"btn btn-sm join-item "+(tab==='pull'?'btn-primary':'')} onClick={()=>setTab('pull')}>Pull list</button>
        </div>
        {tab==='library' && <button type="button" className="btn btn-sm btn-secondary" disabled={busy} onClick={searchMissing}>Search missing</button>}
      </div>
      {msg && <div className="alert alert-info text-xs py-2">{msg}</div>}

      {tab==='library' && (
        <>
          <input className="input input-bordered input-sm w-full max-w-md" placeholder="Filter series…" value={q} onChange={e=>setQ(e.target.value)} />
          <div className="poster-grid">
            {filtered.map(c => (
              <PosterTile key={c.id} title={c.title} year={c.year} poster={c.poster_path} status={c.status}
                onClick={()=>setDetailId(c.id)} />
            ))}
            {!filtered.length && <div className="col-span-full opacity-50 text-sm p-6">No comics yet</div>}
          </div>
        </>
      )}

      {tab==='arcs' && (
        <div className="grid lg:grid-cols-5 gap-4">
          <div className="lg:col-span-2 space-y-3">
            <div className="flex gap-2">
              <input className="input input-bordered input-sm flex-1" placeholder="New story arc name" value={newArcName} onChange={e=>setNewArcName(e.target.value)} />
              <button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={createArc}>Create</button>
            </div>
            <div className="space-y-1 max-h-[60vh] overflow-y-auto">
              {(arcs||[]).map(a=>(
                <button key={a.id} type="button"
                  className={"w-full text-left p-3 rounded-xl border transition "+(arcDetail?.id===a.id?'border-primary bg-primary/10':'border-base-content/10 bg-base-200 hover:bg-base-300')}
                  onClick={()=>openArc(a.id)}>
                  <div className="font-medium text-sm">{a.name}</div>
                  <div className="text-[10px] opacity-50">{a.issues_linked||a.issue_count||0} issues in reading order</div>
                </button>
              ))}
              {!arcs.length && <p className="text-sm opacity-50 p-4">No story arcs yet — create one to build a reading order.</p>}
            </div>
          </div>
          <div className="lg:col-span-3 card bg-base-200 border border-base-content/5">
            <div className="card-body p-4 gap-3">
              {!arcDetail && <p className="text-sm opacity-50">Select an arc to view reading order and issue links.</p>}
              {arcDetail && (
                <>
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h2 className="font-semibold text-lg">{arcDetail.name}</h2>
                      {arcDetail.description && <p className="text-xs opacity-60 mt-1">{arcDetail.description}</p>}
                    </div>
                    <button type="button" className="btn btn-ghost btn-xs text-error" onClick={async()=>{
                      if (!confirm('Delete arc?')) return;
                      await fetch('/api/comics/arcs/'+arcDetail.id,{method:'DELETE'});
                      setArcDetail(null); loadArcs();
                    }}>Delete</button>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="table table-sm">
                      <thead><tr><th>#</th><th>Series</th><th>Issue</th><th>Linked</th></tr></thead>
                      <tbody>
                        {(arcDetail.issues||[]).map(iss=>(
                          <tr key={iss.id}>
                            <td className="tabular-nums opacity-50">{iss.reading_order||'—'}</td>
                            <td>{iss.series_name}</td>
                            <td>{iss.issue_number||'—'}</td>
                            <td>{iss.media_item_id ? <span className="badge badge-success badge-xs">yes</span> : <span className="badge badge-ghost badge-xs">no</span>}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {!(arcDetail.issues||[]).length && <p className="text-xs opacity-50">No issues in this arc yet. Add via API or pull-list linking.</p>}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {tab==='pull' && (
        <div className="space-y-4">
          <div className="card bg-base-200 border border-base-content/5">
            <div className="card-body p-4 gap-2">
              <h3 className="font-semibold text-sm">Add to weekly pull</h3>
              <div className="grid sm:grid-cols-4 gap-2">
                <input className="input input-bordered input-sm" placeholder="Series" value={newPull.series_name} onChange={e=>setNewPull({...newPull, series_name:e.target.value})} />
                <input className="input input-bordered input-sm" placeholder="Issue #" value={newPull.issue_number} onChange={e=>setNewPull({...newPull, issue_number:e.target.value})} />
                <input className="input input-bordered input-sm" placeholder="Publisher" value={newPull.publisher} onChange={e=>setNewPull({...newPull, publisher:e.target.value})} />
                <input className="input input-bordered input-sm" type="date" value={newPull.release_date} onChange={e=>setNewPull({...newPull, release_date:e.target.value})} />
              </div>
              <button type="button" className="btn btn-sm btn-primary w-fit" disabled={busy} onClick={addPull}>Add</button>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="table table-sm">
              <thead><tr><th>Series</th><th>Issue</th><th>Publisher</th><th>Date</th><th>Watch</th><th>Grabbed</th></tr></thead>
              <tbody>
                {(pull||[]).map(p=>(
                  <tr key={p.id}>
                    <td className="font-medium">{p.series_name}</td>
                    <td>{p.issue_number||'—'}</td>
                    <td className="opacity-60">{p.publisher||'—'}</td>
                    <td className="tabular-nums text-xs">{p.release_date||'—'}</td>
                    <td><input type="checkbox" className="checkbox checkbox-xs" checked={!!p.watched} onChange={e=>togglePull(p.id,'watched',e.target.checked)} /></td>
                    <td><input type="checkbox" className="checkbox checkbox-xs checkbox-success" checked={!!p.grabbed} onChange={e=>togglePull(p.id,'grabbed',e.target.checked)} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!pull.length && <p className="text-sm opacity-50 p-4">Pull list empty — add this week’s issues manually or run pull sync when configured.</p>}
          </div>
        </div>
      )}
    </div>
  );
}

function ComicDetailPage({ comicId, onBack }) {
  const [item, setItem] = useState(null);
  const [issues, setIssues] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const [ixResults, setIxResults] = useState(null);
  const [ixLoading, setIxLoading] = useState(false);

  const load = React.useCallback(() => {
    fetch('/api/comics/'+comicId).then(r=>r.json()).then(setItem).catch(e=>setMsg(String(e.message||e)));
    fetch('/api/comics/'+comicId+'/issues').then(r=>r.json()).then(d=>setIssues(Array.isArray(d)?d:[])).catch(()=>[]);
  }, [comicId]);
  useEffect(()=>{ load(); }, [load]);

  async function autoSearch() {
    setBusy(true); setMsg(null);
    try {
      const r = await fetch(`/api/comics/${comicId}/search`,{method:'POST'}).then(x=>x.json());
      setMsg(r?.title ? `Grabbed: ${r.title}` : JSON.stringify(r));
      load();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  async function openIx() {
    setIxLoading(true); setIxResults([]);
    try {
      const data = await fetch(`/api/comics/${comicId}/interactive-search`).then(x=>x.json()); setIxResults(data && !Array.isArray(data) ? data : { results: data?.results || data || [], rejected: data?.rejected || [] }); const rows = data?.results || data || [];
      setIxResults(rows||[]);
    } catch(e) { setMsg(String(e.message||e)); }
    setIxLoading(false);
  }
  async function grabRel(rel) {
    setBusy(true);
    try {
      await fetch(`/api/comics/${comicId}/grab`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(grabPayload(rel))});
      setMsg('Grabbed: '+rel.title); setIxResults(null); load();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  async function syncIssues() {
    setBusy(true);
    try {
      const r = await fetch(`/api/comics/${comicId}/issues/sync`,{method:'POST'}).then(x=>x.json());
      setMsg(`Issues synced: ${r.count||r.synced||JSON.stringify(r)}`);
      load();
    } catch(e) { setMsg(String(e.message||e)); }
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
              const data = await fetch(`/api/comics/${comicId}/interactive-search`).then(r=>r.json()).catch(()=>({}));
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
        <button type="button" className="btn btn-sm" disabled={busy} onClick={syncIssues}>Sync issues</button>
        <button type="button" className="btn btn-sm btn-ghost text-error" onClick={async()=>{ await fetch('/api/comics/'+comicId,{method:'DELETE'}); onBack(); }}>Delete</button>
      </>}
    >
      <InteractiveResultsTable results={ixResults} loading={ixLoading} busy={busy} onGrab={grabRel} onClose={()=>setIxResults(null)} />
      {issues.length>0 && (
        <div className="card bg-base-200"><div className="card-body p-4">
          <h3 className="font-semibold text-sm">Issues ({issues.length})</h3>
          <div className="overflow-x-auto max-h-64 overflow-y-auto">
            <table className="table table-xs">
              <thead><tr><th>#</th><th>Title</th><th>Status</th><th>Mon</th></tr></thead>
              <tbody>
                {issues.map(iss=>(
                  <tr key={iss.id}>
                    <td>{iss.issue_number}</td>
                    <td className="text-xs">{iss.title||'—'}</td>
                    <td><span className="badge badge-xs">{iss.status}</span></td>
                    <td>{iss.monitored?'✓':'—'}</td>
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




export { ComicsPullPanel, ComicsPage, ComicDetailPage };
