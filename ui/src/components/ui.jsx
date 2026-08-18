import { useState, useEffect } from "react";
import Ic from "../icons.jsx";
import { api, TMDB } from "../api.js";
import { THEME_GROUPS, nextTheme } from "../theme.js";

function libraryStatuses(item, { isTv = false } = {}) {
  const chips = [];
  if (!item) return chips;
  const st = (item.status && (item.status.value || item.status) || "").toString().toLowerCase();
  const hasFile = !!(item.file_path) || st === "downloaded" || st === "completed";
  if (hasFile) chips.push({ id: "downloaded", label: "On disk", color: "success", symbol: "✓" });
  else if (item.monitored) chips.push({ id: "monitored", label: "Monitored", color: "warning", symbol: "●" });
  else if (item.id || item.external_id) chips.push({ id: "added", label: "In library", color: "info", symbol: "+" });

  // TV airing status
  const ss = (item.series_status || "").toLowerCase();
  if (isTv || ss) {
    if (ss === "continuing" || ss === "continuing series")
      chips.push({ id: "continuing", label: "Continuing", color: "secondary", symbol: "▶" });
    else if (ss === "ended" || ss === "ended series")
      chips.push({ id: "ended", label: "Ended", color: "neutral", symbol: "■" });
    else if (ss === "upcoming")
      chips.push({ id: "upcoming", label: "Upcoming", color: "accent", symbol: "◇" });
    else if (ss === "canceled" || ss === "cancelled")
      chips.push({ id: "canceled", label: "Canceled", color: "error", symbol: "✕" });
  }

  // Series / volume membership (comics, books, audiobooks, movie collections)
  if (item.series_name)
    chips.push({ id: "series", label: item.series_name, color: "primary", symbol: "◎" });
  else if (item.collection_id || item.collection_name)
    chips.push({ id: "series", label: item.collection_name || "Collection", color: "primary", symbol: "◎" });
  else if (item.volume_title)
    chips.push({ id: "series", label: item.volume_title, color: "primary", symbol: "◎" });

  return chips;
}

function StatusBadgeStack({ chips, className = "" }) {
  if (!chips || !chips.length) return null;
  // Show up to 3 stacked in the corner
  const show = chips.slice(0, 3);
  return (
    <div className={"absolute top-1.5 right-1.5 flex flex-col gap-1 items-end z-10 " + className}>
      {show.map(c => (
        <span key={c.id}
          className={"badge badge-sm gap-0.5 shadow text-[10px] border-0 badge-" + c.color}
          title={c.label}>
          <span className="font-bold">{c.symbol}</span>
          {show.length <= 2 && <span className="hidden sm:inline max-w-[4.5rem] truncate">{c.label}</span>}
        </span>
      ))}
    </div>
  );
}

function ringClassFromChips(chips) {
  if (!chips || !chips.length) return "";
  // Primary ring from first chip; secondary outline via box-shadow for multi
  const primary = chips[0];
  const map = {
    success: "ring-2 ring-success",
    warning: "ring-2 ring-warning",
    info: "ring-2 ring-info",
    secondary: "ring-2 ring-secondary",
    neutral: "ring-2 ring-base-content/40",
    accent: "ring-2 ring-accent",
    error: "ring-2 ring-error",
    primary: "ring-2 ring-primary",
  };
  let cls = (map[primary.color] || "") + " ring-offset-1 ring-offset-base-100";
  if (chips.length >= 2) {
    // second color as outer glow via style handled on element
    cls += " ring-offset-2";
  }
  return cls;
}

