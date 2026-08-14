/** MediaOS API client + auth fetch wrapper */
import { getToken, setToken } from "./storage.js";

const ADULT_UNLOCK_KEY = 'mediaos_adult_unlock';
function getAdultUnlock() { try { return sessionStorage.getItem(ADULT_UNLOCK_KEY); } catch { return null; } }
function setAdultUnlock(t) { try { if (t) sessionStorage.setItem(ADULT_UNLOCK_KEY, t); else sessionStorage.removeItem(ADULT_UNLOCK_KEY); } catch {} }
function adultFetch(input, init={}) {
  const headers = new Headers(init.headers || {});
  const tok = getAdultUnlock();
  if (tok) headers.set('X-Adult-Unlock', tok);
  return fetch(input, { ...init, headers });
}


const _fetch = window.fetch.bind(window);
window.fetch = (input, init={}) => {
  const headers = new Headers(init.headers || {});
  const tok = getToken();
  if (tok && !headers.has('Authorization')) headers.set('Authorization', 'Bearer ' + tok);
  return _fetch(input, { ...init, headers }).then(async r => {
    if (r.status === 401 && !String(input).includes('/api/auth/')) {
      // Shared login waiter so concurrent 401s share one modal
      try {
        if (!window.__mediaos_auth_waiter) {
          window.__mediaos_auth_waiter = new Promise((resolve) => {
            const done = (ev) => {
              window.removeEventListener('mediaos-auth-credentials', done);
              window.__mediaos_auth_waiter = null;
              resolve(ev.detail || null);
            };
            window.addEventListener('mediaos-auth-credentials', done);
            window.dispatchEvent(new CustomEvent('mediaos-auth-required', { detail: { url: String(input) } }));
            setTimeout(() => {
              window.removeEventListener('mediaos-auth-credentials', done);
              window.__mediaos_auth_waiter = null;
              resolve(null);
            }, 120000);
          });
        }
        const creds = await window.__mediaos_auth_waiter;
        if (creds && creds.username) {
          // Only one caller should hit /login; others reuse token after
          if (!window.__mediaos_auth_login) {
            window.__mediaos_auth_login = (async () => {
              const res = await _fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: creds.username, password: creds.password || '' }),
              });
              const j = await res.json().catch(() => ({}));
              if (j.token) {
                setToken(j.token);
                window.dispatchEvent(new CustomEvent('mediaos-auth-success'));
                return j.token;
              }
              window.dispatchEvent(new CustomEvent('mediaos-auth-failed', { detail: { message: j.detail || j.message || 'Login failed' } }));
              return null;
            })().finally(() => { setTimeout(() => { window.__mediaos_auth_login = null; }, 500); });
          }
          const token = await window.__mediaos_auth_login;
          if (token) {
            return _fetch(input, {
              ...init,
              headers: new Headers({ ...(init.headers || {}), Authorization: 'Bearer ' + token }),
            });
          }
        }
      } catch (_) {}
    }
    return r;
  });
};

