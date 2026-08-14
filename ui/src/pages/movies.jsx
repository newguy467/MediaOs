import React, { useState, useEffect, useCallback, useRef } from "react";
import Ic, { Icons, P } from "../icons.jsx";
import { getToken, setToken, getAdvanced, setAdvancedFlag, AUTH_TOKEN_KEY } from "../storage.js";
import { api, TMDB, adultFetch } from "../api.js";
import { PageChrome, PosterTile, LibraryModuleShell, MediaDetailShell, LibraryLegend, LibraryHeader, MediaCard, StatusBadgeStack, libraryStatuses, CollectionProgressWidget, TeachEmpty, AddModal, SkeletonLoader } from "../components/ui.jsx";
import { InteractiveResultsPanel, InteractiveResultsTable, MediaPlayer, HlsVideo, grabPayload, releaseDownloadUrl } from "../components/media.jsx";

function MoviesPage({ movies, refreshMovies, setMiniPlayer, setPage, libLoading=false }) {
  const [detailId, setDetailId] = useState(null);
  const [q, setQ] = useState('');
  const [filter, setFilter] = useState('all'); // all | monitored | missing | downloaded
  const [selected, setSelected] = useState({});
  const [qp, setQp] = useState('');
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);

  if (detailId) {
    return <MovieDetailPage movieId={detailId} onBack={()=>setDetailId(null)} refreshMovies={refreshMovies} setMiniPlayer={setMiniPlayer} />;
  }

  const filtered = (movies||[]).filter(m => {
    if (q && !(m.title||'').toLowerCase().includes(q.toLowerCase())) return false;
    if (filter==='monitored' && !m.monitored) return false;
    if (filter==='missing' && !(['wanted','missing','failed'].includes(m.status))) return false;
    if (filter==='downloaded' && m.status!=='downloaded' && !m.file_path) return false;
    return true;
  });

  async function searchAllMissing() {
    setBusy(true); setMsg(null);
    try {
      const r = await api.movies.searchMissing();
      setMsg(`Searched ${r.searched||0}   grabbed ${r.grabbed||0}`);
      refreshMovies && refreshMovies();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }

  return (
    <LibraryModuleShell
      title="Movies"
      active={filter}
      onNav={(id) => {
        const routes = { tv:'tv', music:'music', books:'books', audiobooks:'audiobooks', comics:'comics', discover:'discover', queue:'queue', settings:'settings-hub' };
        if (routes[id]) { setPage && setPage(routes[id]); return; }
        if (['all','monitored','missing','downloaded'].includes(id)) setFilter(id);
      }}
      nav={[
        { id: 'all', label: 'Movies' },
        { id: 'tv', label: 'TV' },
        { id: 'music', label: 'Music' },
        { id: 'books', label: 'Books' },
        { id: 'audiobooks', label: 'Audiobooks' },
        { id: 'comics', label: 'Comics' },
        { id: 'discover', label: 'Discover' },
        { id: 'queue', label: 'Queue' },
        { id: 'settings', label: 'Settings' },
      ]}
      tools={<>
        <input className="mr-search" placeholder="Search movies…" value={q} onChange={e=>setQ(e.target.value)} />
        <button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={searchAllMissing}>Search missing</button>
      </>}
    >
      {msg && <div className="alert alert-info text-xs py-2 mb-3">{msg}</div>}
      {libLoading && !movies?.length && <SkeletonLoader rows={12} />}
      <div className="poster-grid">
        {filtered.map(m => (
          <PosterTile
            key={m.id}
            title={m.title}
            year={m.year}
            poster={m.poster_path}
            status={m.status}
            quality={m.quality_profile || (m.status==='downloaded' ? 'HD' : null)}
            onClick={() => setDetailId(m.id)}
          />
        ))}
      </div>
      {!filtered.length && <div className="opacity-50 text-sm p-8 text-center">No movies — use Discover or search to add</div>}
    </LibraryModuleShell>
  );
}

