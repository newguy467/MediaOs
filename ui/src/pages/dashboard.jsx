import { useState, useEffect } from "react";
import { api, TMDB } from "../api.js";
function GuidedFirstRun({ setPage }) {
  const [data, setData] = useState(null);
  const [tab, setTab] = useState('movies');
  useEffect(()=>{ fetch('/api/setup/guided').then(r=>r.json()).then(d=>{
    setData(d);
    // open first incomplete library
    const libs = d.libraries || [];
    const first = libs.find(l => !l.complete) || libs[0];
    if (first) setTab(first.id);
  }).catch(e => { try { setMsg(String(e.message||e)); } catch(_) { console.warn(e); } }); }, []);
  if (!data) return null;
  const libs = data.libraries || [];
  if (libs.length && libs.every(l => l.complete)) return null;
  const lib = libs.find(l => l.id === tab) || libs[0];
  const steps = (lib && lib.steps) || data.steps || [];
  const pct = (lib && lib.pct) != null ? lib.pct : data.pct;
  return (
    <div className="card bg-base-200 border border-primary/30 shadow-lg mb-6">
      <div className="card-body gap-3 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="font-semibold">First-run checklist</h2>
            <p className="text-xs opacity-60">Folder → downloader → add → get a file — for each library you care about</p>
          </div>
          <div className="text-sm font-mono">Overall {data.overall_pct ?? data.pct}%</div>
        </div>
        <div className="flex flex-wrap gap-1">
          {libs.map(l=>(
            <button key={l.id} type="button"
              className={"btn btn-xs " + (tab===l.id ? "btn-primary" : "btn-ghost")}
              onClick={()=>setTab(l.id)}>
              {l.complete ? "✓ " : ""}{l.label} ({l.done_count}/{l.total})
            </button>
          ))}
        </div>
        {lib && (
          <>
            <progress className="progress progress-primary w-full h-2" value={pct} max="100" />
            <ul className="space-y-2">
              {steps.map(s=>(
                <li key={s.id} className={"flex gap-3 items-start p-2 rounded-lg "+(s.done?"bg-success/10":"bg-base-300/50")}>
                  <span className={"mt-0.5 w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold "+(s.done?"bg-success text-success-content":"bg-base-100 border")}>
                    {s.done ? "✓" : " "}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className={"text-sm font-medium "+(s.done?"opacity-70 line-through":"")}>{s.title}</div>
                    <div className="text-xs opacity-60">{s.detail}</div>
                    {s.help && !s.done && <div className="text-xs opacity-50 mt-0.5">{s.help}</div>}
                  </div>
                  {!s.done && s.action && setPage && (
                    <button type="button" className="btn btn-xs btn-primary shrink-0" onClick={()=>setPage(s.action)}>Go</button>
                  )}
                </li>
              ))}
            </ul>
          </>
        )}
        <div className="text-xs opacity-50">
          Recommended: <code className="text-xs">{data.recommended_compose}</code>
          {" "}  Skip libraries you do not use. GPU/VPN stay optional power packs.
        </div>
      </div>
    </div>
  );
}

function fmtBytes(n) {
  if (n == null) return '—';
  const units = ['B','KiB','MiB','GiB','TiB','PiB'];
  let u = 0, v = n;
  while (v >= 1024 && u < units.length - 1) { v /= 1024; u++; }
  return `${v.toFixed(v < 10 && u > 0 ? 1 : 0)} ${units[u]}`;
}

