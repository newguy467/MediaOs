import React, { useState, useEffect, useCallback, useRef } from "react";
import Ic, { Icons, P } from "../icons.jsx";
import { getToken, setToken, getAdvanced, setAdvancedFlag, AUTH_TOKEN_KEY } from "../storage.js";
import {api, TMDB, adultFetch, getAdultUnlock} from "../api.js";
import { PageChrome, PosterTile, LibraryModuleShell, MediaDetailShell, LibraryLegend, LibraryHeader, MediaCard, StatusBadgeStack, libraryStatuses, CollectionProgressWidget, TeachEmpty, AddModal } from "../components/ui.jsx";
import { InteractiveResultsPanel, InteractiveResultsTable, MediaPlayer, HlsVideo } from "../components/media.jsx";

function DiscoverPage({ movies, series, music = [], refreshMovies, refreshSeries, enabledModules = [], setPage }) {

  const [adultQ, setAdultQ] = useState('');
  const [adultResults, setAdultResults] = useState([]);
  const [adultBusy, setAdultBusy] = useState(false);
  const [adultMsg, setAdultMsg] = useState(null);
  async function searchAdultDiscover(e) {
    e && e.preventDefault();
    if (!adultQ.trim()) return;
    setAdultBusy(true); setAdultMsg(null);
    try {
      const tok = (typeof getAdultUnlock === 'function') ? getAdultUnlock() : null;
      const headers = {};
      if (tok) headers['X-Adult-Unlock'] = tok;
      const r = await fetch('/api/discover/adult/search?q='+encodeURIComponent(adultQ.trim()), { headers }).then(x=>x.json());
      setAdultResults(r.results||[]);
      if (r.hint) setAdultMsg(r.hint);
      if (!(r.results||[]).length && !r.hint) setAdultMsg('No results — set TPDB_API_KEY in Settings → Adult');
    } catch(ex) { setAdultMsg(String(ex.message||ex)); }
    setAdultBusy(false);
  }
  async function addAdultFromDiscover(row) {
    setAdultBusy(true);
    try {
      await api.adult.add({
        title: row.title, year: row.year, external_id: row.external_id,
        overview: row.overview, poster_path: row.poster_path,
      });
      setAdultMsg('Added: '+row.title);
    } catch(ex) { setAdultMsg(String(ex.message||ex)); }
    setAdultBusy(false);
  }

  const [mode, setMode] = useState('browse'); // browse | search
  const [tab, setTab] = useState('movie');
  const [kind, setKind] = useState('popular');
  const [q, setQ] = useState('');
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [profiles, setProfiles] = useState([]);
  const [profile, setProfile] = useState('');
  const [busy, setBusy] = useState(null);
  const [msg, setMsg] = useState(null);
  const [genres, setGenres] = useState([]);
  const [genreId, setGenreId] = useState('');
  const [year, setYear] = useState('');
  const [network, setNetwork] = useState('');
  const [lang, setLang] = useState('');
  const [minScore, setMinScore] = useState('');
  const [musicTag, setMusicTag] = useState('');
  const [musicYear, setMusicYear] = useState('');
  const [musicTags, setMusicTags] = useState([]);

  const movieKinds = [['popular','Popular'],['trending','Trending'],['top_rated','Top rated'],['now_playing','In theatres'],['upcoming','Upcoming']];
  const tvKinds = [['popular','Popular'],['trending','Trending'],['top_rated','Top rated'],['on_the_air','On air']];
  const musicKinds = [['popular','Popular'],['new','New releases']];
  // Common TMDb TV networks
  const networks = [
    { id: '', label: 'Any network' },
    { id: '213', label: 'Netflix' },
    { id: '49', label: 'HBO' },
    { id: '2552', label: 'Apple TV+' },
    { id: '1024', label: 'Amazon' },
    { id: '2739', label: 'Disney+' },
    { id: '453', label: 'Hulu' },
    { id: '67', label: 'BBC' },
  ];

  useEffect(() => { api.settings.profiles().then(setProfiles).catch(e => { console.warn(e); if (typeof setMsg === 'function') setMsg(String(e.message || e)); }); }, []);
  useEffect(() => {
    if (tab === 'music') {
      fetch('/api/discover/music/tags').then(r=>r.json()).then(d=>setMusicTags(d.tags||[])).catch(()=>setMusicTags([]));
      setGenreId('');
      return;
    }
    fetch('/api/discover/genres?media=' + (tab==='movie'?'movie':'tv'))
      .then(r=>r.json()).then(d=>setGenres(d.genres||[])).catch(()=>setGenres([]));
    setGenreId('');
  }, [tab]);

  useEffect(() => {
    if (mode !== 'browse') return;
    setLoading(true); setMsg(null);
    // Filtered discover when genre/year/network set
    if (genreId || year || (tab==='tv' && network)) {
      const params = new URLSearchParams({ page: '1', sort_by: 'popularity.desc' });
      if (genreId) params.set('with_genres', genreId);
      if (year && tab==='movie') params.set('year', year);
      if (network && tab==='tv') params.set('with_networks', network);
      if (lang) params.set('with_original_language', lang);
      if (minScore) params.set('vote_average_gte', minScore);
      const path = tab==='movie' ? '/api/discover/movies/discover?' : '/api/discover/tv/discover?';
      fetch(path + params.toString()).then(r=>r.json())
        .then(d=>setItems(d.results||[])).catch(()=>setItems([])).finally(()=>setLoading(false));
      return;
    }
    if (tab === 'music') {
      const params = new URLSearchParams();
      if (musicTag) params.set('tag', musicTag);
      if (musicYear) params.set('year', musicYear);
      const base = kind === 'new' ? '/api/discover/music/new' : '/api/discover/music/popular';
      const qs = params.toString();
      fetch(base + (qs ? '?' + qs : '')).then(r=>r.json()).then(d=>setItems(d.results||[])).catch(()=>setItems([])).finally(()=>setLoading(false));
      return;
    }
    const fn = tab === 'movie' ? api.discover.movies : api.discover.tv;
    fn(kind).then(setItems).catch(()=>setItems([])).finally(()=>setLoading(false));
  }, [mode, tab, kind, genreId, year, network, lang, minScore, musicTag, musicYear]);

  useEffect(() => {
    if (mode !== 'search' || !q.trim()) { if (mode==='search') setItems([]); return; }
    setLoading(true);
    const h = setTimeout(async () => {
      try {
        if (tab === 'music') {
          const r = await fetch('/api/discover/music/search?q=' + encodeURIComponent(q)).then(x=>x.json());
          setItems(r.results || []);
        } else {
          const r = tab === 'movie' ? await api.movies.search(q) : await api.tv.search(q);
          setItems(r || []);
        }
      } catch { setItems([]); }
      setLoading(false);
    }, 400);
    return () => clearTimeout(h);
  }, [mode, q, tab]);

  // Map external_id → full library item for multi-status chips
  const libMap = {};
  const libSource = tab==='movie' ? movies : tab==='music' ? (music||[]) : series;
  (libSource||[]).forEach(m => {
    libMap[m.external_id] = m;
    libMap[String(m.external_id)] = m;
    if (m.title) libMap['t:'+String(m.title).toLowerCase()] = m;
  });
  const existing = new Set(Object.keys(libMap));
  const kinds = tab === 'movie' ? movieKinds : tab === 'music' ? musicKinds : tvKinds;
  const movieProfiles = profiles.filter(p => p.media_type === 'movie');
  const TMDB = 'https://image.tmdb.org/t/p/w342';

  async function addItem(item) {
    const ext = item.external_id || item.tmdb_id || item.id;
    setBusy(ext); setMsg(null);
    try {
      if (tab === 'movie') {
        await api.movies.add(ext, profile ? { quality_profile: profile } : {});
        refreshMovies && await refreshMovies();
      } else if (tab === 'music') {
        const mbid = item.external_mbid || item.mbid || (String(item.id||'').includes('-') ? item.id : null);
        let eid = item.external_id;
        if (eid == null || Number.isNaN(Number(eid))) {
          const s = String(mbid || item.title || ext || 'x');
          eid = Math.abs(s.split('').reduce((a,c)=>((a<<5)-a)+c.charCodeAt(0)|0,0)) % (10**12);
        }
        const body = {
          external_id: Number(eid),
          external_mbid: mbid || null,
          title: item.title || item.album || item.name,
          artist: item.artist || item.artist_name || null,
          year: item.year || null,
          monitored: true,
          search_now: true,
        };
        const res = await api.music.add(body);
        if (res && res.ok === false) throw new Error('Add failed');
        if (res && res.status && res.status >= 400) {
          const err = await res.json().catch(()=>({}));
          throw new Error(err.detail || res.statusText || 'Add failed');
        }
        setMsg('Added album: ' + body.title);
      } else {
        await api.tv.add(ext);
        refreshSeries && await refreshSeries();
      }
      if (tab !== 'music') setMsg('Added ' + (item.title || item.name));
    } catch (e) { setMsg(String(e.message||e)); }
    setBusy(null);
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="mr-page-title">Discover</h1>
          <p className="text-sm opacity-50">Browse   genres   networks   search — Overseerr-style</p>
        </div>
        <div className="tabs tabs-boxed">
          <a className={'tab '+(mode==='browse'?'tab-active':'')} onClick={()=>setMode('browse')}>Browse</a>
          <a className={'tab '+(mode==='search'?'tab-active':'')} onClick={()=>setMode('search')}>Search</a>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 items-center">
        <div className="tabs tabs-boxed tabs-sm">
          <a className={'tab '+(tab==='movie'?'tab-active':'')} onClick={()=>setTab('movie')}>Movies</a>
          <a className={'tab '+(tab==='tv'?'tab-active':'')} onClick={()=>setTab('tv')}>TV</a>
          {(enabledModules||[]).includes('adult') && <a className={'tab '+(tab==='adult'?'tab-active':'')} onClick={()=>setTab('adult')}>Adult</a>}
          <a className={'tab '+(tab==='music'?'tab-active':'')} onClick={()=>{setTab('music'); setKind('popular');}}>Music</a>
        </div>
        {tab==='music' && mode==='browse' && (
          <div className="flex flex-wrap gap-2 items-center mb-3">
            <select className="select select-bordered select-xs" value={musicTag} onChange={e=>setMusicTag(e.target.value)}>
              <option value="">All genres</option>
              {musicTags.map(t=><option key={t} value={t}>{t}</option>)}
            </select>
            <input className="input input-bordered input-xs w-24" type="number" placeholder="Year" value={musicYear}
              onChange={e=>setMusicYear(e.target.value)} min="1950" max="2100" />
            {(musicTag || musicYear) && (
              <button type="button" className="btn btn-ghost btn-xs" onClick={()=>{setMusicTag(''); setMusicYear('');}}>Clear</button>
            )}
          </div>
        )}
        {mode==='browse' && !genreId && !(tab==='tv'&&network) && !year && kinds.map(([k,label])=>(
          <button type="button" key={k} className={'btn btn-xs '+(kind===k?'btn-primary':'btn-ghost')} onClick={()=>setKind(k)}>{label}</button>
        ))}
        {mode==='search' && (
          <input className="input input-bordered input-sm w-56" placeholder="Search title…" value={q} onChange={e=>setQ(e.target.value)} />
        )}
        {tab==='movie' && (
          <select className="select select-bordered select-xs" value={profile} onChange={e=>setProfile(e.target.value)}>
            <option value="">Default profile</option>
            {movieProfiles.map(p=><option key={p.id} value={p.name}>{p.name}</option>)}
          </select>
        )}
      </div>

      {/* Filter chips */}
      {mode==='browse' && (
        <div className="space-y-2">
          <div className="flex flex-wrap gap-1.5 items-center">
            <span className="text-[10px] uppercase opacity-40 font-semibold mr-1">Genres</span>
            <button type="button" className={'btn btn-xs '+(genreId===''?'btn-primary':'btn-ghost')} onClick={()=>setGenreId('')}>All</button>
            {genres.slice(0, 18).map(g=>(
              <button type="button" key={g.id} className={'btn btn-xs '+(String(genreId)===String(g.id)?'btn-primary':'btn-ghost')}
                onClick={()=>setGenreId(String(g.id))}>{g.name}</button>
            ))}
          </div>
          {tab==='movie' && (
            <div className="flex flex-wrap gap-1.5 items-center">
              <span className="text-[10px] uppercase opacity-40 font-semibold mr-1">Year</span>
              {['', '2026','2025','2024','2023','2022','2020','2015'].map(y=>(
                <button type="button" key={y||'any'} className={'btn btn-xs '+(year===y?'btn-primary':'btn-ghost')} onClick={()=>setYear(y)}>{y||'Any'}</button>
              ))}
            </div>
          )}
          <div className="flex flex-wrap gap-1.5 items-center">
            <span className="text-[10px] uppercase opacity-40 font-semibold mr-1">Min score</span>
            {[['','Any'],['6','6+'],['7','7+'],['8','8+']].map(([id,label])=>(
              <button type="button" key={id||'any'} className={'btn btn-xs '+(minScore===id?'btn-primary':'btn-ghost')} onClick={()=>setMinScore(id)}>{label}</button>
            ))}
          </div>
          <div className="flex flex-wrap gap-1.5 items-center">
            <span className="text-[10px] uppercase opacity-40 font-semibold mr-1">Language</span>
            {[['','Any'],['en','EN'],['ja','JA'],['ko','KO'],['zh','ZH'],['es','ES'],['fr','FR'],['de','DE']].map(([id,label])=>(
              <button type="button" key={id||'any'} className={'btn btn-xs '+(lang===id?'btn-primary':'btn-ghost')} onClick={()=>setLang(id)}>{label}</button>
            ))}
          </div>
          {tab==='tv' && (
            <div className="flex flex-wrap gap-1.5 items-center">
              <span className="text-[10px] uppercase opacity-40 font-semibold mr-1">Network</span>
              {networks.map(n=>(
                <button type="button" key={n.id||'any'} className={'btn btn-xs '+(network===n.id?'btn-primary':'btn-ghost')}
                  onClick={()=>setNetwork(n.id)}>{n.label}</button>
              ))}
            </div>
          )}
        </div>
      )}

      {msg && <p className="text-xs opacity-60">{msg}</p>}
      {loading ? <div className="flex justify-center py-16"><span className="loading loading-spinner loading-lg text-primary"/></div> : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
          {items.map(item=>{
            const ext = item.external_id || item.tmdb_id || item.id;
            const title = item.title || item.name;
            const poster = item.poster_path;
            const libItem = libMap[ext] || libMap[String(ext)] || null;
            const chips = libraryStatuses(libItem, { isTv: tab==='tv' });
            const inLib = !!libItem;
            const ring = ringClassFromChips(chips);
            return (
              <div key={ext} className="mr-tile group">
                <div className="art">
                  {poster ? <img src={poster.startsWith('http')?poster:TMDB+poster} alt="" loading="lazy"/> :
                    <div className="w-full h-full flex items-center justify-center text-xs opacity-30 p-2 text-center">{title}</div>}
                  <StatusBadgeStack chips={chips} />
                </div>
                <div className="meta">
                  <div className="title">{title}</div>
                  <div className="badges">
                    <span className="text-[10px] opacity-50">{item.year || (item.release_date||item.first_air_date||'').slice(0,4)}</span>
                  </div>
                  <button type="button" className="btn btn-primary btn-xs w-full mt-2" disabled={!!busy||inLib} onClick={()=>addItem(item)}>
                    {inLib?'In library':busy===ext?'…':'Add'}
                  </button>
                </div>
              </div>
            );
          })}
          {!items.length && <p className="text-sm opacity-40 col-span-full">No results</p>}
        </div>
      )}
      <LibraryLegend showTv={tab==='tv'} showSeries={false} />
    
      {tab==='adult' && (enabledModules||[]).includes('adult') && (
        <div className="space-y-4">
          <form onSubmit={searchAdultDiscover} className="flex flex-wrap gap-2">
            <input className="input input-bordered input-sm flex-1 min-w-[12rem]" placeholder="Search adult metadata (TPDB)…"
              value={adultQ} onChange={e=>setAdultQ(e.target.value)} />
            <button type="submit" className="btn btn-primary btn-sm" disabled={adultBusy||!adultQ.trim()}>Search</button>
          </form>
          {adultMsg && <div className="alert alert-info text-xs py-2">{adultMsg}</div>}
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {(adultResults||[]).map((r,i)=>(
              <div key={r.external_id||i} className="card bg-base-200 border border-base-content/10">
                <div className="card-body p-3 flex-row gap-3">
                  {r.poster_path ? <img src={r.poster_path} alt="" className="w-16 h-24 object-cover rounded" /> :
                    <div className="w-16 h-24 bg-base-300 rounded" />}
                  <div className="min-w-0 flex-1">
                    <div className="font-medium text-sm truncate">{r.title}</div>
                    <div className="text-xs opacity-50">{[r.year||'—', r.site].filter(Boolean).join(' · ')}</div>
                    <button type="button" className="btn btn-xs btn-primary mt-2" disabled={adultBusy}
                      onClick={()=>addAdultFromDiscover(r)}>Add to library</button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

</div>
  );
}




export { DiscoverPage };
