import React, { useState, useEffect, useCallback, useRef } from "react";
import Ic, { Icons, P } from "../icons.jsx";
import { getToken, setToken, getAdvanced, setAdvancedFlag, AUTH_TOKEN_KEY } from "../storage.js";
import { api, TMDB, adultFetch } from "../api.js";
import { PageChrome, PosterTile, LibraryModuleShell, MediaDetailShell, LibraryLegend, LibraryHeader, MediaCard, StatusBadgeStack, libraryStatuses, CollectionProgressWidget, TeachEmpty, AddModal } from "../components/ui.jsx";
import { InteractiveResultsPanel, InteractiveResultsTable, MediaPlayer, HlsVideo, grabPayload, releaseDownloadUrl } from "../components/media.jsx";
import musicStore from "../player/store.js";
import useMusicPlayer from "../player/useMusicPlayer.js";

function fmtMs(ms) {
  if (!ms || !isFinite(ms)) return "";
  const s = Math.round(ms / 1000);
  const m = Math.floor(s / 60);
  return m + ":" + String(s % 60).padStart(2, "0");
}

function trackToQueueItem(tr, album) {
  return {
    id: tr.id,
    path: tr.file_path,
    title: tr.title || tr.name,
    artist: (album && (album.artist_name || album.artist)) || tr.artist_name || "",
    album: (album && album.title) || "",
    poster_path: (album && album.poster_path) || null,
    duration_ms: tr.duration_ms,
    track_number: tr.track_number,
    disc_number: tr.disc_number,
  };
}

function PlayBtn({ onClick, size = "sm", className = "", title = "Play" }) {
  return (
    <button type="button" title={title}
      className={"btn btn-primary btn-circle btn-" + size + " " + className}
      onClick={(e) => { e.stopPropagation(); onClick && onClick(e); }}>
      <span className="w-4 h-4"><Ic.Play /></span>
    </button>
  );
}