function StorageWidget({ setPage }) {
  const [data, setData] = useState(null);
  const [msg, setMsg] = useState(null);
  useEffect(() => {
    fetch('/api/storage/summary').then(r=>r.json()).then(setData).catch(e=>setMsg(String(e.message||e)));
  }, []);
  const folders = data?.folders || [];
  return (
    <div className="card bg-base-200 border border-base-content/5">
      <div className="card-body p-4 gap-2">
        <div className="flex justify-between items-center">
          <h2 className="font-semibold text-sm">Storage</h2>
          <button type="button" className="btn btn-xs btn-ghost" onClick={()=>setPage&&setPage('backup')}>Manage</button>
        </div>
        {msg && <p className="text-xs opacity-50">Storage stats unavailable ({msg})</p>}
        {!data && !msg && <span className="loading loading-spinner loading-xs"/>}
        {data && !folders.length && <p className="text-xs opacity-50">No library folders mounted yet</p>}
        <div className="space-y-2">
          {folders.map(f => {
            const pct = f.total ? Math.round((f.used / f.total) * 100) : 0;
            const warn = pct >= 90;
            return (
              <div key={f.id} className="text-xs">
                <div className="flex justify-between items-baseline gap-2">
                  <span className="font-medium truncate">{f.label}</span>
                  <span className="opacity-50 truncate">{f.path}</span>
                </div>
                <div className="flex items-center gap-2 mt-0.5">
                  <progress
                    className={"progress w-full h-2 " + (warn ? "progress-error" : "progress-primary")}
                    value={pct} max="100"
                  />
                  <span className="tabular-nums opacity-70 shrink-0 w-32 text-right">
                    {fmtBytes(f.used)} / {fmtBytes(f.total)}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function GlossaryPage() {
  const [terms, setTerms] = useState([]);
  useEffect(()=>{ fetch('/api/setup/glossary').then(r=>r.json()).then(d=>setTerms(d.terms||[])).catch(e => { try { setMsg(String(e.message||e)); } catch(_) { console.warn(e); } }); }, []);
  return (
    <div className="space-y-4 max-w-2xl">
      <div>
        <h1 className="mr-page-title">Glossary</h1>
        <p className="text-sm opacity-60">Ten terms — no *arr jargon required</p>
      </div>
      <div className="space-y-2">
        {terms.map(t=>(
          <div key={t.term} className="p-3 bg-base-200 rounded-lg">
            <div className="font-semibold text-sm">{t.term}</div>
            <div className="text-sm opacity-70">{t.def}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function DashboardPage({ movies, series, music=[], books=[], audiobooks=[], setPage, enabledModules }) {
  const em = enabledModules || ['movies','tv'];
  const DEFAULT_LAYOUT = [
    { id: 'stats', enabled: true },
    { id: 'calendar', enabled: true },
    { id: 'queue', enabled: true },
    { id: 'wanted', enabled: true },
    { id: 'recent', enabled: true },
    { id: 'activity', enabled: true },
    { id: 'storage', enabled: true },
    { id: 'health', enabled: true },
    { id: 'nowplaying', enabled: true },
    { id: 'dvr', enabled: true },
    { id: 'external_arr', enabled: true },
    { id: 'games_wanted', enabled: true },
    { id: 'continue_watching', enabled: true },
    { id: 'continue_reading', enabled: true },
  ];
  const [layout, setLayout] = useState(() => {
    try {
      const raw = localStorage.getItem('mediaos.dashboard.layout');
      if (raw) {
        const saved = JSON.parse(raw);
        if (Array.isArray(saved)) {
          // Merge in any new default widgets (e.g. continue_reading) without
          // wiping the user's enable/order preferences for known ids.
          const have = new Set(saved.map(w => w && w.id).filter(Boolean));
          const merged = [...saved];
          for (const w of DEFAULT_LAYOUT) {
            if (!have.has(w.id)) merged.push({ ...w });
          }
          return merged;
        }
      }
    } catch {}
    return DEFAULT_LAYOUT;
  });
  const [edit, setEdit] = useState(false);
  const [bundle, setBundle] = useState(null);
  const [nowPlaying, setNowPlaying] = useState(null);
  const [attention, setAttention] = useState([]);
  const load = () => {
    fetch('/api/overhaul/dashboard').then(r=>r.json()).then(setBundle).catch(()=>setBundle(null));
    fetch('/api/now-playing').then(r=>r.json()).then(setNowPlaying).catch(()=>setNowPlaying(null));
    fetch('/api/library/attention').then(r=>r.json()).then(d=>setAttention(d.items||[])).catch(()=>setAttention([]));
  };
  useEffect(()=>{ load(); const i=setInterval(load, 30000); return ()=>clearInterval(i); }, []);
  function saveLayout(next) {
    setLayout(next);
    try { localStorage.setItem('mediaos.dashboard.layout', JSON.stringify(next)); } catch {}
  }
  function toggleWidget(id) {
    saveLayout(layout.map(w => w.id===id ? {...w, enabled: !w.enabled} : w));
  }
  function moveWidget(id, dir) {
    const idx = layout.findIndex(w=>w.id===id);
    if (idx < 0) return;
    const j = idx + dir;
    if (j < 0 || j >= layout.length) return;
    const next = [...layout];
    const tmp = next[idx]; next[idx] = next[j]; next[j] = tmp;
    saveLayout(next);
  }
  const lib = bundle?.library || {};
  const wanted = bundle?.wanted || {};
  const cal = bundle?.calendar || [];
  const queue = bundle?.queue || [];
  const activity = bundle?.activity || [];
  const recent = bundle?.recent || [];
  const health = bundle?.health || {};
  const dvr = bundle?.dvr_jobs || [];
  const externalArr = bundle?.external_arr || [];
  const gamesWanted = bundle?.games_wanted || [];
  const continueWatching = bundle?.continue_watching || [];
  const continueReading = bundle?.continue_reading || [];
  const movieN = movies?.length ?? lib.movie ?? 0;
  const tvN = series?.length ?? lib.tv ?? 0;

  const widgetDefs = {
    stats: {
      label: 'Library stats',
      render: () => (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            {label:'Movies', n: movieN, page:'movies'},
            {label:'TV', n: tvN, page:'tv'},
            {label:'Music', n: music.length||lib.music||0, page:'music'},
            {label:'Books', n: books.length||lib.book||0, page:'books'},
          ].map(c=>(
            <button key={c.label} type="button" className="card bg-base-200 hover:border-primary border border-base-content/5 text-left"
              onClick={()=>setPage && setPage(c.page)}>
              <div className="card-body p-3">
                <div className="text-2xl font-bold tabular-nums">{c.n}</div>
                <div className="text-xs opacity-60">{c.label}</div>
              </div>
            </button>
          ))}
        </div>
      ),
    },
    calendar: {
      label: 'Upcoming / airing',
      render: () => (
        <div className="card bg-base-200 border border-base-content/5">
          <div className="card-body p-4 gap-2">
            <div className="flex justify-between items-center">
              <h2 className="font-semibold text-sm">Calendar (next 14 days)</h2>
              <button type="button" className="btn btn-xs btn-ghost" onClick={()=>setPage && setPage('calendar')}>Open</button>
            </div>
            {(cal||[]).slice(0,8).map((e,i)=>(
              <div key={i} className="flex gap-2 text-xs items-baseline">
                <span className="opacity-50 w-24 shrink-0 tabular-nums">{(e.air_date||'').slice(0,10)}</span>
                <span className="font-medium truncate">{e.series}</span>
                <span className="opacity-60">S{String(e.season).padStart(2,'0')}E{String(e.episode).padStart(2,'0')}</span>
                <span className={"badge badge-xs ml-auto "+(e.status==='downloaded'?'badge-success':'badge-ghost')}>{e.status}</span>
              </div>
            ))}
            {!cal.length && <p className="text-xs opacity-50">No upcoming monitored episodes — add TV series and keep monitor on.</p>}
            <p className="text-[10px] opacity-40 mt-1">Missing episodes auto-search on the scheduler (RSS lookback).</p>
          </div>
        </div>
      ),
    },
    queue: {
      label: 'Download queue',
      render: () => (
        <div className="card bg-base-200 border border-base-content/5">
          <div className="card-body p-4 gap-2">
            <div className="flex justify-between"><h2 className="font-semibold text-sm">Queue</h2>
              <button type="button" className="btn btn-xs btn-ghost" onClick={()=>setPage&&setPage('queue')}>Open</button></div>
            {(queue||[]).slice(0,6).map(q=>(
              <div key={q.id} className="text-xs truncate"><span className="badge badge-xs mr-1">{q.status}</span>{q.title}</div>
            ))}
            {!queue.length && <p className="text-xs opacity-50">Queue empty</p>}
          </div>
        </div>
      ),
    },
    wanted: {
      label: 'Wanted counts',
      render: () => (
        <div className="card bg-base-200 border border-base-content/5">
          <div className="card-body p-4 gap-2">
            <div className="flex justify-between"><h2 className="font-semibold text-sm">Wanted</h2>
              <button type="button" className="btn btn-xs btn-ghost" onClick={()=>setPage&&setPage('wanted')}>Open</button></div>
            <div className="flex flex-wrap gap-2 text-xs">
              {Object.entries(wanted).map(([k,v])=>(
                <span key={k} className="badge badge-ghost gap-1">{k}: <b>{v}</b></span>
              ))}
              {!Object.keys(wanted).length && <span className="opacity-50">None</span>}
            </div>
          </div>
        </div>
      ),
    },
    recent: {
      label: 'Recently downloaded',
      render: () => (
        <div className="card bg-base-200 border border-base-content/5">
          <div className="card-body p-4 gap-2">
            <h2 className="font-semibold text-sm">Recently downloaded</h2>
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
              {(recent||[]).slice(0,6).map(r=>(
                <div key={r.id} className="text-center">
                  {r.poster_path ? <img src={r.poster_path} alt="" className="rounded aspect-[2/3] object-cover w-full" /> :
                    <div className="rounded aspect-[2/3] bg-base-300" />}
                  <div className="text-[10px] truncate mt-1">{r.title}</div>
                </div>
              ))}
            </div>
            {!recent.length && <p className="text-xs opacity-50">Nothing downloaded yet</p>}
          </div>
        </div>
      ),
    },
    activity: {
      label: 'Activity feed',
      render: () => (
        <div className="card bg-base-200 border border-base-content/5">
          <div className="card-body p-4 gap-1">
            <div className="flex justify-between"><h2 className="font-semibold text-sm">Activity</h2>
              <button type="button" className="btn btn-xs btn-ghost" onClick={()=>setPage&&setPage('activity')}>History</button></div>
            {(activity||[]).slice(0,8).map(a=>(
              <div key={a.id} className="text-xs opacity-80 truncate">{a.message||a.event}</div>
            ))}
            {!activity.length && <p className="text-xs opacity-50">No activity yet</p>}
          </div>
        </div>
      ),
    },

    nowplaying: {
      label: 'Now playing',
      render: () => (
        <div className="card bg-base-200 border border-base-content/5">
          <div className="card-body p-4 gap-2">
            <h2 className="font-semibold text-sm">Now playing</h2>
            {(nowPlaying?.sessions||[]).map((s,i)=>(
              <div key={i} className="text-xs flex flex-wrap gap-2 items-baseline">
                <span className="badge badge-xs badge-primary">{s.source}</span>
                <span className="font-medium truncate">{s.title||'—'}</span>
                {s.user && <span className="opacity-50">{s.user}</span>}
                {s.state && <span className="opacity-50">{s.state}</span>}
                {s.progress_percent != null && <span className="tabular-nums opacity-50">{s.progress_percent}%</span>}
              </div>
            ))}
            {!nowPlaying?.sessions?.length && (
              <p className="text-xs opacity-50">
                {nowPlaying?.configured ? 'Nothing playing right now' : (nowPlaying?.hint || 'Configure Plex or Tautulli in settings to show sessions')}
              </p>
            )}
          </div>
        </div>
      ),
    },

    storage: {
      label: 'Storage',
      render: () => <StorageWidget setPage={setPage} />,
    },
    health: {
      label: 'System health',
      render: () => (
        <div className="card bg-base-200 border border-base-content/5">
          <div className="card-body p-4 gap-1 text-xs">
            <div className="flex justify-between items-center">
              <h2 className="font-semibold text-sm">System</h2>
              <button type="button" className="btn btn-xs btn-ghost" onClick={()=>setPage&&setPage('settings')}>Settings</button>
            </div>
            <div>MediaOs <b>v{health.version||'—'}</b> · {health.status||'ok'}</div>
            <div className="opacity-50">Scheduler searches new/missing TV episodes automatically (calendar + RSS lookback).</div>
            {(health.status && String(health.status).toLowerCase()!=='ok') && (
              <div className="alert alert-warning text-xs py-1 mt-1">
                Health not OK — open <button type="button" className="link" onClick={()=>setPage&&setPage('settings')}>Settings</button>
                {' '}or <button type="button" className="link" onClick={()=>setPage&&setPage('settings-vpnsettings')}>VPN</button>.
              </div>
            )}
            {(externalArr||[]).some(a=>a.status==='down') && (
              <div className="text-xs text-error mt-1">
                External *arr down — <button type="button" className="link" onClick={()=>setPage&&setPage('settings-integrations')}>Integrations</button>
              </div>
            )}
          </div>
        </div>
      ),
    },
    dvr: {
      label: 'DVR jobs',
      render: () => (
        <div className="card bg-base-200 border border-base-content/5">
          <div className="card-body p-4 gap-2">
            <div className="flex justify-between"><h2 className="font-semibold text-sm">Live TV DVR</h2>
              <button type="button" className="btn btn-xs btn-ghost" onClick={()=>setPage&&setPage('livetv')}>Open</button></div>
            {(dvr||[]).slice(0,6).map(j=>(
              <div key={j.id} className="text-xs truncate"><span className="badge badge-xs mr-1">{j.status}</span>{j.title} <span className="opacity-50">{j.channel_name||''}</span></div>
            ))}
            {!dvr.length && <p className="text-xs opacity-50">No scheduled/active recordings</p>}
          </div>
        </div>
      ),
    },
    external_arr: {
      label: 'External *arr',
      render: () => (
        <div className="card bg-base-200 border border-base-content/5">
          <div className="card-body p-4 gap-2">
            <h2 className="font-semibold text-sm">External *arr status</h2>
            {(externalArr||[]).map(a=>(
              <div key={a.name} className="text-xs flex gap-2 items-center">
                <span className={"badge badge-xs "+(a.status==='up'?'badge-success':a.status==='down'?'badge-error':'badge-ghost')}>{a.status}</span>
                <span className="font-medium uppercase">{a.name}</span>
                <span className="opacity-50 truncate">{a.version||a.url||''}</span>
              </div>
            ))}
            {!externalArr.length && <p className="text-xs opacity-50">Configure Sonarr/Radarr/Lidarr/Prowlarr URLs in settings</p>}
          </div>
        </div>
      ),
    },
    games_wanted: {
      label: 'Games wanted',
      render: () => (
        <div className="card bg-base-200 border border-base-content/5">
          <div className="card-body p-4 gap-2">
            <div className="flex justify-between"><h2 className="font-semibold text-sm">Games wanted</h2>
              <button type="button" className="btn btn-xs btn-ghost" onClick={()=>setPage&&setPage('games')}>Open</button></div>
            {(gamesWanted||[]).slice(0,6).map(g=>(
              <div key={g.id} className="text-xs truncate">{g.title} <span className="opacity-50">{g.status}</span></div>
            ))}
            {!gamesWanted.length && <p className="text-xs opacity-50">No monitored games</p>}
          </div>
        </div>
      ),
    },
    continue_watching: {
      label: 'Continue watching',
      render: () => (
        <div className="card bg-base-200 border border-base-content/5">
          <div className="card-body p-4 gap-2">
            <h2 className="font-semibold text-sm">Continue watching</h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2">
              {(continueWatching||[]).slice(0,6).map((c,i)=>(
                <button key={i} type="button" className="text-left group" onClick={()=>{
                  if (c.page) setPage && setPage(c.page);
                  window.dispatchEvent(new CustomEvent('mediaos-open-item', {
                    detail: { mediaType: c.media_type, id: c.media_item_id || c.game_id },
                  }));
                }}>
                  <div className="aspect-[2/3] w-full rounded overflow-hidden bg-base-300 relative">
                    {c.poster_path
                      ? <img className="w-full h-full object-cover group-hover:opacity-80" src={c.poster_path.startsWith('http')?c.poster_path:`${TMDB}${c.poster_path}`} alt="" loading="lazy" />
                      : <div className="w-full h-full flex items-center justify-center text-xs opacity-40 p-1 text-center">{c.title}</div>}
                    <progress className="progress progress-primary absolute bottom-0 left-0 right-0 h-1 rounded-none" value={Math.round(c.progress_percent||0)} max="100"></progress>
                  </div>
                  <div className="text-xs mt-1 truncate">{c.title}</div>
                  {c.subtitle && <div className="text-[10px] opacity-50 truncate">{c.subtitle}</div>}
                </button>
              ))}
            </div>
            {!continueWatching.length && <p className="text-xs opacity-50">No in-progress items</p>}
          </div>
        </div>
      ),
    },
    continue_reading: {
      label: 'Continue reading',
      render: () => (
        <div className="card bg-base-200 border border-base-content/5">
          <div className="card-body p-4 gap-2">
            <h2 className="font-semibold text-sm">Continue reading</h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2">
              {(continueReading||[]).slice(0,6).map((c,i)=>(
                <button key={i} type="button" className="text-left group" onClick={()=>{
                  if (c.page) setPage && setPage(c.page);
                  window.dispatchEvent(new CustomEvent('mediaos-open-item', {
                    detail: { mediaType: c.media_type, id: c.media_item_id },
                  }));
                }}>
                  <div className="aspect-[2/3] w-full rounded overflow-hidden bg-base-300 relative">
                    {c.poster_path
                      ? <img className="w-full h-full object-cover group-hover:opacity-80" src={c.poster_path.startsWith('http')?c.poster_path:c.poster_path} alt="" loading="lazy" />
                      : <div className="w-full h-full flex items-center justify-center text-xs opacity-40 p-1 text-center">{c.title}</div>}
                  </div>
                  <div className="text-xs mt-1 truncate">{c.title}</div>
                  {c.subtitle && <div className="text-[10px] opacity-50 truncate">{c.subtitle}</div>}
                </button>
              ))}
            </div>
            {!continueReading.length && (
              <div className="text-xs opacity-50 space-y-1">
                <p>No in-progress comics/manga</p>
                <p>Open a comic and mark pages read, or <button type="button" className="link link-hover" onClick={()=>saveLayout(DEFAULT_LAYOUT)}>reset dashboard layout</button> if this widget was hidden.</p>
              </div>
            )}
          </div>
        </div>
      ),
    },

  };

  return (
    <div className="space-y-4 max-w-6xl">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="mr-page-title">Home</h1>
          
      <div className="prismarr-strip flex flex-wrap gap-2 items-center p-2 mb-3 rounded-lg bg-base-300/60 border border-base-content/10 text-xs">
        <span className="font-semibold opacity-70 mr-1">Control</span>
        <button type="button" className="btn btn-xs" onClick={()=>setPage&&setPage('queue')}>Queue</button>
        <button type="button" className="btn btn-xs" onClick={()=>setPage&&setPage('wanted')}>Wanted</button>
        {em.includes('livetv') && <button type="button" className="btn btn-xs" onClick={()=>setPage&&setPage('livetv')}>DVR</button>}
        {em.includes('games') && <button type="button" className="btn btn-xs" onClick={()=>setPage&&setPage('games')}>Games</button>}
        <button type="button" className="btn btn-xs" onClick={()=>setPage&&setPage('activity')}>History</button>
        <button type="button" className="btn btn-xs" onClick={()=>setPage&&setPage('calendar')}>Calendar</button>
        <button type="button" className="btn btn-xs" onClick={()=>setPage&&setPage('indexers')}>Indexers</button>
        <button type="button" className="btn btn-xs btn-ghost" onClick={()=>setPage&&setPage('settings-hub')}>Settings</button>
        <span className="ml-auto opacity-50 tabular-nums">{movieN} movies · {tvN} series</span>
      </div>

          <p className="mr-page-sub">Your media OS dashboard — editable widgets</p>
        </div>
        <div className="flex gap-2">
          <button type="button" className={"btn btn-sm "+(edit?'btn-primary':'btn-ghost')} onClick={()=>setEdit(e=>!e)}>{edit?'Done':'Edit widgets'}</button>
          <button type="button" className="btn btn-sm btn-ghost" onClick={load}>Refresh</button>
        </div>
      </div>
      {edit && (
        <div className="card bg-base-200 border border-primary/30"><div className="card-body p-3 gap-2">
          <p className="text-xs opacity-70">Toggle and reorder widgets. Layout is saved in this browser.</p>
          {layout.map(w=>(
            <div key={w.id} className="flex items-center gap-2 text-sm">
              <input type="checkbox" className="checkbox checkbox-sm" checked={!!w.enabled} onChange={()=>toggleWidget(w.id)} />
              <span className="flex-1">{widgetDefs[w.id]?.label || w.id}</span>
              <button type="button" className="btn btn-xs" onClick={()=>moveWidget(w.id,-1)}>↑</button>
              <button type="button" className="btn btn-xs" onClick={()=>moveWidget(w.id,1)}>↓</button>
            </div>
          ))}
          <button type="button" className="btn btn-xs btn-ghost w-fit" onClick={()=>saveLayout(DEFAULT_LAYOUT)}>Reset defaults</button>
        </div></div>
      )}
      <div className="space-y-4">
        {attention.length > 0 && (
        <div className="alert alert-warning text-xs py-2 mb-3 flex flex-wrap gap-2 items-center">
          <span className="font-semibold">Needs attention</span>
          {attention.slice(0,6).map((a,i)=>(
            <span key={i} className="badge badge-sm badge-outline truncate max-w-[10rem]">{a.kind}: {a.title}</span>
          ))}
          <button type="button" className="btn btn-xs" onClick={()=>setPage&&setPage('activity')}>Open activity</button>
        </div>
      )}
      {layout.filter(w=>w.enabled && (w.id!=='games_wanted' || em.includes('games')) && (w.id!=='dvr' || em.includes('livetv'))).map(w=>(
          <div key={w.id}>{widgetDefs[w.id]?.render?.()}</div>
        ))}
      </div>
    </div>
  );
}



function OverhaulDashboardPage({ setPage, enabledModules }) {
  const em = enabledModules || ['movies', 'tv'];
  const [data, setData] = useState(null);
  const [msg, setMsg] = useState(null);
  useEffect(() => {
    fetch('/api/overhaul/dashboard').then(r=>r.json()).then(setData).catch(e=>setMsg(String(e)));
  }, []);
  return (
    <div className="p-4 max-w-6xl mx-auto space-y-4">
      <div className="flex items-center gap-2">
        <h1 className="mr-page-title flex-1">Dashboard</h1>
        <button type="button" className="btn btn-sm" onClick={()=>setPage && setPage('settings-hub')}>Settings</button>
      </div>
      {msg && <div className="alert alert-warning text-xs">{msg}</div>}
      {!data && !msg && <span className="loading loading-spinner"/>}
      {data && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {Object.entries(data.wanted||{}).map(([k,v])=>(
              <div key={k} className="stat bg-base-200 rounded-box p-3">
                <div className="stat-title text-xs">{k} wanted</div>
                <div className="stat-value text-2xl">{v}</div>
              </div>
            ))}
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            <div className="card bg-base-200">
              <div className="card-body p-3">
                <h2 className="font-semibold text-sm">Queue</h2>
                <ul className="text-xs space-y-1 max-h-48 overflow-auto">
                  {(data.queue||[]).map(q=>(
                    <li key={q.id}>{q.title||'#'+q.id} <span className="opacity-50">{q.status}</span></li>
                  ))}
                  {!(data.queue||[]).length && <li className="opacity-50">Empty</li>}
                </ul>
              </div>
            </div>
            <div className="card bg-base-200">
              <div className="card-body p-3">
                <h2 className="font-semibold text-sm">Activity</h2>
                <ul className="text-xs space-y-1 max-h-48 overflow-auto">
                  {(data.activity||[]).map(a=>(
                    <li key={a.id}><span className="badge badge-xs mr-1">{a.event}</span>{a.message||''}</li>
                  ))}
                  {!(data.activity||[]).length && <li className="opacity-50">None</li>}
                </ul>
              </div>
            </div>
          </div>
          <div className="card bg-base-200">
            <div className="card-body p-3">
              <h2 className="font-semibold text-sm">Calendar (upcoming)</h2>
              <ul className="text-xs space-y-1 max-h-64 overflow-auto">
                {(data.calendar||[]).map((c,i)=>(
                  <li key={i}>{c.air_date?.slice(0,10)} — {c.series} S{c.season}E{c.episode} {c.title||''}</li>
                ))}
                {!(data.calendar||[]).length && <li className="opacity-50">No upcoming episodes with air dates</li>}
              </ul>
            </div>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <button type="button" className="btn btn-xs" onClick={()=>setPage && setPage('settings-quality-matrix')}>Quality matrices</button>
            <button type="button" className="btn btn-xs" onClick={()=>setPage && setPage('comics')}>Comics</button>
            <button type="button" className="btn btn-xs" onClick={()=>setPage && setPage('music')}>Music</button>
            {em.includes('livetv') && <button type="button" className="btn btn-xs" onClick={()=>setPage && setPage('livetv')}>Live TV</button>}
          </div>
        </>
      )}
    </div>
  );
}




export { GuidedFirstRun, GlossaryPage, DashboardPage, OverhaulDashboardPage };
