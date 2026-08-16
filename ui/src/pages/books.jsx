import React, { useState, useEffect, useCallback, useRef } from "react";
import Ic, { Icons, P } from "../icons.jsx";
import { getToken, setToken, getAdvanced, setAdvancedFlag, AUTH_TOKEN_KEY } from "../storage.js";
import { api, TMDB, adultFetch } from "../api.js";
import { PageChrome, PosterTile, LibraryModuleShell, MediaDetailShell, LibraryLegend, LibraryHeader, MediaCard, StatusBadgeStack, libraryStatuses, CollectionProgressWidget, TeachEmpty, AddModal } from "../components/ui.jsx";
import { InteractiveResultsPanel, InteractiveResultsTable, MediaPlayer, HlsVideo, grabPayload, releaseDownloadUrl } from "../components/media.jsx";

function BooksAuthorsTree() {
  const [authors, setAuthors] = useState([]);
  useEffect(()=>{ fetch('/api/books/library/authors').then(r=>r.json()).then(d=>setAuthors(d.authors||[])).catch(e => { try { setMsg(String(e.message||e)); } catch(_) { console.warn(e); } }); }, []);
  return (
    <div className="space-y-3">
      {authors.map(a=>(
        <div key={a.name} className="card bg-base-200"><div className="card-body p-3 gap-1">
          <div className="font-semibold text-sm">{a.name} <span className="opacity-50 font-normal">{a.book_count} books</span></div>
          <div className="flex flex-wrap gap-1">{(a.books||[]).map(b=>(
            <span key={b.id} className="badge badge-sm badge-outline">{b.title}</span>
          ))}</div>
        </div></div>
      ))}
      {!authors.length && <p className="text-sm opacity-40">No authors yet — add books first</p>}
    </div>
  );
}