function LibraryLegend({ showSeries = true, showTv = true }) {
  return (
    <div className="flex flex-wrap gap-3 items-center justify-center pt-4 text-xs opacity-70 border-t border-base-content/10 mt-2">
      <span className="font-semibold opacity-50 uppercase tracking-wide text-[10px]">Legend</span>
      <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-success inline-block"/> On disk</span>
      <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-warning inline-block"/> Monitored</span>
      <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-info inline-block"/> In library</span>
      {showTv && <>
        <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-secondary inline-block"/> Continuing</span>
        <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-base-content/40 inline-block"/> Ended</span>
        <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-accent inline-block"/> Upcoming</span>
      </>}
      {showSeries && (
        <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-primary inline-block"/> In a series</span>
      )}
      <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded border border-base-content/30 inline-block"/> Not in library</span>
    </div>
  );
}


function LogoMark({ className = "", size = 32, full = false, tint = false, rgb = false }) {
  const src = full ? "/logo-full.png" : "/logo-icon.png";
  // Random accent color each full page load (red/yellow/blue/green/…)
  const hue = (typeof window !== "undefined" && window.__mosLogoHue != null)
    ? window.__mosLogoHue
    : (() => {
        const hues = [0, 30, 55, 120, 160, 200, 260, 300];
        const h = hues[Math.floor(Math.random() * hues.length)];
        if (typeof window !== "undefined") window.__mosLogoHue = h;
        return h;
      })();
  const style = {
    width: full ? Math.round(size * 2.4) : size,
    height: size,
    objectFit: "contain",
    ...(tint ? { filter: `hue-rotate(${hue}deg) saturate(1.25)` } : {}),
  };
  return (
    <img
      src={src}
      alt="MediaOS"
      width={full ? Math.round(size * 2.4) : size}
      height={size}
      className={"logo-mark" + (rgb ? " logo-mark--rgb" : "") + " " + className}
      style={style}
      draggable={false}
      onError={(e) => { if (!full && e.currentTarget.src.indexOf("logo-full") < 0) e.currentTarget.src = "/logo-full.png"; }}
    />
  );
}


const PAGE_TITLE_MAP = {
  dashboard: 'Home',
  movies: 'Movies',
  tv: 'TV',
  music: 'Music',
  books: 'Books',
  audiobooks: 'Audiobooks',
  comics: 'Comics',
  manga: 'Manga',
  games: 'Games',
  youtube: 'YouTube',
  podcasts: 'Podcasts',
  livetv: 'Live TV',
  discover: 'Discover',
  queue: 'Queue',
  library: 'Library',
  wanted: 'Wanted',
  calendar: 'Calendar',
  requests: 'Requests',
  adult: 'Adult',
  homelab: 'Homelab',
  login: 'Sign in',
  setup: 'Setup',
  about: 'About',
  modules: 'Module Store',
  scrobbling: 'History',
  tracking: 'Tracking',
  converter: 'Converter',
  'converter-dashboard': 'Converter',
  'settings-hub': 'Settings',
  'settings-vpn': 'VPN',
  'settings-users': 'Users',
  'settings-sessions': 'Sessions',
  'settings-subtitles': 'Subtitles',
};

