/* LEGACY CDN UI — prefer the Vite build in app/static/assets/ (index.html).
 * This file is kept for zero-build / index.cdn.html only and may lag features.
 * Do not add new features here; edit ui/src/app.jsx and rebuild.
 */
const { useState, useEffect, useCallback, useRef } = React;

/* ── Themes (exact list from MediaOs) ──────────────────────────────────── */
const THEMES = [
  'light','dark','cupcake','bumblebee','emerald','corporate','synthwave',
  'retro','cyberpunk','valentine','halloween','garden','forest','aqua',
  'lofi','pastel','fantasy','wireframe','black','luxury','dracula','cmyk',
  'autumn','business','acid','lemonade','night','coffee','winter','dim',
  'nord','sunset','caramellatte','abyss','silk'
];

function applyTheme(t) {
  document.documentElement.setAttribute('data-theme', t);
  localStorage.setItem('mediaos-theme', t);
}
function storedTheme() {
  return localStorage.getItem('mediaos-theme') || 'dark';
}

/* ── Icons (inline SVG, Lucide style) ───────────────────────────────────── */
const P = { viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', strokeWidth:'1.6', strokeLinecap:'round', strokeLinejoin:'round' };
const Ic = {
  Home:       ()=><svg {...P}><path d="M3 9.5L12 3l9 6.5V20a1 1 0 01-1 1H4a1 1 0 01-1-1z"/><path d="M9 21V12h6v9"/></svg>,
  Compass:    ()=><svg {...P}><circle cx="12" cy="12" r="10"/><path d="M16.24 7.76l-2.12 6.36-6.36 2.12 2.12-6.36 6.36-2.12z"/></svg>,
  Library:    ()=><svg {...P}><path d="M2 3h6a4 4 0 014 4v14a3 3 0 00-3-3H2z"/><path d="M22 3h-6a4 4 0 00-4 4v14a3 3 0 013-3h7z"/></svg>,
  Film:       ()=><svg {...P}><rect x="2" y="2" width="20" height="20" rx="2"/><path d="M7 2v20M17 2v20M2 12h20M2 7h5M17 7h5M2 17h5M17 17h5"/></svg>,
  Tv:         ()=><svg {...P}><rect x="2" y="7" width="20" height="15" rx="2"/><path d="M17 2l-5 5-5-5"/></svg>,
  Music:      ()=><svg {...P}><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>,
  Book:       ()=><svg {...P}><path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/></svg>,
  Headphones: ()=><svg {...P}><path d="M3 18v-6a9 9 0 0118 0v6"/><path d="M21 19a2 2 0 01-2 2h-1a2 2 0 01-2-2v-3a2 2 0 012-2h3z"/><path d="M3 19a2 2 0 002 2h1a2 2 0 002-2v-3a2 2 0 00-2-2H3z"/></svg>,
  Activity:   ()=><svg {...P}><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>,
  Calendar:   ()=><svg {...P}><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>,
  Radio:      ()=><svg {...P}><path d="M4.9 19.1C1 15.2 1 8.8 4.9 4.9"/><path d="M7.8 16.2c-2.3-2.3-2.3-6.1 0-8.5"/><circle cx="12" cy="12" r="2"/><path d="M16.2 7.8c2.3 2.3 2.3 6.1 0 8.5"/><path d="M19.1 4.9C23 8.8 23 15.2 19.1 19.1"/></svg>,
  List:       ()=><svg {...P}><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>,
  Shield:     ()=><svg {...P}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>,
  Settings:   ()=><svg {...P}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>,
  Palette:    ()=><svg {...P}><circle cx="13.5" cy="6.5" r=".5"/><circle cx="17.5" cy="10.5" r=".5"/><circle cx="8.5" cy="7.5" r=".5"/><circle cx="6.5" cy="12.5" r=".5"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 011.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z"/></svg>,
  Puzzle:     ()=><svg {...P}><path d="M20.59 13.41l-7.17 7.17a2 2 0 01-2.83 0L2 12V2h10l8.59 8.59a2 2 0 010 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>,
  Download:   ()=><svg {...P}><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>,
  Server:     ()=><svg {...P}><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/></svg>,
  Folder:     ()=><svg {...P}><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/></svg>,
  Eye:        ()=><svg {...P}><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>,
  EyeOff:     ()=><svg {...P}><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>,
  Trash:      ()=><svg {...P}><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a1 1 0 011-1h4a1 1 0 011 1v2"/></svg>,
  Plus:       ()=><svg {...P}><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>,
  Search:     ()=><svg {...P}><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>,
  Refresh:    ()=><svg {...P}><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 102.13-9.36L1 10"/></svg>,
  X:          ()=><svg {...P}><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>,
  Menu:       ()=><svg {...P}><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>,
  ChevDown:   ()=><svg {...P}><polyline points="6 9 12 15 18 9"/></svg>,
  ChevRight:  ()=><svg {...P}><polyline points="9 18 15 12 9 6"/></svg>,
  HardDrive:  ()=><svg {...P}><line x1="22" y1="12" x2="2" y2="12"/><path d="M5.45 5.11L2 12v6a2 2 0 002 2h16a2 2 0 002-2v-6l-3.45-6.89A2 2 0 0016.76 4H7.24a2 2 0 00-1.79 1.11z"/><line x1="6" y1="16" x2="6.01" y2="16"/><line x1="10" y1="16" x2="10.01" y2="16"/></svg>,
  Check:      ()=><svg {...P}><polyline points="20 6 9 17 4 12"/></svg>,
  Inbox:      ()=><svg {...P}><polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11L2 12v6a2 2 0 002 2h16a2 2 0 002-2v-6l-3.45-6.89A2 2 0 0016.76 4H7.24a2 2 0 00-1.79 1.11z"/></svg>,
  AlertTri:   ()=><svg {...P}><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>,
  Loader:     ()=><svg {...P} className="animate-spin"><line x1="12" y1="2" x2="12" y2="6"/><line x1="12" y1="18" x2="12" y2="22"/><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"/><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"/><line x1="2" y1="12" x2="6" y2="12"/><line x1="18" y1="12" x2="22" y2="12"/><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"/><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"/></svg>,
};

/* ── Auth token (Bearer) ─────────────────────────────────────────────────── */
const AUTH_TOKEN_KEY = 'mediaos_token';
function getToken() { try { return localStorage.getItem(AUTH_TOKEN_KEY); } catch { return null; } }
function setToken(t) { try { if (t) localStorage.setItem(AUTH_TOKEN_KEY, t); else localStorage.removeItem(AUTH_TOKEN_KEY); } catch {} }
const _fetch = window.fetch.bind(window);
window.fetch = (input, init={}) => {
  const headers = new Headers(init.headers || {});
  const tok = getToken();
  if (tok && !headers.has('Authorization')) headers.set('Authorization', 'Bearer ' + tok);
  return _fetch(input, { ...init, headers }).then(async r => {
    if (r.status === 401 && !String(input).includes('/api/auth/')) {
      // soft prompt once
      if (!window.__mediaos_auth_prompted) {
        window.__mediaos_auth_prompted = true;
        const u = prompt('Username (mediaos auth)');
        const p = prompt('Password');
        if (u != null) {
          try {
            const res = await _fetch('/api/auth/login', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({username:u, password:p||''}) });
            const j = await res.json();
            if (j.token) { setToken(j.token); return _fetch(input, { ...init, headers: new Headers({ ...(init.headers||{}), Authorization: 'Bearer '+j.token }) }); }
          } catch {}
        }
      }
    }
    return r;
  });
};

/* ── API ─────────────────────────────────────────────────────────────────── */
const api = {
  movies:    { list: ()=>fetch('/api/movies').then(r=>r.json()),
               search: q=>fetch(`/api/movies/search?query=${encodeURIComponent(q)}`).then(r=>r.json()),
               add: (id, opts={})=>fetch('/api/movies',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({external_id:id, ...opts})}),
               update: (id,body)=>fetch(`/api/movies/${id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(typeof body==='boolean'?{monitored:body}:body)}),
               searchNow: id=>fetch(`/api/movies/${id}/search`,{method:'POST'}),
               subtitles: id=>fetch(`/api/movies/${id}/subtitles`,{method:'POST'}).then(r=>r.json()),
               remove: id=>fetch(`/api/movies/${id}`,{method:'DELETE'}) },
  tv:        { list: ()=>fetch('/api/tv').then(r=>r.json()),
               search: q=>fetch(`/api/tv/search?query=${encodeURIComponent(q)}`).then(r=>r.json()),
               add: (id, opts={})=>fetch('/api/tv',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({external_id:id, monitor: opts.monitor||'all', quality_profile: opts.quality_profile||null, search_missing: opts.search_missing!==false})}),
               remove: id=>fetch(`/api/tv/${id}`,{method:'DELETE'}),
               searchMissing: id=>fetch(`/api/tv/${id}/search-missing`,{method:'POST'}).then(r=>r.json()),
               searchSeason: (id,s)=>fetch(`/api/tv/${id}/search-season/${s}`,{method:'POST'}).then(r=>r.json()),
               refresh: id=>fetch(`/api/tv/${id}/refresh`,{method:'POST'}).then(r=>r.json()),
               episodes: id=>fetch(`/api/tv/${id}/episodes`).then(r=>r.json()) },
  import:    { scan: ()=>fetch('/api/import/scan').then(r=>r.json()),
               movie: body=>fetch('/api/import/movie',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(async r=>{ if(!r.ok) throw new Error((await r.json()).detail||r.statusText); return r.json(); }),
               episode: body=>fetch('/api/import/episode',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(async r=>{ if(!r.ok) throw new Error((await r.json()).detail||r.statusText); return r.json(); }) },
  settings:  { profiles: ()=>fetch('/api/settings/profiles').then(r=>r.json()),
               profile: id=>fetch(`/api/settings/profiles/${id}`).then(r=>r.json()),
               saveProfile: (id,body)=>fetch(id?`/api/settings/profiles/${id}`:'/api/settings/profiles',{method:id?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(async r=>{ if(!r.ok) throw new Error((await r.json()).detail||r.statusText); return r.json(); }),
               deleteProfile: id=>fetch(`/api/settings/profiles/${id}`,{method:'DELETE'}),
               setDefaultProfile: id=>fetch(`/api/settings/profiles/${id}/set-default`,{method:'POST'}).then(r=>r.json()),
               score: title=>fetch('/api/quality/score',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title})}).then(r=>r.json()),
               movies: ()=>fetch('/api/settings/movies').then(r=>r.json()),
               vpn: ()=>fetch('/api/settings/vpn').then(r=>r.json()),
               vpnStatus: ()=>fetch('/api/settings/vpn/status').then(r=>r.json()),
               getConfig: group=>fetch(`/api/settings/config/${group}`).then(r=>r.json()),
               saveConfig: (group,body)=>fetch(`/api/settings/config/${group}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(async r=>{ if(!r.ok) throw new Error((await r.json()).detail||r.statusText); return r.json(); }) },
  activity:  { list: ()=>fetch('/api/activity?limit=100').then(r=>r.json()) },
  parity:    { status: ()=>fetch('/api/parity/status').then(r=>r.json()),
               workers: ()=>fetch('/api/parity/workers').then(r=>r.json()),
               traktMovies: ()=>fetch('/api/parity/trakt/trending/movies').then(r=>r.json()),
               searchAllJob: ()=>fetch('/api/parity/workers/search-all',{method:'POST'}).then(r=>r.json()) },
  setup:     { status: ()=>fetch('/api/setup/status').then(r=>r.json()),
               complete: body=>fetch('/api/setup/complete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json()) },
  wanted:    { list: (mt)=>fetch(`/api/wanted${mt?`?media_type=${mt}`:''}`).then(r=>r.json()),
               searchMovie: id=>fetch(`/api/wanted/movies/${id}/search`,{method:'POST'}).then(r=>r.json()),
               searchEpisode: id=>fetch(`/api/wanted/episodes/${id}/search`,{method:'POST'}).then(r=>r.json()),
               searchMusic: id=>fetch(`/api/wanted/music/${id}/search`,{method:'POST'}).then(r=>r.json()),
               searchBook: id=>fetch(`/api/wanted/books/${id}/search`,{method:'POST'}).then(r=>r.json()),
               searchAudiobook: id=>fetch(`/api/wanted/audiobooks/${id}/search`,{method:'POST'}).then(r=>r.json()),
               searchAll: (mt,limit=40)=>fetch(`/api/wanted/search-all?limit=${limit}${mt&&mt!=='all'?`&media_type=${mt}`:''}`,{method:'POST'}).then(r=>r.json()) },
  queue:     { list: ()=>fetch('/api/queue').then(r=>r.json()),
               history: ()=>fetch('/api/queue/history').then(r=>r.json()),
               remove: id=>fetch(`/api/queue/${id}`,{method:'DELETE'}) },
  indexers:  { list: ()=>fetch('/api/indexers').then(r=>r.json()),
               add: body=>fetch('/api/indexers',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json()),
               remove: id=>fetch(`/api/indexers/${id}`,{method:'DELETE'}),
               test: id=>fetch(`/api/indexers/${id}/test`,{method:'POST'}).then(r=>r.json()) },
  system:    { searchAllMissing: ()=>fetch('/api/search-all-missing',{method:'POST'}).then(r=>r.json()) },
  livetv:    { sources: ()=>fetch('/api/livetv/sources').then(r=>r.json()),
               addSource: body=>fetch('/api/livetv/sources',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json()),
               sync: id=>fetch(`/api/livetv/sources/${id}/sync`,{method:'POST'}).then(r=>r.json()),
               channels: (q='')=>fetch(`/api/livetv/channels?q=${encodeURIComponent(q)}&limit=300`).then(r=>r.json()),
               groups: ()=>fetch('/api/livetv/groups').then(r=>r.json()) },
  audiobooks:{ list: ()=>fetch('/api/audiobooks').then(r=>r.json()),
               search: q=>fetch(`/api/audiobooks/search?query=${encodeURIComponent(q)}`).then(r=>r.json()),
               add: body=>fetch('/api/audiobooks',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),
               remove: id=>fetch(`/api/audiobooks/${id}`,{method:'DELETE'}),
               searchNow: id=>fetch(`/api/audiobooks/${id}/search`,{method:'POST'}).then(r=>r.json()) },
  calendar:  { list: (start,end)=>fetch(`/api/calendar?start=${start||''}&end=${end||''}`).then(r=>r.json()) },
  smartlists:{ list: ()=>fetch('/api/smartlists').then(r=>r.json()),
               add: body=>fetch('/api/smartlists',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json()),
               remove: id=>fetch(`/api/smartlists/${id}`,{method:'DELETE'}),
               run: id=>fetch(`/api/smartlists/${id}/run`,{method:'POST'}).then(r=>r.json()),
               runAll: ()=>fetch('/api/smartlists/run-all',{method:'POST'}).then(r=>r.json()) },
  books:     { list: ()=>fetch('/api/books').then(r=>r.json()),
               search: q=>fetch(`/api/books/search?query=${encodeURIComponent(q)}`).then(r=>r.json()),
               add: body=>fetch('/api/books',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),
               remove: id=>fetch(`/api/books/${id}`,{method:'DELETE'}) },
  requests:  { list: (status)=>fetch(`/api/requests${status?`?status=${status}`:''}`).then(r=>r.json()),
               create: body=>fetch('/api/requests',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(async r=>{ if(!r.ok) throw new Error((await r.json()).detail||r.statusText); return r.json(); }),
               approve: (id,quality_profile)=>fetch(`/api/requests/${id}/approve`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({quality_profile:quality_profile||null})}).then(r=>r.json()),
               deny: (id,reason)=>fetch(`/api/requests/${id}/deny`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({reason:reason||null})}).then(r=>r.json()),
               cancel: id=>fetch(`/api/requests/${id}`,{method:'DELETE'}) },
  discover:  { movies: (kind='popular')=>fetch(`/api/discover/movies?kind=${kind}`).then(r=>r.json()),
               tv: (kind='popular')=>fetch(`/api/discover/tv?kind=${kind}`).then(r=>r.json()) },
  music:     { list: ()=>fetch('/api/music').then(r=>r.json()),
               artists: ()=>fetch('/api/music/artists').then(r=>r.json()),
               searchArtist: q=>fetch(`/api/music/mb/artist-search?query=${encodeURIComponent(q)}`).then(r=>r.json()),
               artistAlbums: mbid=>fetch(`/api/music/mb/artist/${mbid}/albums`).then(r=>r.json()),
               addArtistMbid: (mbid, name)=>fetch(`/api/music/add-artist-mbid?mbid=${encodeURIComponent(mbid)}&artist_name=${encodeURIComponent(name||'')}&limit=50`,{method:'POST'}).then(r=>r.json()),
               scanPaths: ()=>fetch('/api/music/scan-paths',{method:'POST'}).then(r=>r.json()),
               tracks: mbid=>fetch(`/api/music/mb/release-group/${mbid}/tracks`).then(r=>r.json()),
               search: q=>fetch(`/api/music/search?query=${encodeURIComponent(q)}`).then(r=>r.json()),
               add: body=>fetch('/api/music',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),
               searchNow: id=>fetch(`/api/music/${id}/search`,{method:'POST'}),
               remove: id=>fetch(`/api/music/${id}`,{method:'DELETE'}),
               addArtist: (artist,limit=30)=>fetch(`/api/music/add-artist?artist=${encodeURIComponent(artist)}&limit=${limit}`,{method:'POST'}).then(r=>r.json()) },
};

const TMDB = 'https://image.tmdb.org/t/p/w342';


function CollectionProgressWidget({ setPage }) {
  const [rows, setRows] = useState([]);
  useEffect(()=>{ fetch('/api/collections/dashboard/summary').then(r=>r.ok?r.json():[]).then(setRows).catch(()=>{}); }, []);
  if (!rows.length) return null;
  return (
    <div className="card bg-base-200 shadow-sm mt-4">
      <div className="card-body p-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-semibold text-sm uppercase tracking-wide opacity-70">Saga Progress</h3>
          <button className="btn btn-ghost btn-xs" onClick={()=>setPage && setPage('collections')}>View all</button>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {rows.slice(0,6).map(c=>(
            <div key={c.id} className="flex items-center gap-3 p-2 rounded-lg bg-base-300/40">
              {c.poster_path ? <img src={c.poster_path.startsWith('http')?c.poster_path:`https://image.tmdb.org/t/p/w92${c.poster_path}`} className="w-10 h-14 object-cover rounded" alt=""/> : <div className="w-10 h-14 bg-base-300 rounded"/>}
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">{c.name}</div>
                <div className="text-xs opacity-60">{c.progress_label}</div>
                <progress className="progress progress-primary h-1 w-full mt-1" value={c.pct} max="100"/>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
function ComicsPage() {
  const [items, setItems] = useState([]); const [q, setQ] = useState(''); const [results, setResults] = useState([]);
  const load = ()=>fetch('/api/comics').then(r=>r.json()).then(setItems).catch(()=>{});
  useEffect(()=>{ load(); }, []);
  const search = ()=>fetch('/api/comics/search?query='+encodeURIComponent(q)).then(r=>r.json()).then(setResults).catch(()=>{});
  const add = async (r)=>{ await fetch('/api/comics', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({external_id:r.external_id, title:r.title, year:r.year, overview:r.overview, poster_path:r.poster_path, external_source:r.external_source||'comicvine', media_kind:r.media_kind==='manga'?'manga':'comic', artist_name:r.publisher||r.author})}); load(); setResults([]); };
  return (<div className="p-4 space-y-4"><h1 className="text-2xl font-bold">Comics / Manga</h1><div className="flex gap-2"><input className="input input-bordered input-sm flex-1" placeholder="Search ComicVine / MangaDex" value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>e.key==='Enter'&&search()}/><button className="btn btn-sm btn-primary" onClick={search}>Search</button></div>{results.length>0 && <div className="grid gap-2 sm:grid-cols-2">{results.map((r,i)=>(<div key={i} className="flex gap-3 p-2 bg-base-200 rounded items-center">{r.poster_path&&<img src={r.poster_path} className="w-12 h-16 object-cover rounded" alt=""/>}<div className="flex-1 min-w-0"><div className="font-medium truncate">{r.title}</div><div className="text-xs opacity-60">{r.media_kind} · {r.external_source}</div></div><button className="btn btn-xs btn-primary" onClick={()=>add(r)}>Add</button></div>))}</div>}<div className="grid gap-2">{items.map(it=>(<div key={it.id} className="flex justify-between p-2 bg-base-200 rounded"><span>{it.title} <span className="badge badge-sm">{it.media_type}</span></span><span className="text-xs opacity-60">{it.status}</span></div>))}</div></div>);
}
function YouTubePage() {
  const [channels, setChannels] = useState([]); const [q, setQ] = useState('');
  const load = ()=>fetch('/api/youtube').then(r=>r.json()).then(setChannels).catch(()=>{});
  useEffect(()=>{ load(); }, []);
  const add = async ()=>{ await fetch('/api/youtube', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({query:q})}); setQ(''); load(); };
  return (<div className="p-4 space-y-4"><h1 className="text-2xl font-bold">YouTube / Creators</h1><div className="flex gap-2"><input className="input input-bordered input-sm flex-1" placeholder="@handle or channel URL" value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>e.key==='Enter'&&add()}/><button className="btn btn-sm btn-primary" onClick={add}>Subscribe</button></div><div className="grid gap-2">{channels.map(c=>(<div key={c.id} className="flex justify-between p-3 bg-base-200 rounded"><div><div className="font-medium">{c.title}</div><div className="text-xs opacity-60">{c.video_count} in feed</div></div><button className="btn btn-xs" onClick={()=>fetch('/api/youtube/'+c.id+'/refresh',{method:'POST'}).then(load)}>Refresh</button></div>))}</div></div>);
}
function CollectionsPage() {
  const [rows, setRows] = useState([]); const [q, setQ] = useState(''); const [results, setResults] = useState([]);
  const load = ()=>fetch('/api/collections').then(r=>r.json()).then(setRows).catch(()=>{});
  useEffect(()=>{ load(); }, []);
  const search = ()=>fetch('/api/collections/search?query='+encodeURIComponent(q)).then(r=>r.json()).then(setResults).catch(()=>{});
  const add = async (r)=>{ await fetch('/api/collections', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({tmdb_id:r.id||r.tmdb_id, add_all:true})}); load(); setResults([]); };
  return (<div className="p-4 space-y-4"><h1 className="text-2xl font-bold">Movie Collections</h1><div className="flex gap-2"><input className="input input-bordered input-sm flex-1" value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>e.key==='Enter'&&search()}/><button className="btn btn-sm btn-primary" onClick={search}>Search</button></div>{results.length>0 && <div className="grid gap-2">{results.map((r,i)=>(<div key={i} className="flex justify-between p-2 bg-base-200 rounded"><span>{r.name||r.title}</span><button className="btn btn-xs btn-primary" onClick={()=>add(r)}>Track</button></div>))}</div>}<div className="grid gap-3 sm:grid-cols-2">{rows.map(c=>(<div key={c.id} className="p-3 bg-base-200 rounded"><div className="font-medium">{c.name}</div><div className="text-xs opacity-60">{c.progress_label}</div><progress className="progress progress-primary h-2 w-full" value={c.total_parts?Math.round(100*c.owned/c.total_parts):0} max="100"/></div>))}</div></div>);
}
function PodcastsPage() {
  const [items, setItems] = useState([]); const [q, setQ] = useState(''); const [results, setResults] = useState([]);
  const load = ()=>fetch('/api/podcasts').then(r=>r.json()).then(setItems).catch(()=>{});
  useEffect(()=>{ load(); }, []);
  const search = ()=>fetch('/api/podcasts/search?query='+encodeURIComponent(q)).then(r=>r.json()).then(setResults).catch(()=>{});
  const add = async (r)=>{ await fetch('/api/podcasts', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({feed_url:r.feed_url})}); load(); setResults([]); };
  return (<div className="p-4 space-y-4"><h1 className="text-2xl font-bold">Podcasts</h1><div className="flex gap-2"><input className="input input-bordered input-sm flex-1" value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>e.key==='Enter'&&search()}/><button className="btn btn-sm btn-primary" onClick={search}>Search</button></div>{results.length>0 && <div className="grid gap-2">{results.map((r,i)=>(<div key={i} className="flex justify-between p-2 bg-base-200 rounded"><span>{r.title}</span><button className="btn btn-xs btn-primary" onClick={()=>add(r)}>Subscribe</button></div>))}</div>}<div className="grid gap-2">{items.map(it=>(<div key={it.id} className="flex justify-between p-2 bg-base-200 rounded"><span>{it.title}</span><span className="text-xs opacity-60">{it.episode_count} eps</span></div>))}</div></div>);
}

