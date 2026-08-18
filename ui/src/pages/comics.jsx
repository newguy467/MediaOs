import React, { useState, useEffect, useCallback, useRef } from "react";
import Ic from "../icons.jsx";
import { api } from "../api.js";
import { PosterTile, MediaDetailShell } from "../components/ui.jsx";
import { InteractiveResultsPanel, InteractiveResultsTable, grabPayload } from "../components/media.jsx";
function ComicsPage({ setPage }) {
  const [items, setItems] = useState([]);
  const [detailId, setDetailId] = useState(null);
  // Jump straight to an item's detail view when opened from Global Search
  // or the dashboard's Continue Watching row.
  useEffect(() => {
    const onOpenItem = (e) => {
      if (!e.detail || !(e.detail.mediaType === 'comic' || e.detail.mediaType === 'manga')) return;
      setDetailId(e.detail.id);
    };
    window.addEventListener('mediaos-open-item', onOpenItem);
    return () => window.removeEventListener('mediaos-open-item', onOpenItem);
  }, []);
  const [tab, setTab] = useState('library'); // library | arcs | pull
  const [selected, setSelected] = useState({});
  const selectedIds = Object.keys(selected);
  const [libFilter, setLibFilter] = useState('all'); // all | comics | manga
  const [mangaIds, setMangaIds] = useState(null); // Set of ids tagged manga (from GET /comics/manga), lazy-loaded
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
  useEffect(() => {
    // Lazy-loaded: only needed once the person filters to Comics/Manga,
    // same reasoning as arcs/pull only loading on tab switch above.
    if ((libFilter === 'manga' || libFilter === 'comics') && mangaIds === null) {
      api.comics.manga()
        .then(rows => setMangaIds(new Set((rows||[]).map(r => r.id))))
        .catch(() => setMangaIds(new Set()));
    }
  }, [libFilter, mangaIds]);

  if (detailId) {
    return <ComicDetailPage comicId={detailId} onBack={()=>{ setDetailId(null); load(); }} />;
  }

  
  async function bulkMonitor(monitored) {
    setBusy(true); setMsg(null);
    try {
      await api.comics.bulk({ ids: selectedIds.map(Number), monitored });
      setSelected({});
      load();
    } catch (e) { setMsg(String(e.message || e)); }
    finally { setBusy(false); }
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

  const filtered = (items||[])
    .filter(c => !q || (c.title||'').toLowerCase().includes(q.toLowerCase()))
    .filter(c => {
      if (libFilter === 'all') return true;
      const isManga = c.media_type === 'manga' || !!(mangaIds && mangaIds.has(c.id));
      return libFilter === 'manga' ? isManga : !isManga;
    });

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
          <div className="flex flex-wrap items-center gap-2">
            <input className="input input-bordered input-sm w-full max-w-md" placeholder="Filter series…" value={q} onChange={e=>setQ(e.target.value)} />
            <div className="join">
              <button type="button" className={"btn btn-xs join-item "+(libFilter==='all'?'btn-primary':'')} onClick={()=>setLibFilter('all')}>All</button>
              <button type="button" className={"btn btn-xs join-item "+(libFilter==='comics'?'btn-primary':'')} onClick={()=>setLibFilter('comics')}>Comics</button>
              <button type="button" className={"btn btn-xs join-item "+(libFilter==='manga'?'btn-primary':'')} onClick={()=>setLibFilter('manga')}>Manga</button>
            </div>
          </div>
          {selectedIds.length > 0 && (
            <div className="card bg-base-200 mb-2">
              <div className="card-body p-3 gap-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs opacity-60">{selectedIds.length} selected</span>
                  {filtered.length > 0 && (
                    <button type="button" className="btn btn-xs btn-ghost" disabled={busy} onClick={()=>{
                      const n={}; filtered.forEach(c=>{ n[c.id]=true; }); setSelected(n);
                    }}>Select all visible</button>
                  )}
                  <button type="button" className="btn btn-xs" disabled={busy} onClick={()=>bulkMonitor(true)}>Monitor</button>
                  <button type="button" className="btn btn-xs" disabled={busy} onClick={()=>bulkMonitor(false)}>Unmonitor</button>
                  <button type="button" className="btn btn-xs btn-ghost" onClick={()=>setSelected({})}>Clear</button>
                </div>
              </div>
            </div>
          )}
          <div className="poster-grid">
            {filtered.map(c => (
              <div key={c.id} className="relative group">
                <label className={`absolute top-2 left-2 z-10 transition-opacity ${selected[c.id] ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`} onClick={e=>e.stopPropagation()}>
                  <input type="checkbox" className="checkbox checkbox-xs checkbox-primary" checked={!!selected[c.id]}
                    onChange={e=>{ setSelected(prev=>{ const n={...prev}; if(e.target.checked) n[c.id]=true; else delete n[c.id]; return n; }); }} />
                </label>
                <PosterTile title={c.title} year={c.year} poster={c.poster_path} status={c.status}
                  onClick={()=>setDetailId(c.id)} />
              </div>
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

function ComicReader({ src, title, issueId, initialPage, onClose, onProgress }) {
  const [meta, setMeta] = useState(null); // {kind, count, pages}
  const [index, setIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [fit, setFit] = useState('width'); // width | height
  const progressDebounceRef = useRef(null);
  // Tracks whether the reader has actually shown a page yet, so the
  // mount-time setIndex(initialPage) below doesn't itself trigger a
  // progress save of the page we just loaded from.
  const openedAtRef = useRef(true);

  useEffect(() => {
    setLoading(true); setErr(null);
    fetch(src.pagesUrl).then(r => { if (!r.ok) throw new Error('Failed to open comic'); return r.json(); })
      .then(d => { setMeta(d); setIndex(Math.min(Math.max(initialPage || 0, 0), Math.max((d?.count || 1) - 1, 0))); openedAtRef.current = true; })
      .catch(e => setErr(String(e.message || e)))
      .finally(() => setLoading(false));
  }, [src.pagesUrl]);

  const count = meta?.count || 0;

  const go = useCallback((delta) => {
    setIndex(i => Math.min(Math.max(i + delta, 0), Math.max(count - 1, 0)));
  }, [count]);

  useEffect(() => {
    function onKey(e) {
      if (e.key === 'ArrowRight' || e.key === ' ') { e.preventDefault(); go(1); }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); go(-1); }
      else if (e.key === 'Escape') onClose();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [go, onClose]);

  // Debounced progress save on page-change — issue-only (whole-item/
  // one-shot reads don't have a comic_issues row to attach progress to).
  useEffect(() => {
    if (!issueId || !count) return;
    if (openedAtRef.current) { openedAtRef.current = false; return; }
    if (progressDebounceRef.current) clearTimeout(progressDebounceRef.current);
    progressDebounceRef.current = setTimeout(() => {
      const isRead = index >= count - 1;
      api.comics.issueProgress(issueId, { last_page_read: index, is_read: isRead }).catch(() => {});
      if (onProgress) onProgress(issueId, { last_page_read: index, is_read: isRead });
    }, 800);
    return () => { if (progressDebounceRef.current) clearTimeout(progressDebounceRef.current); };
  }, [index, issueId, count]);

  function closeAndSave() {
    if (issueId && count) {
      if (progressDebounceRef.current) clearTimeout(progressDebounceRef.current);
      const isRead = index >= count - 1;
      api.comics.issueProgress(issueId, { last_page_read: index, is_read: isRead }).catch(() => {});
      if (onProgress) onProgress(issueId, { last_page_read: index, is_read: isRead });
    }
    onClose();
  }

  return (
    <div className="fixed inset-0 z-50 bg-black flex flex-col">
      <div className="flex items-center gap-2 px-3 py-2 bg-base-300/95 text-base-content">
        <span className="text-sm font-semibold flex-1 truncate">{title}</span>
        {count > 0 && <span className="text-xs tabular-nums opacity-70">{index + 1} / {count}</span>}
        <button type="button" className="btn btn-ghost btn-xs" onClick={() => setFit(f => f === 'width' ? 'height' : 'width')}>
          {fit === 'width' ? 'Fit height' : 'Fit width'}
        </button>
        <button type="button" className="btn btn-ghost btn-xs btn-square" onClick={closeAndSave}><Ic.X /></button>
      </div>
      <div className="flex-1 relative overflow-auto flex items-center justify-center bg-black">
        {loading && <p className="text-white/60 text-sm">Loading…</p>}
        {err && <p className="text-error text-sm p-4">{err}</p>}
        {!loading && !err && count > 0 && (
          <img
            key={index}
            src={src.pageUrlFor(index)}
            alt={`Page ${index + 1}`}
            className={(fit === 'width' ? 'w-full h-auto' : 'h-full w-auto') + ' select-none cursor-pointer'}
            onClick={(e) => {
              const rect = e.currentTarget.getBoundingClientRect();
              const clickX = e.clientX - rect.left;
              go(clickX > rect.width / 2 ? 1 : -1);
            }}
          />
        )}
        {!loading && !err && count === 0 && <p className="text-white/60 text-sm">No pages found in this file.</p>}
      </div>
      <div className="flex items-center justify-center gap-2 px-3 py-2 bg-base-300/95">
        <button type="button" className="btn btn-sm" disabled={index <= 0} onClick={() => go(-1)}>← Prev</button>
        <input type="range" min={0} max={Math.max(count - 1, 0)} value={index}
          onChange={e => setIndex(Number(e.target.value))} className="range range-xs w-48" />
        <button type="button" className="btn btn-sm" disabled={index >= count - 1} onClick={() => go(1)}>Next →</button>
      </div>
    </div>
  );
}

function ComicDetailPage({ comicId, onBack }) {
  const [item, setItem] = useState(null);
  const [issueChecked, setIssueChecked] = useState({});
  const issueCheckedIds = Object.keys(issueChecked);
  const [issues, setIssues] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const [ixResults, setIxResults] = useState(null);
  const [ixLoading, setIxLoading] = useState(false);
  const [reading, setReading] = useState(null); // {pagesUrl, pageUrlFor, title}
  const [ixIssue, setIxIssue] = useState(null); // issue object currently being interactively searched
  const [ixIssueResults, setIxIssueResults] = useState(null);
  const [ixIssueLoading, setIxIssueLoading] = useState(false);

  const load = React.useCallback(() => {
    fetch('/api/comics/'+comicId).then(r=>r.json()).then(setItem).catch(e=>setMsg(String(e.message||e)));
    fetch('/api/comics/'+comicId+'/issues').then(r=>r.json()).then(d=>setIssues(Array.isArray(d)?d:[])).catch(()=>[]);
  }, [comicId]);
  useEffect(()=>{ load(); }, [load]);

  
  async function setTrackStatus(status) {
    setBusy(true); setMsg(null);
    try {
      const r = await fetch('/api/tracking', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ media_item_id: comicId, status }),
      });
      if (!r.ok) throw new Error((await r.json().catch(()=>({}))).detail || 'Track failed');
      setMsg('Tracking: ' + String(status).replace(/_/g, ' '));
    } catch (e) { setMsg(String(e.message || e)); }
    finally { setBusy(false); }
  }

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
  async function manualPick() {
    // GET /releases: a plain ranked list (no rejected/stats envelope),
    // built for a manual picker and also falling back to the Books
    // Torznab category when Comics/Manga turns up nothing — broader
    // recall than /interactive-search, useful when a release is only
    // mistagged as a generic ebook by an indexer. Feeds the same
    // InteractiveResultsTable + grab flow as Interactive search.
    setIxLoading(true); setIxResults([]);
    try {
      const rows = await api.comics.releases(comicId);
      setIxResults(Array.isArray(rows) ? rows : (rows?.results || []));
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
  async function markManga() {
    setBusy(true);
    try {
      await api.comics.tagManga(comicId);
      setMsg('Tagged as manga');
      load();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }

  async function bulkIssueMonitor(monitored) {
    setBusy(true); setMsg(null);
    try {
      for (const id of issueCheckedIds) {
        await api.comics.monitorIssue(Number(id), { monitored });
      }
      const ids = new Set(issueCheckedIds.map(Number));
      setIssues(rows => rows.map(r => ids.has(r.id) ? { ...r, monitored } : r));
      setIssueChecked({});
    } catch (e) { setMsg(String(e.message || e)); }
    finally { setBusy(false); }
  }

  async function toggleIssueMonitor(iss) {
    try {
      await api.comics.monitorIssue(iss.id, { monitored: !iss.monitored });
      setIssues(rows => rows.map(r => r.id === iss.id ? { ...r, monitored: !iss.monitored } : r));
    } catch(e) { setMsg(String(e.message||e)); }
  }
  async function openIssueSearch(iss) {
    setIxIssue(iss); setIxIssueResults(null); setIxIssueLoading(true);
    try {
      const data = await api.comics.searchIssue(comicId, iss.id);
      setIxIssueResults(data || []);
    } catch(e) { setMsg(String(e.message||e)); setIxIssueResults([]); }
    setIxIssueLoading(false);
  }
  async function grabIssueRelease(rel) {
    if (!ixIssue) return;
    setBusy(true);
    try {
      await api.comics.grabIssue(comicId, ixIssue.id, grabPayload(rel));
      setMsg('Grabbed: '+rel.title);
      setIxIssueResults(null); setIxIssue(null);
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
        {item.file_path && (
          <button type="button" className="btn btn-sm btn-primary gap-1" onClick={() => setReading({
            pagesUrl: `/api/comics/${comicId}/pages`,
            pageUrlFor: i => `/api/comics/${comicId}/page/${i}`,
            title: item.title,
          })}>
            <span className="w-4 h-4"><Ic.Book /></span> Read
          </button>
        )}
        <button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={autoSearch}>Search & grab</button>
        <select className="select select-bordered select-sm" defaultValue="" disabled={busy}
          onChange={e=>{ if(e.target.value) { setTrackStatus(e.target.value); e.target.value=''; } }} title="Unified tracking">
          <option value="">Track…</option>
          <option value="planned">Planned</option>
          <option value="in_progress">In progress</option>
          <option value="completed">Completed</option>
          <option value="on_hold">On hold</option>
          <option value="dropped">Dropped</option>
        </select>
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
        <button type="button" className="btn btn-sm btn-secondary" disabled={busy||ixLoading} onClick={manualPick} title="Ranked list, broader category fallback">Manual pick</button>
        <button type="button" className="btn btn-sm" disabled={busy} onClick={syncIssues}>Sync issues</button>
        {item.media_type==='comic' && (item.quality_profile||'').toLowerCase()!=='manga' && (
          <button type="button" className="btn btn-sm" disabled={busy} onClick={markManga} title="Mark this series as manga (quality profile + Manga filter)">Mark as manga</button>
        )}
        <button type="button" className="btn btn-sm btn-ghost text-error" onClick={async()=>{ await fetch('/api/comics/'+comicId,{method:'DELETE'}); onBack(); }}>Delete</button>
      </>}
    >
      <InteractiveResultsTable results={ixResults} loading={ixLoading} busy={busy} onGrab={grabRel} onClose={()=>setIxResults(null)} />
      {ixIssue && (
        <InteractiveResultsPanel
          data={ixIssueResults}
          loading={ixIssueLoading}
          busy={busy}
          onGrab={grabIssueRelease}
          onClose={()=>{ setIxIssue(null); setIxIssueResults(null); }}
        />
      )}
      {issues.length>0 && (
        <div className="card bg-base-200"><div className="card-body p-4">
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <h3 className="font-semibold text-sm flex-1">Issues ({issues.length})</h3>
            {issueCheckedIds.length > 0 && (
              <>
                <span className="text-xs opacity-60">{issueCheckedIds.length} selected</span>
                <button type="button" className="btn btn-xs" disabled={busy} onClick={()=>bulkIssueMonitor(true)}>Monitor selected</button>
                <button type="button" className="btn btn-xs" disabled={busy} onClick={()=>bulkIssueMonitor(false)}>Unmonitor selected</button>
                <button type="button" className="btn btn-xs btn-ghost" onClick={()=>setIssueChecked({})}>Clear</button>
              </>
            )}
            <button type="button" className="btn btn-xs btn-ghost" onClick={()=>{
              const n={}; issues.forEach(i=>{ n[i.id]=true; }); setIssueChecked(n);
            }}>Select all</button>
          </div>
          <div className="overflow-x-auto max-h-64 overflow-y-auto">
            <table className="table table-xs">
              <thead><tr><th></th><th>Mon</th><th>#</th><th>Title</th><th>Status</th><th></th></tr></thead>
              <tbody>
                {issues.map(iss=>(
                  <tr key={iss.id}>
                    <td>
                      <input type="checkbox" className="checkbox checkbox-xs checkbox-primary" checked={!!issueChecked[iss.id]}
                        onChange={e=>{ setIssueChecked(prev=>{ const n={...prev}; if(e.target.checked) n[iss.id]=true; else delete n[iss.id]; return n; }); }} />
                    </td>
                    <td>
                      <input type="checkbox" className="checkbox checkbox-xs" checked={!!iss.monitored}
                        onChange={()=>toggleIssueMonitor(iss)} title="Monitored" />
                    </td>
                    <td>{iss.issue_number}</td>
                    <td className="text-xs">{iss.title||'—'}</td>
                    <td><span className="badge badge-xs">{iss.status}</span></td>
                    <td className="flex gap-0.5 flex-wrap">
                      {iss.file_path && (
                        <button type="button" className="btn btn-ghost btn-xs gap-1" onClick={() => setReading({
                          pagesUrl: `/api/comics/issues/${iss.id}/pages`,
                          pageUrlFor: i => `/api/comics/issues/${iss.id}/page/${i}`,
                          title: `${item.title} #${iss.issue_number||''}`,
                          issueId: iss.id,
                          initialPage: iss.last_page_read || 0,
                        })}>
                          <span className="w-3 h-3"><Ic.Book /></span> Read
                        </button>
                      )}
                      {iss.is_read && <span className="badge badge-xs badge-success ml-1" title="Read">✓</span>}
                      <button type="button" className="btn btn-ghost btn-xs" disabled={busy} onClick={()=>openIssueSearch(iss)} title="Interactive search">Search</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div></div>
      )}
      {reading && <ComicReader
        src={reading} title={reading.title}
        issueId={reading.issueId} initialPage={reading.initialPage}
        onClose={() => setReading(null)}
        onProgress={(issueId, patch) => setIssues(rows => rows.map(r => r.id === issueId ? { ...r, ...patch } : r))}
      />}
    </MediaDetailShell>
  );
}




export { ComicsPage, ComicDetailPage };