function MovieDetailPage({ movieId, onBack, refreshMovies, setMiniPlayer }) {
  const [movie, setMovie] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const [ixResults, setIxResults] = useState(null);
  const [ixLoading, setIxLoading] = useState(false);

  const load = React.useCallback(() => {
    api.movies.get(movieId).then(setMovie).catch(e=>setMsg(String(e.message||e)));
  }, [movieId]);
  useEffect(()=>{ load(); }, [load]);

  async function toggleMonitor() {
    if (!movie) return;
    setBusy(true);
    try {
      await api.movies.update(movie.id, { monitored: !movie.monitored });
      load(); refreshMovies && refreshMovies();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  async function autoSearch() {
    setBusy(true); setMsg(null);
    try {
      const r = await api.movies.searchNow(movieId);
      const body = r && r.json ? await r.json().catch(()=>null) : r;
      setMsg(body?.title ? `Grabbed: ${body.title}` : 'Search finished (no grab)');
      load(); refreshMovies && refreshMovies();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  async function openInteractive() {
    setIxLoading(true); setIxResults([]); setMsg(null);
    try {
      const rows = await api.movies.interactive(movieId);
      setIxResults(rows||[]);
    } catch(e) { setMsg(String(e.message||e)); }
    setIxLoading(false);
  }
  async function grabRel(rel) {
    setBusy(true);
    try {
      await api.movies.grab(movieId, grabPayload(rel));
      setMsg(`Grabbed: ${rel.title}`);
      setIxResults(null);
      load(); refreshMovies && refreshMovies();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  async function doRefresh() {
    setBusy(true);
    try {
      await api.movies.refresh(movieId);
      load(); refreshMovies && refreshMovies();
      setMsg('Metadata refreshed');
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  async function doSubs() {
    setBusy(true);
    try {
      const r = await api.movies.subtitles(movieId);
      setMsg(r?.path ? `Subtitle: ${r.path}` : JSON.stringify(r));
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  async function clearFile() {
    setBusy(true);
    try {
      await api.movies.file(movieId, { clear: true });
      load(); refreshMovies && refreshMovies();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  async function remove() {
    if (!confirm('Remove from library?')) return;
    await api.movies.remove(movieId);
    refreshMovies && refreshMovies();
    onBack && onBack();
  }

  if (!movie) return <div className="p-6 opacity-50">Loading…</div>;
  const poster = movie.poster_path
    ? (movie.poster_path.startsWith('http') ? movie.poster_path : `https://image.tmdb.org/t/p/w500${movie.poster_path}`)
    : null;

  return (
    <div className="space-y-4 max-w-5xl">
      <button type="button" className="btn btn-ghost btn-sm" onClick={onBack}>← Library</button>
      {msg && <div className="alert alert-info text-xs py-2">{msg}</div>}
      <div className="flex flex-col md:flex-row gap-4">
        <div className="w-40 shrink-0">
          {poster
            ? <img src={poster} alt="" className="rounded-lg shadow w-full" />
            : <div className="aspect-[2/3] bg-base-300 rounded-lg" />}
        </div>
        <div className="flex-1 space-y-2">
          <h1 className="text-2xl font-bold">{movie.title} {movie.year && <span className="opacity-50 font-normal">({movie.year})</span>}</h1>
          <div className="flex flex-wrap gap-2 items-center">
            <span className={'badge '+(movie.status==='downloaded'?'badge-success':'badge-warning')}>{movie.status}</span>
            <span className={'badge '+(movie.monitored?'badge-primary':'badge-ghost')}>{movie.monitored?'Monitored':'Unmonitored'}</span>
            {movie.quality_profile && <span className="badge badge-outline">{movie.quality_profile}</span>}
            {movie.quality_score!=null && <span className="badge badge-ghost">score {movie.quality_score}</span>}
          </div>
          {movie.overview && <p className="text-sm opacity-70 max-w-2xl">{movie.overview}</p>}
          {movie.file_path && <p className="text-xs font-mono opacity-50 break-all">{movie.file_path}</p>}
          <div className="flex flex-wrap gap-2 pt-2">
            <button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={autoSearch}>Search & grab</button>
            <button type="button" className="btn btn-sm btn-accent" disabled={busy} title="Prefer stream / .strm path"
              onClick={async ()=>{
                setBusy(true); setMsg(null);
                try {
                  const rows = await api.movies.interactive(movieId);
                  const first = (rows||[])[0];
                  if (first && (first.download_url||first.magnet)) {
                    await fetch('/api/overhaul/streams', {
                      method:'POST', headers:{'Content-Type':'application/json'},
                      body: JSON.stringify({ title: first.title||movie.title, stream_url: first.download_url||first.magnet, media_item_id: movieId, provider: first.indexer||'search' })
                    });
                    setMsg('Stream link added from top result');
                  } else setMsg('No streamable release found');
                } catch(e) { setMsg(String(e.message||e)); }
                setBusy(false);
              }}>Stream</button>
            <button type="button" className="btn btn-sm btn-secondary" disabled={busy||ixLoading} onClick={openInteractive}>Interactive search</button>
            <button type="button" className="btn btn-sm" disabled={busy} onClick={toggleMonitor}>{movie.monitored?'Unmonitor':'Monitor'}</button>
            <button type="button" className="btn btn-sm" disabled={busy} onClick={doRefresh}>Refresh metadata</button>
            {movie.file_path && <button type="button" className="btn btn-sm" disabled={busy} onClick={doSubs}>Subtitles</button>}
            {movie.file_path && setMiniPlayer && (
              <button type="button" className="btn btn-sm" onClick={()=>setMiniPlayer({ itemId: movie.id, title: movie.title, path: movie.file_path })}>Play</button>
            )}
            {movie.file_path && <button type="button" className="btn btn-sm btn-ghost" disabled={busy} onClick={clearFile}>Clear file</button>}
            <button type="button" className="btn btn-sm btn-ghost text-error" onClick={remove}>Delete</button>
          </div>
        </div>
      </div>

      {(ixLoading || ixResults) && (
        <InteractiveResultsPanel data={ixResults} loading={ixLoading} busy={busy} onGrab={grabRel} onClose={()=>setIxResults(null)} />
      )}
    </div>
  );
}




export { MoviesPage, MovieDetailPage };