function humanizePageTitle(title) {
  if (title == null || title === '') return '';
  const key = String(title);
  if (PAGE_TITLE_MAP[key]) return PAGE_TITLE_MAP[key];
  return key.replace(/^settings-?/, '').replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function PageChrome({ children, title }) {
  const label = humanizePageTitle(title);
  return (
    <div className="mos-page-chrome">
      {/* Mobile-only brand strip — desktop mockup keeps logo only in left sidebar */}
      <div className="mos-top-logo-bar flex lg:hidden items-center gap-2.5 mb-3 sticky top-0 z-20 py-2 -mt-1 px-1 bg-base-100/95 backdrop-blur-md border-b border-base-content/10">
        <div className="w-8 h-8 flex items-center justify-center shrink-0 rounded-xl bg-primary/10 ring-1 ring-primary/20">
          <LogoMark size={26} rgb />
        </div>
        <div className="font-bold tracking-tight text-sm">
          <span className="bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">MediaOS</span>
        </div>
        {label && <span className="text-xs opacity-40 ml-1">· {label}</span>}
      </div>
      {children}
    </div>
  );
}


/* ── HLS (Node-built hls.js) for Live TV & library streams ─────────────── */

function SplashScreen({ visible }) {
  if (!visible) return null;
  return (
    <div className="mr-splash fixed inset-0 z-[100] flex flex-col items-center justify-center bg-base-100 transition-opacity duration-500">
      <div className="flex flex-col items-center gap-6">
        <div className="mr-splash-logo flex items-center justify-center">
          <LogoMark size={72} full className="rounded-none w-auto" />
        </div>
        <div className="text-xs uppercase tracking-[0.3em] opacity-50">Loading library</div>
        <progress className="progress progress-primary w-44" />
      </div>
    </div>
  );
}






function CollectionProgressWidget({ setPage }) {
  const [rows, setRows] = useState([]);
  const [loaded, setLoaded] = useState(false);
  useEffect(()=>{ fetch('/api/collections/dashboard/summary').then(r=>r.ok?r.json():[]).then(d=>{setRows(d||[]); setLoaded(true);}).catch(()=>setLoaded(true)); }, []);
  return (
    <div className="card bg-base-200 shadow-md mt-4 border border-primary/20">
      <div className="card-body p-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-semibold text-sm uppercase tracking-wide text-primary">Saga Progress</h3>
          <button type="button" className="btn btn-primary btn-xs" onClick={()=>setPage && setPage('collections')}>{rows.length ? 'View all' : 'Track a collection'}</button>
        </div>
        {!loaded && <p className="text-xs opacity-50">Loading…</p>}
        {loaded && !rows.length && (
          <p className="text-sm opacity-60">No movie collections tracked yet. Track MCU, Bond, Star Wars… and watch completion here on the home dashboard.</p>
        )}
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {rows.slice(0,9).map(c=>(
            <div key={c.id} className="flex items-center gap-3 p-2 rounded-lg bg-base-300/40 hover:bg-base-300 cursor-pointer" onClick={()=>setPage && setPage('collections')}>
              {c.poster_path ? <img src={c.poster_path.startsWith('http')?c.poster_path:`https://image.tmdb.org/t/p/w92${c.poster_path}`} className="w-10 h-14 object-cover rounded" alt=""/> : <div className="w-10 h-14 bg-base-300 rounded"/>}
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">{c.name}</div>
                <div className="text-xs opacity-60">{c.progress_label}</div>
                <progress className="progress progress-primary h-1.5 w-full mt-1" value={c.pct} max="100"/>
              </div>
              <span className="text-xs font-mono opacity-70">{c.pct}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}


function MediaDetailShell({ title, year, poster, status, monitored, overview, filePath, qualityProfile, msg, busy, onBack, actions, children }) {
  return (
    <div className="space-y-4 max-w-5xl">
      <button type="button" className="btn btn-ghost btn-sm" onClick={onBack}>← Library</button>
      {msg && <div className="alert alert-info text-xs py-2">{msg}</div>}
      <div className="flex flex-col md:flex-row gap-4">
        <div className="w-36 shrink-0">
          {poster
            ? <img src={poster} alt="" className="rounded-lg shadow w-full" />
            : <div className="aspect-[2/3] bg-base-300 rounded-lg" />}
        </div>
        <div className="flex-1 space-y-2">
          <h1 className="text-2xl font-bold">{title} {year && <span className="opacity-50 font-normal">({year})</span>}</h1>
          <div className="flex flex-wrap gap-2 items-center">
            {status && <span className={'badge '+(status==='downloaded'?'badge-success':'badge-warning')}>{status}</span>}
            {monitored!=null && <span className={'badge '+(monitored?'badge-primary':'badge-ghost')}>{monitored?'Monitored':'Unmonitored'}</span>}
            {qualityProfile && <span className="badge badge-outline">{qualityProfile}</span>}
          </div>
          {overview && <p className="text-sm opacity-70 max-w-2xl">{overview}</p>}
          {filePath && <p className="text-xs font-mono opacity-50 break-all">{filePath}</p>}
          <div className="flex flex-wrap gap-2 pt-2">{actions}</div>
        </div>
      </div>
      {children}
    </div>
  );
}


function StatsGrid({ movies, series, music=[], books=[], audiobooks=[], setPage }) {
  const downloaded = movies.filter(m=>m.status==='downloaded').length;
  const downloading = movies.filter(m=>m.status==='downloading').length +
    series.reduce((a,s)=>a+(s.episode_count-s.downloaded_count > 0 ? 1 : 0), 0);
  const totalEpisodes = series.reduce((a,s)=>a+s.episode_count, 0);
  const doneEpisodes = series.reduce((a,s)=>a+s.downloaded_count, 0);
  const musicDone = music.filter(m=>m.status==='downloaded').length;
  const booksDone = books.filter(b=>b.status==='downloaded').length;
  const abDone = audiobooks.filter(a=>a.status==='downloaded').length;

  const stats = [
    { label:'Movies', value:movies.length, sub:`${downloaded} downloaded   ${downloading} grabbing`,
      Icon:Ic.Film, color:'bg-primary/10 text-primary', progress:movies.length>0?downloaded/movies.length:0,
      pc:'progress-primary', onClick:()=>setPage('movies') },
    { label:'TV Shows', value:series.length, sub:`${totalEpisodes} episodes   ${doneEpisodes} downloaded`,
      Icon:Ic.Tv, color:'bg-secondary/10 text-secondary', progress:totalEpisodes>0?doneEpisodes/totalEpisodes:0,
      pc:'progress-secondary', onClick:()=>setPage('tv') },
    { label:'Downloading', value:downloading, sub: downloading===0 ? 'Queue is empty' : 'Active grabs',
      Icon:Ic.Download, color:'bg-accent/10 text-accent', progress:0, pc:'progress-accent', onClick:()=>setPage('activity') },
    { label:'Music', value:music.length, sub: music.length ? `${musicDone} downloaded` : 'No albums yet',
      Icon:Ic.Music, color:'bg-info/10 text-info', progress:music.length>0?musicDone/music.length:0,
      pc:'progress-info', onClick:()=>setPage('music') },
    { label:'Books', value:books.length, sub: books.length ? `${booksDone} downloaded` : 'No books yet',
      Icon:Ic.Book, color:'bg-warning/10 text-warning', progress:books.length>0?booksDone/books.length:0,
      pc:'progress-warning', onClick:()=>setPage('books') },
    { label:'Audiobooks', value:audiobooks.length, sub: audiobooks.length ? `${abDone} downloaded` : 'No audiobooks yet',
      Icon:Ic.Headphones, color:'bg-success/10 text-success', progress:audiobooks.length>0?abDone/audiobooks.length:0,
      pc:'progress-success', onClick:()=>setPage('audiobooks') },
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
          <button type="button" className="btn btn-ghost btn-xs btn-square" onClick={onClose}><Ic.X /></button>
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
                <button type="button"
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

function LibraryModuleShell({ title, nav, active, onNav, children, tools }) {
  return (
    <div className="mr-module mos-mock-panel">
      <aside className="mr-module-nav hidden md:block">
        <div className="mod-title">{title}</div>
        {(nav || []).map(n => (
          <button key={n.id} type="button" className={active === n.id ? 'active' : ''} onClick={() => onNav && onNav(n.id)}>
            {n.icon && <span className="w-4 h-4 opacity-80">{n.icon}</span>}
            {n.label}
          </button>
        ))}
      </aside>
      <div className="mr-module-body">
        <div className="mr-toolbar">
          <h1 className="mr-page-title">{title}</h1>
          {tools}
        </div>
        <div className="flex md:hidden flex-wrap gap-1 mb-3">
          {(nav || []).map(n => (
            <button key={n.id} type="button" className={'mr-chip' + (active === n.id ? ' on' : '')} onClick={() => onNav && onNav(n.id)}>{n.label}</button>
          ))}
        </div>
        {children}
      </div>
    </div>
  );
}

function PosterTile({ title, year, poster, status, quality, onClick, badges }) {
  const src = poster
    ? (String(poster).startsWith('http') ? poster : `https://image.tmdb.org/t/p/w342${poster}`)
    : null;
  const st = (status || '').toString().toLowerCase();
  return (
    <div className="mr-tile" onClick={onClick} role="button" tabIndex={0}>
      <div className="art">
        {src
          ? <img src={src} alt="" loading="lazy" />
          : <div className="w-full h-full flex items-center justify-center text-3xl font-bold opacity-20">{(title||'?')[0]}</div>}
        <div className="absolute top-2 left-2 flex flex-col gap-1">
          {quality && <span className="pill hd">{quality}</span>}
        </div>
      </div>
      <div className="meta">
        <div className="title">{title}</div>
        <div className="badges">
          {year && <span className="text-[10px] opacity-50">{year}</span>}
          {st === 'downloaded' || st === 'completed' ? (
            <span className="pill ok">Downloaded</span>
          ) : st ? (
            <span className="pill warn">{status}</span>
          ) : null}
          {(badges || []).map((b, i) => <span key={i} className="pill">{b}</span>)}
        </div>
      </div>
    </div>
  );
}

function MediaCard({ item, type, onSearchNow, onToggleMonitor, onDelete, onPlay }) {
  const [busy, setBusy] = useState(false);
  const isMovie = type==='movie';
  const pct = !isMovie && item.episode_count>0 ? Math.round(item.downloaded_count/item.episode_count*100) : 0;

  async function doSearch(e) {
    e.preventDefault(); setBusy(true);
    try { await onSearchNow(item.id); } catch(e) {}
    setBusy(false);
  }

  const chips = libraryStatuses(item, { isTv: !isMovie });
  const ring = ringClassFromChips(chips);

  return (
    <div className={"media-card group relative aspect-poster cursor-pointer "+ring}>
      {item.poster_path
        ? <img className="h-full w-full object-cover" src={TMDB+item.poster_path} alt={item.title} loading="lazy" />
        : <div className="h-full w-full flex items-center justify-center text-4xl font-bold text-base-content/20 font-mono">{item.title?.[0]}</div>}

      {/* Multi-status stack (on disk + continuing/ended + series) */}
      <StatusBadgeStack chips={chips} />

      {/* Top-left: type + episode progress */}
      <div className="absolute top-2 left-2 z-10 flex flex-col gap-1">
        <div className={`badge badge-xs border-none font-semibold shadow ${isMovie?'bg-primary/80 text-primary-content':'bg-secondary/80 text-secondary-content'}`}>
          {isMovie?'Movie':'TV'}
        </div>
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
            {isMovie && item.file_path && onPlay && (
              <button type="button" className="btn btn-xs btn-primary border-none flex-1" onClick={e=>{e.preventDefault();e.stopPropagation();onPlay(item);}}>
                Play
              </button>
            )}
            {isMovie && onSearchNow && (
              <button type="button" className="btn btn-xs btn-ghost bg-white/20 text-white hover:bg-white/30 border-none flex-1" onClick={doSearch} disabled={busy}>
                {busy ? <Ic.Loader /> : <Ic.Refresh />}
              </button>
            )}
            {onToggleMonitor && (
              <button type="button" className="btn btn-xs btn-ghost bg-white/20 text-white hover:bg-white/30 border-none flex-1" onClick={e=>{e.preventDefault();onToggleMonitor(item);}}>
                {item.monitored ? <Ic.Eye /> : <Ic.EyeOff />}
              </button>
            )}
            {onDelete && (
              <button type="button" className="btn btn-xs btn-ghost bg-white/20 text-white hover:bg-red-400/50 border-none flex-1" onClick={e=>{e.preventDefault();onDelete(item);}}>
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
        <button type="button" className="btn btn-primary btn-sm gap-2" onClick={onAdd}>
          <span className="w-4 h-4"><Ic.Plus /></span>Add
        </button>
      </div>
    </div>
  );
}

/* ── Dashboard Page ──────────────────────────────────────────────────────── */

function TeachEmpty({ title, children, actionLabel, onAction }) {
  return (
    <div className="text-center py-16 px-6 max-w-lg mx-auto">
      <h2 className="text-lg font-semibold mb-2">{title}</h2>
      <div className="text-sm text-base-content/60 space-y-2 text-left bg-base-200 rounded-lg p-4 mb-4">{children}</div>
      {onAction && <button type="button" className="btn btn-primary btn-sm" onClick={onAction}>{actionLabel||'Go'}</button>}
    </div>
  );
}




function SkeletonLoader({ rows = 6, kind = "grid" }) {
  if (kind === "table") {
    return (
      <div className="space-y-2 p-2 animate-pulse">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="h-8 bg-base-300 rounded w-full" />
        ))}
      </div>
    );
  }
  return (
    <div className="poster-grid animate-pulse">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="rounded-lg bg-base-300 aspect-[2/3]" />
      ))}
    </div>
  );
}



function ThemeToggle({ theme, setTheme, className = "" }) {
  const next = nextTheme(theme);
  return (
    <button
      type="button"
      className={"btn btn-ghost btn-sm btn-circle " + className}
      title={`Next theme: ${next}`}
      aria-label={`Change theme. Current: ${theme}. Next: ${next}`}
      onClick={() => setTheme(next)}
    >
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5" aria-hidden="true">
        <path d="M12 3a9 9 0 1 0 9 9 7 7 0 0 1-9-9Z" />
        <path d="M19 3v4M17 5h4" />
      </svg>
    </button>
  );
}

function ThemesPage({ currentTheme, setTheme }) {
  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="mr-page-title flex-1">Themes</h1>
        <button type="button" className="btn btn-primary btn-sm" onClick={() => setTheme(nextTheme(currentTheme))}>
          Next preset
        </button>
      </div>

      <div className="card border border-primary/20 bg-base-200">
        <div className="card-body py-4">
          <div className="flex flex-wrap items-center gap-3">
            <span className="w-4 h-4 rounded-full bg-primary shadow-[0_0_16px] shadow-primary/40" aria-hidden="true" />
            <span className="text-sm">Current preset: <strong className="text-primary">{currentTheme}</strong></span>
            <span className="text-xs opacity-60">All presets keep the same MediaOS layout; only the palette changes.</span>
          </div>
        </div>
      </div>

      {THEME_GROUPS.map((group) => (
        <section key={group.label} className="space-y-2">
          <h2 className="text-xs uppercase tracking-wider opacity-60 font-semibold">{group.label}</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
            {group.themes.map((theme) => (
              <button
                key={theme}
                type="button"
                className={"theme-preset btn btn-sm justify-start " + (currentTheme === theme ? "btn-primary" : "btn-outline")}
                onClick={() => setTheme(theme)}
                aria-pressed={currentTheme === theme}
              >
                <span className="theme-preset-dot" aria-hidden="true" />
                <span className="truncate">{theme}</span>
              </button>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

export {
  SkeletonLoader, ThemesPage, ThemeToggle, libraryStatuses, StatusBadgeStack, ringClassFromChips, LibraryLegend, LogoMark, PageChrome,
  SplashScreen, CollectionProgressWidget, MediaDetailShell,
  StatsGrid, AddModal, LibraryModuleShell, PosterTile, MediaCard, LibraryHeader, TeachEmpty,
};