/* ── API ─────────────────────────────────────────────────────────────────── */
const api = {
  movies:    { list: ()=>fetch('/api/movies').then(r=>r.json()),
               get: id=>fetch(`/api/movies/${id}`).then(r=>r.json()),
               search: q=>fetch(`/api/movies/search?query=${encodeURIComponent(q)}`).then(r=>r.json()),
               add: (id, opts={})=>fetch('/api/movies',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({external_id:id, ...opts})}),
               update: (id,body)=>fetch(`/api/movies/${id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(typeof body==='boolean'?{monitored:body}:body)}),
               searchNow: id=>fetch(`/api/movies/${id}/search`,{method:'POST'}),
               searchMissing: ()=>fetch('/api/movies/search-missing',{method:'POST'}).then(r=>r.json()),
               interactive: id=>fetch(`/api/movies/${id}/interactive-search`).then(r=>r.json()),
               grab: (id, body)=>fetch(`/api/movies/${id}/grab`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json()),
               refresh: id=>fetch(`/api/movies/${id}/refresh`,{method:'POST'}).then(r=>r.json()),
               file: (id, body)=>fetch(`/api/movies/${id}/file`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json()),
               subtitles: id=>fetch(`/api/movies/${id}/subtitles`,{method:'POST'}).then(r=>r.json()),
               remove: id=>fetch(`/api/movies/${id}`,{method:'DELETE'}) },
  tv:        { list: ()=>fetch('/api/tv').then(r=>r.json()),
               search: q=>fetch(`/api/tv/search?query=${encodeURIComponent(q)}`).then(r=>r.json()),
               add: (id, opts={})=>fetch('/api/tv',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({external_id:id, monitor: opts.monitor||'all', quality_profile: opts.quality_profile||null, search_missing: opts.search_missing!==false})}),
               remove: id=>fetch(`/api/tv/${id}`,{method:'DELETE'}),
               searchMissing: id=>fetch(`/api/tv/${id}/search-missing`,{method:'POST'}).then(r=>r.json()),
               searchSeason: (id,s)=>fetch(`/api/tv/${id}/search-season/${s}`,{method:'POST'}).then(r=>r.json()),
               interactiveEpisode: (epId)=>fetch(`/api/tv/episodes/${epId}/interactive-search`).then(r=>r.json()),
               interactiveSeason: (id,s,packs=true)=>fetch(`/api/tv/${id}/seasons/${s}/interactive-search?packs_only=${packs}`).then(r=>r.json()),
               interactiveSeriesPack: (id)=>fetch(`/api/tv/${id}/interactive-search/series-pack`).then(r=>r.json()),
               grabEpisode: (epId, body)=>fetch(`/api/tv/episodes/${epId}/grab`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json()),
               episodeFile: (epId, body)=>fetch(`/api/tv/episodes/${epId}/file`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json()),

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
               qualityMatrix: ()=>fetch('/api/quality-ui/matrix').then(r=>r.json()),
               qualityMatrixFamily: (f)=>fetch(`/api/quality-ui/matrix/${f}`).then(r=>r.json()),
               qualityMatrixSet: (f,name,score)=>fetch(`/api/quality-ui/matrix/${f}/${encodeURIComponent(name)}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,score})}).then(r=>r.json()),
               qualityMatrixDelete: (f,name)=>fetch(`/api/quality-ui/matrix/${f}/${encodeURIComponent(name)}`,{method:'DELETE'}).then(r=>r.json()),
               qualityMatrixReset: (f)=>fetch(`/api/quality-ui/matrix/reset${f?`?family=${f}`:''}`,{method:'POST'}).then(r=>r.json()),
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
               complete: body=>fetch('/api/setup/complete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json()),
               apply: body=>fetch('/api/setup/apply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json()) },
  wanted:    { list: (mt)=>fetch(`/api/wanted${mt?`?media_type=${mt}`:''}`).then(r=>r.json()),
               searchMovie: id=>fetch(`/api/wanted/movies/${id}/search`,{method:'POST'}).then(r=>r.json()),
               searchEpisode: id=>fetch(`/api/wanted/episodes/${id}/search`,{method:'POST'}).then(r=>r.json()),
               searchMusic: id=>fetch(`/api/wanted/music/${id}/search`,{method:'POST'}).then(r=>r.json()),
               searchBook: id=>fetch(`/api/wanted/books/${id}/search`,{method:'POST'}).then(r=>r.json()),
               searchAudiobook: id=>fetch(`/api/wanted/audiobooks/${id}/search`,{method:'POST'}).then(r=>r.json()),
               searchAdult: id=>fetch(`/api/wanted/adult/${id}/search`,{method:'POST'}).then(r=>r.json()),
               searchAll: (mt,limit=40)=>fetch(`/api/wanted/search-all?limit=${limit}${mt&&mt!=='all'?`&media_type=${mt}`:''}`,{method:'POST'}).then(r=>r.json()) },
  queue:     { list: ()=>fetch('/api/queue').then(r=>r.json()),
               history: ()=>fetch('/api/queue/history').then(r=>r.json()),
               remove: id=>fetch(`/api/queue/${id}`,{method:'DELETE'}) },
  adult: {
    status: ()=>fetch('/api/adult/status').then(r=>r.json()),
    unlock: (passcode)=>fetch('/api/adult/unlock',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({passcode})}).then(r=>r.json()),
    list: ()=>adultFetch('/api/adult').then(r=>r.json()),
    get: (id)=>adultFetch('/api/adult/'+id).then(r=>r.json()),
    add: (body)=>adultFetch('/api/adult',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json()),
    update: (id,body)=>adultFetch('/api/adult/'+id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json()),
    remove: (id)=>adultFetch('/api/adult/'+id,{method:'DELETE'}),
    searchNow: (id)=>adultFetch('/api/adult/'+id+'/search',{method:'POST'}).then(r=>r.json()),
    searchMissing: ()=>adultFetch('/api/adult/search-missing',{method:'POST'}).then(r=>r.json()),
    interactive: (id)=>adultFetch('/api/adult/'+id+'/interactive-search').then(r=>r.json()),
    grab: (id, body)=>adultFetch('/api/adult/'+id+'/grab',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json()),
    refresh: (id)=>adultFetch('/api/adult/'+id+'/refresh',{method:'POST'}).then(r=>r.json()),
    metadataSearch: (q)=>adultFetch('/api/adult/metadata/search?query='+encodeURIComponent(q)).then(r=>r.json()),
    metadataStatus: ()=>adultFetch('/api/adult/metadata/status').then(r=>r.json()),
    file: (id, body)=>adultFetch('/api/adult/'+id+'/file',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json()),
  },
  indexers:  { list: ()=>fetch('/api/indexers').then(r=>r.json()),
               add: body=>fetch('/api/indexers',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json()),
               remove: id=>fetch(`/api/indexers/${id}`,{method:'DELETE'}),
               test: id=>fetch(`/api/indexers/${id}/test`,{method:'POST'}).then(r=>r.json()) },
  system:    { searchAllMissing: ()=>fetch('/api/search-all-missing',{method:'POST'}).then(r=>r.json()) },
  livetv:    { sources: ()=>fetch('/api/livetv/sources').then(r=>r.json()),
               addSource: body=>fetch('/api/livetv/sources',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json()),
               sync: id=>fetch(`/api/livetv/sources/${id}/sync`,{method:'POST'}).then(r=>r.json()),
               channels: (q='')=>fetch(`/api/livetv/channels?q=${encodeURIComponent(q)}&limit=300`).then(r=>r.json()),
               channelsEditor: ()=>fetch('/api/livetv/channels/editor?include_disabled=true&limit=2000').then(r=>r.json()),
               patchChannel: (id, body)=>fetch('/api/livetv/channels/'+id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json()),
               bulkChannels: (body)=>fetch('/api/livetv/channels/bulk',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json()),

               groups: ()=>fetch('/api/livetv/groups').then(r=>r.json()) },
  audiobooks:{ list: ()=>fetch('/api/audiobooks').then(r=>r.json()),
               get: id=>fetch(`/api/audiobooks/${id}`).then(r=>r.json()),
               search: q=>fetch(`/api/audiobooks/search?query=${encodeURIComponent(q)}`).then(r=>r.json()),
               add: body=>fetch('/api/audiobooks',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),
               remove: id=>fetch(`/api/audiobooks/${id}`,{method:'DELETE'}),
               searchNow: id=>fetch(`/api/audiobooks/${id}/search`,{method:'POST'}).then(r=>r.json()),
               searchMissing: ()=>fetch('/api/audiobooks/search-missing',{method:'POST'}).then(r=>r.json()),
               interactive: id=>fetch(`/api/audiobooks/${id}/interactive-search`).then(r=>r.json()),
               grab: (id,body)=>fetch(`/api/audiobooks/${id}/grab`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json()),
               update: (id,body)=>fetch(`/api/audiobooks/${id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json()) },
  comics:    { list: ()=>fetch('/api/comics').then(r=>r.json()),
               get: id=>fetch(`/api/comics/${id}`).then(r=>r.json()),
               search: q=>fetch(`/api/comics/search?query=${encodeURIComponent(q)}`).then(r=>r.json()),
               add: body=>fetch('/api/comics',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json()),
               remove: id=>fetch(`/api/comics/${id}`,{method:'DELETE'}),
               searchNow: id=>fetch(`/api/comics/${id}/search`,{method:'POST'}).then(r=>r.json()),
               searchMissing: ()=>fetch('/api/comics/search-missing',{method:'POST'}).then(r=>r.json()),
               interactive: id=>fetch(`/api/comics/${id}/interactive-search`).then(r=>r.json()),
               grab: (id,body)=>fetch(`/api/comics/${id}/grab`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json()),
               issues: id=>fetch(`/api/comics/${id}/issues`).then(r=>r.json()),
               syncIssues: id=>fetch(`/api/comics/${id}/issues/sync`,{method:'POST'}).then(r=>r.json()),
               update: (id,body)=>fetch(`/api/comics/${id}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json()) },
  calendar:  { list: (start,end)=>fetch(`/api/calendar?start=${start||''}&end=${end||''}`).then(r=>r.json()) },
  smartlists:{ list: ()=>fetch('/api/smartlists').then(r=>r.json()),
               add: body=>fetch('/api/smartlists',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json()),
               remove: id=>fetch(`/api/smartlists/${id}`,{method:'DELETE'}),
               run: id=>fetch(`/api/smartlists/${id}/run`,{method:'POST'}).then(r=>r.json()),
               runAll: ()=>fetch('/api/smartlists/run-all',{method:'POST'}).then(r=>r.json()) },
  books:     { list: ()=>fetch('/api/books').then(r=>r.json()),
               get: id=>fetch(`/api/books/${id}`).then(r=>r.json()),
               search: q=>fetch(`/api/books/search?query=${encodeURIComponent(q)}`).then(r=>r.json()),
               add: body=>fetch('/api/books',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),
               remove: id=>fetch(`/api/books/${id}`,{method:'DELETE'}),
               searchNow: id=>fetch(`/api/books/${id}/search`,{method:'POST'}).then(r=>r.json()),
               searchMissing: ()=>fetch('/api/books/search-missing',{method:'POST'}).then(r=>r.json()),
               interactive: id=>fetch(`/api/books/${id}/interactive-search`).then(r=>r.json()),
               grab: (id, body)=>fetch(`/api/books/${id}/grab`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json()),
               update: (id, body)=>fetch(`/api/books/${id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json()),
               refresh: id=>fetch(`/api/books/${id}/refresh`,{method:'POST'}).then(r=>r.json()),
               file: (id, body)=>fetch(`/api/books/${id}/file`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json()) },
  requests:  { list: (status)=>fetch(`/api/requests${status?`?status=${status}`:''}`).then(r=>r.json()),
               create: body=>fetch('/api/requests',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(async r=>{ if(!r.ok) throw new Error((await r.json()).detail||r.statusText); return r.json(); }),
               approve: (id,quality_profile)=>fetch(`/api/requests/${id}/approve`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({quality_profile:quality_profile||null})}).then(r=>r.json()),
               deny: (id,reason)=>fetch(`/api/requests/${id}/deny`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({reason:reason||null})}).then(r=>r.json()),
               cancel: id=>fetch(`/api/requests/${id}`,{method:'DELETE'}) },
  discover:  { movies: (kind='popular')=>fetch(`/api/discover/movies/${String(kind).replace(/_/g,'-')}`).then(r=>r.json()),
               tv: (kind='popular')=>fetch(`/api/discover/tv/${String(kind).replace(/_/g,'-')}`).then(r=>r.json()) },
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
               searchMissing: ()=>fetch('/api/music/search-missing',{method:'POST'}).then(r=>r.json()),
               get: id=>fetch(`/api/music/${id}`).then(r=>r.json()),
               interactive: id=>fetch(`/api/music/${id}/interactive-search`).then(r=>r.json()),
               grab: (id,body)=>fetch(`/api/music/${id}/grab`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json()),
               update: (id,body)=>fetch(`/api/music/${id}?`+new URLSearchParams(Object.fromEntries(Object.entries(body).filter(([,v])=>v!=null))).toString(),{method:'PATCH'}).then(r=>r.json()),
               remove: id=>fetch(`/api/music/${id}`,{method:'DELETE'}),
               addArtist: (artist,limit=30)=>fetch(`/api/music/add-artist?artist=${encodeURIComponent(artist)}&limit=${limit}`,{method:'POST'}).then(r=>r.json()) },
};


const TMDB = 'https://image.tmdb.org/t/p/w342';

export { api, adultFetch, getAdultUnlock, setAdultUnlock, ADULT_UNLOCK_KEY, TMDB };
