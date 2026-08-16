import React, { useState, useEffect, useCallback, useRef } from "react";
import Ic, { Icons, P } from "../icons.jsx";
import { getToken, setToken, getAdvanced, setAdvancedFlag, AUTH_TOKEN_KEY } from "../storage.js";
import { api, TMDB, adultFetch } from "../api.js";
import { PageChrome, PosterTile, LibraryModuleShell, MediaDetailShell, LibraryLegend, LibraryHeader, MediaCard, StatusBadgeStack, libraryStatuses, CollectionProgressWidget, TeachEmpty, AddModal, SkeletonLoader } from "../components/ui.jsx";
import { InteractiveResultsPanel, InteractiveResultsTable, MediaPlayer, HlsVideo, grabPayload, releaseDownloadUrl } from "../components/media.jsx";

function TvPage({ series, refreshSeries, setMiniPlayer, setPage, libLoading=false }) {
  const showSkeleton = libLoading && !(series&&series.length);
  // skeleton rendered in list body when showSkeleton
  const [detailId, setDetailId] = useState(null);
  // Jump straight to an item's detail view when opened from Global Search
  // or the dashboard's Continue Watching row.
  useEffect(() => {
    const onOpenItem = (e) => {
      if (!e.detail || !(e.detail.mediaType === 'tv')) return;
      setDetailId(e.detail.id);
    };
    window.addEventListener('mediaos-open-item', onOpenItem);
    return () => window.removeEventListener('mediaos-open-item', onOpenItem);
  }, []);
  const [profiles, setProfiles] = useState([]);
  const [tvNav, setTvNav] = useState('series'); // series | add | import | mass | seasonpass
  const [q, setQ] = useState('');
  const [sort, setSort] = useState('title'); // title | progress | missing | year
  const [filter, setFilter] = useState('all'); // all | monitored | missing | complete
  const [selected, setSelected] = useState({});
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const TMDB = 'https://image.tmdb.org/t/p/w342';

  useEffect(() => { api.settings.profiles().then(setProfiles).catch(e => { console.warn(e); if (typeof setMsg === 'function') setMsg(String(e.message || e)); }); }, []);
  if (showSkeleton && !detailId) {
    return (
      <LibraryModuleShell title="TV" nav={[{id:'all',label:'Series'}]} active="all" onNav={()=>{}} tools={null}>
        <SkeletonLoader rows={12} />
      </LibraryModuleShell>
    );
  }
  if (detailId) {
    return <SeriesDetailPage seriesId={detailId} onBack={()=>setDetailId(null)} refreshSeries={refreshSeries} setMiniPlayer={setMiniPlayer} />;
  }
  const tvProfiles = profiles.filter(p => p.media_type === 'tv');

  async function setProfile(id, name) {
    await fetch(`/api/tv/${id}`, { method:'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ quality_profile: name || null }) });
    refreshSeries && refreshSeries();
  }
  async function toggleMonitored(s) {
    await fetch(`/api/tv/${s.id}`, { method:'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ monitored: !s.monitored }) });
    refreshSeries && refreshSeries();
  }
  async function updateAll() {
    setBusy(true); setMsg('');
    try {
      const r = await api.system.searchAllMissing();
      setMsg(`Searched missing — episodes: ${r.episodes ?? '—'}`);
      refreshSeries && refreshSeries();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }

  let list = [...(series||[])];
  if (q.trim()) {
    const qq = q.toLowerCase();
    list = list.filter(s => (s.title||'').toLowerCase().includes(qq));
  }
  if (filter === 'monitored') list = list.filter(s => s.monitored);
  if (filter === 'missing') list = list.filter(s => (s.missing_count||0) > 0);
  if (filter === 'complete') list = list.filter(s => s.episode_count > 0 && s.downloaded_count >= s.episode_count);
  list.sort((a,b) => {
    if (sort === 'year') return (b.year||0) - (a.year||0);
    if (sort === 'missing') return (b.missing_count||0) - (a.missing_count||0);
    if (sort === 'progress') {
      const pa = a.episode_count ? a.downloaded_count/a.episode_count : 0;
      const pb = b.episode_count ? b.downloaded_count/b.episode_count : 0;
      return pb - pa;
    }
    return (a.title||'').localeCompare(b.title||'');
  });

  const letters = [...new Set(list.map(s => ((s.title||'?')[0]||'?').toUpperCase()).filter(c => /[A-Z0-9]/.test(c)))].sort();

  const navItems = [
    { id:'series', label:'Series', icon: Ic.Tv },
    { id:'add', label:'Add New', icon: Ic.Plus },
    { id:'import', label:'Library Import', icon: Ic.Folder },
    { id:'mass', label:'Mass Editor', icon: Ic.List },
    { id:'seasonpass', label:'Season Pass', icon: Ic.Activity },
  ];

  function progressColor(s) {
    if (!s.episode_count) return 'bg-base-content/30';
    if (s.downloaded_count >= s.episode_count) return 'bg-success';
    if (s.downloaded_count > 0) return 'bg-info';
    return 'bg-warning';
  }

  return (
    <div className="mr-module">
      <aside className="mr-module-nav hidden md:block">
        <div className="mod-title">TV</div>
        {navItems.map(n => (
              <button key={n.id} type="button" className={tvNav===n.id?'active':''} onClick={()=>setTvNav(n.id)}>
                <n.icon /> {n.label}
              </button>
        ))}
        <div className="mx-2 my-3 border-t border-primary/10" />
        <button type="button" onClick={()=>setPage && setPage('calendar')}><Ic.Calendar /> Calendar</button>
        <button type="button" onClick={()=>setPage && setPage('wanted')}><Ic.AlertTri /> Wanted</button>
        <button type="button" onClick={()=>setPage && setPage('discover')}><Ic.Compass /> Discover</button>
        <div className="mt-4 px-2 text-[10px] opacity-40">{series.length} series</div>
      </aside>

      <div className="mr-module-body space-y-4">
        {/* Toolbar */}
        <div className="flex flex-wrap items-center gap-2 justify-between">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="mr-page-title">
              {tvNav==='series'?'Series':tvNav==='add'?'Add Series':tvNav==='import'?'Library Import':tvNav==='mass'?'Mass Editor':'Season Pass'}
            </h1>
            {tvNav==='series' && (
              <span className="badge badge-ghost badge-sm">{list.length}</span>
            )}
          </div>
          <div className="flex items-center gap-1.5 flex-wrap shrink-0">
            <button type="button" className="btn btn-ghost btn-sm gap-1 shrink-0" disabled={busy} onClick={updateAll} title="Search all missing episodes">
              <Ic.Refresh /> Update all
            </button>
            <button type="button" className="btn btn-ghost btn-sm gap-1 shrink-0" disabled={busy} onClick={async()=>{
              setBusy(true);
              for (const s of series.filter(x=>x.monitored && (x.missing_count||0)>0).slice(0,20)) {
                try { await api.tv.searchMissing(s.id); } catch(e) { setMsg(String(e.message||e)); }
              }
              setBusy(false); setMsg('RSS-style missing search queued'); refreshSeries && refreshSeries();
            }} title="Search monitored missing">
              <Ic.Rss /> RSS Sync
            </button>
            <label className="input input-bordered input-sm flex items-center gap-2 w-36 max-w-[11rem] shrink-0">
              <Ic.Search />
              <input className="grow bg-transparent outline-none text-sm min-w-0" placeholder="Search" value={q} onChange={e=>setQ(e.target.value)} />
            </label>
            <select className="select select-bordered select-sm w-28 shrink-0" value={sort} onChange={e=>setSort(e.target.value)}>
              <option value="title">Title</option>
              <option value="progress">Progress</option>
              <option value="missing">Missing</option>
              <option value="year">Year</option>
            </select>
            <select className="select select-bordered select-sm w-28 shrink-0" value={filter} onChange={e=>setFilter(e.target.value)}>
              <option value="all">All</option>
              <option value="monitored">Monitored</option>
              <option value="missing">Has missing</option>
              <option value="complete">Complete</option>
            </select>
          </div>
        </div>
        {msg && <div className="text-xs opacity-60">{msg}</div>}
        {tvNav==='series' && Object.keys(selected).length > 0 && (
          <div className="card bg-base-200 mb-2">
            <div className="card-body p-3 gap-2">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs opacity-60">{Object.keys(selected).length} selected</span>
                <button type="button" className="btn btn-xs" onClick={()=>setTvNav('mass')}>Open Mass Editor</button>
                <button type="button" className="btn btn-xs" disabled={busy} onClick={async()=>{
                  try { await api.tv.bulk({ ids: Object.keys(selected).map(Number), monitored: true }); setSelected({}); refreshSeries && refreshSeries(); }
                  catch(e){ setMsg(String(e.message||e)); }
                }}>Monitor</button>
                <button type="button" className="btn btn-xs" disabled={busy} onClick={async()=>{
                  try { await api.tv.bulk({ ids: Object.keys(selected).map(Number), monitored: false }); setSelected({}); refreshSeries && refreshSeries(); }
                  catch(e){ setMsg(String(e.message||e)); }
                }}>Unmonitor</button>
                <button type="button" className="btn btn-xs btn-ghost" onClick={()=>setSelected({})}>Clear</button>
              </div>
            </div>
          </div>
        )}


        {tvNav==='add' && (
          <div className="space-y-3">
            <p className="text-sm opacity-60">Search TMDb and add series to the library (same as Discover → TV).</p>
            <button type="button" className="btn btn-primary btn-sm" onClick={()=>setPage && setPage('discover')}>Open Discover</button>
          </div>
        )}
        {tvNav==='import' && (
          <div className="space-y-3">
            <p className="text-sm opacity-60">Import existing folders under your TV library path, or pull from Sonarr.</p>
            <div className="flex gap-2 flex-wrap">
              <button type="button" className="btn btn-sm" onClick={()=>setPage && setPage('import')}>Manual import (downloads)</button>
              <button type="button" className="btn btn-sm" onClick={()=>setPage && setPage('settings-integrations')}>Sonarr migrator</button>
              <button type="button" className="btn btn-sm" onClick={()=>setPage && setPage('settings-library')}>Library paths</button>
            </div>
          </div>
        )}
        {tvNav==='mass' && (
          <div className="space-y-3">
            <p className="text-sm opacity-60">Select series on the grid (Series tab), then apply bulk actions here.</p>
            <div className="flex gap-2 flex-wrap">
              <button type="button" className="btn btn-sm" disabled={!Object.keys(selected).length} onClick={async()=>{
                for (const id of Object.keys(selected)) {
                  await fetch(`/api/tv/${id}`, { method:'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ monitored: true }) });
                }
                setSelected({}); refreshSeries && refreshSeries();
              }}>Monitor selected</button>
              <button type="button" className="btn btn-sm" disabled={!Object.keys(selected).length} onClick={async()=>{
                for (const id of Object.keys(selected)) {
                  await fetch(`/api/tv/${id}`, { method:'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ monitored: false }) });
                }
                setSelected({}); refreshSeries && refreshSeries();
              }}>Unmonitor selected</button>
              <button type="button" className="btn btn-sm btn-primary" disabled={!Object.keys(selected).length} onClick={async()=>{
                for (const id of Object.keys(selected)) {
                  try { await api.tv.searchMissing(Number(id)); } catch(e) { setMsg(String(e.message||e)); }
                }
                setMsg('Search queued for selected');
              }}>Search missing</button>
              <button type="button" className="btn btn-sm btn-accent" disabled={!Object.keys(selected).length} onClick={async()=>{
                try {
                  await api.tv.bulk({ ids: Object.keys(selected).map(Number), monitored: true });
                  setMsg('Monitored selected (Season Pass-style: keep grabbing new eps)');
                  setSelected({}); refreshSeries && refreshSeries();
                } catch(e) { setMsg(String(e.message||e)); }
              }} title="Monitor selected series so future episodes stay wanted">Season Pass monitor</button>
              <button type="button" className="btn btn-sm btn-ghost" onClick={()=>setTvNav('seasonpass')}>Open Season Pass tab</button>
              <select className="select select-bordered select-sm" id="tv-bulk-profile" defaultValue="">
                <option value="">Bulk quality…</option>
                {tvProfiles.map(p=><option key={p.id} value={p.name}>{p.name}</option>)}
              </select>
              <button type="button" className="btn btn-sm" disabled={!Object.keys(selected).length} onClick={async()=>{
                const sel = document.getElementById('tv-bulk-profile');
                const qp = sel && sel.value; if(!qp) return;
                await fetch('/api/tv/bulk', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ ids: Object.keys(selected).map(Number), quality_profile: qp })});
                setSelected({}); refreshSeries && refreshSeries();
              }}>Apply profile</button>
            </div>
            <p className="text-xs opacity-50">{Object.keys(selected).length} selected — switch to Series and click posters while holding selection mode, or use checkboxes on cards.</p>
          </div>
        )}
        {tvNav==='seasonpass' && (
          <div className="space-y-3">
            <p className="text-sm opacity-60">Monitored series with missing episodes — Season Pass style overview.</p>
            <div className="overflow-x-auto">
              <table className="table table-sm">
                <thead><tr><th>Series</th><th>Progress</th><th>Missing</th><th>Profile</th><th></th></tr></thead>
                <tbody>
                  {series.filter(s=>s.monitored && (s.missing_count||0)>0).map(s=>(
                    <tr key={s.id} className="hover">
                      <td><button type="button" className="link link-hover font-medium" onClick={()=>setDetailId(s.id)}>{s.title}</button></td>
                      <td className="font-mono text-xs">{s.downloaded_count}/{s.episode_count}</td>
                      <td><span className="badge badge-warning badge-sm">{s.missing_count}</span></td>
                      <td className="text-xs">{s.quality_profile||'Default'}</td>
                      <td><button type="button" className="btn btn-xs btn-primary" onClick={()=>api.tv.searchMissing(s.id).then(()=>setMsg('Searching '+s.title))}>Search</button></td>
                    </tr>
                  ))}
                  {series.filter(s=>s.monitored && (s.missing_count||0)>0).length===0 && (
                    <tr><td colSpan={5} className="opacity-40">No missing monitored episodes</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {tvNav==='series' && (
          series.length===0 ? (
            <div className="text-sm text-base-content/60 max-w-md space-y-1 py-8">
              <p className="font-medium">No TV series yet</p>
              <p>Use Add New, Discover → TV, or <button type="button" className="link link-primary" onClick={()=>setPage&&setPage('setup')}>Setup wizard</button>. Then open a series and search missing.</p>
            </div>
          ) : (
            <div className="flex gap-3">
              <div className="flex-1 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-7 gap-3">
                {list.map(s => {
                  const dl = s.downloaded_count||0;
                  const ep = s.episode_count||0;
                  const pct = ep ? Math.round(100*dl/ep) : 0;
                  const complete = ep>0 && dl>=ep;
                  return (
                    <div key={s.id} className="group relative rounded-lg overflow-hidden bg-base-200 shadow-sm hover:shadow-md hover:ring-2 hover:ring-primary/40 transition-all cursor-pointer"
                      onClick={()=>setDetailId(s.id)}>
                      {/* select checkbox for mass editor */}
                      <label className={`absolute top-1.5 left-1.5 z-10 transition-opacity ${selected[s.id] ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`} onClick={e=>e.stopPropagation()}>
                        <input type="checkbox" className="checkbox checkbox-xs checkbox-primary" checked={!!selected[s.id]}
                          onChange={e=>{ setSelected(prev=>{ const n={...prev}; if(e.target.checked) n[s.id]=true; else delete n[s.id]; return n; }); }} />
                      </label>
                      <div className="aspect-[2/3] bg-base-300 relative">
                        {s.poster_path
                          ? <img src={TMDB+s.poster_path} alt={s.title} className="w-full h-full object-cover" loading="lazy" />
                          : <div className="w-full h-full flex items-center justify-center opacity-30 text-xs p-2 text-center">{s.title}</div>}
                        {/* progress strip */}
                        <div className={"absolute bottom-0 left-0 right-0 h-1.5 "+progressColor(s)}>
                          <div className="h-full bg-white/30" style={{width: pct+'%'}} />
                        </div>
                        <div className={"absolute bottom-2 left-2 badge badge-sm font-mono border-0 text-white shadow "+(complete?'bg-success':dl>0?'bg-info':'bg-warning')}>
                          {dl}/{ep}
                        </div>
                      </div>
                      <div className="p-2 space-y-0.5">
                        <div className="text-xs font-semibold leading-tight line-clamp-2 min-h-[2rem]">{s.title}{s.year?` (${s.year})`:''}</div>
                        <div className="flex items-center gap-1 flex-wrap">
                          <button type="button" className={"badge badge-xs border-0 "+(s.monitored?'badge-success':'badge-ghost')}
                            onClick={e=>{ e.stopPropagation(); toggleMonitored(s); }}>
                            {s.monitored?'Monitored':'Not monitored'}
                          </button>
                          <span className="badge badge-xs badge-outline truncate max-w-[5.5rem]">{s.quality_profile||'any'}</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
              {/* letter jump */}
              <div className="hidden xl:flex flex-col text-[10px] opacity-50 sticky top-20 h-fit gap-0.5 pl-1">
                {letters.map(L => (
                  <button type="button" key={L} className="hover:text-primary hover:opacity-100" onClick={()=>{
                    const el = list.find(s => ((s.title||'')[0]||'').toUpperCase()===L);
                    if (el) setDetailId(el.id);
                  }}>{L}</button>
                ))}
              </div>
            </div>
          )
        )}
      </div>
    </div>
  );
}




function SeriesDetailPage({ seriesId, onBack, refreshSeries, setMiniPlayer }) {
  const [series, setSeries] = useState(null);
  const [episodes, setEpisodes] = useState([]);
  const [profiles, setProfiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [playingEp, setPlayingEp] = useState(null);
  const [seasonTab, setSeasonTab] = useState('all');
  // Interactive search panel
  const [ixEp, setIxEp] = useState(null); // episode being searched
  const [ixSeason, setIxSeason] = useState(null);
  const [ixResults, setIxResults] = useState([]);
  const [ixLoading, setIxLoading] = useState(false);
  const TMDB = 'https://image.tmdb.org/t/p/w342';

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      fetch(`/api/tv/${seriesId}`).then(r=>r.json()),
      api.tv.episodes(seriesId),
      api.settings.profiles().catch(()=>[]),
    ]).then(([s, eps, prof]) => {
      setSeries(s); setEpisodes(eps||[]); setProfiles(prof||[]);
    }).catch(e=>setMsg(String(e))).finally(()=>setLoading(false));
  }, [seriesId]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    let es;
    try {
      es = new EventSource('/api/sse/events');
      es.addEventListener('queue', () => load());
      es.addEventListener('activity', () => load());
    } catch(e) {}
    return () => { try { es && es.close(); } catch(e) {} };
  }, [load]);

  const seasons = React.useMemo(() => {
    const m = {};
    episodes.forEach(e => {
      if (!m[e.season_number]) m[e.season_number] = [];
      m[e.season_number].push(e);
    });
    return Object.keys(m).map(Number).sort((a,b)=>a-b).map(s => ({
      season: s,
      eps: m[s].sort((a,b)=>a.episode_number-b.episode_number),
      downloaded: m[s].filter(e=>e.status==='downloaded'||e.file_path).length,
      total: m[s].length,
    }));
  }, [episodes]);

  async function openSeriesPackSearch() {
    setIxEp(null); setIxSeason(null); setIxResults(null); setIxLoading(true);
    try {
      const data = await api.tv.interactiveSeriesPack(seriesId);
      setIxResults(data || { results: [], rejected: [] });
    } catch(e) { setMsg(String(e.message||e)); setIxResults({ results: [], rejected: [] }); }
    setIxLoading(false);
  }
  async function searchMissing() {
    setBusy(true); setMsg(null);
    try {
      const r = await api.tv.searchMissing(seriesId);
      setMsg(`Search missing: ${r.searched||0} auto-grabs`);
      load(); refreshSeries && refreshSeries();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  async function searchSeason(s) {
    setBusy(true);
    try {
      const r = await api.tv.searchSeason(seriesId, s);
      setMsg(`Season ${s}: ${(r.grabs||[]).length} grabs`);
      load();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  async function openInteractiveEpisode(ep) {
    setIxEp(ep); setIxSeason(null); setIxResults(null); setIxLoading(true);
    try {
      const data = await api.tv.interactiveEpisode(ep.id);
      setIxResults(data || { results: [], rejected: [] });
    } catch(e) { setMsg(String(e.message||e)); setIxResults({ results: [], rejected: [] }); }
    setIxLoading(false);
  }
  async function openInteractiveSeason(s) {
    setIxSeason(s); setIxEp(null); setIxResults(null); setIxLoading(true);
    try {
      const data = await api.tv.interactiveSeason(seriesId, s);
      setIxResults(data || { results: [], rejected: [] });
    } catch(e) { setMsg(String(e.message||e)); setIxResults({ results: [], rejected: [] }); }
    setIxLoading(false);
  }
  async function grabRelease(rel) {
    if (!ixEp && ixSeason==null) return;
    setBusy(true);
    try {
      // For season pack, grab against first missing ep in season
      let epId = ixEp?.id;
      if (!epId && ixSeason!=null) {
        const ep = episodes.find(e => e.season_number===ixSeason && e.monitored && e.status!=='downloaded');
        epId = ep?.id;
      }
      if (!epId) { setMsg('No episode target for grab'); setBusy(false); return; }
      await api.tv.grabEpisode(epId, grabPayload(rel));
      setMsg('Grabbed: ' + rel.title);
      setIxResults([]); setIxEp(null); setIxSeason(null);
      load(); refreshSeries && refreshSeries();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  async function fileAction(ep, action) {
    setBusy(true);
    try {
      if (action==='clear') await api.tv.episodeFile(ep.id, { clear: true });
      if (action==='delete') {
        if (!confirm('Delete file from disk and mark episode missing?')) { setBusy(false); return; }
        await api.tv.episodeFile(ep.id, { delete_file: true });
      }
      load();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  async function refreshMeta() {
    setBusy(true);
    try { await api.tv.refresh(seriesId); load(); setMsg('Metadata refreshed'); }
    catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  async function setProfile(name) {
    await fetch(`/api/tv/${seriesId}`, { method:'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ quality_profile: name || null }) });
    load(); refreshSeries && refreshSeries();
  }
  async function toggleEp(ep) {
    await fetch(`/api/tv/episodes/${ep.id}`, { method:'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ monitored: !ep.monitored }) });
    load();
  }
  
  async function setTrackStatus(status) {
    setBusy(true); setMsg(null);
    try {
      const r = await fetch('/api/tracking', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ media_item_id: seriesId, status }),
      });
      if (!r.ok) throw new Error((await r.json().catch(()=>({}))).detail || 'Track failed');
      setMsg('Tracking: ' + String(status).replace(/_/g, ' '));
    } catch (e) { setMsg(String(e.message || e)); }
    finally { setBusy(false); }
  }

  async function toggleMonitored() {
    await fetch(`/api/tv/${seriesId}`, { method:'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ monitored: !series.monitored }) });
    load(); refreshSeries && refreshSeries();
  }

  function fmtSize(n) {
    if (n==null) return '—';
    if (n > 1e9) return (n/1e9).toFixed(1)+' GB';
    if (n > 1e6) return (n/1e6).toFixed(0)+' MB';
    return n+' B';
  }

  if (loading && !series) return <div className="flex justify-center py-20"><span className="loading loading-spinner loading-lg text-primary"/></div>;
  if (!series) return <div className="p-6"><button type="button" className="btn btn-sm" onClick={onBack}>Back</button><p className="mt-4 opacity-50">Series not found</p></div>;

  const tvProfiles = (profiles||[]).filter(p=>p.media_type==='tv');
  const dl = series.downloaded_count||0;
  const ep = series.episode_count||0;
  const shownSeasons = seasonTab==='all' ? seasons : seasons.filter(s=>String(s.season)===String(seasonTab));

  return (
    <div className="space-y-4 max-w-6xl">
      <button type="button" className="btn btn-ghost btn-sm" onClick={onBack}>← Series</button>
      <div className="flex flex-col md:flex-row gap-4">
        <div className="w-40 shrink-0">
          {series.poster_path
            ? <img src={TMDB+series.poster_path} className="rounded-lg shadow-lg w-full" alt=""/>
            : <div className="aspect-[2/3] bg-base-200 rounded-lg"/>}
        </div>
        <div className="flex-1 space-y-2">
          <h1 className="text-2xl font-bold">{series.title}{series.year?` (${series.year})`:''}</h1>
          <div className="flex flex-wrap gap-2 items-center">
            <button type="button" className={"badge badge-lg border-0 "+(series.monitored?'badge-success':'badge-ghost')} onClick={toggleMonitored}>
              {series.monitored?'Monitored':'Not monitored'}
            </button>
            <span className="badge badge-lg badge-outline font-mono">{dl}/{ep}</span>
            <span className="badge badge-outline">{series.series_type||'standard'}</span>
            <select className="select select-bordered select-sm" value={series.quality_profile||''} onChange={e=>setProfile(e.target.value)}>
              <option value="">Default profile</option>
              {tvProfiles.map(p=><option key={p.id} value={p.name}>{p.name}</option>)}
            </select>
            <select className="select select-bordered select-sm" defaultValue="" disabled={busy}
              onChange={e=>{ if(e.target.value) { setTrackStatus(e.target.value); e.target.value=''; } }} title="Unified tracking">
              <option value="">Track…</option>
              <option value="planned">Planned</option>
              <option value="in_progress">In progress</option>
              <option value="completed">Completed</option>
              <option value="on_hold">On hold</option>
              <option value="dropped">Dropped</option>
            </select>
          </div>
          <progress className="progress progress-primary w-full max-w-md h-2" value={ep?Math.round(100*dl/ep):0} max="100" />
          {series.overview && <p className="text-sm opacity-70 line-clamp-4 max-w-2xl">{series.overview}</p>}
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={searchMissing}>Search missing (auto)</button>
            <button type="button" className="btn btn-sm btn-accent" disabled={busy} title="Add top interactive-search result as stream / .strm (parity)"
              onClick={async ()=>{
                setBusy(true); setMsg(null);
                try {
                  const rows = await api.tv.interactiveSeriesPack(seriesId);
                  const list = Array.isArray(rows) ? rows : (rows?.results || []);
                  const first = list[0];
                  if (first && (first.download_url || first.magnet)) {
                    await fetch('/api/overhaul/streams', {
                      method:'POST', headers:{'Content-Type':'application/json'},
                      body: JSON.stringify({
                        title: first.title || series.title,
                        stream_url: first.download_url || first.magnet,
                        media_item_id: seriesId,
                        provider: first.indexer || 'search'
                      })
                    });
                    setMsg('Stream link added from top result');
                  } else setMsg('No streamable release found');
                } catch(e) { setMsg(String(e.message||e)); }
                setBusy(false);
              }}>Stream</button>
            <button type="button" className="btn btn-sm" disabled={busy} onClick={refreshMeta}>Refresh metadata</button>
            <button type="button" className="btn btn-sm" onClick={load}>Reload</button>
          </div>
          {msg && <p className="text-xs opacity-60">{msg}</p>}
        </div>
      </div>

      {/* Interactive search panel */}
      {(ixLoading || ixResults) && (ixEp || ixSeason!=null || (ixResults && !Array.isArray(ixResults))) && (
        <InteractiveResultsPanel
          data={ixResults}
          loading={ixLoading}
          busy={busy}
          onGrab={grabRelease}
          onClose={()=>{ setIxEp(null); setIxSeason(null); setIxResults(null); }}
        />
      )}

      <div className="tabs tabs-boxed flex-wrap w-fit">
        <a className={'tab '+(seasonTab==='all'?'tab-active':'')} onClick={()=>setSeasonTab('all')}>All seasons</a>
        {seasons.map(s=>(
          <a key={s.season} className={'tab '+(String(seasonTab)===String(s.season)?'tab-active':'')} onClick={()=>setSeasonTab(s.season)}>
            S{String(s.season).padStart(2,'0')} ({s.downloaded}/{s.total})
          </a>
        ))}
      </div>

      {shownSeasons.map(({season, eps, downloaded, total}) => (
        <div key={season} className="card bg-base-200 shadow-sm">
          <div className="card-body p-3 gap-2">
            <div className="flex justify-between items-center flex-wrap gap-2">
              <h2 className="font-semibold text-sm">Season {season} <span className="font-mono opacity-60">{downloaded}/{total}</span></h2>
              <div className="flex gap-1">
                <button type="button" className="btn btn-xs" disabled={busy} onClick={()=>openInteractiveSeason(season)}>Interactive search</button>
                <button type="button" className="btn btn-xs btn-primary" disabled={busy} onClick={()=>searchSeason(season)}>Auto season</button>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="table table-xs">
                <thead><tr><th></th><th>Ep</th><th>Title</th><th>Air</th><th>Status</th><th>Abs</th><th>File</th><th></th></tr></thead>
                <tbody>
                  {eps.map(e=>{
                    const have = e.status==='downloaded'||e.file_path;
                    return (
                      <tr key={e.id} className="hover">
                        <td><input type="checkbox" className="checkbox checkbox-xs" checked={!!e.monitored} onChange={()=>toggleEp(e)} title="Monitored"/></td>
                        <td className="font-mono text-xs">E{String(e.episode_number).padStart(2,'0')}</td>
                        <td className="text-sm">{e.title||'—'}</td>
                        <td className="text-xs opacity-50 whitespace-nowrap">{e.air_date||'—'}</td>
                        <td><span className={"badge badge-xs "+(have?'badge-success':e.monitored?'badge-warning':'badge-ghost')}>{have?'Downloaded':e.status}</span></td>
                        <td className="font-mono text-xs opacity-50">{e.absolute_episode_number??'—'}</td>
                        <td className="text-[10px] font-mono opacity-40 max-w-[8rem] truncate" title={e.file_path||''}>{e.file_path ? e.file_path.split('/').pop() : '—'}</td>
                        <td className="flex gap-0.5 flex-wrap">
                          <button type="button" className="btn btn-ghost btn-xs" onClick={()=>openInteractiveEpisode(e)} title="Interactive search">Search</button>
                          {have && <button type="button" className="btn btn-ghost btn-xs" onClick={()=>setPlayingEp(e)}>Play</button>}
                          {have && <button type="button" className="btn btn-ghost btn-xs" onClick={()=>fileAction(e,'clear')} title="Unlink file">Unlink</button>}
                          {have && <button type="button" className="btn btn-ghost btn-xs text-error" onClick={()=>fileAction(e,'delete')} title="Delete file">Del</button>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ))}

      {playingEp && (
        <div className="fixed inset-x-0 bottom-0 z-50 p-3 bg-base-300/95 border-t backdrop-blur">
          <div className="flex justify-between mb-1">
            <span className="text-sm font-medium">{series.title} S{String(playingEp.season_number).padStart(2,'0')}E{String(playingEp.episode_number).padStart(2,'0')}</span>
            <button type="button" className="btn btn-xs" onClick={()=>setPlayingEp(null)}>Close</button>
          </div>
          <MediaPlayer episodeId={playingEp.id} title={playingEp.title} onClose={()=>setPlayingEp(null)} />
        </div>
      )}
    </div>
  );
}




export { TvPage, SeriesDetailPage };