/* ── Sidebar ─────────────────────────────────────────────────────────────── */
function Sidebar({ page, setPage, counts, onClose }) {
  const [open, setOpen] = useState(() => {
    if (['movies','tv','music','books','audiobooks'].includes(page)) return 'library';
    if (page.startsWith('settings')) return 'settings';
    return null;
  });

  const NAV = [
    { key:'dashboard', label:'Home', Icon:Ic.Home },
    { key:'discover',  label:'Discover', Icon:Ic.Compass },
    { key:'requests',  label:'Requests', Icon:Ic.Inbox, count:counts.requests||undefined },
    { key:'library', label:'Library', Icon:Ic.Library,
      children:[
        { key:'movies',      label:'Movies',      Icon:Ic.Film,       count:counts.movies },
        { key:'tv',          label:'TV Shows',     Icon:Ic.Tv,         count:counts.tv },
        { key:'music',       label:'Music',        Icon:Ic.Music,      count:counts.music },
        { key:'books',       label:'Books',        Icon:Ic.Book },
        { key:'audiobooks',  label:'Audiobooks',   Icon:Ic.Headphones },
        { key:'comics',      label:'Comics/Manga', Icon:Ic.Book },
        { key:'podcasts',    label:'Podcasts',     Icon:Ic.Radio },
        { key:'youtube',     label:'YouTube',      Icon:Ic.Compass },
        { key:'collections', label:'Collections',  Icon:Ic.Film },
      ]},
    { key:'import',     label:'Import',      Icon:Ic.Folder },
    { key:'wanted',     label:'Wanted',      Icon:Ic.AlertTri },
    { key:'queue',      label:'Queue',       Icon:Ic.Download },
    { key:'activity',   label:'Activity',    Icon:Ic.Activity },
    { key:'workers',    label:'Workers',     Icon:Ic.Activity },
    { key:'calendar',   label:'Calendar',    Icon:Ic.Calendar },
    { key:'livetv',     label:'Live TV / IPTV',     Icon:Ic.Radio },
    { key:'smartlists', label:'Smart Lists', Icon:Ic.List },
    { key:'quality-lab', label:'Quality Lab', Icon:Ic.Puzzle },
    { key:'parity', label:'Parity', Icon:Ic.Puzzle },
    { key:'settings', label:'Settings', Icon:Ic.Settings,
      children:[
        { key:'settings-indexers',   label:'Indexers',          Icon:Ic.Puzzle },
        { key:'settings-downloads',  label:'Download Clients',  Icon:Ic.Download },
        { key:'settings-library',    label:'Library Storage',   Icon:Ic.Folder },
        { key:'settings-themes',     label:'Themes',            Icon:Ic.Palette },
        { key:'settings-quality',    label:'Quality Profiles',  Icon:Ic.Puzzle },
        { key:'settings-vpn',        label:'VPN',               Icon:Ic.Shield },
        { key:'settings-system',     label:'System',            Icon:Ic.Server },
        { key:'settings-integrations', label:'Integrations',     Icon:Ic.Puzzle },
      ]},
  ];

  const isActive = k => page === k;
  const isParentActive = item => item.children?.some(c => c.key === page);

  function go(k, close=true) {
    setPage(k);
    if (close && onClose) onClose();
  }

  return (
    <aside className="mr-sidebar flex flex-col h-full w-64">
      <div className="mr-brand">
        <div className="mr-brand-mark"><img src="/logo-icon.png" alt="MediaOs" width="28" height="28" className="logo-mark" style={{width:28,height:28,objectFit:"contain"}} draggable={false} /></div>
        <div>
          <div className="mr-brand-title">mediaos</div>
          <div className="text-[10px] opacity-40 tracking-wide uppercase">media automation</div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto py-2">
        <ul className="menu menu-sm px-2 gap-0.5">
          {NAV.map(item => (
            <li key={item.key}>
              {item.children ? (<>
                <button
                  className={`flex items-center gap-3 w-full rounded-lg px-3 py-2 text-sm font-medium transition-colors text-left
                    ${(isParentActive(item)||open===item.key) ? 'bg-base-300 text-base-content font-semibold active-nav' : 'text-base-content/70 hover:bg-base-300 hover:text-base-content'}`}
                  onClick={()=>setOpen(open===item.key?null:item.key)}
                >
                  <span className="w-4 h-4 flex-shrink-0"><item.Icon /></span>
                  <span className="flex-1">{item.label}</span>
                  <span className={`w-3 h-3 transition-transform ${open===item.key?'rotate-180':''}`}><Ic.ChevDown /></span>
                </button>
                {open===item.key && (
                  <ul className="ml-3 mt-0.5 gap-0.5 flex flex-col border-l border-base-300 pl-2">
                    {item.children.map(c=>(
                      <li key={c.key}>
                        <button
                          disabled={!!c.soon}
                          className={`flex items-center gap-2.5 w-full rounded-lg px-2.5 py-1.5 text-sm transition-colors text-left
                            ${isActive(c.key) ? 'bg-base-300 text-base-content font-semibold active-nav' :
                              c.soon ? 'text-base-content/30 cursor-default' :
                              'text-base-content/70 hover:bg-base-300 hover:text-base-content'}`}
                          onClick={()=>!c.soon && go(c.key)}
                        >
                          {c.Icon && <span className="w-3.5 h-3.5 flex-shrink-0"><c.Icon /></span>}
                          <span className="flex-1">{c.label}</span>
                          {c.count !== undefined && <span className="badge badge-ghost badge-sm text-xs">{c.count}</span>}
                          {c.soon && <span className="badge badge-ghost badge-sm text-xs opacity-40">Soon</span>}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </>) : (
                <button
                  disabled={!!item.soon}
                  className={`flex items-center gap-3 w-full rounded-lg px-3 py-2 text-sm font-medium transition-colors text-left
                    ${isActive(item.key) ? 'bg-base-300 text-base-content font-semibold active-nav' :
                      item.soon ? 'text-base-content/30 cursor-default' :
                      'text-base-content/70 hover:bg-base-300 hover:text-base-content'}`}
                  onClick={()=>!item.soon && go(item.key)}
                >
                  <span className="w-4 h-4 flex-shrink-0"><item.Icon /></span>
                  <span className="flex-1">{item.label}</span>
                  {item.count !== undefined && <span className="badge badge-primary badge-sm text-xs">{item.count}</span>}
                  {item.soon && <span className="badge badge-ghost badge-sm text-xs opacity-40">Soon</span>}
                </button>
              )}
            </li>
          ))}
        </ul>
      </nav>

      <div className="border-t border-base-300 px-5 py-3">
        <div className="text-xs text-base-content/40 font-mono">mediaos v0.1.0</div>
        <div className="text-xs text-base-content/25">one shelf, every format</div>
      </div>
    </aside>
  );
}

/* ── Stats Grid (MediaOs DashboardStatsGrid pattern) ───────────────────── */
function StatsGrid({ movies, series, setPage }) {
  const downloaded = movies.filter(m=>m.status==='downloaded').length;
  const downloading = movies.filter(m=>m.status==='downloading').length +
    series.reduce((a,s)=>a+(s.episode_count-s.downloaded_count > 0 ? 1 : 0), 0);
  const totalEpisodes = series.reduce((a,s)=>a+s.episode_count, 0);
  const doneEpisodes = series.reduce((a,s)=>a+s.downloaded_count, 0);

  const stats = [
    { label:'Movies', value:movies.length, sub:`${downloaded} downloaded · ${downloading} grabbing`,
      Icon:Ic.Film, color:'bg-primary/10 text-primary', progress:movies.length>0?downloaded/movies.length:0,
      pc:'progress-primary', onClick:()=>setPage('movies') },
    { label:'TV Shows', value:series.length, sub:`${totalEpisodes} episodes · ${doneEpisodes} downloaded`,
      Icon:Ic.Tv, color:'bg-secondary/10 text-secondary', progress:totalEpisodes>0?doneEpisodes/totalEpisodes:0,
      pc:'progress-secondary', onClick:()=>setPage('tv') },
    { label:'Downloading', value:downloading, sub: downloading===0 ? 'Queue is empty' : 'Active grabs',
      Icon:Ic.Download, color:'bg-accent/10 text-accent', progress:0, pc:'progress-accent', onClick:()=>setPage('activity') },
    { label:'Music', value:0, sub:'Not yet tracked', Icon:Ic.Music, color:'bg-info/10 text-info', progress:0, pc:'progress-info', disabled:true },
    { label:'Books', value:0, sub:'Not yet tracked', Icon:Ic.Book, color:'bg-warning/10 text-warning', progress:0, pc:'progress-warning', disabled:true },
    { label:'Audiobooks', value:0, sub:'Not yet tracked', Icon:Ic.Headphones, color:'bg-success/10 text-success', progress:0, pc:'progress-success', disabled:true },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3">
      {stats.map((s,i)=>(
        <div key={i}
          className={`stat-tile ${s.onClick&&!s.disabled?'cursor-pointer':''}`}
          onClick={s.onClick && !s.disabled ? s.onClick : undefined}
        >
          <div className="card-body p-3 gap-1.5">
            <div className="flex items-center gap-2">
              <div className={`rounded-lg p-1.5 flex-shrink-0 ${s.color}`}><s.Icon /></div>
              <span className={`text-xl font-bold ${s.disabled?'text-base-content/30':''}`}>{s.value}</span>
              <span className={`text-sm ${s.disabled?'text-base-content/20':'text-base-content/60'}`}>{s.label}</span>
            </div>
            <div className={`text-xs truncate ${s.disabled?'text-base-content/25':'text-base-content/50'}`}>{s.sub}</div>
            {s.progress > 0
              ? <progress className={`progress ${s.pc} h-1`} value={s.progress*100} max="100" />
              : <div className="h-1" />}
          </div>
        </div>
      ))}
    </div>
  );
}

/* ── Add to Library Modal ────────────────────────────────────────────────── */
function AddModal({ type, existingIds, onClose, onAdded }) {
  const [q, setQ] = useState('');
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [addingId, setAddingId] = useState(null);

  useEffect(()=>{
    if (!q.trim()) { setResults([]); return; }
    setSearching(true);
    const h = setTimeout(async()=>{
      try {
        const r = await (type==='movie' ? api.movies.search(q) : api.tv.search(q));
        setResults(r||[]);
      } catch(e) { setResults([]); }
      setSearching(false);
    }, 350);
    return ()=>clearTimeout(h);
  }, [q, type]);

  async function handleAdd(item) {
    setAddingId(item.external_id);
    try {
      await (type==='movie' ? api.movies.add(item.external_id) : api.tv.add(item.external_id));
      await onAdded();
    } catch(e) {}
    setAddingId(null);
  }

  return (
    <div className="modal modal-open" onClick={onClose}>
      <div className="modal-box max-w-lg p-0 overflow-hidden" onClick={e=>e.stopPropagation()}>
        <div className="flex items-center gap-3 px-4 py-3 border-b border-base-300">
          <span className="w-4 h-4 text-base-content/50 flex-shrink-0"><Ic.Search /></span>
          <input autoFocus className="input input-sm flex-1 bg-transparent border-none shadow-none focus:outline-none text-sm"
            placeholder={`Search for a ${type==='movie'?'movie':'TV show'}…`}
            value={q} onChange={e=>setQ(e.target.value)} />
          <button className="btn btn-ghost btn-xs btn-square" onClick={onClose}><Ic.X /></button>
        </div>
        <div className="max-h-96 overflow-y-auto divide-y divide-base-300">
          {searching && <div className="p-6 text-center text-sm text-base-content/50">Searching…</div>}
          {!searching && q && !results.length && <div className="p-6 text-center text-sm text-base-content/50">No results found.</div>}
          {results.map(r=>{
            const already = existingIds.has(r.external_id);
            return (
              <div key={r.external_id} className="flex items-center gap-3 px-4 py-2.5 hover:bg-base-200">
                {r.poster_path
                  ? <img className="w-10 h-14 object-cover rounded flex-shrink-0 bg-base-300" src={TMDB+r.poster_path} alt="" />
                  : <div className="w-10 h-14 rounded bg-base-300 flex items-center justify-center text-base-content/30 font-bold text-lg flex-shrink-0">{r.title?.[0]}</div>}
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-sm truncate">{r.title}</div>
                  <div className="text-xs text-base-content/50 font-mono">{r.year||'—'}</div>
                </div>
                <button
                  className={`btn btn-sm btn-outline ${already?'btn-disabled':''}`}
                  disabled={already || addingId===r.external_id}
                  onClick={()=>!already && handleAdd(r)}
                >{already?'Added':addingId===r.external_id?'Adding…':'Add'}</button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/* ── Media Card (MediaOs LibraryMediaCard pattern) ─────────────────────── */
function MediaCard({ item, type, onSearchNow, onToggleMonitor, onDelete }) {
  const [busy, setBusy] = useState(false);
  const isMovie = type==='movie';
  const pct = !isMovie && item.episode_count>0 ? Math.round(item.downloaded_count/item.episode_count*100) : 0;

  async function doSearch(e) {
    e.preventDefault(); setBusy(true);
    try { await onSearchNow(item.id); } catch(e) {}
    setBusy(false);
  }

  return (
    <div className="media-card group relative aspect-poster cursor-pointer">
      {item.poster_path
        ? <img className="h-full w-full object-cover" src={TMDB+item.poster_path} alt={item.title} loading="lazy" />
        : <div className="h-full w-full flex items-center justify-center text-4xl font-bold text-base-content/20 font-mono">{item.title?.[0]}</div>}

      {/* Top-right: monitored badge */}
      <div className="absolute top-2 right-2 z-10 flex flex-col items-end gap-1">
        <div className={`badge badge-sm border-none shadow ${item.monitored?'bg-success/80 text-success-content':'bg-base-300/80 text-base-content/60'}`}>
          {item.monitored ? <Ic.Eye /> : <Ic.EyeOff />}
        </div>
        <div className={`badge badge-xs border-none font-semibold shadow ${isMovie?'bg-primary/80 text-primary-content':'bg-secondary/80 text-secondary-content'}`}>
          {isMovie?'Movie':'TV'}
        </div>
      </div>

      {/* Top-left: status */}
      <div className="absolute top-2 left-2 z-10 flex flex-col gap-1">
        {isMovie && (
          <div className={`badge badge-sm border-none shadow ${item.status==='downloaded'?'bg-success/80 text-success-content':item.status==='downloading'?'bg-info/80 text-info-content':'bg-error/80 text-error-content'}`}>
            {item.status==='downloaded'?<Ic.Check />:item.status==='downloading'?<Ic.Download />:<Ic.AlertTri />}
          </div>
        )}
        {!isMovie && (
          <div className="badge badge-sm border-none bg-base-100/80 text-base-content shadow font-mono text-xs">
            {item.downloaded_count}/{item.episode_count}
          </div>
        )}
      </div>

      {/* Series progress bar */}
      {!isMovie && <progress className={`progress absolute bottom-0 left-0 right-0 h-1 w-full ${pct===100?'progress-success':'progress-primary'}`} value={pct} max="100" />}

      {/* Hover overlay */}
      <div className="media-card-overlay absolute inset-0 flex flex-col justify-end bg-gradient-to-t from-black/90 via-black/20 to-transparent p-3">
        <div className="translate-y-2 transform transition-transform duration-300 group-hover:translate-y-0">
          <h3 className="text-sm font-bold text-white line-clamp-2 leading-tight">{item.title}</h3>
          <div className="flex items-center justify-between gap-2 mt-1">
            {item.year && <span className="text-xs text-white/70 font-mono">{item.year}</span>}
            {!isMovie && <span className="text-xs text-white/70">{pct}%</span>}
          </div>
          <div className="flex gap-1.5 mt-2">
            {isMovie && onSearchNow && (
              <button className="btn btn-xs btn-ghost bg-white/20 text-white hover:bg-white/30 border-none flex-1" onClick={doSearch} disabled={busy}>
                {busy ? <Ic.Loader /> : <Ic.Refresh />}
              </button>
            )}
            {onToggleMonitor && (
              <button className="btn btn-xs btn-ghost bg-white/20 text-white hover:bg-white/30 border-none flex-1" onClick={e=>{e.preventDefault();onToggleMonitor(item);}}>
                {item.monitored ? <Ic.Eye /> : <Ic.EyeOff />}
              </button>
            )}
            {onDelete && (
              <button className="btn btn-xs btn-ghost bg-white/20 text-white hover:bg-red-400/50 border-none flex-1" onClick={e=>{e.preventDefault();onDelete(item);}}>
                <Ic.Trash />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Library Page Header (shared pattern) ────────────────────────────────── */
function LibraryHeader({ title, count, onAdd, filterEl }) {
  return (
    <div className="flex items-start justify-between gap-4 mb-6">
      <div>
        <h1 className="mr-page-title">{title}</h1>
        <p className="text-base-content/60 text-sm mt-0.5">{count} in library</p>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        {filterEl}
        <button className="btn btn-primary btn-sm gap-2" onClick={onAdd}>
          <span className="w-4 h-4"><Ic.Plus /></span>Add
        </button>
      </div>
    </div>
  );
}

/* ── Dashboard Page ──────────────────────────────────────────────────────── */
function DashboardPage({ movies, series, setPage }) {
  const recent_movies = [...movies].sort((a,b)=>new Date(b.added_at)-new Date(a.added_at)).slice(0,8);
  const recent_series = [...series].sort((a,b)=>new Date(b.added_at)-new Date(a.added_at)).slice(0,8);
  const downloading = [...movies.filter(m=>m.status==='downloading')].slice(0,5);
  const isEmpty = movies.length===0 && series.length===0;

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="mr-page-title">Dashboard</h1>
          <p className="text-base-content/60 text-sm mt-0.5">Your media at a glance</p>
        </div>
        <div className="flex gap-2">
          <button className="btn btn-sm gap-2" onClick={()=>setPage('movies')}>
            <span className="w-4 h-4"><Ic.Plus /></span>Add content
          </button>
        </div>
      </div>

      <StatsGrid movies={movies} series={series} setPage={setPage} />

      {isEmpty ? (
        <div className="card bg-base-200 border border-dashed border-base-content/20">
          <div className="card-body items-center text-center py-16 gap-4">
            <div className="w-16 h-16 text-base-content/20"><Ic.Library /></div>
            <h2 className="text-xl font-semibold">Your library is empty</h2>
            <p className="text-base-content/50 text-sm max-w-sm">Add movies and TV shows to start building your collection. mediaos will automatically search, grab, and organize everything.</p>
            <div className="flex gap-3">
              <button className="btn btn-primary btn-sm" onClick={()=>setPage('movies')}>Add Movies</button>
              <button className="btn btn-secondary btn-sm" onClick={()=>setPage('tv')}>Add TV Shows</button>
            </div>
          </div>
        </div>
      ) : (
        <div className="grid gap-8 lg:grid-cols-3">
          <div className="lg:col-span-2 space-y-8">
            {recent_movies.length>0 && (
              <section>
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-lg font-semibold">Recently Added Movies</h2>
                  <button className="btn btn-ghost btn-xs" onClick={()=>setPage('movies')}>View all</button>
                </div>
                <div className="poster-grid">
                  {recent_movies.map(m=>(
                    <div key={m.id} className="media-card aspect-poster relative hover:ring-2 hover:ring-primary/40 cursor-pointer transition-all">
                      {m.poster_path ? <img src={TMDB+m.poster_path} className="w-full h-full object-cover" alt={m.title} loading="lazy" /> :
                        <div className="w-full h-full flex items-center justify-center text-2xl font-bold text-base-content/20">{m.title?.[0]}</div>}
                    </div>
                  ))}
                </div>
              </section>
            )}
            {recent_series.length>0 && (
              <section>
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-lg font-semibold">Recently Added Series</h2>
                  <button className="btn btn-ghost btn-xs" onClick={()=>setPage('tv')}>View all</button>
                </div>
                <div className="poster-grid">
                  {recent_series.map(s=>(
                    <div key={s.id} className="media-card aspect-poster relative hover:ring-2 hover:ring-secondary/40 cursor-pointer transition-all">
                      {s.poster_path ? <img src={TMDB+s.poster_path} className="w-full h-full object-cover" alt={s.title} loading="lazy" /> :
                        <div className="w-full h-full flex items-center justify-center text-2xl font-bold text-base-content/20">{s.title?.[0]}</div>}
                      <progress className="progress progress-secondary absolute bottom-0 left-0 right-0 h-0.5 w-full" value={s.episode_count>0?Math.round(s.downloaded_count/s.episode_count*100):0} max="100" />
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>

          {/* Right sidebar: activity */}
          <div className="space-y-4">
            <h2 className="text-lg font-semibold">Active Downloads</h2>
            {downloading.length===0 ? (
              <div className="card bg-base-200 p-4 text-center text-sm text-base-content/40">
                <div className="w-8 h-8 mx-auto mb-2 text-base-content/20"><Ic.Download /></div>
                Queue is empty
              </div>
            ) : downloading.map(m=>(
              <div key={m.id} className="card bg-base-200 p-3 flex flex-row items-center gap-3">
                <div className="w-10 h-14 flex-shrink-0 rounded overflow-hidden bg-base-300">
                  {m.poster_path ? <img src={TMDB+m.poster_path} className="w-full h-full object-cover" alt="" /> :
                    <div className="w-full h-full flex items-center justify-center font-bold text-base-content/20">{m.title?.[0]}</div>}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-sm truncate">{m.title}</div>
                  <div className="text-xs text-base-content/50 font-mono">{m.year}</div>
                  <div className="badge badge-info badge-sm mt-1 border-none">Downloading</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Movies Page ─────────────────────────────────────────────────────────── */
function MoviesPage({ movies, refreshMovies }) {
  const [modal, setModal] = useState(false);
  const [filter, setFilter] = useState('all');
  const [view, setView] = useState('grid');
  const [profiles, setProfiles] = useState([]);
  const existingIds = new Set(movies.map(m=>m.external_id));

  useEffect(() => { api.settings.profiles().then(setProfiles).catch(()=>{}); }, []);
  const movieProfiles = profiles.filter(p => p.media_type === 'movie');
  const filtered = filter==='all' ? movies : movies.filter(m=>m.status===filter);

  async function handleToggleMonitor(item) {
    try { await api.movies.update(item.id, !item.monitored); await refreshMovies(); } catch(e){}
  }
  async function handleSearchNow(id) {
    try { await api.movies.searchNow(id); await refreshMovies(); } catch(e){}
  }
  async function handleDelete(item) {
    if (!confirm(`Remove "${item.title}" from library?`)) return;
    try { await api.movies.remove(item.id); await refreshMovies(); } catch(e){}
  }
  async function setProfile(id, name) {
    try {
      await api.movies.update(id, { quality_profile: name || null });
      await refreshMovies();
    } catch(e){}
  }

  return (
    <div>
      <LibraryHeader
        title="Movies" count={movies.length}
        onAdd={()=>setModal(true)}
        filterEl={
          <div className="flex gap-2 items-center">
            <select className="select select-sm bg-base-200 border-base-300" value={filter} onChange={e=>setFilter(e.target.value)}>
              <option value="all">All</option>
              <option value="wanted">Wanted</option>
              <option value="downloading">Downloading</option>
              <option value="downloaded">Downloaded</option>
              <option value="missing">Missing</option>
            </select>
            <div className="join">
              <button className={`btn btn-sm join-item ${view==='grid'?'btn-active':''}`} onClick={()=>setView('grid')}>Grid</button>
              <button className={`btn btn-sm join-item ${view==='table'?'btn-active':''}`} onClick={()=>setView('table')}>Table</button>
            </div>
          </div>
        }
      />
      {movies.length===0 ? (
        <div className="text-center py-20 text-base-content/40">
          <div className="w-16 h-16 mx-auto mb-4 text-base-content/20"><Ic.Film /></div>
          <p className="text-lg font-medium">No movies yet</p>
          <p className="text-sm mt-1">Search and add a movie to get started.</p>
          <button className="btn btn-primary btn-sm mt-4" onClick={()=>setModal(true)}>Add Movie</button>
        </div>
      ) : view === 'table' ? (
        <div className="overflow-x-auto">
          <table className="table table-sm">
            <thead><tr><th>Title</th><th>Year</th><th>Status</th><th>Profile</th><th></th></tr></thead>
            <tbody>
              {filtered.map(m => (
                <tr key={m.id} className="hover">
                  <td className="font-medium">{m.title}</td>
                  <td className="text-base-content/50">{m.year||'—'}</td>
                  <td><span className="badge badge-sm">{m.status}</span></td>
                  <td>
                    <select className="select select-bordered select-xs max-w-[10rem]" value={m.quality_profile||''}
                      onChange={e=>setProfile(m.id, e.target.value)}>
                      <option value="">Default</option>
                      {movieProfiles.map(p => <option key={p.id} value={p.name}>{p.name}</option>)}
                    </select>
                  </td>
                  <td className="flex gap-1">
                    <button className="btn btn-ghost btn-xs" onClick={()=>handleSearchNow(m.id)}>Search</button>
                    <button className="btn btn-ghost btn-xs" onClick={()=>handleToggleMonitor(m)}>{m.monitored?'Unmonitor':'Monitor'}</button>
                    <button className="btn btn-ghost btn-xs text-error" onClick={()=>handleDelete(m)}>Del</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="poster-grid">
          {filtered.map(m=>(
            <MediaCard key={m.id} item={m} type="movie"
              onSearchNow={handleSearchNow}
              onToggleMonitor={handleToggleMonitor}
              onDelete={handleDelete} />
          ))}
        </div>
      )}
      {modal && <AddModal type="movie" existingIds={existingIds} onClose={()=>setModal(false)} onAdded={async()=>{await refreshMovies();}} />}
    </div>
  );
}

/* ── TV Page ─────────────────────────────────────────────────────────────── */
function TvPage({ series, refreshSeries }) {
  const [detailId, setDetailId] = useState(null);
  const [profiles, setProfiles] = useState([]);
  useEffect(() => { api.settings.profiles().then(setProfiles).catch(()=>{}); }, []);
  if (detailId) {
    return <SeriesDetailPage seriesId={detailId} onBack={()=>setDetailId(null)} refreshSeries={refreshSeries} />;
  }
  const tvProfiles = profiles.filter(p => p.media_type === 'tv');
  async function setProfile(id, name) {
    await fetch(`/api/tv/${id}`, { method:'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ quality_profile: name || null }) });
    refreshSeries && refreshSeries();
  }
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="mr-page-title">TV Shows</h1>
          <p className="text-sm text-base-content/50">{series.length} series</p>
        </div>
        <button className="btn btn-sm btn-primary" onClick={async()=>{
          const r = await api.system.searchAllMissing();
          alert(`Wanted search: movies ${r.movies}, episodes ${r.episodes}, music ${r.music}`);
          refreshSeries && refreshSeries();
        }}>Search all missing</button>
      </div>
      {series.length===0 ? (
        <p className="text-base-content/40">No series — use Discover to add</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="table table-sm">
            <thead><tr><th>Title</th><th>Progress</th><th>Missing</th><th>Profile</th><th></th></tr></thead>
            <tbody>
              {series.map(s => (
                <tr key={s.id} className="hover">
                  <td>
                    <button className="font-medium link link-hover text-left" onClick={()=>setDetailId(s.id)}>{s.title}</button>
                    <div className="text-xs text-base-content/40">{s.year||''}</div>
                  </td>
                  <td className="font-mono text-sm">{s.downloaded_count}/{s.episode_count}</td>
                  <td>{s.missing_count ? <span className="badge badge-warning badge-sm">{s.missing_count}</span> : '—'}</td>
                  <td>
                    <select className="select select-bordered select-xs max-w-[10rem]" value={s.quality_profile||''}
                      onChange={e=>setProfile(s.id, e.target.value)}>
                      <option value="">Default</option>
                      {tvProfiles.map(p => <option key={p.id} value={p.name}>{p.name}</option>)}
                    </select>
                  </td>
                  <td className="flex gap-1">
                    <button className="btn btn-ghost btn-xs" onClick={()=>setDetailId(s.id)}>Episodes</button>
                    <button className="btn btn-ghost btn-xs" onClick={()=>api.tv.searchMissing(s.id).then(()=>alert('Searching missing…'))}>Search</button>
                    <button className="btn btn-ghost btn-xs text-error" onClick={async()=>{await api.tv.remove(s.id); refreshSeries();}}>Del</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}


function DiscoverPage({ movies, series, refreshMovies, refreshSeries }) {
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

  const movieKinds = [['popular','Popular'],['trending','Trending'],['top_rated','Top rated'],['now_playing','In theatres'],['upcoming','Upcoming']];
  const tvKinds = [['popular','Popular'],['trending','Trending'],['top_rated','Top rated'],['on_the_air','On air']];

  useEffect(() => { api.settings.profiles().then(setProfiles).catch(()=>{}); }, []);

  useEffect(() => {
    if (mode !== 'browse') return;
    setLoading(true); setMsg(null);
    const fn = tab === 'movie' ? api.discover.movies : api.discover.tv;
    fn(kind).then(setItems).catch(()=>setItems([])).finally(()=>setLoading(false));
  }, [mode, tab, kind]);

  useEffect(() => {
    if (mode !== 'search' || !q.trim()) { if (mode==='search') setItems([]); return; }
    setLoading(true);
    const h = setTimeout(async () => {
      try {
        const r = tab === 'movie' ? await api.movies.search(q) : await api.tv.search(q);
        setItems(r || []);
      } catch { setItems([]); }
      setLoading(false);
    }, 400);
    return () => clearTimeout(h);
  }, [mode, q, tab]);

  const existing = new Set((tab==='movie'?movies:series).map(m => m.external_id));
  const kinds = tab === 'movie' ? movieKinds : tvKinds;
  const movieProfiles = profiles.filter(p => p.media_type === 'movie');

  async function addItem(item) {
    setBusy(item.external_id); setMsg(null);
    try {
      if (tab === 'movie') {
        await api.movies.add(item.external_id, profile ? { quality_profile: profile } : {});
        refreshMovies && await refreshMovies();
      } else {
        await api.tv.add(item.external_id);
        refreshSeries && await refreshSeries();
      }
      setMsg('Added ' + item.title);
    } catch (e) { setMsg(String(e.message||e)); }
    setBusy(null);
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="mr-page-title">Discover</h1>
          <p className="text-base-content/50 text-sm mt-1">Browse TMDb or search — add & monitor in one click</p>
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          <div className="join">
            <button className={`btn btn-sm join-item ${mode==='browse'?'btn-primary':'btn-ghost'}`} onClick={()=>setMode('browse')}>Browse</button>
            <button className={`btn btn-sm join-item ${mode==='search'?'btn-primary':'btn-ghost'}`} onClick={()=>setMode('search')}>Search</button>
          </div>
          <div className="join">
            <button className={`btn btn-sm join-item ${tab==='movie'?'btn-secondary':'btn-ghost'}`} onClick={()=>setTab('movie')}>Movies</button>
            <button className={`btn btn-sm join-item ${tab==='tv'?'btn-secondary':'btn-ghost'}`} onClick={()=>setTab('tv')}>TV</button>
          </div>
          {tab==='movie' && (
            <select className="select select-bordered select-sm max-w-[12rem]" value={profile} onChange={e=>setProfile(e.target.value)}>
              <option value="">Default profile</option>
              {movieProfiles.map(p => <option key={p.id} value={p.name}>{p.name}</option>)}
            </select>
          )}
        </div>
      </div>

      {mode==='browse' ? (
        <div className="flex flex-wrap gap-2">
          {kinds.map(([k,label]) => (
            <button key={k} className={`btn btn-xs ${kind===k?'btn-accent':'btn-ghost'}`} onClick={()=>setKind(k)}>{label}</button>
          ))}
        </div>
      ) : (
        <label className="input input-bordered flex items-center gap-2 max-w-lg">
          <span className="w-4 h-4 opacity-40"><Ic.Search/></span>
          <input className="grow" placeholder={`Search ${tab==='movie'?'movies':'TV'}…`} value={q} onChange={e=>setQ(e.target.value)} />
        </label>
      )}

      {msg && <div className="alert alert-info text-sm py-2"><span>{msg}</span></div>}

      {loading ? (
        <div className="flex justify-center py-16"><span className="loading loading-spinner loading-lg text-primary"/></div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {items.map(item => {
            const has = existing.has(item.external_id);
            return (
              <div key={item.external_id} className="card bg-base-200 border border-base-300 overflow-hidden">
                <figure className="aspect-[2/3] bg-base-300">
                  {item.poster_path
                    ? <img src={TMDB+item.poster_path} alt="" className="w-full h-full object-cover"/>
                    : <div className="w-full h-full flex items-center justify-center opacity-20"><Ic.Film/></div>}
                </figure>
                <div className="card-body p-3 gap-1">
                  <h3 className="font-medium text-sm line-clamp-2 leading-tight">{item.title}</h3>
                  <div className="text-xs text-base-content/50 flex justify-between">
                    <span>{item.year || '—'}</span>
                    {item.vote_average != null && <span>★ {Number(item.vote_average).toFixed(1)}</span>}
                  </div>
                  <button className={`btn btn-xs mt-1 ${has?'btn-disabled':'btn-primary'}`}
                    disabled={has || busy===item.external_id}
                    onClick={()=>addItem(item)}>
                    {has ? 'In library' : busy===item.external_id ? '…' : 'Add + Monitor'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}


function ImportPage({ movies, series }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(null);
  const [msg, setMsg] = useState(null);
  const [err, setErr] = useState(null);
  const [mode, setMode] = useState({}); // path -> { type:'movie'|'episode', mediaId, season, episode, title, year }

  const refresh = useCallback(() => {
    setLoading(true); setErr(null);
    api.import.scan().then(setItems).catch(e=>setErr(String(e.message||e))).finally(()=>setLoading(false));
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  function setModeField(path, field, value) {
    setMode(m => ({ ...m, [path]: { type:'movie', ...(m[path]||{}), [field]: value } }));
  }

  async function doImport(item) {
    const m = mode[item.path] || { type: 'movie' };
    setBusy(item.path); setMsg(null); setErr(null);
    try {
      let res;
      if (m.type === 'episode') {
        res = await api.import.episode({
          source_path: item.path,
          episode_id: m.episodeId ? Number(m.episodeId) : undefined,
          series_id: m.seriesId ? Number(m.seriesId) : undefined,
          season: m.season != null && m.season !== '' ? Number(m.season) : (item.parsed?.season ?? undefined),
          episode: m.episode != null && m.episode !== '' ? Number(m.episode) : (item.parsed?.episode ?? undefined),
        });
      } else {
        res = await api.import.movie({
          source_path: item.path,
          media_item_id: m.mediaId ? Number(m.mediaId) : undefined,
          title: m.title || undefined,
          year: m.year ? Number(m.year) : (item.parsed?.year || undefined),
        });
      }
      setMsg(`Imported → ${res.dest}`);
      refresh();
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setBusy(null);
    }
  }

  function fmtSize(n) {
    if (!n) return '—';
    if (n > 1e9) return (n/1e9).toFixed(1) + ' GB';
    if (n > 1e6) return (n/1e6).toFixed(0) + ' MB';
    return n + ' B';
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="mr-page-title">Manual Import</h1>
          <p className="text-base-content/50 text-sm mt-1">Scan downloads and move files into your library</p>
        </div>
        <button className="btn btn-primary btn-sm" onClick={refresh} disabled={loading}>
          {loading ? 'Scanning…' : 'Rescan'}
        </button>
      </div>

      {msg && <div className="alert alert-success text-sm"><span>{msg}</span></div>}
      {err && <div className="alert alert-error text-sm"><span>{err}</span></div>}

      {loading ? (
        <div className="flex justify-center py-16"><span className="loading loading-spinner loading-lg text-primary"/></div>
      ) : items.length === 0 ? (
        <div className="text-center py-16 text-base-content/40">
          <div className="w-16 h-16 mx-auto mb-4 opacity-30"><Ic.Folder /></div>
          <p>No video files found in downloads</p>
          <p className="text-xs mt-2">Drop files into the downloads folder mounted at /downloads</p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map(item => {
            const m = mode[item.path] || { type: item.parsed?.season != null ? 'episode' : 'movie' };
            return (
              <div key={item.path} className="card mr-panel border-0">
                <div className="card-body p-4 gap-3">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="font-medium font-mono text-sm break-all">{item.name}</div>
                      <div className="text-xs text-base-content/50 mt-1 flex flex-wrap gap-2">
                        <span>{fmtSize(item.size)}</span>
                        {item.parsed?.resolution && <span className="badge badge-sm badge-ghost">{item.parsed.resolution}</span>}
                        {item.parsed?.source && <span className="badge badge-sm badge-ghost">{item.parsed.source}</span>}
                        {item.parsed?.codec && <span className="badge badge-sm badge-ghost">{item.parsed.codec}</span>}
                        {item.parsed?.season != null && <span className="badge badge-sm badge-secondary">S{String(item.parsed.season).padStart(2,'0')}E{String(item.parsed.episode||0).padStart(2,'0')}</span>}
                      </div>
                    </div>
                    <div className="flex gap-2 items-center">
                      <select className="select select-bordered select-sm" value={m.type||'movie'}
                        onChange={e=>setModeField(item.path,'type',e.target.value)}>
                        <option value="movie">Movie</option>
                        <option value="episode">TV episode</option>
                      </select>
                      <button className="btn btn-primary btn-sm" disabled={busy===item.path} onClick={()=>doImport(item)}>
                        {busy===item.path ? <span className="loading loading-spinner loading-xs"/> : 'Import'}
                      </button>
                    </div>
                  </div>

                  {m.type === 'movie' ? (
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                      <select className="select select-bordered select-sm" value={m.mediaId||''}
                        onChange={e=>setModeField(item.path,'mediaId',e.target.value)}>
                        <option value="">— link to library movie (optional) —</option>
                        {movies.map(mv => <option key={mv.id} value={mv.id}>{mv.title}{mv.year?` (${mv.year})`:''}</option>)}
                      </select>
                      <input className="input input-bordered input-sm" placeholder="Title if untracked"
                        value={m.title||''} onChange={e=>setModeField(item.path,'title',e.target.value)} />
                      <input className="input input-bordered input-sm" placeholder="Year" type="number"
                        value={m.year||item.parsed?.year||''} onChange={e=>setModeField(item.path,'year',e.target.value)} />
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                      <select className="select select-bordered select-sm" value={m.seriesId||''}
                        onChange={e=>setModeField(item.path,'seriesId',e.target.value)}>
                        <option value="">— select series —</option>
                        {series.map(s => <option key={s.id} value={s.id}>{s.title}</option>)}
                      </select>
                      <input className="input input-bordered input-sm" placeholder="Season"
                        type="number" value={m.season??item.parsed?.season??''}
                        onChange={e=>setModeField(item.path,'season',e.target.value)} />
                      <input className="input input-bordered input-sm" placeholder="Episode"
                        type="number" value={m.episode??item.parsed?.episode??''}
                        onChange={e=>setModeField(item.path,'episode',e.target.value)} />
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ── Quality Profiles (full editor) ─────────────────────────────────────── */
function QualityProfilesPage() {
  const empty = () => ({
    name: '', media_type: 'movie', is_default: false, cutoff: '1080p', min_seeders: 3,
    resolutions: ['2160p','1080p','720p','480p'],
    preferred_sources: ['bluray','webdl','webrip','hdtv'],
    custom_formats: [],
  });
  const [profiles, setProfiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [edit, setEdit] = useState(null); // null | {id?, ...form}
  const [msg, setMsg] = useState(null);
  const [scoreTitle, setScoreTitle] = useState('');
  const [scoreResult, setScoreResult] = useState(null);
  const [movieCfg, setMovieCfg] = useState(null);

  const load = () => {
    setLoading(true);
    Promise.all([
      api.settings.profiles(),
      api.settings.movies().catch(()=>null),
    ]).then(([p, m]) => { setProfiles(p||[]); setMovieCfg(m); })
      .catch(()=>{}).finally(()=>setLoading(false));
  };
  useEffect(() => { load(); }, []);

  async function save() {
    setMsg(null);
    try {
      await api.settings.saveProfile(edit.id || null, edit);
      setEdit(null); load(); setMsg('Saved');
    } catch(e) { setMsg(String(e.message||e)); }
  }
  async function remove(id) {
    if (!confirm('Delete this profile?')) return;
    try { await api.settings.deleteProfile(id); load(); } catch(e) { setMsg(String(e.message||e)); }
  }
  async function makeDefault(id) {
    try { await api.settings.setDefaultProfile(id); load(); } catch(e) { setMsg(String(e.message||e)); }
  }
  async function testScore() {
    try {
      const r = await fetch('/api/quality/score', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ title: scoreTitle, media_type: edit?.media_type || 'movie' }),
      }).then(x=>x.json());
      setScoreResult(r);
    } catch(e) { setScoreResult({ error: String(e.message||e) }); }
  }

  function toggleList(key, val) {
    const list = edit[key] || [];
    setEdit({ ...edit, [key]: list.includes(val) ? list.filter(x=>x!==val) : [...list, val] });
  }

  const RES = ['2160p','1080p','720p','480p'];
  const SRC = ['bluray','webdl','webrip','hdtv','hdtv','dvd','cam','ts'];

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex justify-between items-start flex-wrap gap-2">
        <div>
          <h1 className="mr-page-title">Quality Profiles</h1>
          <p className="text-base-content/50 text-sm mt-1">TRaSH-style scoring for movie (and TV) grabs — Radarr replacement core</p>
        </div>
        <button className="btn btn-sm btn-primary" onClick={()=>setEdit(empty())}>New profile</button>
      </div>

      {movieCfg && (
        <div className="alert text-sm py-2">
          <span>
            Movie mode: <b>{movieCfg.download_mode}</b>
            {movieCfg.download_mode==='strm' ? ' (writes .strm, no torrent)' : ' (qBittorrent download)'}
            {' · '}Upgrades: {movieCfg.upgrade_enabled ? `on (gap ${movieCfg.upgrade_min_score_gap})` : 'off'}
            {' · '}Set <code className="text-xs">MOVIE_DOWNLOAD_MODE=strm</code> for stream-without-download
          </span>
        </div>
      )}
      {msg && <div className="alert alert-info text-sm py-2">{msg}</div>}

      {loading ? <span className="loading loading-spinner"/> : (
        <div className="space-y-3">
          {profiles.map(p => (
            <div key={p.id} className="card mr-panel border-0">
              <div className="card-body p-4 gap-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <h2 className="font-semibold">{p.name}</h2>
                  <span className="badge badge-sm">{p.media_type}</span>
                  {p.is_default && <span className="badge badge-sm badge-primary">default</span>}
                  <div className="flex-1"/>
                  <button className="btn btn-ghost btn-xs" onClick={()=>setEdit({...p, id:p.id})}>Edit</button>
                  {!p.is_default && <button className="btn btn-ghost btn-xs" onClick={()=>makeDefault(p.id)}>Set default</button>}
                  {!p.is_default && <button className="btn btn-ghost btn-xs text-error" onClick={()=>remove(p.id)}>Del</button>}
                </div>
                <div className="text-xs opacity-60">Cutoff {p.cutoff} · Min seeders {p.min_seeders} · {(p.preferred_sources||[]).join(', ')}</div>
                <div className="flex flex-wrap gap-1">
                  {(p.custom_formats||[]).slice(0,16).map(cf => (
                    <span key={cf.name} className={`badge badge-sm ${cf.reject?'badge-error':'badge-ghost'}`}>
                      {cf.name}{cf.score?` ${cf.score>0?'+':''}${cf.score}`:''}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {edit && (
        <div className="card mr-panel border border-primary/40">
          <div className="card-body gap-3">
            <h2 className="font-semibold text-lg">{edit.id?'Edit':'New'} profile</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <input className="input input-bordered input-sm" placeholder="Name" value={edit.name} onChange={e=>setEdit({...edit, name:e.target.value})}/>
              <select className="select select-bordered select-sm" value={edit.media_type} onChange={e=>setEdit({...edit, media_type:e.target.value})}>
                <option value="movie">movie</option>
                <option value="tv">tv</option>
              </select>
              <select className="select select-bordered select-sm" value={edit.cutoff} onChange={e=>setEdit({...edit, cutoff:e.target.value})}>
                {RES.map(r=><option key={r} value={r}>Cutoff {r}</option>)}
              </select>
              <input className="input input-bordered input-sm" type="number" placeholder="Min seeders" value={edit.min_seeders}
                onChange={e=>setEdit({...edit, min_seeders:Number(e.target.value)})}/>
            </div>
            <label className="label cursor-pointer justify-start gap-2">
              <input type="checkbox" className="checkbox checkbox-sm" checked={!!edit.is_default} onChange={e=>setEdit({...edit, is_default:e.target.checked})}/>
              <span className="label-text text-sm">Default for {edit.media_type}</span>
            </label>
            <div>
              <div className="text-xs font-medium mb-1">Resolutions</div>
              <div className="flex flex-wrap gap-2">{RES.map(r=>(
                <label key={r} className="label cursor-pointer gap-1 py-0">
                  <input type="checkbox" className="checkbox checkbox-xs" checked={(edit.resolutions||[]).includes(r)} onChange={()=>toggleList('resolutions', r)}/>
                  <span className="label-text text-xs">{r}</span>
                </label>
              ))}</div>
            </div>
            <div>
              <div className="text-xs font-medium mb-1">Preferred sources</div>
              <div className="flex flex-wrap gap-2">{['bluray','webdl','webrip','hdtv','dvd'].map(r=>(
                <label key={r} className="label cursor-pointer gap-1 py-0">
                  <input type="checkbox" className="checkbox checkbox-xs" checked={(edit.preferred_sources||[]).includes(r)} onChange={()=>toggleList('preferred_sources', r)}/>
                  <span className="label-text text-xs">{r}</span>
                </label>
              ))}</div>
            </div>
            <div>
              <div className="text-xs font-medium mb-1">Custom formats ({(edit.custom_formats||[]).length}) — edit via API for full TRaSH sets; defaults seeded</div>
              <div className="flex flex-wrap gap-1 max-h-24 overflow-y-auto">
                {(edit.custom_formats||[]).map(cf=>(
                  <span key={cf.name} className={`badge badge-sm ${cf.reject?'badge-error':'badge-ghost'}`}>{cf.name} {cf.score||0}</span>
                ))}
              </div>
            </div>
            <div className="flex gap-2">
              <button className="btn btn-sm btn-primary" onClick={save} disabled={!edit.name}>Save</button>
              <button className="btn btn-sm btn-ghost" onClick={()=>setEdit(null)}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      <div className="card mr-panel border-0">
        <div className="card-body gap-2">
          <h2 className="font-semibold">Score tester (soak / debug)</h2>
          <div className="flex gap-2">
            <input className="input input-bordered input-sm flex-1" placeholder="Release title…" value={scoreTitle} onChange={e=>setScoreTitle(e.target.value)}/>
            <button className="btn btn-sm" onClick={testScore}>Score</button>
          </div>
          {scoreResult && (
            <pre className="text-xs bg-base-300 p-2 rounded overflow-x-auto">{JSON.stringify(scoreResult, null, 2)}</pre>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Activity Page ───────────────────────────────────────────────────────── */
function ActivityPage({ movies }) {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const active = movies.filter(m=>m.status==='downloading');

  useEffect(() => {
    api.activity.list().then(setEvents).catch(()=>setEvents([])).finally(()=>setLoading(false));
    const id = setInterval(() => api.activity.list().then(setEvents).catch(()=>{}), 15000);
    return () => clearInterval(id);
  }, []);

  const badge = (ev) => {
    const map = { grabbed:'badge-info', organized:'badge-success', imported:'badge-success',
      upgrade:'badge-warning', failed:'badge-error', blocked:'badge-error', searched:'badge-ghost' };
    return map[ev] || 'badge-ghost';
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="mr-page-title">Activity</h1>
        <p className="text-base-content/60 text-sm mt-0.5">Downloads, imports, upgrades, and history</p>
      </div>

      <div>
        <h2 className="font-semibold mb-3">Downloading now</h2>
        {active.length===0 ? (
          <p className="text-sm text-base-content/40">Queue is empty</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="table table-sm">
              <thead><tr><th>Title</th><th>Status</th><th>Score</th></tr></thead>
              <tbody>
                {active.map(m=>(
                  <tr key={m.id}>
                    <td className="font-medium">{m.title}</td>
                    <td><span className="badge badge-info badge-sm">Downloading</span></td>
                    <td className="font-mono text-sm">{m.quality_score ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div>
        <h2 className="font-semibold mb-3">Event log</h2>
        {loading ? <span className="loading loading-spinner text-primary"/> : events.length===0 ? (
          <p className="text-sm text-base-content/40">No events yet</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="table table-sm">
              <thead><tr><th>When</th><th>Event</th><th>Message</th></tr></thead>
              <tbody>
                {events.map(e=>(
                  <tr key={e.id}>
                    <td className="text-xs font-mono whitespace-nowrap">{e.created_at ? new Date(e.created_at).toLocaleString() : ''}</td>
                    <td><span className={`badge badge-sm ${badge(e.event)}`}>{e.event}</span></td>
                    <td className="text-sm">{e.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Themes Page ─────────────────────────────────────────────────────────── */
function ThemesPage({ currentTheme, setTheme }) {
  return (
    <div>
      <div className="mb-6">
        <h1 className="mr-page-title">Themes</h1>
        <p className="text-base-content/60 text-sm mt-0.5">
          {THEMES.length} themes available · currently using <span className="font-mono font-semibold text-primary">{currentTheme}</span>
        </p>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
        {THEMES.map(t=>(
          <button
            key={t}
            data-theme={t}
            onClick={()=>setTheme(t)}
            className={`rounded-xl p-3 text-left transition-all border-2 bg-base-100 hover:scale-105
              ${currentTheme===t ? 'border-primary ring-2 ring-primary/30' : 'border-base-300 hover:border-base-content/30'}`}
          >
            {/* Color swatches using the theme's own CSS vars */}
            <div className="flex gap-1 mb-2">
              <div className="h-4 flex-1 rounded bg-primary" />
              <div className="h-4 flex-1 rounded bg-secondary" />
              <div className="h-4 flex-1 rounded bg-accent" />
              <div className="h-4 flex-1 rounded bg-neutral" />
            </div>
            <div className="flex items-center gap-1">
              <span className="text-xs font-mono font-medium text-base-content capitalize">{t}</span>
              {currentTheme===t && <span className="ml-auto w-3 h-3 text-primary flex-shrink-0"><Ic.Check /></span>}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

/* ── Editable Settings group (Download Clients / Library Storage / System) ── */
function ConfigGroupPage({ group, title, Icon, description }) {
  const [fields, setFields] = useState(null);
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null);

  const load = () => {
    api.settings.getConfig(group).then(data=>{
      setFields(data);
      const f = {};
      for (const k in data) f[k] = data[k].value ?? '';
      setForm(f);
    }).catch(()=>setFields({}));
  };
  useEffect(() => { load(); }, [group]);

  function setVal(k, v) { setForm(prev=>({ ...prev, [k]: v })); }

  async function save() {
    setSaving(true); setMsg(null);
    try {
      const updated = await api.settings.saveConfig(group, form);
      setFields(updated);
      const f = {};
      for (const k in updated) f[k] = updated[k].value ?? '';
      setForm(f);
      setMsg('Saved — takes effect immediately, no restart needed.');
    } catch(e) { setMsg(String(e.message||e)); }
    setSaving(false);
  }

  return (
    <div className="max-w-2xl">
      <div className="mb-6">
        <h1 className="mr-page-title">{title}</h1>
        <p className="text-base-content/60 text-sm mt-0.5">{description}</p>
      </div>
      {!fields ? <span className="loading loading-spinner"/> : Object.keys(fields).length===0 ? (
        <div className="card bg-base-200 border border-dashed border-base-content/20 max-w-md">
          <div className="card-body items-center text-center py-12 gap-4">
            <div className="w-12 h-12 text-base-content/20"><Icon /></div>
            <p className="text-base-content/50 text-sm">Nothing configurable in this group.</p>
          </div>
        </div>
      ) : (
        <div className="mr-panel p-5 space-y-4">
          {msg && <div className="alert alert-info text-sm py-2">{msg}</div>}
          {Object.entries(fields).map(([key, meta])=>(
            <div key={key} className="form-control">
              <label className="label py-1"><span className="label-text text-sm">{meta.label}</span></label>
              {typeof meta.value === 'boolean' || form[key]===true || form[key]===false ? (
                <input type="checkbox" className="toggle toggle-sm"
                  checked={!!form[key]} onChange={e=>setVal(key, e.target.checked)} />
              ) : (
                <input
                  type={meta.secret ? 'password' : 'text'}
                  className="input input-bordered input-sm w-full"
                  value={form[key] ?? ''}
                  placeholder={meta.secret ? 'unchanged' : ''}
                  onChange={e=>setVal(key, e.target.value)} />
              )}
            </div>
          ))}
          <div className="pt-2">
            <button className="btn btn-primary btn-sm" disabled={saving} onClick={save}>
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Coming Soon Page ────────────────────────────────────────────────────── */
function ComingSoonPage({ title, Icon, description }) {
  return (
    <div className="flex flex-col items-start gap-4 pt-8 max-w-md">
      <div className="w-12 h-12 text-primary"><Icon /></div>
      <div>
        <h1 className="text-2xl font-bold">{title}</h1>
        <p className="text-base-content/60 text-sm mt-1">{description}</p>
      </div>
      <div className="badge badge-outline">Coming soon</div>
    </div>
  );
}

/* ── Page Router ─────────────────────────────────────────────────────────── */

/* ── Music Page ──────────────────────────────────────────────────────────── */
function MusicPage() {
  const [albums, setAlbums] = useState([]);
  const [q, setQ] = useState('');
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState(null);

  const load = useCallback(() => {
    api.music.list().then(setAlbums).catch(()=>setAlbums([])).finally(()=>setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);

  async function doSearch(e) {
    e && e.preventDefault();
    if (!q.trim()) return;
    setSearching(true); setMsg(null);
    try { setResults(await api.music.search(q.trim())); }
    catch { setResults([]); }
    setSearching(false);
  }

  async function addAlbum(r) {
    try {
      await api.music.add({
        external_id: r.external_id,
        external_mbid: r.external_mbid,
        title: r.title,
        artist: r.artist,
        year: r.year,
      });
      setMsg('Added ' + r.title);
      setResults([]); setQ('');
      load();
    } catch (e) { setMsg(String(e.message||e)); }
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="mr-page-title">Music</h1>
        <p className="text-base-content/50 text-sm mt-1">MusicBrainz search · Prowlarr audio · organize to /music/Artist/Album</p>
      </div>
      {msg && <div className="alert alert-info text-sm py-2"><span>{msg}</span></div>}
      <form onSubmit={doSearch} className="flex gap-2 flex-wrap">
        <input className="input input-bordered flex-1 min-w-[12rem]" placeholder="Artist or album…" value={q} onChange={e=>setQ(e.target.value)} />
        <button className="btn btn-primary" disabled={searching}>{searching?'…':'Search album'}</button>
        <button type="button" className="btn btn-secondary" disabled={!q.trim()||searching}
          onClick={async()=>{ setSearching(true); setMsg(null); try { const r=await api.music.addArtist(q.trim()); setMsg(`Added ${r.added} albums for ${r.artist} (${r.skipped} skipped)`); load(); } catch(e){ setMsg(String(e.message||e)); } setSearching(false); }}>
          Add artist discography
        </button>
        <button type="button" className="btn btn-ghost" onClick={async()=>{ try { const r=await api.music.scanPaths(); setMsg(`Path scan: ok ${r.ok}, missing ${r.marked_missing}, restored ${r.restored}`); load(); } catch(e){ setMsg(String(e.message||e)); } }}>
          Scan paths
        </button>
      </form>
      {results.length > 0 && (
        <div className="card mr-panel border-0">
          <div className="card-body p-3 gap-0">
            {results.map(r => (
              <div key={r.external_mbid||r.external_id} className="flex items-center justify-between gap-2 py-2 border-b border-base-300 last:border-0">
                <div className="min-w-0">
                  <div className="font-medium text-sm truncate">{r.title}</div>
                  <div className="text-xs text-base-content/50">{[r.year,r.overview].filter(Boolean).join(' · ')}</div>
                </div>
                <button className="btn btn-xs btn-primary shrink-0" onClick={()=>addAlbum(r)}>Add</button>
              </div>
            ))}
          </div>
        </div>
      )}
      <div>
        <h2 className="font-semibold mb-3">Library ({albums.length})</h2>
        {loading ? <span className="loading loading-spinner text-primary"/> : albums.length===0 ? (
          <p className="text-sm text-base-content/40">No albums yet — search above to add</p>
        ) : (
          <table className="table table-sm">
            <thead><tr><th>Title</th><th>Year</th><th>Status</th><th></th></tr></thead>
            <tbody>
              {albums.map(a => (
                <tr key={a.id}>
                  <td className="font-medium">{a.title}</td>
                  <td className="font-mono text-sm">{a.year||'—'}</td>
                  <td><span className="badge badge-sm">{a.status}</span></td>
                  <td className="flex gap-1">
                    <button className="btn btn-ghost btn-xs" onClick={()=>api.music.searchNow(a.id).then(()=>setMsg('Search queued'))}>Search</button>
                    <button className="btn btn-ghost btn-xs text-error" onClick={async()=>{await api.music.remove(a.id); load();}}>Del</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}


/* ── Series Detail (Sonarr-style) ────────────────────────────────────────── */
function SeriesDetailPage({ seriesId, onBack, refreshSeries }) {
  const [series, setSeries] = useState(null);
  const [episodes, setEpisodes] = useState([]);
  const [profiles, setProfiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);

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

  const seasons = React.useMemo(() => {
    const m = {};
    episodes.forEach(e => {
      if (!m[e.season_number]) m[e.season_number] = [];
      m[e.season_number].push(e);
    });
    return Object.keys(m).map(Number).sort((a,b)=>a-b).map(s => ({ season: s, eps: m[s].sort((a,b)=>a.episode_number-b.episode_number) }));
  }, [episodes]);

  async function searchMissing() {
    setBusy(true); setMsg(null);
    try {
      const r = await api.tv.searchMissing(seriesId);
      setMsg(`Search missing: ${r.searched||0} actions, ${JSON.stringify(r.grabs||[]).slice(0,120)}`);
      load(); refreshSeries && refreshSeries();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }

  async function searchSeason(s) {
    setBusy(true); setMsg(null);
    try {
      const r = await api.tv.searchSeason(seriesId, s);
      setMsg(`Season ${s}: ${(r.grabs||[]).length} grabs`);
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
    await fetch(`/api/tv/${seriesId}`, {
      method:'PATCH', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ quality_profile: name || null })
    });
    load(); refreshSeries && refreshSeries();
  }

  async function toggleEp(ep) {
    await fetch(`/api/tv/episodes/${ep.id}`, {
      method:'PATCH', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ monitored: !ep.monitored })
    });
    load();
  }

  if (loading) return <div className="flex justify-center py-20"><span className="loading loading-spinner loading-lg text-primary"/></div>;
  if (!series) return <div className="p-6">Series not found <button className="btn btn-sm" onClick={onBack}>Back</button></div>;

  const tvProfiles = profiles.filter(p => p.media_type === 'tv');

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex flex-wrap items-start gap-4">
        <button className="btn btn-ghost btn-sm" onClick={onBack}>← Library</button>
        <div className="flex-1 min-w-0">
          <h1 className="mr-page-title">{series.title}</h1>
          <p className="text-sm text-base-content/50 mt-1">
            {series.year||''} · {series.episode_count} eps · {series.downloaded_count} downloaded · {series.missing_count} missing
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <select className="select select-bordered select-sm" value={series.quality_profile||''}
            onChange={e=>setProfile(e.target.value)}>
            <option value="">Default profile</option>
            {tvProfiles.map(p => <option key={p.id} value={p.name}>{p.name}</option>)}
          </select>
          <button className="btn btn-sm btn-ghost" disabled={busy} onClick={refreshMeta}>Refresh</button>
          <button className="btn btn-sm btn-primary" disabled={busy} onClick={searchMissing}>Search missing</button>
        </div>
      </div>
      {msg && <div className="alert alert-info text-sm py-2"><span className="font-mono text-xs break-all">{msg}</span></div>}

      {seasons.map(({season, eps}) => (
        <div key={season} className="card mr-panel border-0">
          <div className="card-body p-4 gap-2">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold">Season {season}</h2>
              <button className="btn btn-xs btn-secondary" disabled={busy} onClick={()=>searchSeason(season)}>Search season</button>
            </div>
            <div className="overflow-x-auto">
              <table className="table table-xs">
                <thead><tr><th></th><th>Ep</th><th>Title</th><th>Air</th><th>Status</th><th></th></tr></thead>
                <tbody>
                  {eps.map(ep => (
                    <tr key={ep.id} className={!ep.monitored ? 'opacity-40' : ''}>
                      <td>
                        <input type="checkbox" className="checkbox checkbox-xs" checked={!!ep.monitored}
                          onChange={()=>toggleEp(ep)} />
                      </td>
                      <td className="font-mono">E{String(ep.episode_number).padStart(2,'0')}</td>
                      <td className="text-sm">{ep.title||'—'}</td>
                      <td className="text-xs font-mono">{ep.air_date||''}</td>
                      <td><span className={`badge badge-xs ${ep.status==='downloaded'?'badge-success':ep.status==='downloading'?'badge-info':'badge-ghost'}`}>{ep.status}</span></td>
                      <td>
                        {ep.status!=='downloaded' && ep.monitored && (
                          <button className="btn btn-ghost btn-xs" onClick={()=>fetch(`/api/tv/episodes/${ep.id}/search`,{method:'POST'}).then(()=>setMsg('Episode search queued'))}>Search</button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}


function BooksPage() {
  const [items, setItems] = useState([]);
  const [q, setQ] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState(null);
  const load = () => api.books.list().then(setItems).catch(()=>[]).finally(()=>setLoading(false));
  useEffect(() => { load(); }, []);
  async function searchGrab(id) {
    setMsg('Searching…');
    try {
      const r = await fetch(`/api/books/${id}/search`, {method:'POST'}).then(x=>x.json());
      setMsg(r.found ? `Grabbed: ${r.title}` : 'No release found');
      load();
    } catch(e) { setMsg(String(e.message||e)); }
  }
  return (
    <div className="space-y-6 max-w-4xl">
      <h1 className="mr-page-title">Books</h1>
      <p className="text-sm text-base-content/50">Open Library search · Prowlarr eBook grabs (organize path next)</p>
      <form className="flex gap-2" onSubmit={async e=>{e.preventDefault(); setResults(await api.books.search(q));}}>
        <input className="input input-bordered flex-1" value={q} onChange={e=>setQ(e.target.value)} placeholder="Title or author…"/>
        <button className="btn btn-primary">Search</button>
      </form>
      {results.length>0 && results.map(r=>(
        <div key={r.external_id} className="flex justify-between items-center py-2 border-b border-base-300">
          <div><div className="font-medium text-sm">{r.title}</div><div className="text-xs opacity-50">{r.year} {r.overview}</div></div>
          <button className="btn btn-xs btn-primary" onClick={async()=>{await api.books.add(r); setResults([]); load();}}>Add</button>
        </div>
      ))}
      {msg && <div className="alert alert-info text-sm py-2">{msg}</div>}
      <h2 className="font-semibold">Library ({items.length})</h2>
      {loading ? <span className="loading loading-spinner"/> : items.map(b=>(
        <div key={b.id} className="flex justify-between items-center py-1 gap-2">
          <span className="flex-1">{b.title} <span className="badge badge-xs">{b.status}</span></span>
          <button className="btn btn-ghost btn-xs" onClick={()=>searchGrab(b.id)}>Search</button>
          <button className="btn btn-ghost btn-xs text-error" onClick={async()=>{await api.books.remove(b.id); load();}}>Del</button>
        </div>
      ))}
    </div>
  );
}


function LiveTvPage() {
  const [sources, setSources] = useState([]);
  const [channels, setChannels] = useState([]);
  const [q, setQ] = useState('');
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [msg, setMsg] = useState(null);
  const load = () => {
    api.livetv.sources().then(setSources).catch(()=>[]);
    api.livetv.channels(q).then(setChannels).catch(()=>[]);
  };
  useEffect(() => { load(); }, []);
  return (
    <div className="space-y-6 max-w-5xl">
      <h1 className="mr-page-title">Live TV</h1>
      <p className="text-sm text-base-content/50">M3U playlists &amp; Xtream Codes — stream URLs for VLC / Jellyfin / Dispatcharr</p>
      <div className="card mr-panel border-0">
        <div className="card-body gap-2">
          <h2 className="font-semibold">Add M3U source</h2>
          <div className="flex flex-wrap gap-2">
            <input className="input input-bordered input-sm" placeholder="Name" value={name} onChange={e=>setName(e.target.value)} />
            <input className="input input-bordered input-sm flex-1 min-w-[16rem]" placeholder="https://…/playlist.m3u" value={url} onChange={e=>setUrl(e.target.value)} />
            <button className="btn btn-sm btn-primary" onClick={async()=>{
              await api.livetv.addSource({name: name||'M3U', kind:'m3u', url});
              setName(''); setUrl(''); load();
            }}>Add</button>
          </div>
        </div>
      </div>
      <div className="space-y-2">
        <h2 className="font-semibold">Sources</h2>
        {sources.map(s=>(
          <div key={s.id} className="flex items-center gap-2 text-sm">
            <span className="font-medium">{s.name}</span>
            <span className="badge badge-xs">{s.kind}</span>
            <span className="opacity-50">{s.channel_count} ch</span>
            <button className="btn btn-xs" onClick={async()=>{ setMsg('Syncing…'); const r=await api.livetv.sync(s.id); setMsg(`Synced ${r.synced}`); load(); }}>Sync</button>
          </div>
        ))}
      </div>
      {msg && <div className="alert alert-info text-sm py-2">{msg}</div>}
      <div className="flex gap-2">
        <input className="input input-bordered input-sm flex-1" placeholder="Filter channels…" value={q} onChange={e=>setQ(e.target.value)}
          onKeyDown={e=>{ if(e.key==='Enter') api.livetv.channels(q).then(setChannels); }} />
        <button className="btn btn-sm" onClick={()=>api.livetv.channels(q).then(setChannels)}>Search</button>
      </div>
      <div className="overflow-x-auto max-h-[28rem]">
        <table className="table table-xs">
          <thead><tr><th>Name</th><th>Group</th><th>Stream</th></tr></thead>
          <tbody>
            {channels.map(c=>(
              <tr key={c.id}>
                <td className="font-medium">{c.name}</td>
                <td className="opacity-60">{c.group_title||'—'}</td>
                <td className="font-mono text-[10px] max-w-xs truncate"><a className="link" href={c.stream_url} target="_blank" rel="noreferrer">{c.stream_url}</a></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}


function AudiobooksPage() {
  const [items, setItems] = useState([]);
  const [q, setQ] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState(null);
  const load = () => api.audiobooks.list().then(setItems).catch(()=>[]).finally(()=>setLoading(false));
  useEffect(() => { load(); }, []);
  async function searchGrab(id) {
    setMsg('Searching…');
    try {
      const r = await api.audiobooks.searchNow(id);
      setMsg(r.found ? `Grabbed: ${r.title}` : 'No release found');
      load();
    } catch(e) { setMsg(String(e.message||e)); }
  }
  return (
    <div className="space-y-6 max-w-4xl">
      <h1 className="mr-page-title">Audiobooks</h1>
      <p className="text-sm text-base-content/50">Open Library search · Prowlarr audiobook grabs · organize to AUDIOBOOKS_LIBRARY_PATH</p>
      <form className="flex gap-2" onSubmit={async e=>{e.preventDefault(); setResults(await api.audiobooks.search(q));}}>
        <input className="input input-bordered flex-1" value={q} onChange={e=>setQ(e.target.value)} placeholder="Title or author…"/>
        <button className="btn btn-primary">Search</button>
      </form>
      {results.length>0 && results.map(r=>(
        <div key={r.external_id} className="flex justify-between items-center py-2 border-b border-base-300">
          <div><div className="font-medium text-sm">{r.title}</div><div className="text-xs opacity-50">{r.year} {r.overview}</div></div>
          <button className="btn btn-xs btn-primary" onClick={async()=>{await api.audiobooks.add(r); setResults([]); load();}}>Add</button>
        </div>
      ))}
      {msg && <div className="alert alert-info text-sm py-2">{msg}</div>}
      <h2 className="font-semibold">Library ({items.length})</h2>
      {loading ? <span className="loading loading-spinner"/> : items.map(b=>(
        <div key={b.id} className="flex justify-between items-center py-1 gap-2">
          <span className="flex-1">{b.title} <span className="badge badge-xs">{b.status}</span></span>
          <button className="btn btn-ghost btn-xs" onClick={()=>searchGrab(b.id)}>Search</button>
          <button className="btn btn-ghost btn-xs text-error" onClick={async()=>{await api.audiobooks.remove(b.id); load();}}>Del</button>
        </div>
      ))}
    </div>
  );
}

function CalendarPage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const start = new Date(); start.setDate(start.getDate()-7);
    const end = new Date(); end.setDate(end.getDate()+30);
    const fmt = d => d.toISOString().slice(0,10);
    api.calendar.list(fmt(start), fmt(end)).then(setItems).catch(()=>[]).finally(()=>setLoading(false));
  }, []);
  const byDate = {};
  items.forEach(it => { (byDate[it.air_date] = byDate[it.air_date]||[]).push(it); });
  const dates = Object.keys(byDate).sort();
  const today = new Date().toISOString().slice(0,10);
  return (
    <div className="space-y-6 max-w-4xl">
      <h1 className="mr-page-title">Calendar</h1>
      <p className="text-sm text-base-content/50">TV air dates — past 7 days through next 30</p>
      {loading ? <span className="loading loading-spinner"/> : dates.length===0 ? (
        <p className="text-base-content/40">No episodes with air dates in range. Add series and refresh metadata.</p>
      ) : dates.map(d => (
        <div key={d} className="card mr-panel border-0">
          <div className="card-body p-4 gap-2">
            <h2 className={`font-semibold ${d===today?'text-primary':''}`}>{d}{d===today?' · Today':''}</h2>
            {byDate[d].map(ep => (
              <div key={ep.episode_id} className="flex items-center gap-3 text-sm">
                <span className="font-mono text-xs opacity-60 w-16">S{String(ep.season_number).padStart(2,'0')}E{String(ep.episode_number).padStart(2,'0')}</span>
                <span className="font-medium flex-1">{ep.series_title}{ep.episode_title?` — ${ep.episode_title}`:''}</span>
                <span className={`badge badge-xs ${ep.has_file?'badge-success':ep.status==='downloading'?'badge-info':'badge-ghost'}`}>{ep.has_file?'downloaded':ep.status}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function SmartListsPage() {
  const [items, setItems] = useState([]);
  const [name, setName] = useState('');
  const [listId, setListId] = useState('');
  const [minYear, setMinYear] = useState('');
  const [minVote, setMinVote] = useState('');
  const [msg, setMsg] = useState(null);
  const load = () => api.smartlists.list().then(setItems).catch(()=>[]);
  useEffect(() => { load(); }, []);
  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex justify-between items-start flex-wrap gap-2">
        <div>
          <h1 className="mr-page-title">Smart Lists</h1>
          <p className="text-sm text-base-content/50">TMDb lists / discover → auto-add wanted movies on a schedule</p>
        </div>
        <button className="btn btn-sm btn-primary" onClick={async()=>{ const r=await api.smartlists.runAll(); setMsg(`Ran ${r.lists} lists, added ${r.added}`); load(); }}>Run all now</button>
      </div>
      <div className="card mr-panel border-0">
        <div className="card-body gap-2">
          <h2 className="font-semibold">Add TMDb list</h2>
          <div className="flex flex-wrap gap-2">
            <input className="input input-bordered input-sm" placeholder="Name" value={name} onChange={e=>setName(e.target.value)} />
            <input className="input input-bordered input-sm" placeholder="TMDb list ID" value={listId} onChange={e=>setListId(e.target.value)} />
            <input className="input input-bordered input-sm w-24" placeholder="Min year" value={minYear} onChange={e=>setMinYear(e.target.value)} />
            <input className="input input-bordered input-sm w-24" placeholder="Min ★" value={minVote} onChange={e=>setMinVote(e.target.value)} />
            <button className="btn btn-sm btn-primary" onClick={async()=>{
              await api.smartlists.add({
                name: name||`List ${listId}`, source:'tmdb_list', source_ref:String(listId),
                min_year: minYear?Number(minYear):null, min_vote_average: minVote?Number(minVote):null,
              });
              setName(''); setListId(''); setMinYear(''); setMinVote(''); load();
            }}>Add</button>
          </div>
          <p className="text-xs opacity-50">Or discover: source tmdb_discover with min year/vote filters (leave list ID as "discover").</p>
          <button className="btn btn-xs btn-ghost w-fit" onClick={async()=>{
            await api.smartlists.add({
              name: name||`Discover ${minYear||''}+`, source:'tmdb_discover', source_ref:'discover',
              min_year: minYear?Number(minYear):null, max_year: minYear?Number(minYear):null,
              min_vote_average: minVote?Number(minVote):null,
            });
            load();
          }}>Add discover rule instead</button>
        </div>
      </div>
      {msg && <div className="alert alert-info text-sm py-2">{msg}</div>}
      <table className="table table-sm">
        <thead><tr><th>Name</th><th>Source</th><th>Filters</th><th>Last run</th><th></th></tr></thead>
        <tbody>
          {items.map(s=>(
            <tr key={s.id}>
              <td className="font-medium">{s.name} {!s.enabled && <span className="badge badge-ghost badge-xs">off</span>}</td>
              <td className="text-xs">{s.source}:{s.source_ref}</td>
              <td className="text-xs">{[s.min_year&&`≥${s.min_year}`, s.min_vote_average&&`★${s.min_vote_average}+`].filter(Boolean).join(' ')||'—'}</td>
              <td className="text-xs">{s.last_run_at?`${s.last_run_at.slice(0,16)} (+${s.last_added_count})`:'never'}</td>
              <td className="flex gap-1">
                <button className="btn btn-ghost btn-xs" onClick={async()=>{ const r=await api.smartlists.run(s.id); setMsg(`Added ${r.added}`); load(); }}>Run</button>
                <button className="btn btn-ghost btn-xs text-error" onClick={async()=>{await api.smartlists.remove(s.id); load();}}>Del</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}


function VpnSettingsPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const load = () => {
    setLoading(true);
    api.settings.vpn().then(setData).catch(e=>setErr(String(e.message||e))).finally(()=>setLoading(false));
  };
  useEffect(() => { load(); const t=setInterval(load, 15000); return ()=>clearInterval(t); }, []);
  const st = data?.status || {};
  const healthy = st.healthy;
  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex justify-between items-start">
        <div>
          <h1 className="mr-page-title">VPN</h1>
          <p className="text-sm text-base-content/50">Gluetun / tunnel health · kill switch blocks grabs when down</p>
        </div>
        <button className="btn btn-sm" onClick={load}>Refresh</button>
      </div>
      {loading && !data ? <span className="loading loading-spinner"/> : err ? (
        <div className="alert alert-error text-sm">{err}</div>
      ) : (
        <>
          <div className={`alert ${!data?.enabled?'alert-warning':healthy?'alert-success':'alert-error'} text-sm`}>
            <span>
              {!data?.enabled ? 'VPN checks disabled (VPN_ENABLED=false)' :
                healthy ? `Tunnel healthy · ${st.public_ip||'ip?'}${st.country?` · ${st.country}`:''}` :
                `Tunnel unhealthy — grabs ${data.kill_switch?'BLOCKED':'allowed (kill switch off)'}`}
            </span>
          </div>
          <div className="card mr-panel border-0">
            <div className="card-body gap-1 text-sm">
              <div className="flex justify-between"><span className="opacity-60">Enabled</span><span>{String(data.enabled)}</span></div>
              <div className="flex justify-between"><span className="opacity-60">Provider</span><span>{data.provider}</span></div>
              <div className="flex justify-between"><span className="opacity-60">Gluetun URL</span><span className="font-mono text-xs">{data.gluetun_url||'—'}</span></div>
              <div className="flex justify-between"><span className="opacity-60">Kill switch</span><span>{String(data.kill_switch)}</span></div>
              <div className="flex justify-between"><span className="opacity-60">Expected country</span><span>{data.expected_country||'any'}</span></div>
              <div className="flex justify-between"><span className="opacity-60">Public IP</span><span className="font-mono">{st.public_ip||'—'}</span></div>
              <div className="flex justify-between"><span className="opacity-60">Country</span><span>{st.country||'—'}</span></div>
            </div>
          </div>
          <div className="text-xs opacity-50 space-y-1">
            <p>Configure via environment (restart required):</p>
            <pre className="bg-base-300 p-3 rounded text-[11px] overflow-x-auto">{`VPN_ENABLED=true
VPN_PROVIDER=gluetun
VPN_GLUETUN_URL=http://gluetun:8000
VPN_KILL_SWITCH=true
VPN_EXPECTED_COUNTRY=NL`}</pre>
            <p>Route qBittorrent through the same Gluetun network so torrents exit via VPN. mediaos kill switch only blocks new grabs when the tunnel reports unhealthy.</p>
          </div>
        </>
      )}
    </div>
  );
}


/* ── Requests (native Overseerr/Jellyseerr replacement) ─────────────────── */
const REQUEST_MEDIA_TYPES = [
  { key:'movie',     label:'Movie',      search:q=>api.movies.search(q) },
  { key:'tv',        label:'TV Show',    search:q=>api.tv.search(q) },
  { key:'music',     label:'Music',      search:q=>api.music.search(q) },
  { key:'book',      label:'Book',       search:q=>api.books.search(q) },
  { key:'audiobook', label:'Audiobook',  search:q=>api.audiobooks.search(q) },
];

function RequestStatusBadge({ status }) {
  const cls = status==='pending' ? 'badge-warning' : status==='approved' ? 'badge-success' : status==='denied' ? 'badge-error' : 'badge-ghost';
  return <span className={`badge badge-sm ${cls}`}>{status}</span>;
}

function NewRequestModal({ onClose, onRequested }) {
  const [mediaType, setMediaType] = useState('movie');
  const [q, setQ] = useState('');
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [note, setNote] = useState('');
  const [err, setErr] = useState(null);

  const typeDef = REQUEST_MEDIA_TYPES.find(t=>t.key===mediaType);

  useEffect(()=>{
    if (!q.trim()) { setResults([]); return; }
    setSearching(true);
    const h = setTimeout(async()=>{
      try { setResults(await typeDef.search(q) || []); } catch(e) { setResults([]); }
      setSearching(false);
    }, 350);
    return ()=>clearTimeout(h);
  }, [q, mediaType]);

  async function submit(item) {
    setBusyId(item.external_id); setErr(null);
    try {
      await api.requests.create({
        media_type: mediaType,
        external_id: item.external_id,
        title: item.title || item.artist_name || 'Untitled',
        year: item.year || null,
        overview: item.overview || null,
        poster_path: item.poster_path || null,
        artist_name: item.artist_name || item.artist || null,
        note: note || null,
      });
      onRequested();
    } catch(e) { setErr(String(e.message || e)); }
    setBusyId(null);
  }

  return (
    <div className="modal modal-open" onClick={onClose}>
      <div className="modal-box max-w-lg p-0 overflow-hidden" onClick={e=>e.stopPropagation()}>
        <div className="flex items-center gap-2 px-4 py-3 border-b border-base-300">
          <select className="select select-sm bg-base-200 border-base-300" value={mediaType} onChange={e=>{setMediaType(e.target.value); setResults([]);}}>
            {REQUEST_MEDIA_TYPES.map(t=><option key={t.key} value={t.key}>{t.label}</option>)}
          </select>
          <input autoFocus className="input input-sm flex-1 bg-transparent border-none shadow-none focus:outline-none text-sm"
            placeholder="Search…" value={q} onChange={e=>setQ(e.target.value)} />
          <button className="btn btn-ghost btn-xs btn-square" onClick={onClose}><Ic.X /></button>
        </div>
        <div className="px-4 pt-3">
          <input className="input input-bordered input-xs w-full" placeholder="Note (optional)" value={note} onChange={e=>setNote(e.target.value)} />
        </div>
        {err && <div className="alert alert-error text-xs py-1.5 mx-4 mt-2">{err}</div>}
        <div className="max-h-96 overflow-y-auto divide-y divide-base-300 mt-2">
          {searching && <div className="p-6 text-center text-sm text-base-content/50">Searching…</div>}
          {!searching && q && !results.length && <div className="p-6 text-center text-sm text-base-content/50">No results found.</div>}
          {results.map(r=>(
            <div key={r.external_id} className="flex items-center gap-3 px-4 py-2.5 hover:bg-base-200">
              {r.poster_path
                ? <img className="w-10 h-14 object-cover rounded flex-shrink-0 bg-base-300" src={TMDB+r.poster_path} alt="" />
                : <div className="w-10 h-14 rounded bg-base-300 flex items-center justify-center text-base-content/30 font-bold text-lg flex-shrink-0">{(r.title||r.artist_name||'?')[0]}</div>}
              <div className="flex-1 min-w-0">
                <div className="font-medium text-sm truncate">{r.title || r.artist_name}</div>
                <div className="text-xs text-base-content/50 font-mono">{r.year||'—'}</div>
              </div>
              <button className="btn btn-sm btn-outline" disabled={busyId===r.external_id} onClick={()=>submit(r)}>
                {busyId===r.external_id?'Requesting…':'Request'}
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function RequestsPage() {
  const [tab, setTab] = useState('pending');
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState(false);
  const [msg, setMsg] = useState(null);

  const load = () => {
    setLoading(true);
    api.requests.list(tab==='all' ? undefined : tab).then(setItems).catch(()=>setItems([])).finally(()=>setLoading(false));
  };
  useEffect(() => { load(); }, [tab]);

  async function approve(r) {
    setMsg(null);
    try { await api.requests.approve(r.id); setMsg(`Approved "${r.title}" — searching now.`); load(); }
    catch(e) { setMsg(String(e.message||e)); }
  }
  async function deny(r) {
    const reason = prompt('Reason (optional)') || null;
    try { await api.requests.deny(r.id, reason); load(); } catch(e) { setMsg(String(e.message||e)); }
  }
  async function cancel(r) {
    if (!confirm(`Cancel request for "${r.title}"?`)) return;
    try { await api.requests.cancel(r.id); load(); } catch(e) {}
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex justify-between items-start">
        <div>
          <h1 className="mr-page-title">Requests</h1>
          <p className="text-sm text-base-content/50">Submit → approve → auto-add + auto-search</p>
        </div>
        <button className="btn btn-sm btn-primary" onClick={()=>setModal(true)}>
          <span className="w-4 h-4"><Ic.Plus /></span> New request
        </button>
      </div>

      <div className="tabs tabs-boxed w-fit">
        {['pending','approved','denied','all'].map(t=>(
          <a key={t} className={`tab capitalize ${tab===t?'tab-active':''}`} onClick={()=>setTab(t)}>{t}</a>
        ))}
      </div>

      {msg && <div className="alert alert-info text-sm py-2">{msg}</div>}

      {loading ? <span className="loading loading-spinner"/> : items.length===0 ? (
        <div className="text-center py-16 text-base-content/40">
          <div className="w-14 h-14 mx-auto mb-3 text-base-content/20"><Ic.Inbox /></div>
          <p className="text-sm">No {tab==='all'?'':tab} requests.</p>
        </div>
      ) : (
        <div className="divide-y divide-base-300">
          {items.map(r=>(
            <div key={r.id} className="flex items-center gap-3 py-3">
              {r.poster_path
                ? <img className="w-10 h-14 object-cover rounded flex-shrink-0 bg-base-300" src={TMDB+r.poster_path} alt="" />
                : <div className="w-10 h-14 rounded bg-base-300 flex items-center justify-center text-base-content/30 font-bold text-lg flex-shrink-0">{(r.title||'?')[0]}</div>}
              <div className="flex-1 min-w-0">
                <div className="font-medium text-sm truncate">{r.title} {r.year?<span className="opacity-50 font-normal">({r.year})</span>:null}</div>
                <div className="text-xs text-base-content/50 flex gap-2 items-center flex-wrap">
                  <span className="badge badge-ghost badge-xs uppercase">{r.media_type}</span>
                  {r.requested_by && <span>by {r.requested_by}</span>}
                  {r.note && <span className="italic truncate max-w-[16rem]">"{r.note}"</span>}
                  <span className="font-mono">{r.created_at ? new Date(r.created_at).toLocaleDateString() : ''}</span>
                </div>
              </div>
              <RequestStatusBadge status={r.status} />
              {r.status==='pending' ? (
                <div className="flex gap-1">
                  <button className="btn btn-success btn-xs" onClick={()=>approve(r)}>Approve</button>
                  <button className="btn btn-ghost btn-xs text-error" onClick={()=>deny(r)}>Deny</button>
                </div>
              ) : (
                <button className="btn btn-ghost btn-xs text-error" onClick={()=>cancel(r)}>Remove</button>
              )}
            </div>
          ))}
        </div>
      )}

      {modal && <NewRequestModal onClose={()=>setModal(false)} onRequested={()=>{ setModal(false); setTab('pending'); load(); }} />}
    </div>
  );
}

function QueuePage() {
  const [items, setItems] = useState([]);
  const [hist, setHist] = useState({downloads:[], events:[]});
  const [tab, setTab] = useState('queue');
  const load = () => {
    api.queue.list().then(setItems).catch(()=>setItems([]));
    api.queue.history().then(setHist).catch(()=>setHist({downloads:[],events:[]}));
  };
  useEffect(() => { load(); const i=setInterval(load, 10000); return ()=>clearInterval(i); }, []);
  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex justify-between items-start">
        <div>
          <h1 className="mr-page-title">Queue &amp; History</h1>
          <p className="text-sm text-base-content/50">Live qB progress · download records · activity events</p>
        </div>
        <button className="btn btn-sm" onClick={load}>Refresh</button>
      </div>
      <div className="tabs tabs-boxed w-fit">
        <a className={`tab ${tab==='queue'?'tab-active':''}`} onClick={()=>setTab('queue')}>Queue ({items.length})</a>
        <a className={`tab ${tab==='history'?'tab-active':''}`} onClick={()=>setTab('history')}>History</a>
        <a className={`tab ${tab==='events'?'tab-active':''}`} onClick={()=>setTab('events')}>Events</a>
      </div>
      {tab==='queue' && (
        <table className="table table-sm">
          <thead><tr><th>Title</th><th>Type</th><th>Progress</th><th>State</th><th>Score</th><th></th></tr></thead>
          <tbody>
            {items.length===0 ? <tr><td colSpan={6} className="opacity-40">Queue empty</td></tr> :
              items.map(q=>(
                <tr key={q.download_id}>
                  <td className="font-medium text-sm">{q.title}<div className="text-xs opacity-50 truncate max-w-xs">{q.release_title}</div></td>
                  <td className="text-xs">{q.media_type}</td>
                  <td className="font-mono text-xs">{q.progress!=null?`${Math.round(q.progress*100)}%`:'—'}</td>
                  <td className="text-xs">{q.qbit_state||q.status}</td>
                  <td className="font-mono text-xs">{q.quality_score??'—'}</td>
                  <td><button className="btn btn-ghost btn-xs text-error" onClick={async()=>{await api.queue.remove(q.download_id); load();}}>Remove</button></td>
                </tr>
              ))}
          </tbody>
        </table>
      )}
      {tab==='history' && (
        <table className="table table-sm">
          <thead><tr><th>When</th><th>Title</th><th>Status</th><th>Indexer</th><th>Score</th></tr></thead>
          <tbody>
            {(hist.downloads||[]).map(d=>(
              <tr key={d.download_id}>
                <td className="text-xs font-mono">{d.added_at?new Date(d.added_at).toLocaleString():''}</td>
                <td className="text-sm">{d.title}<div className="text-xs opacity-50">{d.release_title}</div></td>
                <td><span className="badge badge-sm">{d.status}</span></td>
                <td className="text-xs">{d.indexer||'—'}</td>
                <td className="font-mono text-xs">{d.quality_score??'—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {tab==='events' && (
        <table className="table table-sm">
          <thead><tr><th>When</th><th>Event</th><th>Message</th></tr></thead>
          <tbody>
            {(hist.events||[]).map(e=>(
              <tr key={e.id}>
                <td className="text-xs font-mono whitespace-nowrap">{e.created_at?new Date(e.created_at).toLocaleString():''}</td>
                <td><span className="badge badge-sm">{e.event}</span></td>
                <td className="text-sm">{e.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function IndexersPage() {
  const [items, setItems] = useState([]);
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [key, setKey] = useState('');
  const [msg, setMsg] = useState(null);
  const load = () => api.indexers.list().then(setItems).catch(()=>[]);
  useEffect(() => { load(); }, []);
  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="mr-page-title">Indexers</h1>
        <p className="text-sm text-base-content/50">Built-in Torznab/Newznab — works alongside or instead of Prowlarr</p>
      </div>
      <div className="card mr-panel border-0">
        <div className="card-body gap-2">
          <h2 className="font-semibold">Add Torznab indexer</h2>
          <div className="flex flex-wrap gap-2">
            <input className="input input-bordered input-sm" placeholder="Name" value={name} onChange={e=>setName(e.target.value)} />
            <input className="input input-bordered input-sm flex-1 min-w-[14rem]" placeholder="https://indexer/api" value={url} onChange={e=>setUrl(e.target.value)} />
            <input className="input input-bordered input-sm" placeholder="API key" value={key} onChange={e=>setKey(e.target.value)} />
            <button className="btn btn-sm btn-primary" onClick={async()=>{
              await api.indexers.add({name, url, api_key:key||null, kind:'torznab'});
              setName(''); setUrl(''); setKey(''); load();
            }}>Add</button>
          </div>
        </div>
      </div>
      {msg && <div className="alert alert-info text-sm py-2">{typeof msg==='string'?msg:JSON.stringify(msg)}</div>}
      <table className="table table-sm">
        <thead><tr><th>Name</th><th>URL</th><th>Status</th><th></th></tr></thead>
        <tbody>
          {items.map(ix=>(
            <tr key={ix.id}>
              <td className="font-medium">{ix.name} {!ix.enabled && <span className="badge badge-xs">off</span>}</td>
              <td className="text-xs font-mono max-w-xs truncate">{ix.url}</td>
              <td className="text-xs">{ix.last_error?`err: ${ix.last_error}`:(ix.last_ok_at?`ok ${ix.last_ok_at.slice(0,16)}`:'untested')}</td>
              <td className="flex gap-1">
                <button className="btn btn-ghost btn-xs" onClick={async()=>{ const r=await api.indexers.test(ix.id); setMsg(r); load(); }}>Test</button>
                <button className="btn btn-ghost btn-xs text-error" onClick={async()=>{await api.indexers.remove(ix.id); load();}}>Del</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}


function IntegrationsPage() {
  const [data, setData] = useState(null);
  const [jdupes, setJdupes] = useState(null);
  useEffect(() => { fetch('/api/tools/integrations').then(r=>r.json()).then(setData).catch(()=>{}); }, []);
  return (
    <div className="space-y-6 max-w-3xl">
      <h1 className="mr-page-title">Integrations</h1>
      <p className="text-sm text-base-content/50">LunaSea · Cross-Seed · Unpack · jdupes</p>
      {!data ? <span className="loading loading-spinner"/> : (
        <div className="space-y-4">
          <div className="card mr-panel border-0"><div className="card-body gap-1 text-sm">
            <h2 className="font-semibold">Jellyseerr</h2>
            <p>Settings → Services → add <b>Radarr</b> and <b>Sonarr</b> both pointing at mediaos URL.</p>
            <p className="text-xs opacity-60">API key = ARR_API_KEY · root folders and quality profiles come from mediaos shim</p>
          </div></div>
          <div className="card mr-panel border-0"><div className="card-body gap-1 text-sm">
            <h2 className="font-semibold">LunaSea</h2>
            <p>Point Sonarr/Radarr host at this mediaos URL. API key = <code>ARR_API_KEY</code> or <code>AUTH_API_KEY</code>.</p>
            <p className="text-xs opacity-60">Shim: {data.lunasea.arr_api} — library, calendar, queue, history, search commands</p>
          </div></div>
          <div className="card mr-panel border-0"><div className="card-body gap-1 text-sm">
            <h2 className="font-semibold">Cross-Seed</h2>
            <p>{data.cross_seed.configured ? `Configured → ${data.cross_seed.url}` : 'Set CROSS_SEED_URL + CROSS_SEED_API_KEY'}</p>
            <p className="text-xs opacity-60">Notifies on organize ({data.cross_seed.notifies_on})</p>
          </div></div>
          <div className="card mr-panel border-0"><div className="card-body gap-1 text-sm">
            <h2 className="font-semibold">Unpack</h2>
            <p>{data.unpack.enabled ? 'Enabled' : 'Disabled'} · formats: {(data.unpack.formats||[]).join(', ')}</p>
            <p className="text-xs opacity-60">Extracts archives before organize (needs unrar/7z on host for non-zip)</p>
          </div></div>
          <div className="card mr-panel border-0"><div className="card-body gap-2 text-sm">
            <h2 className="font-semibold">jdupes</h2>
            <p>{data.jdupes.enabled ? 'Enabled' : 'Disabled'} · binary: {data.jdupes.binary} · hardlink: {String(data.jdupes.hardlink_mode)}</p>
            <button className="btn btn-sm btn-primary w-fit" onClick={async()=>{
              const r = await fetch('/api/tools/jdupes/scan',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}).then(x=>x.json());
              setJdupes(r);
            }}>Scan libraries for duplicates</button>
            {jdupes && <pre className="text-xs bg-base-300 p-2 rounded overflow-auto max-h-48">{JSON.stringify(jdupes,null,2)}</pre>}
          </div></div>
        </div>
      )}
    </div>
  );
}


function WantedPage() {
  const [data, setData] = useState({ movies:[], episodes:[], music:[], books:[], audiobooks:[], counts:{} });
  const [tab, setTab] = useState('movies');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(null);
  const [msg, setMsg] = useState(null);
  const load = () => { setLoading(true); api.wanted.list().then(setData).catch(()=>{}).finally(()=>setLoading(false)); };
  useEffect(() => { load(); }, []);
  async function searchOne(kind, id) {
    setBusy(kind+'-'+id); setMsg(null);
    try {
      const fn = {movie:api.wanted.searchMovie, episode:api.wanted.searchEpisode, music:api.wanted.searchMusic, book:api.wanted.searchBook, audiobook:api.wanted.searchAudiobook}[kind];
      const r = await fn(id);
      setMsg(r.found ? ('Grabbed: '+(r.title||'release')+' ('+(r.indexer||'?')+')') : (r.error || 'No release found'));
      load();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(null);
  }
  async function searchAuto(scope) {
    setBusy('auto-'+scope); setMsg(null);
    try {
      const r = await api.wanted.searchAll(scope==='all'?null:scope, 50);
      const parts = Object.entries(r).filter(([k,v])=>typeof v==='number'&&v>0).map(([k,v])=>k+': '+v);
      setMsg(parts.length ? ('Automatic search grabbed — '+parts.join(', ')) : 'Automatic search finished — nothing new grabbed');
      load();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(null);
  }
  const c = data.counts || {};
  const tabs = [
    { key:'movies', label:'Movies ('+(c.movies||0)+')' },
    { key:'episodes', label:'TV ('+(c.episodes||0)+')' },
    { key:'music', label:'Music ('+(c.music||0)+')' },
    { key:'books', label:'Books ('+(c.books||0)+')' },
    { key:'audiobooks', label:'Audiobooks ('+(c.audiobooks||0)+')' },
  ];
  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex flex-wrap justify-between items-start gap-3">
        <div>
          <h1 className="mr-page-title">Wanted</h1>
          <p className="mr-page-sub">Missing monitored items — search one manually or run automatic search</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn btn-sm btn-ghost" onClick={load} disabled={!!busy}>Refresh</button>
          <button className="btn btn-sm btn-primary" disabled={!!busy} onClick={()=>searchAuto(tab==='episodes'?'tv':tab)}>
            {busy&&String(busy).startsWith('auto')?'Searching…':'Auto-search tab'}
          </button>
          <button className="btn btn-sm btn-secondary" disabled={!!busy} onClick={()=>searchAuto('all')}>Auto-search all</button>
        </div>
      </div>
      {msg && <div className="alert alert-info text-sm py-2"><span>{msg}</span></div>}
      <div className="tabs tabs-boxed w-fit flex-wrap">
        {tabs.map(t=>(<a key={t.key} className={'tab '+(tab===t.key?'tab-active':'')} onClick={()=>setTab(t.key)}>{t.label}</a>))}
      </div>
      {loading ? <span className="loading loading-spinner text-primary"/> : (
        <div className="mr-panel overflow-x-auto">
          {tab==='movies' && <table className="table table-sm"><thead><tr><th>Title</th><th>Year</th><th>Status</th><th>Last search</th><th></th></tr></thead><tbody>
            {(data.movies||[]).length===0?<tr><td colSpan={5} className="opacity-40">No missing movies</td></tr>:
              data.movies.map(m=>(<tr key={m.id}><td className="font-medium">{m.title}</td><td className="text-xs opacity-50">{m.year||'—'}</td><td><span className="badge badge-sm">{m.status}</span></td><td className="text-xs font-mono">{m.last_searched_at?new Date(m.last_searched_at).toLocaleString():'never'}</td>
              <td><button className="btn btn-xs btn-primary" disabled={!!busy} onClick={()=>searchOne('movie',m.id)}>{busy==='movie-'+m.id?'…':'Search'}</button></td></tr>))}</tbody></table>}
          {tab==='episodes' && <table className="table table-sm"><thead><tr><th>Series</th><th>Ep</th><th>Title</th><th>Air</th><th>Status</th><th></th></tr></thead><tbody>
            {(data.episodes||[]).length===0?<tr><td colSpan={6} className="opacity-40">No missing episodes</td></tr>:
              data.episodes.map(e=>(<tr key={e.id}><td className="font-medium text-sm">{e.series_title}</td><td className="font-mono text-xs">S{String(e.season_number).padStart(2,'0')}E{String(e.episode_number).padStart(2,'0')}</td><td className="text-sm opacity-70">{e.title||'—'}</td><td className="text-xs">{e.air_date||'—'}</td><td><span className="badge badge-sm">{e.status}</span></td>
              <td><button className="btn btn-xs btn-primary" disabled={!!busy} onClick={()=>searchOne('episode',e.id)}>{busy==='episode-'+e.id?'…':'Search'}</button></td></tr>))}</tbody></table>}
          {tab==='music' && <table className="table table-sm"><thead><tr><th>Artist</th><th>Album</th><th>Year</th><th>Status</th><th></th></tr></thead><tbody>
            {(data.music||[]).length===0?<tr><td colSpan={5} className="opacity-40">No missing albums</td></tr>:
              data.music.map(m=>(<tr key={m.id}><td className="text-sm">{m.artist_name||'—'}</td><td className="font-medium">{m.title}</td><td className="text-xs opacity-50">{m.year||'—'}</td><td><span className="badge badge-sm">{m.status}</span></td>
              <td><button className="btn btn-xs btn-primary" disabled={!!busy} onClick={()=>searchOne('music',m.id)}>{busy==='music-'+m.id?'…':'Search'}</button></td></tr>))}</tbody></table>}
          {tab==='books' && <table className="table table-sm"><thead><tr><th>Title</th><th>Author</th><th>Status</th><th></th></tr></thead><tbody>
            {(data.books||[]).length===0?<tr><td colSpan={4} className="opacity-40">No missing books</td></tr>:
              data.books.map(b=>(<tr key={b.id}><td className="font-medium">{b.title}</td><td className="text-sm opacity-60">{b.overview||'—'}</td><td><span className="badge badge-sm">{b.status}</span></td>
              <td><button className="btn btn-xs btn-primary" disabled={!!busy} onClick={()=>searchOne('book',b.id)}>{busy==='book-'+b.id?'…':'Search'}</button></td></tr>))}</tbody></table>}
          {tab==='audiobooks' && <table className="table table-sm"><thead><tr><th>Title</th><th>Author</th><th>Status</th><th></th></tr></thead><tbody>
            {(data.audiobooks||[]).length===0?<tr><td colSpan={4} className="opacity-40">No missing audiobooks</td></tr>:
              data.audiobooks.map(a=>(<tr key={a.id}><td className="font-medium">{a.title}</td><td className="text-sm opacity-60">{a.overview||'—'}</td><td><span className="badge badge-sm">{a.status}</span></td>
              <td><button className="btn btn-xs btn-primary" disabled={!!busy} onClick={()=>searchOne('audiobook',a.id)}>{busy==='audiobook-'+a.id?'…':'Search'}</button></td></tr>))}</tbody></table>}
        </div>
      )}
    </div>
  );
}


function SetupWizardPage({ onDone }) {
  const [st, setSt] = useState(null);
  const [form, setForm] = useState({ tmdb_api_key:'', tvdb_api_key:'', qbit_url:'', qbit_username:'admin', qbit_password:'', prowlarr_url:'', prowlarr_api_key:'', movies_library_path:'/movies', tv_library_path:'/tv', sabnzbd_url:'', sabnzbd_api_key:'', real_debrid_token:'', opensubtitles_api_key:'', auth_username:'', auth_password:'', arr_api_key:'' });
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null);
  useEffect(()=>{ api.setup.status().then(setSt).catch(()=>{}); }, []);
  function set(k,v){ setForm(f=>({...f,[k]:v})); }
  async function save() {
    setSaving(true); setMsg(null);
    try {
      const r = await api.setup.complete({ ...form, mark_complete:true });
      setMsg('Saved. Restart container to fully apply env if needed.');
      if (onDone) onDone();
      api.setup.status().then(setSt);
    } catch(e){ setMsg(String(e.message||e)); }
    setSaving(false);
  }
  return (
    <div className="max-w-lg mx-auto space-y-5 py-4">
      <div className="text-center">
        <div className="mr-brand-mark mx-auto mb-3 !w-12 !h-12"><img src="/logo-icon.png" alt="MediaOs" width="48" height="48" className="logo-mark" style={{width:48,height:48,objectFit:"contain"}} draggable={false} /></div>
        <h1 className="mr-page-title">Welcome to mediaos</h1>
        <p className="mr-page-sub">First-run setup — connect metadata, downloads, and library paths</p>
      </div>
      {st && (
        <ul className="text-sm space-y-1 opacity-70">
          {st.steps.map((s,i)=><li key={i}>• {s}</li>)}
        </ul>
      )}
      <div className="mr-panel p-4 space-y-3">
        <label className="form-control"><span className="label-text text-xs">TMDb API key</span>
          <input className="input input-bordered input-sm" value={form.tmdb_api_key} onChange={e=>set('tmdb_api_key',e.target.value)} placeholder="required for movies"/></label>
        <label className="form-control"><span className="label-text text-xs">TVDb API key</span>
          <input className="input input-bordered input-sm" value={form.tvdb_api_key} onChange={e=>set('tvdb_api_key',e.target.value)}/></label>
        <label className="form-control"><span className="label-text text-xs">qBittorrent URL</span>
          <input className="input input-bordered input-sm" value={form.qbit_url} onChange={e=>set('qbit_url',e.target.value)} placeholder="http://qbittorrent:8080"/></label>
        <div className="grid grid-cols-2 gap-2">
          <input className="input input-bordered input-sm" value={form.qbit_username} onChange={e=>set('qbit_username',e.target.value)} placeholder="user"/>
          <input className="input input-bordered input-sm" type="password" value={form.qbit_password} onChange={e=>set('qbit_password',e.target.value)} placeholder="password"/>
        </div>
        <label className="form-control"><span className="label-text text-xs">Prowlarr URL + API key</span>
          <input className="input input-bordered input-sm mb-1" value={form.prowlarr_url} onChange={e=>set('prowlarr_url',e.target.value)} placeholder="http://prowlarr:9696"/>
          <input className="input input-bordered input-sm" value={form.prowlarr_api_key} onChange={e=>set('prowlarr_api_key',e.target.value)} placeholder="api key"/></label>
        <div className="grid grid-cols-2 gap-2">
          <input className="input input-bordered input-sm" value={form.movies_library_path} onChange={e=>set('movies_library_path',e.target.value)} placeholder="/movies"/>
          <input className="input input-bordered input-sm" value={form.tv_library_path} onChange={e=>set('tv_library_path',e.target.value)} placeholder="/tv"/>
        </div>
        <input className="input input-bordered input-sm" placeholder="SABnzbd URL" value={form.sabnzbd_url} onChange={e=>set('sabnzbd_url',e.target.value)} />
        <input className="input input-bordered input-sm" placeholder="SABnzbd API key" value={form.sabnzbd_api_key} onChange={e=>set('sabnzbd_api_key',e.target.value)} />
        <input className="input input-bordered input-sm" placeholder="Real-Debrid token" value={form.real_debrid_token} onChange={e=>set('real_debrid_token',e.target.value)} />
        <input className="input input-bordered input-sm" placeholder="OpenSubtitles API key" value={form.opensubtitles_api_key} onChange={e=>set('opensubtitles_api_key',e.target.value)} />
        <input className="input input-bordered input-sm" placeholder="Admin username" value={form.auth_username} onChange={e=>set('auth_username',e.target.value)} />
        <input className="input input-bordered input-sm" type="password" placeholder="Admin password" value={form.auth_password} onChange={e=>set('auth_password',e.target.value)} />
        <input className="input input-bordered input-sm" placeholder="ARR/Jellyseerr API key" value={form.arr_api_key} onChange={e=>set('arr_api_key',e.target.value)} />
        <button className="btn btn-primary w-full" disabled={saving} onClick={save}>{saving?'Saving…':'Finish setup'}</button>
        {msg && <p className="text-xs opacity-60">{msg}</p>}
        <button className="btn btn-ghost btn-sm w-full" onClick={()=>onDone && onDone()}>Skip for now</button>
      </div>
    </div>
  );
}



function WorkersPage() {
  const [jobs, setJobs] = useState([]);
  const [auto, setAuto] = useState(true);
  const refresh = () => api.parity.workers().then(setJobs).catch(()=>{});
  useEffect(() => {
    refresh();
    if (!auto) return;
    const id = setInterval(refresh, 2000);
    return () => clearInterval(id);
  }, [auto]);
  const statusBadge = (s) => {
    const map = { queued: 'badge-ghost', running: 'badge-info', done: 'badge-success', failed: 'badge-error' };
    return map[s] || 'badge-ghost';
  };
  const running = (jobs||[]).filter(j => j.status === 'running' || j.status === 'queued');
  const done = (jobs||[]).filter(j => j.status === 'done' || j.status === 'failed');
  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="mr-page-title">Workers</h1>
          <p className="mr-page-sub">Rich progress across search, grab, organize, scan, and list sync tasks</p>
        </div>
        <div className="flex gap-2 items-center">
          <label className="label cursor-pointer gap-2 py-0">
            <span className="label-text text-xs">Live</span>
            <input type="checkbox" className="toggle toggle-sm toggle-primary" checked={auto} onChange={e=>setAuto(e.target.checked)} />
          </label>
          <button className="btn btn-sm btn-primary" onClick={()=>api.parity.searchAllJob().then(refresh)}>Queue search-all</button>
          <button className="btn btn-sm btn-ghost" onClick={refresh}>Refresh</button>
        </div>
      </div>

      <div className="grid sm:grid-cols-3 gap-3">
        <div className="mr-panel p-4">
          <div className="text-xs opacity-50">Active</div>
          <div className="text-2xl font-semibold">{running.length}</div>
        </div>
        <div className="mr-panel p-4">
          <div className="text-xs opacity-50">Completed</div>
          <div className="text-2xl font-semibold">{(jobs||[]).filter(j=>j.status==='done').length}</div>
        </div>
        <div className="mr-panel p-4">
          <div className="text-xs opacity-50">Failed</div>
          <div className="text-2xl font-semibold text-error">{(jobs||[]).filter(j=>j.status==='failed').length}</div>
        </div>
      </div>

      <div className="space-y-3">
        <h2 className="font-semibold text-sm opacity-70">Active & queued</h2>
        {running.length === 0 && <div className="mr-panel p-6 text-sm opacity-40">No active workers</div>}
        {running.map(j => (
          <div key={j.id} className="mr-panel p-4 space-y-2">
            <div className="flex justify-between gap-2 items-center">
              <div className="font-mono text-sm">{j.name}</div>
              <span className={'badge badge-sm ' + statusBadge(j.status)}>{j.status}</span>
            </div>
            <progress className="progress progress-primary w-full" value={j.progress||0} max="100" />
            <div className="flex justify-between text-xs opacity-60">
              <span>{j.message || '…'}</span>
              <span>{Math.round(j.progress||0)}%</span>
            </div>
            <div className="text-[10px] opacity-40 font-mono">{j.id} · {j.created_at}</div>
          </div>
        ))}
      </div>

      <div className="mr-panel overflow-x-auto">
        <h2 className="font-semibold text-sm p-4 pb-0">History</h2>
        <table className="table table-sm">
          <thead><tr><th>Job</th><th>Status</th><th>Progress</th><th>Message</th><th>Finished</th></tr></thead>
          <tbody>
            {done.length === 0
              ? <tr><td colSpan={5} className="opacity-40">No finished jobs yet</td></tr>
              : done.map(j => (
                <tr key={j.id}>
                  <td className="font-mono text-xs">{j.name}</td>
                  <td><span className={'badge badge-sm ' + statusBadge(j.status)}>{j.status}</span></td>
                  <td>
                    <progress className={'progress w-24 ' + (j.status==='failed'?'progress-error':'progress-success')} value={j.progress||0} max="100" />
                  </td>
                  <td className="text-xs max-w-xs truncate">{j.message || (j.result ? JSON.stringify(j.result).slice(0,80) : '')}</td>
                  <td className="text-xs opacity-50">{j.finished_at || '—'}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}


function ParityPage() {
  const [st, setSt] = useState(null);
  const [jobs, setJobs] = useState([]);
  useEffect(()=>{ api.parity.status().then(setSt).catch(()=>{}); api.parity.workers().then(setJobs).catch(()=>{}); }, []);
  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="mr-page-title">MediaOs parity</h1>
        <p className="mr-page-sub">Feature map, streaming clients, workers</p>
      </div>
      {st && (
        <>
          <div className="mr-panel p-4">
            <h2 className="font-semibold mb-2">Features</h2>
            <div className="grid sm:grid-cols-2 gap-2 text-sm">
              {Object.entries(st.features||{}).map(([k,v])=>(
                <div key={k} className="flex justify-between gap-2 border-b border-base-300/40 py-1">
                  <span className="font-mono text-xs">{k}</span>
                  <span className={'badge badge-sm '+(v.status==='done'?'badge-success':v.status==='partial'?'badge-warning':'badge-ghost')}>{v.status}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="mr-panel p-4">
            <h2 className="font-semibold mb-2">Clients</h2>
            <pre className="text-xs opacity-70 overflow-auto">{JSON.stringify(st.clients,null,2)}</pre>
          </div>
          <div className="mr-panel p-4">
            <h2 className="font-semibold mb-2">Streaming providers</h2>
            <ul className="text-sm space-y-1">{(st.streaming_providers||[]).map(p=>(
              <li key={p.id}>{p.name}: {p.enabled?'on':'off'}</li>
            ))}</ul>
          </div>
        </>
      )}
      <div className="flex gap-2">
        <button className="btn btn-sm btn-primary" onClick={()=>api.parity.searchAllJob().then(()=>api.parity.workers().then(setJobs))}>Queue search-all job</button>
        <button className="btn btn-sm btn-ghost" onClick={()=>api.parity.workers().then(setJobs)}>Refresh jobs</button>
      </div>
      <div className="mr-panel overflow-x-auto">
        <table className="table table-sm"><thead><tr><th>Job</th><th>Status</th><th>Progress</th><th>Message</th></tr></thead>
        <tbody>{(jobs||[]).length===0?<tr><td colSpan={4} className="opacity-40">No jobs</td></tr>:
          jobs.map(j=>(<tr key={j.id}><td className="font-mono text-xs">{j.name}</td><td>{j.status}</td><td>{j.progress}%</td><td className="text-xs">{j.message}</td></tr>))}</tbody></table>
      </div>
    </div>
  );
}


function IptvGuidePage() {
  const [guide, setGuide] = useState(null);
  const [portal, setPortal] = useState('');
  const [mac, setMac] = useState('');
  const [stalker, setStalker] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(()=>{ fetch('/api/livetv/guide').then(r=>r.json()).then(setGuide).catch(()=>{}); }, []);
  async function connectStalker(discover) {
    setBusy(true);
    try {
      const r = await fetch('/api/livetv/stalker/connect',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({portal_url:portal,mac:mac||null,discover})}).then(r=>r.json());
      setStalker(r);
    } catch(e){ setStalker({error:String(e)}); }
    setBusy(false);
  }
  const groups = guide?.groups || {};
  return (
    <div className="space-y-6">
      <div>
        <h1 className="mr-page-title">IPTV Guide</h1>
        <p className="mr-page-sub">Channel grid · Stalker portal · MAC discovery</p>
      </div>
      <div className="mr-panel p-4 space-y-2">
        <h2 className="font-semibold text-sm">Stalker portal</h2>
        <input className="input input-bordered input-sm w-full" placeholder="http://portal.example/c/" value={portal} onChange={e=>setPortal(e.target.value)} />
        <input className="input input-bordered input-sm w-full" placeholder="MAC (optional)" value={mac} onChange={e=>setMac(e.target.value)} />
        <div className="flex gap-2">
          <button className="btn btn-sm btn-primary" disabled={busy||!portal} onClick={()=>connectStalker(false)}>Connect</button>
          <button className="btn btn-sm btn-secondary" disabled={busy||!portal} onClick={()=>connectStalker(true)}>Discover MACs</button>
        </div>
        {stalker && <pre className="text-xs opacity-70 overflow-auto max-h-48">{JSON.stringify(stalker,null,2)}</pre>}
      </div>
      <div className="flex flex-wrap gap-2">
        {(guide?.group_names||[]).map(g=>(<span key={g} className="badge badge-outline">{g} ({(groups[g]||[]).length})</span>))}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {Object.entries(groups).map(([g, chs])=>(
          <div key={g} className="mr-panel p-3">
            <h3 className="font-semibold text-sm mb-2">{g}</h3>
            <ul className="space-y-1 max-h-64 overflow-auto text-sm">
              {(chs||[]).map(ch=>(
                <li key={ch.id} className="flex items-center gap-2">
                  {ch.logo ? <img src={ch.logo} className="w-6 h-6 rounded object-cover" /> : <span className="w-6 h-6 rounded bg-base-300" />}
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium">{ch.name}</div>
                    <div className="text-[10px] opacity-50 truncate">Now: {ch.now||'—'} · Next: {ch.next||'—'}</div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      {(!guide || (guide.total||0)===0) && <p className="opacity-50 text-sm">No channels yet — import M3U/Xtream or connect Stalker.</p>}
    </div>
  );
}


function QualityLabPage() {
  const [factors, setFactors] = useState(null);
  const [title, setTitle] = useState('Movie.Title.2024.2160p.BluRay.REMUX.HDR.Atmos-FRAMESTOR');
  const [result, setResult] = useState(null);
  useEffect(()=>{ fetch('/api/quality-ui/factors').then(r=>r.json()).then(setFactors).catch(()=>{}); }, []);
  async function score() {
    const r = await fetch('/api/quality-ui/score',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title})}).then(r=>r.json());
    setResult(r);
  }
  return (
    <div className="space-y-6 max-w-3xl">
      <div><h1 className="mr-page-title">Quality Lab</h1>
      <p className="mr-page-sub">Dictionarry-class factors · score tester · language profiles</p></div>
      <div className="mr-panel p-4 space-y-2">
        <input className="input input-bordered input-sm w-full font-mono text-xs" value={title} onChange={e=>setTitle(e.target.value)} />
        <button className="btn btn-sm btn-primary" onClick={score}>Score release</button>
        {result && <pre className="text-xs opacity-80 overflow-auto">{JSON.stringify(result,null,2)}</pre>}
      </div>
      {factors && (
        <div className="mr-panel p-4">
          <h2 className="font-semibold mb-2">Factor families (~{factors.factor_families})</h2>
          <div className="grid sm:grid-cols-2 gap-3 text-xs">
            {['resolution','source','codec','hdr','audio'].map(k=>(
              <div key={k}><div className="font-mono opacity-60 mb-1">{k}</div>
              <pre className="opacity-70 overflow-auto max-h-32">{JSON.stringify(factors[k],null,1)}</pre></div>
            ))}
          </div>
          <h3 className="font-semibold mt-4 mb-1">Language profiles</h3>
          <ul className="text-sm">{(factors.language_profiles||[]).map(p=>(
            <li key={p.id}>{p.name}: {(p.languages||[]).join(', ')} · HI {p.hearing_impaired}</li>
          ))}</ul>
        </div>
      )}
    </div>
  );
}

function PageContent({ page, movies, series, refreshMovies, refreshSeries, setPage, theme, setTheme }) {
  switch(page) {
    case 'dashboard':    return <><DashboardPage movies={movies} series={series} setPage={setPage} /><CollectionProgressWidget setPage={setPage} /></>;
    case 'comics':       return <ComicsPage />;
    case 'youtube':      return <YouTubePage />;
    case 'collections':  return <CollectionsPage />;
    case 'podcasts':     return <PodcastsPage />;
    case 'movies':       return <MoviesPage movies={movies} refreshMovies={refreshMovies} />;
    case 'tv':           return <TvPage series={series} refreshSeries={refreshSeries} />;
    case 'discover':     return <DiscoverPage movies={movies} series={series} refreshMovies={refreshMovies} refreshSeries={refreshSeries} />;
    case 'requests':     return <RequestsPage />;
    case 'import':       return <ImportPage movies={movies} series={series} />;
    case 'quality-lab': return <QualityLabPage />;
    case 'workers': return <WorkersPage />;
    case 'parity': return <ParityPage />;
    case 'setup': return <SetupWizardPage onDone={()=>{ if(setPage) setPage('dashboard'); }} />;
    case 'wanted': return <WantedPage />;
    case 'queue':        return <QueuePage />;
    case 'activity':     return <ActivityPage movies={movies} />;
    case 'settings-quality': return <QualityProfilesPage />;
    case 'settings-vpn':     return <VpnSettingsPage />;
    case 'settings-themes': return <ThemesPage currentTheme={theme} setTheme={setTheme} />;
    case 'settings-indexers':  return <IndexersPage />;
    case 'settings-downloads': return <ConfigGroupPage group="downloads" title="Download Clients" Icon={Ic.Download} description="qBittorrent, SABnzbd, NZBGet — changes apply immediately, no restart." />;
    case 'settings-library':   return <ConfigGroupPage group="library" title="Library Storage" Icon={Ic.Folder} description="Library and downloads paths — changes apply immediately, no restart." />;
    case 'settings-system':    return <ConfigGroupPage group="system" title="System" Icon={Ic.Server} description="Search, upgrades, and notification settings — changes apply immediately, no restart." />;
    case 'settings-integrations': return <IntegrationsPage />;
    case 'music':        return <MusicPage />;
    case 'books':        return <BooksPage />;
    case 'audiobooks':   return <AudiobooksPage />;
    case 'calendar':     return <CalendarPage />;
    case 'livetv': return <IptvGuidePage />;
    case 'livetv_old':       return <LiveTvPage />;
    case 'smartlists':   return <SmartListsPage />;
    default:             return <DashboardPage movies={movies} series={series} setPage={setPage} />;
  }
}

/* ── App Root ────────────────────────────────────────────────────────────── */
function App() {
  const [page, setPage] = useState('dashboard');
  const [theme, setThemeState] = useState(storedTheme());
  const [mobileOpen, setMobileOpen] = useState(false);
  const [movies, setMovies] = useState([]);
  const [series, setSeries] = useState([]);
  const [setupNeeded, setSetupNeeded] = useState(false);
  const [setupChecked, setSetupChecked] = useState(false);
  const [pendingRequests, setPendingRequests] = useState(0);

  function setTheme(t) { setThemeState(t); applyTheme(t); }

  const refreshMovies = useCallback(async()=>{
    try { setMovies(await api.movies.list()); } catch(e){}
  }, []);
  const refreshSeries = useCallback(async()=>{
    try { setSeries(await api.tv.list()); } catch(e){}
  }, []);
  const refreshRequests = useCallback(async()=>{
    try { setPendingRequests((await api.requests.list('pending')).length); } catch(e){}
  }, []);

  useEffect(()=>{ refreshMovies(); refreshSeries(); refreshRequests();
    api.setup.status().then(s=>{ setSetupNeeded(!s.complete); setSetupChecked(true); if(!s.complete) setPage('setup'); }).catch(()=>setSetupChecked(true));
    const i = setInterval(refreshRequests, 30000);
    return ()=>clearInterval(i);
  }, []);

  const counts = { movies: movies.length, tv: series.length, music: 0, requests: pendingRequests };

  return (
    <div className="drawer lg:drawer-open min-h-screen mr-shell">
      <input id="mr-drawer" type="checkbox" className="drawer-toggle"
        checked={mobileOpen} onChange={e=>setMobileOpen(e.target.checked)} readOnly />

      <div className="drawer-content flex flex-col mr-main">
        <div className="navbar mr-topbar lg:hidden">
          <label htmlFor="mr-drawer" className="btn btn-ghost btn-square btn-sm" onClick={()=>setMobileOpen(!mobileOpen)}>
            <span className="w-5 h-5"><Ic.Menu /></span>
          </label>
          <div className="mr-brand-mark !w-7 !h-7"><img src="/logo-icon.png" alt="MediaOs" width="22" height="22" className="logo-mark" style={{width:22,height:22,objectFit:"contain"}} draggable={false} /></div>
          <span className="font-bold ml-1 tracking-tight">mediaos</span>
        </div>
        <main className="flex-1 mr-content">
          <PageContent page={page} movies={movies} series={series}
            refreshMovies={refreshMovies} refreshSeries={refreshSeries}
            setPage={setPage} theme={theme} setTheme={setTheme} />
        </main>
        <nav className="mr-bottom-nav lg:hidden">
          {[
            {k:'dashboard', label:'Home', Icon:Ic.Home},
            {k:'wanted', label:'Wanted', Icon:Ic.AlertTri},
            {k:'queue', label:'Queue', Icon:Ic.Download},
            {k:'discover', label:'Discover', Icon:Ic.Compass},
            {k:'settings-system', label:'Settings', Icon:Ic.Settings},
          ].map(i=>(
            <button key={i.k} className={page===i.k||(i.k.startsWith('settings')&&page.startsWith('settings'))?'active':''}
              onClick={()=>setPage(i.k)}>
              <span className="w-5 h-5"><i.Icon /></span>
              {i.label}
            </button>
          ))}
        </nav>
      </div>

      <div className="drawer-side z-30">
        <label htmlFor="mr-drawer" className="drawer-overlay mr-drawer-backdrop" onClick={()=>setMobileOpen(false)} />
        <Sidebar page={page} setPage={p=>{setPage(p);}} counts={counts} onClose={()=>setMobileOpen(false)} />
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