function MusicPage({ setPage }) {
  const [items, setItems] = useState([]);
  const [tree, setTree] = useState([]);
  const [view, setView] = useState('hierarchy'); // hierarchy | grid | incomplete | liked | smart
  const [detailId, setDetailId] = useState(null);
  // Jump straight to an item's detail view when opened from Global Search
  // or the dashboard's Continue Watching row.
  useEffect(() => {
    const onOpenItem = (e) => {
      if (!e.detail || !(e.detail.mediaType === 'music')) return;
      setDetailId(e.detail.id);
    };
    window.addEventListener('mediaos-open-item', onOpenItem);
    return () => window.removeEventListener('mediaos-open-item', onOpenItem);
  }, []);
  const [expanded, setExpanded] = useState({});
  const [incomplete, setIncomplete] = useState([]);
  const [q, setQ] = useState('');
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState({});
  const selectedIds = Object.keys(selected);
  const { likes } = useMusicPlayer();

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


  async function bulkMonitor(monitored) {
    setBusy(true); setMsg(null);
    try {
      await fetch('/api/music/bulk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: selectedIds.map(Number), monitored }),
      }).then(async r => { if (!r.ok) throw new Error((await r.json().catch(()=>({}))).detail || r.statusText); return r.json(); });
      setSelected({});
      load();
    } catch (e) { setMsg(String(e.message || e)); }
    finally { setBusy(false); }
  }

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

  const likedCount = Object.keys(likes||{}).length;

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
          <button type="button" className={"btn btn-sm join-item "+(view==='liked'?'btn-primary':'')} onClick={()=>setView('liked')}>
            Liked{likedCount ? " ("+likedCount+")" : ""}
          </button>
          <button type="button" className={"btn btn-sm join-item gap-1 "+(view==='smart'?'btn-primary':'')} onClick={()=>setView('smart')}>
            <span className="w-3.5 h-3.5"><Ic.Sliders /></span> Smart
          </button>
        </div>
        <button type="button" className="btn btn-sm btn-secondary" disabled={busy} onClick={searchMissing}>Search missing</button>
        <button type="button" className="btn btn-sm" onClick={()=>setPage && setPage('discover')}>Discover</button>
      </div>
      {msg && <div className="alert alert-info text-xs py-2">{msg}</div>}
      <input className="input input-bordered input-sm w-full max-w-md" placeholder="Filter artist or album…" value={q} onChange={e=>setQ(e.target.value)} />

      {view === 'hierarchy' && (
        <div className="space-y-1">
          {selectedIds.length > 0 && (
            <div className="card bg-base-200 mb-2">
              <div className="card-body p-3">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs opacity-60">{selectedIds.length} selected</span>
                  <button type="button" className="btn btn-xs" disabled={busy} onClick={()=>bulkMonitor(true)}>Monitor</button>
                  <button type="button" className="btn btn-xs" disabled={busy} onClick={()=>bulkMonitor(false)}>Unmonitor</button>
                  <button type="button" className="btn btn-xs btn-ghost" onClick={()=>setSelected({})}>Clear</button>
                </div>
              </div>
            </div>
          )}
          {filteredTree.map(artist => {
            const open = expanded[artist.name];
            const dl = (artist.albums||[]).filter(a=>a.status==='downloaded').length;
            return (
              <div key={artist.name} className="card bg-base-200/80 border border-base-content/5 overflow-hidden">
                <button type="button" className="flex items-center gap-3 p-3 w-full text-left hover:bg-base-300/40"
                  onClick={()=>setExpanded(e=>({...e, [artist.name]: !open}))}>
                  <span className="text-xs opacity-40 w-4">{open?'▼':'▶'}</span>
                  <div className="w-8 h-8 rounded-full bg-base-300 flex items-center justify-center shrink-0">
                    <span className="w-4 h-4 opacity-50"><Ic.Mic /></span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-sm truncate">{artist.name}</div>
                    <div className="text-[10px] opacity-50">{artist.album_count} albums · {dl} on disk</div>
                  </div>
                  <span className="badge badge-sm badge-ghost">{artist.album_count}</span>
                </button>
                {open && (
                  <div className="border-t border-base-content/5 divide-y divide-base-content/5">
                    {(artist.albums||[]).map(al => (
                      <div key={al.id} className="flex items-center gap-2 px-4 py-2 hover:bg-primary/10">
                        <input type="checkbox" className="checkbox checkbox-xs checkbox-primary" checked={!!selected[al.id]}
                          onChange={e=>{ setSelected(prev=>{ const n={...prev}; if(e.target.checked) n[al.id]=true; else delete n[al.id]; return n; }); }}
                          onClick={e=>e.stopPropagation()} />
                        <button type="button"
                        className="flex items-center gap-3 flex-1 min-w-0 text-left"
                        onClick={()=>setDetailId(al.id)}>
                        <div className="w-10 h-10 rounded bg-base-300 overflow-hidden shrink-0 flex items-center justify-center">
                          {al.poster_path ? <img src={al.poster_path} alt="" className="object-cover w-full h-full"/> : <span className="w-4 h-4 opacity-30"><Ic.Disc /></span>}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium truncate">{al.title}</div>
                          <div className="text-[10px] opacity-50">{al.year||'—'} · {al.monitored?'monitored':'unmonitored'}</div>
                        </div>
                        <span className={'badge badge-xs '+(al.status==='downloaded'?'badge-success':al.status==='wanted'?'badge-warning':'badge-ghost')}>{al.status}</span>
                        </button>
                      </div>
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
        <>
          {selectedIds.length > 0 && (
            <div className="card bg-base-200 mb-2">
              <div className="card-body p-3">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs opacity-60">{selectedIds.length} selected</span>
                  {filteredGrid.length > 0 && (
                    <button type="button" className="btn btn-xs btn-ghost" onClick={()=>{
                      const n={}; filteredGrid.forEach(a=>{ n[a.id]=true; }); setSelected(n);
                    }}>Select all visible</button>
                  )}
                  <button type="button" className="btn btn-xs" disabled={busy} onClick={()=>bulkMonitor(true)}>Monitor</button>
                  <button type="button" className="btn btn-xs" disabled={busy} onClick={()=>bulkMonitor(false)}>Unmonitor</button>
                  <button type="button" className="btn btn-xs btn-ghost" onClick={()=>setSelected({})}>Clear</button>
                </div>
              </div>
            </div>
          )}
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
            {filteredGrid.map(a=>(
              <div key={a.id} className="card bg-base-200 shadow-sm hover:ring-1 hover:ring-primary/40 group relative">
                <label className={`absolute top-2 left-2 z-10 transition-opacity ${selected[a.id] ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`} onClick={e=>e.stopPropagation()}>
                  <input type="checkbox" className="checkbox checkbox-xs checkbox-primary" checked={!!selected[a.id]}
                    onChange={e=>{ setSelected(prev=>{ const n={...prev}; if(e.target.checked) n[a.id]=true; else delete n[a.id]; return n; }); }} />
                </label>
                <div className="cursor-pointer" onClick={()=>setDetailId(a.id)}>
                  <figure className="aspect-square bg-base-300 overflow-hidden relative">
                    {a.poster_path ? <img src={a.poster_path} alt="" className="object-cover w-full h-full" /> : <div className="flex items-center justify-center h-full opacity-30"><span className="w-8 h-8"><Ic.Disc /></span></div>}
                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition flex items-center justify-center">
                      <PlayBtn size="md" onClick={()=>setDetailId(a.id)} title="Open album" />
                    </div>
                  </figure>
                  <div className="card-body p-2 gap-0.5">
                    <div className="text-xs font-semibold line-clamp-1">{a.title}</div>
                    <div className="text-[10px] opacity-60 line-clamp-1">{a.artist_name||''}</div>
                    <span className={'badge badge-xs '+(a.status==='downloaded'?'badge-success':a.monitored?'badge-warning':'badge-ghost')}>{a.monitored ? a.status : 'off'}</span>
                  </div>
                </div>
              </div>
            ))}
            {!filteredGrid.length && <div className="col-span-full opacity-50 text-sm p-6">No albums yet</div>}
          </div>
        </>
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

      {view === 'liked' && <LikedView items={items} onOpen={setDetailId} />}
      {view === 'smart' && <SmartPlaylistsView />}
    </div>
  );
}

const SMART_SOURCES = [
  { value: 'library_genre', label: 'Genre' },
  { value: 'library_mood', label: 'Mood' },
  { value: 'library_recent', label: 'Recently added' },
  { value: 'library_most_played', label: 'Most played' },
];

function SmartPlaylistsView() {
  const [lists, setLists] = useState([]);
  const [openId, setOpenId] = useState(null);
  const [tracks, setTracks] = useState([]);
  const [smartSel, setSmartSel] = useState({});
  const smartSelIds = Object.keys(smartSel);
  const [loadingTracks, setLoadingTracks] = useState(false);
  const [msg, setMsg] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: '', source: 'library_genre', genre_filter: '', mood_filter: '', added_within_days: 30, min_play_count: 1, result_limit: 50 });

  const load = () => { api.musicSmartlists.list().then(setLists).catch(()=>setLists([])); };
  useEffect(()=>{ load(); }, []);

  useEffect(() => {
    if (!openId) { setTracks([]); return; }
    let cancelled = false;
    setLoadingTracks(true);
    api.musicSmartlists.tracks(openId).then(d=>{ if (!cancelled) setTracks(Array.isArray(d)?d:[]); })
      .catch(()=>{ if (!cancelled) setTracks([]); })
      .finally(()=>{ if (!cancelled) setLoadingTracks(false); });
    return ()=>{ cancelled = true; };
  }, [openId]);

  function trackFromRow(t) {
    return {
      id: t.id, path: t.file_path, title: t.title,
      artist: t.artist_name || '', album: t.album_title || '',
      poster_path: t.poster_path || null, duration_ms: t.duration_ms,
      track_number: t.track_number, disc_number: t.disc_number,
    };
  }

  function playList() {
    const q = tracks.map(trackFromRow);
    if (q.length) musicStore.setQueue(q, 0, true);
  }
  function queueSmartSelected() {
    const picks = tracks.filter((t,i) => smartSel[t.id] || smartSel[i] || smartSel[t.file_path]);
    const q = picks.map(trackFromRow);
    if (q.length) musicStore.setQueue(q, 0, true);
  }

  async function createList(e) {
    e.preventDefault();
    if (!form.name.trim()) return;
    const body = { name: form.name.trim(), source: form.source, result_limit: Number(form.result_limit)||50 };
    if (form.source === 'library_genre') body.genre_filter = form.genre_filter;
    if (form.source === 'library_mood') body.mood_filter = form.mood_filter;
    if (form.source === 'library_recent') body.added_within_days = Number(form.added_within_days)||30;
    if (form.source === 'library_most_played') body.min_play_count = Number(form.min_play_count)||1;
    try {
      await api.musicSmartlists.create(body);
      setForm({ name: '', source: 'library_genre', genre_filter: '', mood_filter: '', added_within_days: 30, min_play_count: 1, result_limit: 50 });
      setShowCreate(false);
      load();
    } catch(e2) { setMsg(String(e2.message||e2)); }
  }

  async function removeList(id) {
    try { await api.musicSmartlists.remove(id); if (openId === id) setOpenId(null); load(); }
    catch(e) { setMsg(String(e.message||e)); }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs opacity-60">{lists.length} smart playlist{lists.length===1?'':'s'} · live-updating filters over your library</span>
        <button type="button" className="btn btn-sm btn-primary" onClick={()=>setShowCreate(s=>!s)}>{showCreate?'Cancel':'New smart playlist'}</button>
      </div>
      {msg && <div className="alert alert-warning text-xs py-2">{msg}</div>}

      {showCreate && (
        <form className="card bg-base-200 border border-base-content/10" onSubmit={createList}>
          <div className="card-body p-3 gap-2">
            <div className="flex flex-wrap gap-2">
              <input className="input input-bordered input-sm flex-1 min-w-[160px]" placeholder="Name" value={form.name} onChange={e=>setForm(f=>({...f, name:e.target.value}))} required />
              <select className="select select-bordered select-sm" value={form.source} onChange={e=>setForm(f=>({...f, source:e.target.value}))}>
                {SMART_SOURCES.map(s=><option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </div>
            {form.source === 'library_genre' && (
              <input className="input input-bordered input-sm" placeholder="Genre(s), comma-separated" value={form.genre_filter} onChange={e=>setForm(f=>({...f, genre_filter:e.target.value}))} />
            )}
            {form.source === 'library_mood' && (
              <input className="input input-bordered input-sm" placeholder="Mood(s), comma-separated" value={form.mood_filter} onChange={e=>setForm(f=>({...f, mood_filter:e.target.value}))} />
            )}
            {form.source === 'library_recent' && (
              <input type="number" min="1" className="input input-bordered input-sm w-32" placeholder="Days" value={form.added_within_days} onChange={e=>setForm(f=>({...f, added_within_days:e.target.value}))} />
            )}
            {form.source === 'library_most_played' && (
              <input type="number" min="1" className="input input-bordered input-sm w-32" placeholder="Min plays" value={form.min_play_count} onChange={e=>setForm(f=>({...f, min_play_count:e.target.value}))} />
            )}
            <div className="flex items-center gap-2">
              <input type="number" min="1" max="500" className="input input-bordered input-sm w-24" title="Max tracks" value={form.result_limit} onChange={e=>setForm(f=>({...f, result_limit:e.target.value}))} />
              <button type="submit" className="btn btn-sm btn-primary">Create</button>
            </div>
          </div>
        </form>
      )}

      <div className="space-y-1">
        {lists.map(sl => {
          const open = openId === sl.id;
          const srcLabel = (SMART_SOURCES.find(s=>s.value===sl.source)||{}).label || sl.source;
          return (
            <div key={sl.id} className="card bg-base-200/80 border border-base-content/5 overflow-hidden">
              <button type="button" className="flex items-center gap-3 p-3 w-full text-left hover:bg-base-300/40"
                onClick={()=>setOpenId(open ? null : sl.id)}>
                <span className="text-xs opacity-40 w-4">{open?'▼':'▶'}</span>
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-sm truncate">{sl.name}</div>
                  <div className="text-[10px] opacity-50">{srcLabel}{sl.genre_filter?` · ${sl.genre_filter}`:''}{sl.mood_filter?` · ${sl.mood_filter}`:''}</div>
                </div>
                <button type="button" className="btn btn-ghost btn-xs text-error" onClick={(e)=>{ e.stopPropagation(); removeList(sl.id); }}>Delete</button>
              </button>
              {open && (
                <div className="border-t border-base-content/5 p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs opacity-60">{loadingTracks ? 'Loading…' : `${tracks.length} tracks`}</span>
                    {smartSelIds.length > 0 && (
                      <>
                        <span className="text-xs opacity-60">{smartSelIds.length} selected</span>
                        <button type="button" className="btn btn-xs btn-primary" onClick={queueSmartSelected}>Queue selected</button>
                        <button type="button" className="btn btn-xs btn-ghost" onClick={()=>setSmartSel({})}>Clear</button>
                      </>
                    )}
                    <button type="button" className="btn btn-sm btn-primary gap-1" disabled={loadingTracks||!tracks.length} onClick={playList}>
                      <span className="w-4 h-4"><Ic.Play /></span> Play all
                    </button>
                  </div>
                  <div className="space-y-1">
                    {tracks.map((t,i)=>(
                      <div key={t.id||i} className="flex items-center gap-3 px-3 py-1.5 rounded bg-base-100/60 hover:bg-primary/10">
                        <input type="checkbox" className="checkbox checkbox-xs checkbox-primary" checked={!!(smartSel[t.id]||smartSel[i]||smartSel[t.file_path])}
                          onChange={e=>{ setSmartSel(prev=>{ const n={...prev}; const k=t.id||t.file_path||i; if(e.target.checked) n[k]=true; else delete n[k]; return n; }); }}
                          onClick={e=>e.stopPropagation()} />
                        <div className="flex items-center gap-3 flex-1 min-w-0 cursor-pointer"
                          onClick={()=>musicStore.setQueue(tracks.map(trackFromRow), i, true)}>
                          <span className="text-[10px] tabular-nums opacity-40 w-5">{i+1}</span>
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium truncate">{t.title}</div>
                            <div className="text-[10px] opacity-50 truncate">{t.artist_name||''} · {t.album_title||''}</div>
                          </div>
                          <span className="text-[10px] tabular-nums opacity-50">{fmtMs(t.duration_ms)}</span>
                        </div>
                      </div>
                    ))}
                    {!loadingTracks && !tracks.length && <div className="opacity-50 text-xs p-3">No matching tracks yet — tag albums with genre/mood or keep listening.</div>}
                  </div>
                </div>
              )}
            </div>
          );
        })}
        {!lists.length && !showCreate && <div className="opacity-50 text-sm p-6">No smart playlists yet — create one above.</div>}
      </div>
    </div>
  );
}

function LikedView({ items, onOpen }) {
  const { likes } = useMusicPlayer();
  const [likedTracks, setLikedTracks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [likedSel, setLikedSel] = useState({});
  const likedSelIds = Object.keys(likedSel);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const likedPaths = new Set(Object.keys(likes||{}));
    const albums = items || [];
    Promise.all(albums.map(a =>
      fetch(`/api/music/album/${a.id}/tracks`).then(r=>r.json()).then(tracks =>
        (Array.isArray(tracks)?tracks:[]).filter(t=>t.file_path && likedPaths.has(t.file_path))
          .map(t=>({ ...t, _album: a }))
      ).catch(()=>[])
    )).then(groups => {
      if (!cancelled) setLikedTracks(groups.flat());
    }).finally(()=>{ if (!cancelled) setLoading(false); });
    return ()=>{ cancelled = true; };
  }, [items, likes]);

  function playAll() {
    const q = likedTracks.map(t => trackToQueueItem(t, t._album));
    if (q.length) musicStore.setQueue(q, 0, true);
  }
  function queueSelected() {
    const picks = likedTracks.filter(t => likedSel[t.id] || likedSel[t.file_path]);
    const q = picks.map(t => trackToQueueItem(t, t._album));
    if (q.length) musicStore.setQueue(q, 0, true);
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <span className="text-xs opacity-60">{likedTracks.length} liked tracks</span>
        <div className="flex gap-1 flex-wrap">
          {likedSelIds.length > 0 && (
            <>
              <span className="text-xs opacity-60 self-center">{likedSelIds.length} selected</span>
              <button type="button" className="btn btn-xs btn-primary" onClick={queueSelected}>Queue selected</button>
              <button type="button" className="btn btn-xs btn-ghost" onClick={()=>setLikedSel({})}>Clear</button>
            </>
          )}
          <button type="button" className="btn btn-sm btn-primary gap-1" disabled={!likedTracks.length} onClick={playAll}>
            <span className="w-4 h-4"><Ic.Play /></span> Play all
          </button>
        </div>
      </div>
      {loading && <div className="opacity-50 text-sm p-6">Loading liked tracks…</div>}
      {!loading && !likedTracks.length && <div className="opacity-50 text-sm p-6">No liked tracks yet — tap the heart on any playing track.</div>}
      <div className="space-y-1">
        {likedTracks.map((t,i)=>(
          <div key={t.id||i} className="flex items-center gap-3 px-3 py-2 rounded bg-base-200 hover:bg-primary/10 group">
            <input type="checkbox" className="checkbox checkbox-xs checkbox-primary" checked={!!(likedSel[t.id]||likedSel[t.file_path])}
              onChange={e=>{ setLikedSel(prev=>{ const n={...prev}; const k=t.id||t.file_path; if(e.target.checked) n[k]=true; else delete n[k]; return n; }); }}
              onClick={e=>e.stopPropagation()} />
            <div className="flex items-center gap-3 flex-1 min-w-0 cursor-pointer"
            onClick={()=>{
              const q = likedTracks.map(x=>trackToQueueItem(x, x._album));
              musicStore.setQueue(q, i, true);
            }}>
            <span className="text-[10px] tabular-nums opacity-40 w-5">{i+1}</span>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate">{t.title||t.name}</div>
              <div className="text-[10px] opacity-50 truncate">{t._album?.artist_name||''} · {t._album?.title||''}</div>
            </div>
            <span className="text-[10px] tabular-nums opacity-50">{fmtMs(t.duration_ms)}</span>
            <span className="w-4 h-4 text-error shrink-0"><Ic.HeartFill /></span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function TrackTagEditor({ track, album, onClose, onSaved }) {
  const [title, setTitle] = useState(track.title || '');
  const [artist, setArtist] = useState((album && (album.artist_name || album.artist)) || '');
  const [albumName, setAlbumName] = useState((album && album.title) || '');
  const [trackNumber, setTrackNumber] = useState(track.track_number || '');
  const [art, setArt] = useState(null);
  const [artPreview, setArtPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  function pickArt(file) {
    if (!file) return;
    setArt(file);
    setArtPreview(URL.createObjectURL(file));
  }

  async function save() {
    setBusy(true); setErr(null);
    try {
      await api.music.updateTrackTags(track.id, {
        title, artist, album: albumName,
        track_number: trackNumber === '' ? null : Number(trackNumber),
      });
      if (art) await api.music.uploadTrackArtwork(track.id, art);
      onSaved();
      onClose();
    } catch (e) { setErr(String(e.message || e)); }
    setBusy(false);
  }

  return (
    <div className="modal modal-open" onClick={onClose}>
      <div className="modal-box max-w-md p-0 overflow-hidden" onClick={e=>e.stopPropagation()}>
        <div className="flex items-center gap-2 px-4 py-3 border-b border-base-300">
          <span className="w-4 h-4 text-base-content/50 flex-shrink-0"><Ic.Edit /></span>
          <span className="text-sm font-semibold flex-1 truncate">Edit tags — {track.title || track.name}</span>
          <button type="button" className="btn btn-ghost btn-xs btn-square" onClick={onClose}><Ic.X /></button>
        </div>
        <div className="p-4 flex flex-col gap-3">
          <p className="text-[10px] opacity-50 -mt-1">
            Writes directly into the audio file's own tags, then updates the library to match.
          </p>
          <label className="form-control">
            <span className="label-text text-xs mb-1">Title</span>
            <input className="input input-bordered input-sm" value={title} onChange={e=>setTitle(e.target.value)} />
          </label>
          <label className="form-control">
            <span className="label-text text-xs mb-1">Artist</span>
            <input className="input input-bordered input-sm" value={artist} onChange={e=>setArtist(e.target.value)} />
          </label>
          <div className="flex gap-3">
            <label className="form-control flex-1">
              <span className="label-text text-xs mb-1">Album</span>
              <input className="input input-bordered input-sm" value={albumName} onChange={e=>setAlbumName(e.target.value)} />
            </label>
            <label className="form-control w-24">
              <span className="label-text text-xs mb-1">Track #</span>
              <input type="number" min="0" className="input input-bordered input-sm" value={trackNumber} onChange={e=>setTrackNumber(e.target.value)} />
            </label>
          </div>
          <label className="form-control">
            <span className="label-text text-xs mb-1">Cover art (JPEG or PNG)</span>
            <div className="flex items-center gap-3">
              {artPreview && <img src={artPreview} alt="" className="w-12 h-12 rounded object-cover border border-base-300" />}
              <input type="file" accept="image/jpeg,image/png" className="file-input file-input-bordered file-input-sm flex-1"
                onChange={e=>pickArt(e.target.files && e.target.files[0])} />
            </div>
          </label>
          {err && <p className="text-xs text-error">{err}</p>}
          <div className="flex justify-end gap-2 pt-1">
            <button type="button" className="btn btn-ghost btn-sm" onClick={onClose} disabled={busy}>Cancel</button>
            <button type="button" className="btn btn-primary btn-sm" onClick={save} disabled={busy}>{busy ? 'Saving…' : 'Save'}</button>
          </div>
        </div>
      </div>
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
  const [genre, setGenre] = useState('');
  const [mood, setMood] = useState('');
  const [tagBusy, setTagBusy] = useState(false);
  const [editingTrack, setEditingTrack] = useState(null);
  const { current, playing } = useMusicPlayer();

  const load = React.useCallback(() => {
    api.music.get(id).then(d=>{ setItem(d); setGenre(d.genre||''); setMood(d.mood||''); }).catch(e=>setMsg(String(e.message||e)));
    fetch(`/api/music/album/${id}/tracks`).then(r=>r.json()).then(d=>setTracks(Array.isArray(d)?d:[])).catch(()=>[]);
    fetch(`/api/music/album/${id}/completeness`).then(r=>r.json()).then(setCompleteness).catch(()=>setCompleteness(null));
  }, [id]);
  useEffect(()=>{ load(); }, [load]);

  async function saveTags() {
    setTagBusy(true);
    try { await api.music.update(id, { genre, mood }); load(); }
    catch(e) { setMsg(String(e.message||e)); }
    setTagBusy(false);
  }

  const playable = tracks.filter(t=>t.file_path);

  function playAlbum(startIdx = 0, shuffle = false) {
    const q = playable.map(t=>trackToQueueItem(t, item));
    if (!q.length) { setMsg('No playable tracks on disk'); return; }
    if (shuffle) {
      musicStore.setQueue(q, 0, false);
      if (!musicStore.state.shuffle) musicStore.toggleShuffle();
      musicStore.next();
    } else {
      musicStore.setQueue(q, startIdx, true);
    }
  }
  function queueAlbum() {
    const q = playable.map(t=>trackToQueueItem(t, item));
    if (!q.length) { setMsg('No playable tracks on disk'); return; }
    musicStore.enqueue(q);
    setMsg('Added '+q.length+' tracks to queue');
  }

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
        <button type="button" className="btn btn-sm btn-primary gap-1" disabled={!playable.length} onClick={()=>playAlbum(0,false)} title="Play album">
          <span className="w-4 h-4"><Ic.Play /></span> Play
        </button>
        <button type="button" className="btn btn-sm btn-secondary gap-1" disabled={!playable.length} onClick={()=>playAlbum(0,true)} title="Shuffle play">
          <span className="w-4 h-4"><Ic.Shuffle /></span> Shuffle
        </button>
        <button type="button" className="btn btn-sm btn-accent gap-1" disabled={!playable.length} onClick={queueAlbum} title="Add to queue">
          <span className="w-4 h-4"><Ic.Queue /></span> Queue
        </button>
        <button type="button" className="btn btn-sm" disabled={busy} onClick={autoSearch}>Search & grab</button>
        <button type="button" className="btn btn-sm" disabled={busy||ixLoading} onClick={openIx}>Interactive</button>
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
      <div className="card bg-base-200 border border-base-content/5">
        <div className="card-body p-3 gap-2">
          <span className="font-semibold text-sm flex items-center gap-1"><span className="w-3.5 h-3.5 opacity-60"><Ic.Sliders /></span> Tags</span>
          <p className="text-[10px] opacity-50">Used to match this album into Genre/Mood smart playlists.</p>
          <div className="flex flex-wrap gap-2">
            <input className="input input-bordered input-sm flex-1 min-w-[140px]" placeholder="Genre(s), comma-separated" value={genre} onChange={e=>setGenre(e.target.value)} />
            <input className="input input-bordered input-sm flex-1 min-w-[140px]" placeholder="Mood(s), comma-separated" value={mood} onChange={e=>setMood(e.target.value)} />
            <button type="button" className="btn btn-sm" disabled={tagBusy} onClick={saveTags}>Save tags</button>
          </div>
        </div>
      </div>
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
          <div className="overflow-x-auto max-h-96">
            <table className="table table-xs">
              <thead><tr><th></th><th>#</th><th>Title</th><th>Disc</th><th>Plays</th><th>Duration</th><th>Status</th><th></th></tr></thead>
              <tbody>
                {tracks.map((tr,i)=>{
                  const isNow = current && tr.file_path && current.path === tr.file_path;
                  const canPlay = !!tr.file_path;
                  const plays = tr.file_path ? musicStore.playCount({ path: tr.file_path }) : 0;
                  return (
                    <tr key={tr.id||i}
                      className={(canPlay ? 'opacity-100 cursor-pointer hover:bg-primary/10 ' : 'opacity-60 ') + (isNow ? 'bg-primary/15 text-primary' : '')}
                      onClick={()=>{ if (canPlay) { const pi = playable.findIndex(p=>p.id===tr.id || p.file_path===tr.file_path); playAlbum(pi<0?0:pi, false); } }}>
                      <td className="w-8">
                        {isNow
                          ? <span className={"w-2 h-2 rounded-full inline-block "+(playing?"bg-primary animate-pulse":"bg-primary/50")} />
                          : null}
                      </td>
                      <td className="tabular-nums opacity-50">{tr.track_number||i+1}</td>
                      <td className="truncate max-w-[220px]">{tr.title||tr.name}</td>
                      <td className="opacity-50">{tr.disc_number||1}</td>
                      <td className="tabular-nums opacity-50">{plays||''}</td>
                      <td className="tabular-nums opacity-50">{fmtMs(tr.duration_ms)}</td>
                      <td><span className={'badge badge-xs '+(canPlay||tr.status==='downloaded'?'badge-success':'badge-ghost')}>{canPlay||tr.status==='downloaded'?'have':(tr.status||'wanted')}</span></td>
                      <td className="w-20">
                        {canPlay && (
                          <span className="flex gap-0.5" onClick={e=>e.stopPropagation()}>
                            <button type="button" className="btn btn-ghost btn-xs" title="Play next"
                              onClick={()=>musicStore.enqueueNext(trackToQueueItem(tr, item))}>+Next</button>
                            <button type="button" className="btn btn-ghost btn-xs" title="Add to queue"
                              onClick={()=>musicStore.enqueue(trackToQueueItem(tr, item))}>+Q</button>
                            <button type="button" className="btn btn-ghost btn-xs" title="Edit tags"
                              onClick={()=>setEditingTrack(tr)}><span className="w-3 h-3"><Ic.Edit /></span></button>
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div></div>
      )}
      {editingTrack && (
        <TrackTagEditor track={editingTrack} album={item} onClose={()=>setEditingTrack(null)} onSaved={load} />
      )}
    </MediaDetailShell>
  );
}

export { MusicPage, MusicDetailPage };