function BookDetailPage({ bookId, onBack, refresh }) {
  const [item, setItem] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const [ixResults, setIxResults] = useState(null);
  const [ixLoading, setIxLoading] = useState(false);
  const load = useCallback(() => {
    api.books.get(bookId).then(setItem).catch(e=>setMsg(String(e.message||e)));
  }, [bookId]);
  useEffect(()=>{ load(); }, [load]);
  
  async function setTrackStatus(status) {
    setBusy(true); setMsg(null);
    try {
      const r = await fetch('/api/tracking', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ media_item_id: bookId, status }),
      });
      if (!r.ok) throw new Error((await r.json().catch(()=>({}))).detail || 'Track failed');
      setMsg('Tracking: ' + String(status).replace(/_/g, ' '));
    } catch (e) { setMsg(String(e.message || e)); }
    finally { setBusy(false); }
  }

  async function autoSearch() {
    setBusy(true); setMsg(null);
    try {
      const r = await api.books.searchNow(bookId);
      setMsg(r?.found ? `Grabbed: ${r.title}` : 'No release found');
      load(); refresh && refresh();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  async function openIx() {
    setIxLoading(true); setIxResults([]); setMsg(null);
    try {
      const d = await api.books.interactive(bookId);
      setIxResults(d?.results || d || []);
    } catch(e) { setMsg(String(e.message||e)); }
    setIxLoading(false);
  }
  async function grabRel(rel) {
    setBusy(true);
    try {
      await api.books.grab(bookId, grabPayload(rel));
      setMsg(`Grabbed: ${rel.title}`); setIxResults(null);
      load(); refresh && refresh();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  if (!item) return <div className="p-6 opacity-50">Loading…</div>;
  return (
    <MediaDetailShell
      title={item.title} year={item.year} poster={item.poster_path}
      status={item.status} monitored={item.monitored}
      overview={item.overview || item.artist_name}
      filePath={item.file_path} qualityProfile={item.quality_profile}
      msg={msg} busy={busy} onBack={onBack}
      actions={<>
        <button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={autoSearch}>Search & grab</button>
        <button type="button" className="btn btn-sm btn-accent" disabled={busy} title="Add top result as stream"
          onClick={async ()=>{
            setBusy(true);
            try {
              const data = await api.books.interactive(bookId);
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
        <button type="button" className="btn btn-sm" disabled={busy} onClick={async()=>{
          setBusy(true);
          try { await api.books.update(bookId, { monitored: !item.monitored }); load(); refresh&&refresh(); }
          catch(e){ setMsg(String(e.message||e)); }
          setBusy(false);
        }}>{item.monitored?'Unmonitor':'Monitor'}</button>
        <select className="select select-bordered select-sm" defaultValue="" disabled={busy}
          onChange={e=>{ if(e.target.value) { setTrackStatus(e.target.value); e.target.value=''; } }} title="Unified tracking">
          <option value="">Track…</option>
          <option value="planned">Planned</option>
          <option value="in_progress">In progress</option>
          <option value="completed">Completed</option>
          <option value="on_hold">On hold</option>
          <option value="dropped">Dropped</option>
        </select>
        <button type="button" className="btn btn-sm" disabled={busy} onClick={async()=>{
          setBusy(true);
          try { await api.books.refresh(bookId); load(); setMsg('Refreshed'); }
          catch(e){ setMsg(String(e.message||e)); }
          setBusy(false);
        }}>Refresh</button>
        {item.file_path && <button type="button" className="btn btn-sm btn-ghost" disabled={busy} onClick={async()=>{
          setBusy(true);
          try { await api.books.file(bookId, { clear: true }); load(); refresh&&refresh(); }
          catch(e){ setMsg(String(e.message||e)); }
          setBusy(false);
        }}>Clear file</button>}
        <button type="button" className="btn btn-sm btn-ghost text-error" onClick={async()=>{ await api.books.remove(bookId); onBack(); refresh&&refresh(); }}>Delete</button>
      </>}
    >
      {(ixLoading || ixResults) && (
        <InteractiveResultsPanel data={Array.isArray(ixResults) ? { results: ixResults, rejected: [] } : (ixResults || { results: [], rejected: [] })} loading={ixLoading} busy={busy} onGrab={grabRel} onClose={()=>setIxResults(null)} />
      )}
    </MediaDetailShell>
  );
}

function BooksPage({ setPage }) {
  // searchAllMissing defined below
  const [items, setItems] = useState([]);
  const [detailId, setDetailId] = useState(null);
  // Jump straight to an item's detail view when opened from Global Search
  // or the dashboard's Continue Watching row.
  useEffect(() => {
    const onOpenItem = (e) => {
      if (!e.detail || !(e.detail.mediaType === 'book')) return;
      setDetailId(e.detail.id);
    };
    window.addEventListener('mediaos-open-item', onOpenItem);
    return () => window.removeEventListener('mediaos-open-item', onOpenItem);
  }, []);
  const [nav, setNav] = useState('library');
  const [q, setQ] = useState('');
  const [results, setResults] = useState([]);
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState(null);
  const [selected, setSelected] = useState({});
  const [qp, setQp] = useState('');
  const [profiles, setProfiles] = useState([]);
  const [busy, setBusy] = useState(false);
  const load = () => api.books.list().then(setItems).catch(()=>[]).finally(()=>setLoading(false));
  useEffect(() => { load(); }, []);
  useEffect(() => { api.settings.profiles().then(setProfiles).catch(()=>{}); }, []);
  const bookProfiles = profiles.filter(p => p.media_type === 'book');
  const selectedIds = Object.keys(selected);
  // toolbar uses searchAllMissing for monitored missing books
  if (detailId) return <BookDetailPage bookId={detailId} onBack={()=>{ setDetailId(null); load(); }} refresh={load} />;

  async function bulkMonitor(monitored) {
    setBusy(true); setMsg(null);
    try {
      await api.books.bulk({ ids: selectedIds.map(Number), monitored });
      setSelected({}); load();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  async function bulkSearchMissing() {
    setBusy(true); setMsg(null);
    try {
      for (const id of selectedIds) { await api.books.searchNow(Number(id)); }
      setMsg('Search queued for selected'); load();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  async function bulkApplyProfile() {
    if (!qp) return;
    setBusy(true); setMsg(null);
    try {
      await api.books.bulk({ ids: selectedIds.map(Number), quality_profile: qp });
      setSelected({}); setQp(''); load();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }

  async function doSearch(e) {
    e && e.preventDefault();
    if (!q.trim()) return;
    try {
      const r = await api.books.search(q);
      setResults(r||[]); setNav('add');
    } catch(err){ setMsg(String(err.message||err)); }
  }
  async function addBook(r) {
    try {
      await api.books.add({ external_id: r.external_id||r.key||0, title: r.title, overview: r.author||r.overview, search_now: true });
      setMsg('Added'); load(); setNav('library');
    } catch(e){ setMsg(String(e.message||e)); }
  }
  async function searchGrab(id) {
    setMsg('Searching…');
    try {
      const r = await fetch(`/api/books/${id}/search`, {method:'POST'}).then(x=>x.json());
      setMsg(r.message||'Search done'); load();
    } catch(e){ setMsg(String(e.message||e)); }
  }
  async function searchAllMissing() {
    setMsg('Searching missing…');
    try {
      const r = await api.books.searchMissing();
      setMsg(`Searched ${r.searched||0} · grabbed ${r.grabbed||0}`); load();
    } catch(e){ setMsg(String(e.message||e)); }
  }
  const hasFile = b => !!(b.file_path || b.status==='downloaded');
  const missingToolbar = (
    <button type="button" className="btn btn-sm btn-primary mb-3" onClick={searchAllMissing}>Search missing</button>
  );
  let list = [...items];
  if (q.trim() && nav==='library') list = list.filter(b => (b.title||'').toLowerCase().includes(q.toLowerCase()));
  if (filter==='downloaded') list = list.filter(hasFile);
  if (filter==='wanted') list = list.filter(b => b.monitored && !hasFile(b));
  if (filter==='monitored') list = list.filter(b => b.monitored);

  return (
    <div className="flex gap-0 min-h-[70vh]">
      <aside className="w-44 shrink-0 border-r border-base-content/10 pr-3 hidden md:block">
        <div className="text-xs font-semibold uppercase tracking-wider opacity-40 mb-3 px-2">Books</div>
        <ul className="menu menu-sm gap-0.5 p-0">
          {[
            {id:'library', label:'Library', Icon:Ic.Book},
            {id:'authors', label:'Authors', Icon:Ic.Book},
            {id:'add', label:'Add New', Icon:Ic.Plus},
            {id:'wanted', label:'Wanted', Icon:Ic.AlertTri},
          ].map(n=>(
            <li key={n.id}><button type="button" className={(nav===n.id?'active ':'')+'rounded-lg'} onClick={()=>setNav(n.id)}><n.Icon /> {n.label}</button></li>
          ))}
        </ul>
        <div className="divider my-3"></div>
        <ul className="menu menu-sm gap-0.5 p-0">
          <li><button type="button" onClick={()=>setPage&&setPage('queue')}><Ic.Download /> Queue</button></li>
          <li><button type="button" onClick={()=>setPage&&setPage('settings-library')}><Ic.Folder /> Library paths</button></li>
          <li><button type="button" onClick={()=>setPage&&setPage('audiobooks')}><Ic.Headphones /> Audiobooks</button></li>
        </ul>
        <div className="mt-4 px-2 text-[10px] opacity-40">{items.length} books</div>
      </aside>
      <div className="flex-1 min-w-0 space-y-4 md:pl-4">
        <div className="flex flex-wrap items-center gap-2 justify-between">
          <h1 className="mr-page-title">{nav==='library'?'Books':nav==='add'?'Add Book':'Wanted'}</h1>
          <div className="flex gap-1.5 flex-wrap">
            <form onSubmit={doSearch} className="flex gap-1">
              <label className="input input-bordered input-sm flex items-center gap-2 w-48">
                <Ic.Search /><input className="grow bg-transparent outline-none text-sm" placeholder="Search Open Library" value={q} onChange={e=>setQ(e.target.value)} />
              </label>
              <button type="button" className="btn btn-sm btn-primary">Search</button>
            </form>
            <select className="select select-bordered select-sm w-28" value={filter} onChange={e=>setFilter(e.target.value)}>
              <option value="all">All</option><option value="monitored">Monitored</option>
              <option value="downloaded">Have</option><option value="wanted">Wanted</option>
            </select>
          </div>
        </div>
        {msg && <div className="text-xs opacity-60">{msg}</div>}
        {nav==='add' && (
          <div className="space-y-2">
            {(results||[]).map((r,i)=>(
              <div key={i} className="flex justify-between gap-2 p-2 rounded-lg bg-base-200">
                <div className="min-w-0"><div className="font-medium text-sm truncate">{r.title}</div>
                  <div className="text-xs opacity-50">{r.author||r.overview||''}</div></div>
                <button type="button" className="btn btn-xs btn-primary" onClick={()=>addBook(r)}>Add</button>
              </div>
            ))}
            {!results.length && <p className="text-sm opacity-50">Search Open Library above</p>}
          </div>
        )}
        {nav==='authors' && <BooksAuthorsTree />}
        {nav==='wanted' && (
          <table className="table table-sm"><thead><tr><th>Title</th><th></th></tr></thead><tbody>
            {items.filter(b=>b.monitored&&!hasFile(b)).map(b=>(
              <tr key={b.id}><td>{b.title}</td><td><button type="button" className="btn btn-xs btn-primary" onClick={()=>setDetailId(b.id)}>Search</button></td></tr>
            ))}
          </tbody></table>
        )}
        {nav==='library' && (
          loading ? <span className="loading loading-spinner"/> : (
          <>
          {selectedIds.length > 0 && (
            <div className="card bg-base-200 mb-3">
              <div className="card-body p-3 gap-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs opacity-60">{selectedIds.length} selected</span>
                  {list.length > 0 && (
                  <button type="button" className="btn btn-xs btn-ghost" disabled={busy} onClick={()=>{
                    const n={};
                    list.forEach(b=>{ n[b.id]=true; });
                    setSelected(n);
                  }}>Select all visible</button>
                  )}
                  <button type="button" className="btn btn-xs" disabled={busy} onClick={()=>bulkMonitor(true)}>Monitor selected</button>
                  <button type="button" className="btn btn-xs" disabled={busy} onClick={()=>bulkMonitor(false)}>Unmonitor selected</button>
                  <button type="button" className="btn btn-xs btn-primary" disabled={busy} onClick={bulkSearchMissing}>Search missing</button>
                  {bookProfiles.length > 0 && (
              <>
              <select className="select select-bordered select-xs" value={qp} onChange={e=>setQp(e.target.value)}>
                    <option value="">Bulk quality…</option>
                    {bookProfiles.map(p=><option key={p.id} value={p.name}>{p.name}</option>)}
                  </select>
                  <button type="button" className="btn btn-xs" disabled={busy||!qp} onClick={bulkApplyProfile}>Apply profile</button>
              </>
              )}
                  <button type="button" className="btn btn-xs btn-ghost" disabled={busy} onClick={()=>setSelected({})}>Clear</button>
                </div>
              </div>
            </div>
          )}
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
            {list.map(b=>{
              const ok = hasFile(b);
              return (
                <div key={b.id} className="group relative rounded-lg overflow-hidden bg-base-200 shadow-sm hover:ring-2 hover:ring-primary/40">
                  <label className={`absolute top-2 left-2 z-10 transition-opacity ${selected[b.id] ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`} onClick={e=>e.stopPropagation()}>
                    <input type="checkbox" className="checkbox checkbox-xs checkbox-primary" checked={!!selected[b.id]}
                      onChange={e=>{ setSelected(prev=>{ const n={...prev}; if(e.target.checked) n[b.id]=true; else delete n[b.id]; return n; }); }} />
                  </label>
                  <div className="aspect-[2/3] bg-base-300 relative flex items-center justify-center cursor-pointer" onClick={()=>setDetailId(b.id)}>
                    {b.poster_path ? <img src={b.poster_path.startsWith('http')?b.poster_path:('https://covers.openlibrary.org/b/id/'+b.poster_path+'-M.jpg')} className="w-full h-full object-cover" alt="" loading="lazy"/> : <Ic.Book />}
                    <div className={"absolute bottom-0 left-0 right-0 h-1.5 "+(ok?'bg-success':b.monitored?'bg-warning':'bg-base-content/20')} />
                    <div className={"absolute bottom-2 left-2 badge badge-sm border-0 text-white "+(ok?'bg-success':'bg-warning')}>{ok?'Have':'Want'}</div>
                  </div>
                  <div className="p-2 space-y-0.5">
                    <div className="text-xs font-semibold line-clamp-2 min-h-[2rem]">{b.title}</div>
                    <span className={"badge badge-xs "+(b.monitored?'badge-success':'badge-ghost')}>{b.monitored?'Monitored':'Off'}</span>
                    <div className="flex gap-1 opacity-0 group-hover:opacity-100">
                      <button type="button" className="btn btn-ghost btn-xs" onClick={()=>setDetailId(b.id)}>Search</button>
                      <button type="button" className="btn btn-ghost btn-xs text-error" onClick={async()=>{await api.books.remove(b.id); load();}}>Del</button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
          </>
          )
        )}
      </div>
    </div>
  );
}





export { BooksAuthorsTree, BookDetailPage, BooksPage };
