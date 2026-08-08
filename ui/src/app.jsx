import React, { useState, useEffect, useCallback, useRef } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

/* ── Splash (Sonarr/Radarr-style boot screen) ─────────────────────────────── */

/* ── Library status badges (multi-color, Sonarr-style) ───────────────────── */
/** Build list of status chips for a library item.
 *  Can stack: downloaded + continuing, monitored + ended, series membership, etc.
 */
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


function LogoMark({ className = "", size = 32 }) {
  return (
    <img
      src="/logo-icon.png"
      alt="MediaOs"
      width={size}
      height={size}
      className={"logo-mark " + className}
      style={{ width: size, height: size, objectFit: "contain" }}
      draggable={false}
    />
  );
}

function SplashScreen({ visible }) {
  if (!visible) return null;
  return (
    <div className="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-base-100 transition-opacity duration-500"
      style={{ background: "radial-gradient(ellipse at center, #2a1540 0%, #0f0a14 70%)" }}>
      <div className="flex flex-col items-center gap-5 animate-pulse">
        <div className="w-24 h-24 flex items-center justify-center drop-shadow-[0_0_24px_rgba(139,92,246,0.45)]">
          <LogoMark size={88} className="!rounded-none" />
        </div>
        <div className="text-2xl font-bold tracking-tight text-base-content">MediaOs</div>
        <div className="text-xs uppercase tracking-[0.25em] opacity-50">Loading library</div>
        <progress className="progress progress-primary w-40" />
      </div>
    </div>
  );
}



/* ── Themes (exact list from MediaOs) ──────────────────────────────────── */
const THEMES = [
  'mediaos','dark','night','dracula','synthwave','cyberpunk','abyss',
  'luxury','dim','black','forest','halloween','nord','business',
  'light','cupcake','corporate','emerald'
];




function InteractiveResultsPanel({ data, loading, busy, onGrab, onClose, mediaItemId }) {
  const [showRejected, setShowRejected] = useState(false);
  const [sortBy, setSortBy] = useState('score');
  const [filter, setFilter] = useState('');
  const [msg, setMsg] = useState(null);
  const results = Array.isArray(data) ? data : (data?.results || []);
  const rejected = Array.isArray(data) ? [] : (data?.rejected || []);
  const stats = Array.isArray(data) ? null : (data?.indexer_results || null);
  const breakdown = Array.isArray(data) ? null : (data?.rejection_breakdown || null);
  const hosts = Array.isArray(data) ? null : (data?.rate_limit?.hosts || null);
  const ms = Array.isArray(data) ? null : data?.search_time_ms;
  const queries = Array.isArray(data) ? null : (data?.queries || null);
  let rows = showRejected ? [...results, ...rejected] : results;
  if (filter.trim()) {
    const f = filter.toLowerCase();
    rows = rows.filter(r => (r.title||'').toLowerCase().includes(f) || (r.indexer||'').toLowerCase().includes(f));
  }
  rows = [...rows].sort((a,b) => {
    if (sortBy === 'seeders') return (b.seeders||0) - (a.seeders||0);
    if (sortBy === 'size') return (b.size||0) - (a.size||0);
    return (b.score||0) - (a.score||0);
  });
  async function blockRow(r) {
    try {
      await fetch('/api/system/blocklist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          release_title: r.title,
          reason: 'interactive blocklist',
          torrent_hash: r.info_hash || null,
          media_item_id: mediaItemId || null,
        }),
      }).then(x => { if (!x.ok) throw new Error('blocklist failed'); return x.json(); });
      setMsg('Blocklisted: ' + r.title);
    } catch (e) { setMsg(String(e.message || e)); }
  }
  function downloadDebug() {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'mediaos-interactive-search.json';
    a.click();
    URL.revokeObjectURL(a.href);
  }
  return (
    <div className="card bg-base-200 border border-primary/30 mt-3">
      <div className="card-body p-3 gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="font-semibold text-sm flex-1">Interactive search</h2>
          {ms != null && <span className="text-xs opacity-50">{ms}ms · {results.length} ok · {rejected.length} rejected</span>}
          <button type="button" className="btn btn-ghost btn-xs" onClick={downloadDebug} title="Export debug JSON">JSON</button>
          <button type="button" className="btn btn-ghost btn-xs" onClick={onClose}>Close</button>
        </div>
        {msg && <div className="text-xs text-warning">{msg}</div>}
        {queries && queries.length > 0 && (
          <div className="text-[10px] opacity-50 truncate" title={queries.join(' | ')}>Queries: {queries.join(' · ')}</div>
        )}
        <div className="flex flex-wrap gap-2 items-center">
          <input className="input input-bordered input-xs w-40" placeholder="Filter…" value={filter} onChange={e=>setFilter(e.target.value)} />
          <select className="select select-bordered select-xs" value={sortBy} onChange={e=>setSortBy(e.target.value)}>
            <option value="score">Score</option>
            <option value="seeders">Seeders</option>
            <option value="size">Size</option>
          </select>
          <label className="label cursor-pointer gap-1 py-0">
            <input type="checkbox" className="checkbox checkbox-xs" checked={showRejected} onChange={e=>setShowRejected(e.target.checked)} />
            <span className="label-text text-xs">Show rejected</span>
          </label>
        </div>
        {stats && stats.length > 0 && (
          <div className="flex flex-wrap gap-1 text-[10px]">
            {stats.map((s,i)=>(
              <span key={i} className={'badge badge-xs ' + (s.error || s.skipped ? 'badge-error' : 'badge-ghost')} title={s.error || s.searchMethod || ''}>
                {s.name}: {s.count}{s.skipped ? ' ⏳' : ''}{s.error && !s.skipped ? ' ✗' : ''} {s.durationMs ? `${s.durationMs}ms` : ''}
              </span>
            ))}
          </div>
        )}
        {hosts && hosts.length > 0 && (
          <div className="flex flex-wrap gap-1 text-[10px] opacity-70">
            {hosts.map((h,i)=>(
              <span key={i} className="badge badge-xs badge-outline" title="host concurrency">
                {h.host}: {h.inflight}/{h.max_parallel} ({h.completed} done)
              </span>
            ))}
          </div>
        )}
        {breakdown && Object.keys(breakdown).length > 0 && (
          <div className="flex flex-wrap gap-1 text-[10px] opacity-80">
            {Object.entries(breakdown).map(([reason, n]) => (
              <span key={reason} className="badge badge-xs badge-warning" title={reason}>{reason}: {n}</span>
            ))}
          </div>
        )}
        {loading && <p className="text-xs opacity-50">Searching indexers…</p>}
        <div className="overflow-x-auto max-h-80">
          <table className="table table-xs">
            <thead><tr><th>Score</th><th>Release</th><th>Indexer</th><th>Size</th><th>Seeders</th><th>Parsed</th><th></th></tr></thead>
            <tbody>
              {rows.map((r,i)=>(
                <tr key={i} className={r.rejected ? 'opacity-50' : ''}>
                  <td className="tabular-nums font-mono text-xs">{r.score ?? '—'}</td>
                  <td className="max-w-xs truncate" title={(r.rejections||[]).join(', ') || r.title}>{r.title}</td>
                  <td className="text-xs">{r.indexer||'—'}</td>
                  <td className="text-xs">{r.size ? (r.size>1e9?(r.size/1e9).toFixed(1)+' GB':(r.size/1e6).toFixed(0)+' MB') : '—'}</td>
                  <td>{r.seeders ?? '—'}</td>
                  <td className="text-[10px]">
                    {(r._parsed?.resolution || r.parsed_resolution) && <span className="badge badge-xs badge-ghost">{r._parsed?.resolution || r.parsed_resolution}</span>}
                    {(r._parsed?.codec || r.parsed_codec) && <span className="badge badge-xs badge-ghost">{r._parsed?.codec || r.parsed_codec}</span>}
                    {(r._parsed?.source || r.parsed_source) && <span className="badge badge-xs badge-ghost">{r._parsed?.source || r.parsed_source}</span>}
                    {r.is_season_pack && <span className="badge badge-xs badge-info">pack</span>}
                    {r.is_multi_season_pack && <span className="badge badge-xs badge-warning">multi</span>}
                    {r.rejected && <span className="badge badge-xs badge-error" title={(r.rejections||[]).join(', ')}>rej</span>}
                    {(r.matched_formats||[]).slice(0,2).map(f=><span key={f} className="badge badge-xs badge-ghost">{f}</span>)}
                  </td>
                  <td className="whitespace-nowrap">
                    {!r.rejected && r.download_url && (
                      <button type="button" className="btn btn-primary btn-xs" disabled={busy} onClick={()=>onGrab(r)}>Grab</button>
                    )}
                    <button type="button" className="btn btn-ghost btn-xs" title="Blocklist" onClick={()=>blockRow(r)}>Block</button>
                  </td>
                </tr>
              ))}
              {!loading && !rows.length && <tr><td colSpan={7} className="opacity-50">No releases</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function applyTheme(t) {
  document.documentElement.setAttribute('data-theme', t === 'dark' ? 'mediaos' : t);
  localStorage.setItem('mediaos-theme', t);
}
function storedTheme() {
  return localStorage.getItem('mediaos-theme') || 'mediaos' || 'mediaos';
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
  Rss:        ()=><svg {...P}><path d="M4 11a9 9 0 019 9"/><path d="M4 4a16 16 0 0116 16"/><circle cx="5" cy="19" r="1"/></svg>,
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
  Users:      ()=><svg {...P}><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>,
  Loader:     ()=><svg {...P} className="animate-spin"><line x1="12" y1="2" x2="12" y2="6"/><line x1="12" y1="18" x2="12" y2="22"/><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"/><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"/><line x1="2" y1="12" x2="6" y2="12"/><line x1="18" y1="12" x2="22" y2="12"/><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"/><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"/></svg>,
};

/* ── Auth token (Bearer) ─────────────────────────────────────────────────── */
const AUTH_TOKEN_KEY = 'mediaos_token';
function getToken() { try { return localStorage.getItem(AUTH_TOKEN_KEY); } catch { return null; } }
function getAdvanced() { try { return localStorage.getItem('mediaos-advanced') === '1'; } catch { return false; } }
function setAdvancedFlag(v) { try { localStorage.setItem('mediaos-advanced', v ? '1' : '0'); } catch {} }

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
               searchMissing: ()=>fetch('/api/music/search-missing',{method:'POST'}).then(r=>r.json()),
               get: id=>fetch(`/api/music/${id}`).then(r=>r.json()),
               interactive: id=>fetch(`/api/music/${id}/interactive-search`).then(r=>r.json()),
               grab: (id,body)=>fetch(`/api/music/${id}/grab`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json()),
               update: (id,body)=>fetch(`/api/music/${id}?`+new URLSearchParams(Object.fromEntries(Object.entries(body).filter(([,v])=>v!=null))).toString(),{method:'PATCH'}).then(r=>r.json()),
               remove: id=>fetch(`/api/music/${id}`,{method:'DELETE'}),
               addArtist: (artist,limit=30)=>fetch(`/api/music/add-artist?artist=${encodeURIComponent(artist)}&limit=${limit}`,{method:'POST'}).then(r=>r.json()) },
};

const TMDB = 'https://image.tmdb.org/t/p/w342';



/* ── Built-in media player (direct + ffmpeg transcode) ───────────────────── */
function playbackKey({ itemId, episodeId, videoId, path }) {
  if (videoId != null) return 'yt:' + videoId;
  if (episodeId != null) return 'ep:' + episodeId;
  if (itemId != null) return 'item:' + itemId;
  if (path) return 'path:' + path;
  return 'unknown';
}
function loadResume(key) {
  try { const v = localStorage.getItem('mediaos-resume:' + key); return v ? parseFloat(v) : 0; } catch { return 0; }
}
function saveResume(key, t) {
  try { if (t > 5) localStorage.setItem('mediaos-resume:' + key, String(Math.floor(t))); } catch {}
}

function MediaPlayer({ itemId, episodeId, videoId, path, title, onClose, compact, podcastEpisodeId, chapters: chaptersProp }) {

  const [info, setInfo] = useState(null);
  const [mode, setMode] = useState('auto'); // auto | direct | transcode
  const [error, setError] = useState('');
  const videoRef = useRef(null);

  const qs = new URLSearchParams();
  if (itemId != null) qs.set('item_id', itemId);
  if (episodeId != null) qs.set('episode_id', episodeId);
  if (videoId != null) qs.set('video_id', videoId);
  if (path) qs.set('path', path);
  if (podcastEpisodeId != null) qs.set('podcast_episode_id', podcastEpisodeId);

  useEffect(() => {
    setError('');
    fetch('/api/player/probe?' + qs.toString())
      .then(r => r.ok ? r.json() : Promise.reject(r.statusText))
      .then(d => {
        setInfo(d);
        setMode(d.needs_transcode ? 'transcode' : 'direct');
      })
      .catch(e => setError(String(e)));
  }, [itemId, episodeId, videoId, path, podcastEpisodeId]);

  const chapters = (Array.isArray(chaptersProp) && chaptersProp.length)
    ? chaptersProp
    : (info?.chapters || []);

  // Normalize chapter start seconds (supports start/startTime/start_time)
  const chapterStarts = chapters.map(c => {
    const s = c.start ?? c.startTime ?? c.start_time ?? c.begin ?? 0;
    return { title: c.title || c.name || 'Chapter', start: Number(s) || 0, type: (c.type || c.category || '').toLowerCase() };
  }).sort((a,b)=>a.start-b.start);

  const introChapter = chapterStarts.find(c => /intro|sponsor|ad|advert|self.?promo|interaction/.test(c.title + ' ' + c.type));
  const outroChapter = [...chapterStarts].reverse().find(c => /outro|end.?credits|credits/.test(c.title + ' ' + c.type));

  function seekTo(sec) {
    const v = videoRef.current;
    if (v && Number.isFinite(sec)) v.currentTime = Math.max(0, sec);
  }
  function skipIntro() {
    if (!introChapter) return;
    // jump to end of intro = start of next chapter, or +90s fallback
    const idx = chapterStarts.indexOf(introChapter);
    const next = chapterStarts[idx + 1];
    seekTo(next ? next.start : introChapter.start + 90);
  }
  function skipOutro() {
    if (outroChapter) seekTo(outroChapter.start);
  }

  const src = (() => {
    if (!info) return '';
    const q = new URLSearchParams(qs);
    if (mode === 'transcode') q.set('transcode', '1');
    return '/api/player/stream?' + q.toString();
  })();

  return (
    <div className="card bg-base-300 shadow-xl border border-primary/30">
      <div className="card-body p-3 gap-2">
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0">
            <div className="font-semibold truncate">{title || info?.name || 'Player'}</div>
            {info && (
              <div className="text-xs opacity-60 truncate">
                {info.video_codec || '—'} / {info.audio_codec || '—'}
                {info.width ? `   ${info.width}x${info.height}` : ''}
                {info.duration ? `   ${Math.round(info.duration/60)}m` : ''}
                {mode === 'transcode' ? '   transcoding via ffmpeg' : '   direct'}
                {chapterStarts.length ? `   ${chapterStarts.length} chapters` : ''}
              </div>
            )}
          </div>
          <div className="flex gap-1 shrink-0 flex-wrap justify-end">
            {introChapter && <button className="btn btn-xs btn-secondary" onClick={skipIntro}>Skip intro</button>}
            {outroChapter && <button className="btn btn-xs btn-ghost" onClick={skipOutro}>Skip to outro</button>}
            <button className={"btn btn-xs " + (mode==='direct'?'btn-primary':'btn-ghost')} onClick={()=>setMode('direct')}>Direct</button>
            <button className={"btn btn-xs " + (mode==='transcode'?'btn-primary':'btn-ghost')} onClick={()=>setMode('transcode')}>Transcode</button>
            {onClose && <button className="btn btn-xs btn-ghost" onClick={onClose}>Close</button>}
          </div>
        </div>
        {error && <div className="alert alert-error text-sm py-1">{error}</div>}
        {src && (
          <video
            key={src}
            ref={videoRef}
            controls
            autoPlay
            playsInline
            className={compact ? "w-full max-h-28 rounded bg-black" : "w-full max-h-[70vh] rounded bg-black"}
            src={src}
            onLoadedMetadata={(e) => {
              const key = playbackKey({ itemId, episodeId, videoId, path });
              const at = loadResume(key);
              if (at > 5 && e.target.duration && at < e.target.duration - 10) {
                e.target.currentTime = at;
              }
            }}
            onTimeUpdate={(e) => {
              const key = playbackKey({ itemId, episodeId, videoId, path });
              if (Math.floor(e.target.currentTime) % 5 === 0) saveResume(key, e.target.currentTime);
            }}
            onPause={(e) => saveResume(playbackKey({ itemId, episodeId, videoId, path }), e.target.currentTime)}
            onError={() => {
              if (mode !== 'transcode') {
                setMode('transcode');
                setError('Direct play failed — switching to ffmpeg transcode…');
              } else {
                setError('Playback failed even with transcode. Check ffmpeg and file path.');
              }
            }}
          />
        )}
        {!src && !error && <div className="text-sm opacity-50 p-6 text-center">Loading stream…</div>}
        
        {chapterStarts.length > 0 && !compact && (
          <div className="flex flex-wrap gap-1 max-h-24 overflow-auto">
            {chapterStarts.map((c,i)=>(
              <button key={i} className="btn btn-xs btn-ghost border border-base-content/10" onClick={()=>seekTo(c.start)} title={c.title}>
                {Math.floor(c.start/60)}:{String(Math.floor(c.start%60)).padStart(2,'0')} {c.title.slice(0,28)}
              </button>
            ))}
          </div>
        )}
<p className="text-[10px] opacity-40">Full codec support: MKV/HEVC/DTS/etc are transcoded on the fly to H.264/AAC. Direct is used for MP4/WebM when possible.</p>
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
          <button className="btn btn-primary btn-xs" onClick={()=>setPage && setPage('collections')}>{rows.length ? 'View all' : 'Track a collection'}</button>
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

function InteractiveResultsTable({ results, loading, busy, onGrab, onClose }) {
  if (!loading && !results) return null;
  return (
    <div className="card bg-base-200 shadow-sm">
      <div className="card-body p-4 gap-2">
        <div className="flex items-center gap-2">
          <h2 className="font-semibold text-sm flex-1">Interactive search</h2>
          {onClose && <button className="btn btn-xs btn-ghost" onClick={onClose}>Close</button>}
        </div>
        {loading && <p className="text-xs opacity-50">Searching indexers…</p>}
        {results && (
          <div className="overflow-x-auto max-h-96 overflow-y-auto">
            <table className="table table-xs">
              <thead><tr><th>Score</th><th>Release</th><th>Indexer</th><th>Size</th><th>Seeders</th><th>Formats</th><th></th></tr></thead>
              <tbody>
                {results.map((r,i)=>(
                  <tr key={i} className="hover">
                    <td className="font-mono">{r.score??'—'}</td>
                    <td className="text-xs max-w-xs truncate" title={r.title}>{r.title}</td>
                    <td className="text-xs">{r.indexer||'—'}</td>
                    <td className="text-xs">{r.size ? (r.size>1e8?(r.size/1e9).toFixed(2)+' GB':(r.size/1e6).toFixed(1)+' MB') : '—'}</td>
                    <td>{r.seeders??'—'}</td>
                    <td className="text-[10px]">{(r.matched_formats||[]).join(', ')}</td>
                    <td><button className="btn btn-xs btn-primary" disabled={busy} onClick={()=>onGrab(r)}>Grab</button></td>
                  </tr>
                ))}
                {!results.length && <tr><td colSpan={7} className="opacity-50">No releases</td></tr>}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function MediaDetailShell({ title, year, poster, status, monitored, overview, filePath, qualityProfile, msg, busy, onBack, actions, children }) {
  return (
    <div className="space-y-4 max-w-5xl">
      <button className="btn btn-ghost btn-sm" onClick={onBack}>← Library</button>
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

function ComicsPullPanel() {
  const [rows, setRows] = useState([]);
  const [msg, setMsg] = useState(null);
  const load = () => fetch('/api/overhaul/comics/pull-list').then(r=>r.json()).then(setRows).catch(()=>[]);
  useEffect(()=>{ load(); }, []);
  return (
    <div className="card bg-base-200 mb-4">
      <div className="card-body p-3 gap-2">
        <div className="flex items-center gap-2">
          <h2 className="font-semibold text-sm flex-1">Weekly pull-list</h2>
          <button className="btn btn-xs" onClick={async()=>{
            setMsg('Syncing…');
            const r = await fetch('/api/overhaul/comics/pull-list/sync',{method:'POST'}).then(x=>x.json()).catch(e=>({error:String(e)}));
            setMsg(JSON.stringify(r));
            load();
          }}>Sync now</button>
        </div>
        {msg && <p className="text-[10px] opacity-60 truncate">{msg}</p>}
        <div className="overflow-x-auto max-h-48">
          <table className="table table-xs">
            <thead><tr><th>Series</th><th>#</th><th>Date</th><th></th></tr></thead>
            <tbody>
              {(rows||[]).map(r=>(
                <tr key={r.id}><td>{r.series_name}</td><td>{r.issue_number||'—'}</td><td>{r.release_date||'—'}</td>
                <td>{r.grabbed?'✓':''}</td></tr>
              ))}
              {!(rows||[]).length && <tr><td colSpan={4} className="opacity-50">Empty — sync or add monitored comics with issue dates</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function ComicsPage({ setPage }) {
  const [items, setItems] = useState([]);
  const [detailId, setDetailId] = useState(null);
  const [tab, setTab] = useState('library'); // library | arcs | pull
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

  if (detailId) {
    return <ComicDetailPage comicId={detailId} onBack={()=>{ setDetailId(null); load(); }} />;
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

  const filtered = (items||[]).filter(c => !q || (c.title||'').toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex-1 min-w-[140px]">
          <h1 className="mr-page-title">Comics</h1>
          <p className="text-xs opacity-50">Library · story arcs · weekly pull list</p>
        </div>
        <div className="join">
          <button className={"btn btn-sm join-item "+(tab==='library'?'btn-primary':'')} onClick={()=>setTab('library')}>Library</button>
          <button className={"btn btn-sm join-item "+(tab==='arcs'?'btn-primary':'')} onClick={()=>setTab('arcs')}>Story arcs</button>
          <button className={"btn btn-sm join-item "+(tab==='pull'?'btn-primary':'')} onClick={()=>setTab('pull')}>Pull list</button>
        </div>
        {tab==='library' && <button className="btn btn-sm btn-secondary" disabled={busy} onClick={searchMissing}>Search missing</button>}
      </div>
      {msg && <div className="alert alert-info text-xs py-2">{msg}</div>}

      {tab==='library' && (
        <>
          <input className="input input-bordered input-sm w-full max-w-md" placeholder="Filter series…" value={q} onChange={e=>setQ(e.target.value)} />
          <div className="poster-grid">
            {filtered.map(c => (
              <PosterTile key={c.id} title={c.title} year={c.year} poster={c.poster_path} status={c.status}
                onClick={()=>setDetailId(c.id)} />
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
              <button className="btn btn-sm btn-primary" disabled={busy} onClick={createArc}>Create</button>
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
                    <button className="btn btn-ghost btn-xs text-error" onClick={async()=>{
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
              <button className="btn btn-sm btn-primary w-fit" disabled={busy} onClick={addPull}>Add</button>
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

function ComicDetailPage({ comicId, onBack }) {
  const [item, setItem] = useState(null);
  const [issues, setIssues] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const [ixResults, setIxResults] = useState(null);
  const [ixLoading, setIxLoading] = useState(false);

  const load = React.useCallback(() => {
    fetch('/api/comics/'+comicId).then(r=>r.json()).then(setItem).catch(e=>setMsg(String(e.message||e)));
    fetch('/api/comics/'+comicId+'/issues').then(r=>r.json()).then(d=>setIssues(Array.isArray(d)?d:[])).catch(()=>[]);
  }, [comicId]);
  useEffect(()=>{ load(); }, [load]);

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
      const rows = await fetch(`/api/comics/${comicId}/interactive-search`).then(x=>x.json());
      setIxResults(rows||[]);
    } catch(e) { setMsg(String(e.message||e)); }
    setIxLoading(false);
  }
  async function grabRel(rel) {
    setBusy(true);
    try {
      await fetch(`/api/comics/${comicId}/grab`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(rel)});
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

  if (!item) return <div className="p-6 opacity-50">Loading…</div>;
  return (
    <MediaDetailShell
      title={item.title} year={item.year} poster={item.poster_path}
      status={item.status} monitored={item.monitored} overview={item.overview}
      filePath={item.file_path} qualityProfile={item.quality_profile}
      msg={msg} busy={busy} onBack={onBack}
      actions={<>
        <button className="btn btn-sm btn-primary" disabled={busy} onClick={autoSearch}>Search & grab</button>
        <button className="btn btn-sm btn-secondary" disabled={busy||ixLoading} onClick={openIx}>Interactive search</button>
        <button className="btn btn-sm" disabled={busy} onClick={syncIssues}>Sync issues</button>
        <button className="btn btn-sm btn-ghost text-error" onClick={async()=>{ await fetch('/api/comics/'+comicId,{method:'DELETE'}); onBack(); }}>Delete</button>
      </>}
    >
      <InteractiveResultsTable results={ixResults} loading={ixLoading} busy={busy} onGrab={grabRel} onClose={()=>setIxResults(null)} />
      {issues.length>0 && (
        <div className="card bg-base-200"><div className="card-body p-4">
          <h3 className="font-semibold text-sm">Issues ({issues.length})</h3>
          <div className="overflow-x-auto max-h-64 overflow-y-auto">
            <table className="table table-xs">
              <thead><tr><th>#</th><th>Title</th><th>Status</th><th>Mon</th></tr></thead>
              <tbody>
                {issues.map(iss=>(
                  <tr key={iss.id}>
                    <td>{iss.issue_number}</td>
                    <td className="text-xs">{iss.title||'—'}</td>
                    <td><span className="badge badge-xs">{iss.status}</span></td>
                    <td>{iss.monitored?'✓':'—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div></div>
      )}
    </MediaDetailShell>
  );
}


function CookiesPastePanel() {
  const [text, setText] = useState('');
  const [status, setStatus] = useState(null);
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);
  const refresh = () => fetch('/api/youtube/cookies/status').then(r=>r.json()).then(setStatus).catch(()=>{});
  useEffect(()=>{ refresh(); }, []);
  const save = async () => {
    setBusy(true); setMsg('');
    try {
      const r = await fetch('/api/youtube/cookies', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({content:text})}).then(x=>x.json());
      if (r.ok) { setMsg(`Saved ${r.bytes} bytes → ${r.path}`); setText(''); refresh(); }
      else setMsg(r.detail || 'Failed');
    } catch(e) { setMsg(String(e)); }
    setBusy(false);
  };
  return (
    <div className="card bg-base-200 shadow">
      <div className="card-body space-y-3">
        <h2 className="card-title text-lg">YouTube login / cookies</h2>
        <p className="text-sm opacity-70">Public RSS works without login. For age-restricted or members-only videos, paste a Netscape cookies export so yt-dlp can authenticate.</p>
        <ol className="list-decimal list-inside text-sm space-y-1 opacity-80">
          <li>Install <strong>Get cookies.txt LOCALLY</strong> (or similar) in your browser.</li>
          <li>While logged into YouTube, export cookies for <code className="text-xs">youtube.com</code>.</li>
          <li>Paste the file contents below and hit Save — one click, no SSH.</li>
        </ol>
        <textarea className="textarea textarea-bordered font-mono text-xs h-40" placeholder="# Netscape HTTP Cookie File&#10;…" value={text} onChange={e=>setText(e.target.value)} />
        <div className="flex gap-2 items-center">
          <button className="btn btn-sm btn-primary" disabled={busy||!text.trim()} onClick={save}>{busy?'Saving…':'Save cookies'}</button>
          {status && <span className="text-xs opacity-60">{status.exists ? `On disk: ${status.path} (${status.size} bytes)` : `No cookies file yet (will write ${status.path})`}</span>}
        </div>
        {msg && <div className="text-sm opacity-80">{msg}</div>}
        <p className="text-xs opacity-50">SponsorBlock strips sponsor/self-promo/intro/outro on download. Library player plays cleaned local files.</p>
      </div>
    </div>
  );
}

function YouTubePage() {
  const [channels, setChannels] = useState([]);
  const [videos, setVideos] = useState([]);
  const [selected, setSelected] = useState(null);
  const [q, setQ] = useState('');
  const [tab, setTab] = useState('channels');
  const load = ()=>fetch('/api/youtube').then(r=>r.json()).then(setChannels).catch(()=>{});
  const loadVideos = (id)=>fetch('/api/youtube/'+id+'/videos').then(r=>r.ok?r.json():[]).then(setVideos).catch(()=>setVideos([]));
  useEffect(()=>{ load(); }, []);
  const add = async ()=>{ await fetch('/api/youtube', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({query:q})}); setQ(''); load(); };
  const openChannel = (c)=>{ setSelected(c); loadVideos(c.id); setTab('videos'); };
  return (
    <div className="p-4 space-y-4 max-w-5xl">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">YouTube / Creators</h1>
          <p className="text-sm opacity-60">Subscribe   auto-download with SponsorBlock ad/sponsor removal   optional cookies login</p>
        </div>
        <div className="flex gap-2">
          <button className={"btn btn-sm "+(tab==='channels'?'btn-primary':'btn-ghost')} onClick={()=>setTab('channels')}>Channels</button>
          <button className={"btn btn-sm "+(tab==='login'?'btn-primary':'btn-ghost')} onClick={()=>setTab('login')}>Login / Cookies</button>
        </div>
      </div>

      {tab==='login' && (
        <CookiesPastePanel />
      )}

      {tab==='channels' && (
        <>
          <div className="flex gap-2">
            <input className="input input-bordered input-sm flex-1" placeholder="@handle or channel / playlist URL" value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>e.key==='Enter'&&add()}/>
            <button className="btn btn-sm btn-primary" onClick={add}>Subscribe</button>
          </div>
          <div className="grid gap-2">
            {channels.map(c=>(
              <div key={c.id} className="flex justify-between items-center p-3 bg-base-200 rounded gap-2">
                <div className="min-w-0 cursor-pointer" onClick={()=>openChannel(c)}>
                  <div className="font-medium truncate">{c.title}</div>
                  <div className="text-xs opacity-60">{c.video_count} in feed   {c.auto_download?'auto':'manual'}</div>
                </div>
                <div className="flex gap-1 shrink-0">
                  <button className="btn btn-xs" onClick={()=>openChannel(c)}>Videos</button>
                  <button className="btn btn-xs" onClick={()=>fetch('/api/youtube/'+c.id+'/refresh',{method:'POST'}).then(load)}>Refresh</button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {tab==='videos' && selected && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <button className="btn btn-sm btn-ghost" onClick={()=>setTab('channels')}>← Channels</button>
            <h2 className="font-semibold">{selected.title}</h2>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {videos.map(v=>(
              <div key={v.id} className="p-3 bg-base-200 rounded space-y-2">
                <div className="font-medium text-sm line-clamp-2">{v.title}</div>
                <div className="text-xs opacity-60">{v.status} {v.published_at?  v.published_at.slice(0,10):''}</div>
                {v.file_path && (
                  <MediaPlayer videoId={v.id} title={v.title} />
                )}
                {!v.file_path && v.status==='wanted' && (
                  <button className="btn btn-xs btn-primary" onClick={()=>fetch('/api/youtube/videos/'+v.id+'/download',{method:'POST'}).then(()=>loadVideos(selected.id))}>Download now</button>
                )}
              </div>
            ))}
            {videos.length===0 && <p className="text-sm opacity-50">No videos yet — hit Refresh on the channel.</p>}
          </div>
        </div>
      )}
    </div>
  );
}
function CollectionsPage() {
  const [rows, setRows] = useState([]); const [q, setQ] = useState(''); const [results, setResults] = useState([]);
  const load = ()=>fetch('/api/collections').then(r=>r.json()).then(setRows).catch(()=>{});
  useEffect(()=>{ load(); }, []);
  const search = ()=>fetch('/api/collections/search?query='+encodeURIComponent(q)).then(r=>r.json()).then(setResults).catch(()=>{});
  const add = async (r)=>{ await fetch('/api/collections', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({tmdb_id:r.id||r.tmdb_id, add_all:true})}); load(); setResults([]); };
  return (<div className="p-4 space-y-4"><h1 className="text-2xl font-bold">Movie Collections</h1><div className="flex gap-2"><input className="input input-bordered input-sm flex-1" value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>e.key==='Enter'&&search()}/><button className="btn btn-sm btn-primary" onClick={search}>Search</button></div>{results.length>0 && <div className="grid gap-2">{results.map((r,i)=>(<div key={i} className="flex justify-between p-2 bg-base-200 rounded"><span>{r.name||r.title}</span><button className="btn btn-xs btn-primary" onClick={()=>add(r)}>Track</button></div>))}</div>}<div className="grid gap-3 sm:grid-cols-2">{rows.map(c=>(<div key={c.id} className="p-3 bg-base-200 rounded"><div className="font-medium">{c.name}</div><div className="text-xs opacity-60">{c.progress_label}</div><progress className="progress progress-primary h-2 w-full" value={c.total_parts?Math.round(100*c.owned/c.total_parts):0} max="100"/></div>))}</div></div>);
}
function formatTime(sec) {
  if (sec == null || isNaN(sec)) return '—';
  const s = Math.max(0, Math.floor(Number(sec)));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  if (h) return `${h}:${String(m).padStart(2,'0')}:${String(r).padStart(2,'0')}`;
  return `${m}:${String(r).padStart(2,'0')}`;
}

function PodcastsPage() {
  const [items, setItems] = useState([]);
  const [q, setQ] = useState('');
  const [results, setResults] = useState([]);
  const [selected, setSelected] = useState(null);
  const [episodes, setEpisodes] = useState([]);
  const [activeEp, setActiveEp] = useState(null);
  const [chapters, setChapters] = useState([]);
  const audioRef = useRef(null);

  const load = () => fetch('/api/podcasts').then(r => r.json()).then(setItems).catch(() => {});
  useEffect(() => { load(); }, []);

  const search = () => fetch('/api/podcasts/search?query=' + encodeURIComponent(q))
    .then(r => r.json()).then(setResults).catch(() => {});

  const add = async (r) => {
    await fetch('/api/podcasts', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ feed_url: r.feed_url }),
    });
    load(); setResults([]);
  };

  const openShow = async (p) => {
    setSelected(p); setActiveEp(null); setChapters([]);
    const eps = await fetch('/api/podcasts/' + p.id + '/episodes').then(r => r.json()).catch(() => []);
    setEpisodes(eps);
  };

  const openEpisode = async (ep) => {
    setActiveEp(ep);
    const detail = await fetch('/api/podcasts/' + selected.id + '/episodes/' + ep.id)
      .then(r => r.ok ? r.json() : null).catch(() => null);
    setChapters((detail && detail.chapters) || []);
    // load audio
    setTimeout(() => {
      if (audioRef.current) {
        audioRef.current.src = (detail && detail.audio_url) || ep.audio_url || '';
        audioRef.current.load();
      }
    }, 0);
  };

  const seekTo = (sec) => {
    if (audioRef.current) {
      audioRef.current.currentTime = sec;
      audioRef.current.play().catch(() => {});
    }
  };
  const skipIntro = () => {
    // Prefer chapter titled intro/ad, else jump to 2nd chapter, else +30s
    if (!chapters.length) { seekTo((audioRef.current?.currentTime || 0) + 30); return; }
    const intro = chapters.find(ch => /intro|advert|ad\b|sponsor|cold open/i.test(ch.title || ''));
    if (intro && chapters.indexOf(intro) < chapters.length - 1) {
      const next = chapters[chapters.indexOf(intro) + 1];
      seekTo(next.start_seconds || 0);
      return;
    }
    if (chapters.length > 1) {
      seekTo(chapters[1].start_seconds || 0);
      return;
    }
    seekTo((chapters[0].start_seconds || 0) + 30);
  };

  return (
    <div className="page-shell">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Podcasts</h1>
          <p className="text-sm opacity-60">Subscribe, auto-download, jump chapters</p>
        </div>
        <div className="flex gap-2 w-full sm:w-auto">
          <input className="input input-bordered input-sm flex-1 min-w-[12rem]"
            placeholder="Search iTunes / podcast name"
            value={q} onChange={e => setQ(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && search()} />
          <button className="btn btn-sm btn-primary" onClick={search}>Search</button>
        </div>
      </div>

      {results.length > 0 && (
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {results.map((r, i) => (
            <div key={i} className="flex gap-3 p-3 rounded-xl bg-base-200 border border-base-300 items-center">
              {r.image ? <img src={r.image} className="w-14 h-14 rounded-lg object-cover" alt="" /> : <div className="w-14 h-14 rounded-lg bg-base-300" />}
              <div className="flex-1 min-w-0">
                <div className="font-medium truncate">{r.title}</div>
                <div className="text-xs opacity-60 truncate">{r.author}</div>
              </div>
              <button className="btn btn-xs btn-primary" onClick={() => add(r)}>Subscribe</button>
            </div>
          ))}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-12">
        <div className="lg:col-span-4 space-y-2">
          <div className="section-title">Library</div>
          {items.map(it => (
            <button key={it.id} onClick={() => openShow(it)}
              className={`w-full text-left flex gap-3 p-3 rounded-xl border transition ${selected && selected.id === it.id ? 'bg-primary/15 border-primary/40' : 'bg-base-200 border-base-300 hover:border-base-content/20'}`}>
              {it.image ? <img src={it.image} className="w-12 h-12 rounded-lg object-cover" alt="" /> : <div className="w-12 h-12 rounded-lg bg-base-300" />}
              <div className="min-w-0">
                <div className="font-medium truncate text-sm">{it.title}</div>
                <div className="text-xs opacity-60">{it.episode_count || 0} episodes</div>
              </div>
            </button>
          ))}
          {!items.length && <div className="text-sm opacity-50 p-4">No podcasts yet — search above.</div>}
        </div>

        <div className="lg:col-span-8 space-y-3">
          {selected ? (
            <>
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold">{selected.title}</h2>
                <button className="btn btn-ghost btn-xs" onClick={() => fetch('/api/podcasts/' + selected.id + '/refresh', { method: 'POST' }).then(() => openShow(selected))}>Refresh feed</button>
              </div>
              <div className="space-y-1 max-h-64 overflow-y-auto rounded-xl border border-base-300 bg-base-200/40">
                {episodes.map(ep => (
                  <button key={ep.id} onClick={() => openEpisode(ep)}
                    className={`w-full text-left px-3 py-2 text-sm flex justify-between gap-2 hover:bg-base-300/50 ${activeEp && activeEp.id === ep.id ? 'bg-primary/10' : ''}`}>
                    <span className="truncate">{ep.title}</span>
                    <span className="text-xs opacity-50 shrink-0">{ep.status}</span>
                  </button>
                ))}
              </div>

              {activeEp && (
                <div className="rounded-2xl border border-base-300 bg-base-200 p-4 space-y-3">
                  <div className="font-medium">{activeEp.title}</div>
                  <audio ref={audioRef} controls className="w-full" src={activeEp.audio_url || undefined} />
                  <div className="flex gap-2">
                    <button type="button" className="btn btn-xs btn-primary" onClick={skipIntro}>Skip intro / ads</button>
                    <button type="button" className="btn btn-xs btn-ghost" onClick={()=>seekTo(0)}>Restart</button>
                  </div>
                  <div>
                    <div className="section-title mb-2">Chapters</div>
                    {chapters.length ? (
                      <div className="flex flex-wrap gap-2">
                        {chapters.map((ch, i) => (
                          <button key={i} type="button" className="btn btn-xs btn-outline gap-1"
                            onClick={() => seekTo(ch.start_seconds)}
                            title={ch.title}>
                            <span className="opacity-60 font-mono">{formatTime(ch.start_seconds)}</span>
                            <span className="max-w-[10rem] truncate">{ch.title}</span>
                          </button>
                        ))}
                      </div>
                    ) : (
                      <div className="text-xs opacity-50">No chapter markers in this episode feed.</div>
                    )}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="rounded-2xl border border-dashed border-base-300 p-10 text-center opacity-50 text-sm">
              Select a podcast to browse episodes & chapters
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Sidebar({ page, setPage, counts, onClose, advanced, enabledModules }) {
  // Flat primary nav — filtered by enabled modules (movies+tv always on)
  const em = enabledModules || ['movies','tv'];
  const primaryAll = [
    { key: 'movies', label: 'Movies', Icon: Ic.Film, count: counts.movies, mod: 'movies' },
    { key: 'tv', label: 'TV', Icon: Ic.Tv, count: counts.tv, mod: 'tv' },
    { key: 'music', label: 'Music', Icon: Ic.Music, count: counts.music, mod: 'music' },
    { key: 'books', label: 'Books', Icon: Ic.Book, count: counts.books, mod: 'books' },
    { key: 'audiobooks', label: 'Audiobooks', Icon: Ic.Headphones, count: counts.audiobooks, mod: 'audiobooks' },
    { key: 'comics', label: 'Comics', Icon: Ic.Book, mod: 'comics' },
    { key: 'discover', label: 'Discover', Icon: Ic.Compass, mod: null },
    { key: 'queue', label: 'Queue', Icon: Ic.Download, mod: null },
    { key: 'modules', label: 'Module Store', Icon: Ic.Box, mod: null },
    { key: 'settings-hub', label: 'Settings', Icon: Ic.Settings, mod: null },
  ];
  // Basic mode: core library modules only in primary; advanced unlocks Live TV / Converter nav
  const advancedOnlyMods = new Set(['livetv', 'converter']);
  const primary = primaryAll.filter(i => {
    if (!i.mod) return true;
    if (!em.includes(i.mod)) return false;
    if (!advanced && advancedOnlyMods.has(i.mod)) return false;
    return true;
  });
  const secondaryAll = [
    { key: 'dashboard', label: 'Home', Icon: Ic.Home, mod: null },
    { key: 'wanted', label: 'Wanted', Icon: Ic.AlertTri, mod: null },
    { key: 'calendar', label: 'Calendar', Icon: Ic.Calendar, mod: null },
    { key: 'requests', label: 'Requests', Icon: Ic.Inbox, count: counts.requests, mod: null },
    { key: 'livetv', label: 'Live TV', Icon: Ic.Radio, mod: 'livetv' },
  ];
  const secondary = secondaryAll.filter(i => {
    if (!i.mod) return true;
    if (!em.includes(i.mod)) return false;
    if (!advanced && advancedOnlyMods.has(i.mod)) return false;
    return true;
  });
  if (advanced) {
    if (em.includes('converter')) secondary.push({ key: 'converter-dashboard', label: 'Converter', Icon: Ic.Activity });
    secondary.push({ key: 'activity', label: 'History', Icon: Ic.Activity });
  }

  const isActive = (k) => page === k || (k === 'settings-hub' && String(page).startsWith('settings'));

  return (
    <aside className="mr-sidebar flex flex-col h-full">
      <div className="mr-brand">
        <div className="mr-brand-mark">
          <LogoMark size={28} />
        </div>
        <div>
          <div className="mr-brand-title">MediaOs</div>
          <div className="text-[10px] opacity-50 tracking-wide">media automation</div>
        </div>
        {onClose && (
          <button type="button" className="btn btn-ghost btn-xs btn-circle ml-auto lg:hidden" onClick={onClose}>✕</button>
        )}
      </div>

      <nav className="flex-1 overflow-y-auto py-3 space-y-0.5">
        {primary.map(item => (
          <button
            key={item.key}
            type="button"
            className={'mr-nav-item' + (isActive(item.key) ? ' active' : '')}
            onClick={() => { setPage(item.key); onClose && onClose(); }}
          >
            <span className="nav-icon"><item.Icon /></span>
            <span className="flex-1">{item.label}</span>
            {item.count != null && item.count > 0 && (
              <span className="text-[10px] opacity-70 tabular-nums">{item.count}</span>
            )}
          </button>
        ))}
        <div className="mx-4 my-3 border-t border-primary/10" />
        {secondary.map(item => (
          <button
            key={item.key}
            type="button"
            className={'mr-nav-item' + (isActive(item.key) ? ' active' : '')}
            onClick={() => { setPage(item.key); onClose && onClose(); }}
          >
            <span className="nav-icon"><item.Icon /></span>
            <span className="flex-1">{item.label}</span>
          </button>
        ))}
      </nav>

      <div className="mr-server-card">
        <div className="label">MediaOs Server</div>
        <div className="value">Library ready</div>
        <div className="bar"><span style={{ width: '52%' }} /></div>
        <div className="text-[10px] opacity-50 mt-1">52% planned capacity</div>
      </div>
    </aside>
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

function LibraryModuleShell({ title, nav, active, onNav, children, tools }) {
  return (
    <div className="mr-module">
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
        {/* mobile nav chips */}
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
              <button className="btn btn-xs btn-primary border-none flex-1" onClick={e=>{e.preventDefault();e.stopPropagation();onPlay(item);}}>
                Play
              </button>
            )}
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

function TeachEmpty({ title, children, actionLabel, onAction }) {
  return (
    <div className="text-center py-16 px-6 max-w-lg mx-auto">
      <h2 className="text-lg font-semibold mb-2">{title}</h2>
      <div className="text-sm text-base-content/60 space-y-2 text-left bg-base-200 rounded-lg p-4 mb-4">{children}</div>
      {onAction && <button className="btn btn-primary btn-sm" onClick={onAction}>{actionLabel||'Go'}</button>}
    </div>
  );
}

function GuidedFirstRun({ setPage }) {
  const [data, setData] = useState(null);
  const [tab, setTab] = useState('movies');
  useEffect(()=>{ fetch('/api/setup/guided').then(r=>r.json()).then(d=>{
    setData(d);
    // open first incomplete library
    const libs = d.libraries || [];
    const first = libs.find(l => !l.complete) || libs[0];
    if (first) setTab(first.id);
  }).catch(()=>{}); }, []);
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
                    <button className="btn btn-xs btn-primary shrink-0" onClick={()=>setPage(s.action)}>Go</button>
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

function GlossaryPage() {
  const [terms, setTerms] = useState([]);
  useEffect(()=>{ fetch('/api/setup/glossary').then(r=>r.json()).then(d=>setTerms(d.terms||[])).catch(()=>{}); }, []);
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

function DashboardPage({ movies, series, music=[], books=[], audiobooks=[], setPage }) {
  const recent_movies = [...movies].sort((a,b)=>new Date(b.added_at)-new Date(a.added_at)).slice(0,8);
  const recent_series = [...series].sort((a,b)=>new Date(b.added_at)-new Date(a.added_at)).slice(0,8);
  const downloading = [...movies.filter(m=>m.status==='downloading')].slice(0,5);
  const isEmpty = movies.length===0 && series.length===0;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="mr-page-title">Dashboard</h1>
          <p className="text-base-content/60 text-sm mt-0.5">Unified control surface — library, queue, calendar</p>
        </div>
        <div className="flex gap-2">
          <button className="btn btn-sm gap-2" onClick={()=>setPage('movies')}>
            <span className="w-4 h-4"><Ic.Plus /></span>Add content
          </button>
        </div>
      </div>

      <GuidedFirstRun setPage={setPage} />
      <StatsGrid movies={movies} series={series} music={music} books={books} audiobooks={audiobooks} setPage={setPage} />

      {/* Prismarr-inspired dense control strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        <button type="button" className="card bg-base-200 hover:bg-base-300 border border-base-content/5 text-left" onClick={()=>setPage('calendar')}>
          <div className="card-body p-3 gap-0.5">
            <div className="text-[10px] uppercase tracking-wide opacity-50">Calendar</div>
            <div className="text-sm font-semibold">Releases</div>
            <div className="text-[10px] opacity-50">Movies + episodes</div>
          </div>
        </button>
        <button type="button" className="card bg-base-200 hover:bg-base-300 border border-base-content/5 text-left" onClick={()=>setPage('queue')}>
          <div className="card-body p-3 gap-0.5">
            <div className="text-[10px] uppercase tracking-wide opacity-50">Queue</div>
            <div className="text-sm font-semibold">Downloads</div>
            <div className="text-[10px] opacity-50">Active + history</div>
          </div>
        </button>
        <button type="button" className="card bg-base-200 hover:bg-base-300 border border-base-content/5 text-left" onClick={()=>setPage('wanted')}>
          <div className="card-body p-3 gap-0.5">
            <div className="text-[10px] uppercase tracking-wide opacity-50">Wanted</div>
            <div className="text-sm font-semibold">Missing</div>
            <div className="text-[10px] opacity-50">Hunt &amp; search</div>
          </div>
        </button>
        <button type="button" className="card bg-base-200 hover:bg-base-300 border border-base-content/5 text-left" onClick={()=>setPage('modules')}>
          <div className="card-body p-3 gap-0.5">
            <div className="text-[10px] uppercase tracking-wide opacity-50">Modules</div>
            <div className="text-sm font-semibold">Expand</div>
            <div className="text-[10px] opacity-50">Music, comics…</div>
          </div>
        </button>
      </div>

      {isEmpty ? (
        <div className="card bg-base-200 border border-dashed border-base-content/20">
          <div className="card-body items-center text-center py-16 gap-4">
            <div className="w-16 h-16 text-base-content/20"><Ic.Library /></div>
            <h2 className="text-xl font-semibold">Your library is empty</h2>
            <button className="btn btn-primary btn-sm mt-2" onClick={()=>setPage&&setPage('setup')}>Open Setup wizard</button>
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
function MoviesPage({ movies, refreshMovies, setMiniPlayer, setPage }) {
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
      onNav={(id) => { if (['all','monitored','missing','downloaded'].includes(id)) setFilter(id); else if (id==='discover') setPage && setPage('discover'); else if (id==='queue') setPage && setPage('queue'); }}
      nav={[
        { id: 'all', label: 'Movies' },
        { id: 'monitored', label: 'Monitored' },
        { id: 'missing', label: 'Missing' },
        { id: 'downloaded', label: 'Downloaded' },
        { id: 'discover', label: 'Discover' },
        { id: 'queue', label: 'Queue' },
      ]}
      tools={<>
        <input className="mr-search" placeholder="Search movies…" value={q} onChange={e=>setQ(e.target.value)} />
        <button className="btn btn-sm btn-primary" disabled={busy} onClick={searchAllMissing}>Search missing</button>
      </>}
    >
      {msg && <div className="alert alert-info text-xs py-2 mb-3">{msg}</div>}
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
      await api.movies.grab(movieId, {
        title: rel.title,
        download_url: rel.download_url,
        indexer: rel.indexer,
        size: rel.size,
        seeders: rel.seeders,
        protocol: rel.protocol,
        quality_score: rel.score,
      });
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
      <button className="btn btn-ghost btn-sm" onClick={onBack}>← Library</button>
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
            <button className="btn btn-sm btn-primary" disabled={busy} onClick={autoSearch}>Search & grab</button>
            <button className="btn btn-sm btn-secondary" disabled={busy||ixLoading} onClick={openInteractive}>Interactive search</button>
            <button className="btn btn-sm" disabled={busy} onClick={toggleMonitor}>{movie.monitored?'Unmonitor':'Monitor'}</button>
            <button className="btn btn-sm" disabled={busy} onClick={doRefresh}>Refresh metadata</button>
            {movie.file_path && <button className="btn btn-sm" disabled={busy} onClick={doSubs}>Subtitles</button>}
            {movie.file_path && setMiniPlayer && (
              <button className="btn btn-sm" onClick={()=>setMiniPlayer({ itemId: movie.id, title: movie.title, path: movie.file_path })}>Play</button>
            )}
            {movie.file_path && <button className="btn btn-sm btn-ghost" disabled={busy} onClick={clearFile}>Clear file</button>}
            <button className="btn btn-sm btn-ghost text-error" onClick={remove}>Delete</button>
          </div>
        </div>
      </div>

      {(ixLoading || ixResults) && (
        <InteractiveResultsPanel data={ixResults} loading={ixLoading} busy={busy} onGrab={grabRel} onClose={()=>setIxResults(null)} />
      )}
          </div>
        </div>
      )}
    </div>
  );
}


function TvPage({ series, refreshSeries, setMiniPlayer, setPage }) {
  const [detailId, setDetailId] = useState(null);
  const [profiles, setProfiles] = useState([]);
  const [tvNav, setTvNav] = useState('series'); // series | add | import | mass | seasonpass
  const [q, setQ] = useState('');
  const [sort, setSort] = useState('title'); // title | progress | missing | year
  const [filter, setFilter] = useState('all'); // all | monitored | missing | complete
  const [selected, setSelected] = useState({});
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const TMDB = 'https://image.tmdb.org/t/p/w342';

  useEffect(() => { api.settings.profiles().then(setProfiles).catch(()=>{}); }, []);
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
            <h1 className="text-xl font-bold tracking-tight">
              {tvNav==='series'?'Series':tvNav==='add'?'Add Series':tvNav==='import'?'Library Import':tvNav==='mass'?'Mass Editor':'Season Pass'}
            </h1>
            {tvNav==='series' && (
              <span className="badge badge-ghost badge-sm">{list.length}</span>
            )}
          </div>
          <div className="flex items-center gap-1.5 flex-wrap">
            <button className="btn btn-ghost btn-sm gap-1" disabled={busy} onClick={updateAll} title="Search all missing episodes">
              <Ic.Refresh /> Update all
            </button>
            <button className="btn btn-ghost btn-sm gap-1" disabled={busy} onClick={async()=>{
              setBusy(true);
              for (const s of series.filter(x=>x.monitored && (x.missing_count||0)>0).slice(0,20)) {
                try { await api.tv.searchMissing(s.id); } catch(e) {}
              }
              setBusy(false); setMsg('RSS-style missing search queued'); refreshSeries && refreshSeries();
            }} title="Search monitored missing">
              <Ic.Rss /> RSS Sync
            </button>
            <label className="input input-bordered input-sm flex items-center gap-2 w-40">
              <Ic.Search />
              <input className="grow bg-transparent outline-none text-sm" placeholder="Search" value={q} onChange={e=>setQ(e.target.value)} />
            </label>
            <select className="select select-bordered select-sm w-28" value={sort} onChange={e=>setSort(e.target.value)}>
              <option value="title">Title</option>
              <option value="progress">Progress</option>
              <option value="missing">Missing</option>
              <option value="year">Year</option>
            </select>
            <select className="select select-bordered select-sm w-28" value={filter} onChange={e=>setFilter(e.target.value)}>
              <option value="all">All</option>
              <option value="monitored">Monitored</option>
              <option value="missing">Has missing</option>
              <option value="complete">Complete</option>
            </select>
          </div>
        </div>
        {msg && <div className="text-xs opacity-60">{msg}</div>}

        {tvNav==='add' && (
          <div className="space-y-3">
            <p className="text-sm opacity-60">Search TMDb and add series to the library (same as Discover → TV).</p>
            <button className="btn btn-primary btn-sm" onClick={()=>setPage && setPage('discover')}>Open Discover</button>
          </div>
        )}
        {tvNav==='import' && (
          <div className="space-y-3">
            <p className="text-sm opacity-60">Import existing folders under your TV library path, or pull from Sonarr.</p>
            <div className="flex gap-2 flex-wrap">
              <button className="btn btn-sm" onClick={()=>setPage && setPage('import')}>Manual import (downloads)</button>
              <button className="btn btn-sm" onClick={()=>setPage && setPage('settings-integrations')}>Sonarr migrator</button>
              <button className="btn btn-sm" onClick={()=>setPage && setPage('settings-library')}>Library paths</button>
            </div>
          </div>
        )}
        {tvNav==='mass' && (
          <div className="space-y-3">
            <p className="text-sm opacity-60">Select series on the grid (Series tab), then apply bulk actions here.</p>
            <div className="flex gap-2 flex-wrap">
              <button className="btn btn-sm" disabled={!Object.keys(selected).length} onClick={async()=>{
                for (const id of Object.keys(selected)) {
                  await fetch(`/api/tv/${id}`, { method:'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ monitored: true }) });
                }
                setSelected({}); refreshSeries && refreshSeries();
              }}>Monitor selected</button>
              <button className="btn btn-sm" disabled={!Object.keys(selected).length} onClick={async()=>{
                for (const id of Object.keys(selected)) {
                  await fetch(`/api/tv/${id}`, { method:'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ monitored: false }) });
                }
                setSelected({}); refreshSeries && refreshSeries();
              }}>Unmonitor selected</button>
              <button className="btn btn-sm btn-primary" disabled={!Object.keys(selected).length} onClick={async()=>{
                for (const id of Object.keys(selected)) {
                  try { await api.tv.searchMissing(Number(id)); } catch(e) {}
                }
                setMsg('Search queued for selected');
              }}>Search missing</button>
              <select className="select select-bordered select-sm" id="tv-bulk-profile" defaultValue="">
                <option value="">Bulk quality…</option>
                {tvProfiles.map(p=><option key={p.id} value={p.name}>{p.name}</option>)}
              </select>
              <button className="btn btn-sm" disabled={!Object.keys(selected).length} onClick={async()=>{
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
                      <td><button className="link link-hover font-medium" onClick={()=>setDetailId(s.id)}>{s.title}</button></td>
                      <td className="font-mono text-xs">{s.downloaded_count}/{s.episode_count}</td>
                      <td><span className="badge badge-warning badge-sm">{s.missing_count}</span></td>
                      <td className="text-xs">{s.quality_profile||'Default'}</td>
                      <td><button className="btn btn-xs btn-primary" onClick={()=>api.tv.searchMissing(s.id).then(()=>setMsg('Searching '+s.title))}>Search</button></td>
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
              <p>Use Add New, Discover → TV, or <button className="link link-primary" onClick={()=>setPage&&setPage('setup')}>Setup wizard</button>. Then open a series and search missing.</p>
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
                      <label className="absolute top-1.5 left-1.5 z-10 opacity-0 group-hover:opacity-100 transition-opacity" onClick={e=>e.stopPropagation()}>
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
                          <button className={"badge badge-xs border-0 "+(s.monitored?'badge-success':'badge-ghost')}
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
                  <button key={L} className="hover:text-primary hover:opacity-100" onClick={()=>{
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



function DiscoverPage({ movies, series, music = [], refreshMovies, refreshSeries }) {
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

  useEffect(() => { api.settings.profiles().then(setProfiles).catch(()=>{}); }, []);
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
          <button key={k} className={'btn btn-xs '+(kind===k?'btn-primary':'btn-ghost')} onClick={()=>setKind(k)}>{label}</button>
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
            <button className={'btn btn-xs '+(genreId===''?'btn-primary':'btn-ghost')} onClick={()=>setGenreId('')}>All</button>
            {genres.slice(0, 18).map(g=>(
              <button key={g.id} className={'btn btn-xs '+(String(genreId)===String(g.id)?'btn-primary':'btn-ghost')}
                onClick={()=>setGenreId(String(g.id))}>{g.name}</button>
            ))}
          </div>
          {tab==='movie' && (
            <div className="flex flex-wrap gap-1.5 items-center">
              <span className="text-[10px] uppercase opacity-40 font-semibold mr-1">Year</span>
              {['', '2026','2025','2024','2023','2022','2020','2015'].map(y=>(
                <button key={y||'any'} className={'btn btn-xs '+(year===y?'btn-primary':'btn-ghost')} onClick={()=>setYear(y)}>{y||'Any'}</button>
              ))}
            </div>
          )}
          <div className="flex flex-wrap gap-1.5 items-center">
            <span className="text-[10px] uppercase opacity-40 font-semibold mr-1">Min score</span>
            {[['','Any'],['6','6+'],['7','7+'],['8','8+']].map(([id,label])=>(
              <button key={id||'any'} className={'btn btn-xs '+(minScore===id?'btn-primary':'btn-ghost')} onClick={()=>setMinScore(id)}>{label}</button>
            ))}
          </div>
          <div className="flex flex-wrap gap-1.5 items-center">
            <span className="text-[10px] uppercase opacity-40 font-semibold mr-1">Language</span>
            {[['','Any'],['en','EN'],['ja','JA'],['ko','KO'],['zh','ZH'],['es','ES'],['fr','FR'],['de','DE']].map(([id,label])=>(
              <button key={id||'any'} className={'btn btn-xs '+(lang===id?'btn-primary':'btn-ghost')} onClick={()=>setLang(id)}>{label}</button>
            ))}
          </div>
          {tab==='tv' && (
            <div className="flex flex-wrap gap-1.5 items-center">
              <span className="text-[10px] uppercase opacity-40 font-semibold mr-1">Network</span>
              {networks.map(n=>(
                <button key={n.id||'any'} className={'btn btn-xs '+(network===n.id?'btn-primary':'btn-ghost')}
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
                  <button className="btn btn-primary btn-xs w-full mt-2" disabled={!!busy||inLib} onClick={()=>addItem(item)}>
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

  const [trashStatus, setTrashStatus] = useState(null);
  const [trashBusy, setTrashBusy] = useState(false);
  const [trashUrl, setTrashUrl] = useState('');
  const loadTrash = () => fetch('/api/quality/trash/status').then(r=>r.json()).then(setTrashStatus).catch(()=>{});
  useEffect(()=>{ loadTrash(); }, []);
  async function runTrashSync() {
    setTrashBusy(true); setMsg(null);
    try {
      const q = trashUrl ? ('?url='+encodeURIComponent(trashUrl)) : '';
      const r = await fetch('/api/quality/trash/sync'+q, { method:'POST' }).then(x=>x.json());
      setMsg(r.ok ? `TRaSH synced from ${r.source} (${r.custom_formats||0} formats)` : `TRaSH sync failed: ${(r.errors||[]).join(', ')}`);
      loadTrash(); load();
    } catch(e) { setMsg(String(e.message||e)); }
    setTrashBusy(false);
  }

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
            {'   '}Upgrades: {movieCfg.upgrade_enabled ? `on (gap ${movieCfg.upgrade_min_score_gap})` : 'off'}
            {'   '}Set <code className="text-xs">MOVIE_DOWNLOAD_MODE=strm</code> for stream-without-download
          </span>
        </div>
      )}
      {msg && <div className="alert alert-info text-sm py-2">{msg}</div>}

      <div className="card bg-base-200 border border-primary/20 shadow-sm">
        <div className="card-body p-4 gap-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="font-semibold text-sm">Live TRaSH Guides</h2>
              <p className="text-xs opacity-50">Sync custom formats &amp; scores from TRaSH (Recyclarr-style). Offline builtin fallback always available.</p>
            </div>
            <button className="btn btn-sm btn-primary" disabled={trashBusy} onClick={runTrashSync}>
              {trashBusy ? 'Syncing…' : 'Sync now'}
            </button>
          </div>
          <div className="flex flex-wrap gap-2 items-center">
            <input className="input input-bordered input-sm flex-1 min-w-[200px]" placeholder="Optional guide URL (leave blank for default/builtin)"
              value={trashUrl} onChange={e=>setTrashUrl(e.target.value)} />
          </div>
          {trashStatus && (
            <div className="text-[11px] opacity-60 flex flex-wrap gap-3">
              <span>Auto-sync: {trashStatus.auto_sync ? 'on' : 'off'}</span>
              <span>URL configured: {trashStatus.configured_url ? 'yes' : 'no'}</span>
              <span className="opacity-80">{trashStatus.message}</span>
            </div>
          )}
        </div>
      </div>

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
                <div className="text-xs opacity-60">Cutoff {p.cutoff}   Min seeders {p.min_seeders}   {(p.preferred_sources||[]).join(', ')}</div>
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
function LogsPage() {
  const [files, setFiles] = useState([]);
  const [file, setFile] = useState('mediaos.log');
  const [lines, setLines] = useState([]);
  const [level, setLevel] = useState('');
  const [q, setQ] = useState('');
  const [auto, setAuto] = useState(true);
  const [err, setErr] = useState('');
  const [dir, setDir] = useState('');
  const bottomRef = React.useRef(null);

  const loadFiles = () => fetch('/api/logs').then(r=>r.json()).then(d=>{
    setFiles(d.files||[]); setDir(d.dir||'');
    if ((d.files||[]).length && !file) setFile(d.files[0].name);
  }).catch(e=>setErr(String(e)));

  const loadTail = () => {
    const params = new URLSearchParams({ file, lines: '300' });
    if (level) params.set('level', level);
    fetch('/api/logs/tail?' + params.toString()).then(r=>r.json()).then(d=>{
      setLines(d.lines||[]);
      if (d.error) setErr(d.error); else setErr('');
    }).catch(e=>setErr(String(e.message||e)));
  };

  const doSearch = async () => {
    if (!q.trim()) return loadTail();
    const params = new URLSearchParams({ file, q, limit: '200' });
    const d = await fetch('/api/logs/search?' + params.toString()).then(r=>r.json());
    setLines(d.matches||[]);
  };

  useEffect(() => { loadFiles(); }, []);
  useEffect(() => {
    loadTail();
    if (!auto) return;
    const id = setInterval(loadTail, 4000);
    return () => clearInterval(id);
  }, [file, level, auto]);

  useEffect(() => {
    if (auto && bottomRef.current) bottomRef.current.scrollIntoView({ behavior: 'smooth' });
  }, [lines, auto]);

  function colorize(line) {
    if (line.includes('| ERROR') || line.includes('| CRITICAL')) return 'text-error';
    if (line.includes('| WARNING') || line.includes('| WARN')) return 'text-warning';
    if (line.includes('| DEBUG')) return 'opacity-50';
    if (line.includes('| INFO')) return 'text-base-content/80';
    return '';
  }

  return (
    <div className="space-y-3 max-w-6xl">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h1 className="mr-page-title">Logs</h1>
          <p className="text-xs opacity-50 font-mono">{dir || '/config/logs'}</p>
        </div>
        <div className="flex flex-wrap gap-1.5 items-center">
          <select className="select select-bordered select-xs" value={file} onChange={e=>setFile(e.target.value)}>
            {(files.length?files:[{name:'mediaos.log'},{name:'mediaos-error.log'},{name:'mediaos-access.log'}]).map(f=>(
              <option key={f.name} value={f.name}>{f.name}{f.size!=null?` (${Math.round(f.size/1024)}KB)`:''}</option>
            ))}
          </select>
          <select className="select select-bordered select-xs" value={level} onChange={e=>setLevel(e.target.value)}>
            <option value="">All levels</option>
            <option value="DEBUG">DEBUG</option>
            <option value="INFO">INFO</option>
            <option value="WARNING">WARNING</option>
            <option value="ERROR">ERROR</option>
          </select>
          <input className="input input-bordered input-xs w-40" placeholder="Search…" value={q} onChange={e=>setQ(e.target.value)}
            onKeyDown={e=>e.key==='Enter'&&doSearch()} />
          <button className="btn btn-xs" onClick={doSearch}>Search</button>
          <button className="btn btn-xs" onClick={loadTail}>Refresh</button>
          <label className="label cursor-pointer gap-1 py-0">
            <input type="checkbox" className="toggle toggle-xs" checked={auto} onChange={e=>setAuto(e.target.checked)} />
            <span className="label-text text-xs">Live</span>
          </label>
          <select className="select select-bordered select-xs" defaultValue="INFO"
            onChange={async e=>{ await fetch('/api/logs/level?level='+e.target.value,{method:'POST'}); }}>
            <option value="DEBUG">Set DEBUG</option>
            <option value="INFO">Set INFO</option>
            <option value="WARNING">Set WARNING</option>
          </select>
        </div>
      </div>
      {err && <div className="alert alert-warning text-xs py-1">{err}</div>}
      <div className="bg-base-300 rounded-lg border border-base-content/10 p-2 font-mono text-[11px] leading-relaxed max-h-[70vh] overflow-auto">
        {lines.length===0 ? <div className="opacity-40 p-4">No log lines — generate traffic or wait for jobs</div> :
          lines.map((line,i)=>(
            <div key={i} className={'whitespace-pre-wrap break-all '+colorize(line)}>{line}</div>
          ))}
        <div ref={bottomRef} />
      </div>
      <p className="text-[10px] opacity-40">Files rotate at ~10MB (app/access) and ~5MB (error). Mount <code>/config/logs</code> to persist. Env: <code>LOG_LEVEL</code>, <code>MEDIAOS_LOG_DIR</code>.</p>
    </div>
  );
}

function ActivityPage({ movies, setPage }) {
  const [tab, setTab] = useState('history'); // queue | history | blocklist
  const [events, setEvents] = useState([]);
  const [blocklist, setBlocklist] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [mediaFilter, setMediaFilter] = useState('all');
  const [q, setQ] = useState('');
  const [dateRange, setDateRange] = useState('all'); // all | 24h | 7d | 30d
  const active = (movies||[]).filter(m=>m.status==='downloading');

  const loadHistory = () => {
    const params = new URLSearchParams({ limit: '250' });
    if (filter !== 'all') params.set('event', filter);
    if (mediaFilter !== 'all') params.set('media_type', mediaFilter);
    fetch('/api/activity?' + params.toString()).then(r=>r.json())
      .then(setEvents).catch(()=>setEvents([])).finally(()=>setLoading(false));
  };
  const loadBlocklist = () => {
    fetch('/api/blocklist').then(r=>r.json()).then(setBlocklist).catch(()=>setBlocklist([]));
  };

  useEffect(() => {
    if (tab === 'history') loadHistory();
    if (tab === 'blocklist') loadBlocklist();
    const id = setInterval(() => {
      if (tab === 'history') loadHistory();
    }, 15000);
    return () => clearInterval(id);
  }, [tab, filter, mediaFilter]);

  const kindMeta = {
    grabbed:   { label: 'Grabbed',   cls: 'badge-info',    icon: '↓' },
    imported:  { label: 'Imported',  cls: 'badge-success', icon: '✓' },
    organized: { label: 'Organized', cls: 'badge-success', icon: '✓' },
    upgraded:  { label: 'Upgraded',  cls: 'badge-warning', icon: '↑' },
    failed:    { label: 'Failed',    cls: 'badge-error',   icon: '✕' },
    blocked:   { label: 'Blocked',   cls: 'badge-error',   icon: '⊘' },
    searched:  { label: 'Searched',  cls: 'badge-ghost',   icon: '⌕' },
    deleted:   { label: 'Deleted',   cls: 'badge-ghost',   icon: '⌫' },
    renamed:   { label: 'Renamed',   cls: 'badge-ghost',   icon: '✎' },
    event:     { label: 'Event',     cls: 'badge-ghost',   icon: ' ' },
  };

  function relTime(iso) {
    if (!iso) return '—';
    const t = new Date(iso).getTime();
    if (isNaN(t)) return iso;
    const s = Math.floor((Date.now() - t) / 1000);
    if (s < 60) return s + 's ago';
    if (s < 3600) return Math.floor(s/60) + 'm ago';
    if (s < 86400) return Math.floor(s/3600) + 'h ago';
    if (s < 86400*7) return Math.floor(s/86400) + 'd ago';
    return new Date(iso).toLocaleString();
  }

  function withinRange(iso) {
    if (dateRange === 'all' || !iso) return true;
    const t = new Date(iso).getTime();
    if (isNaN(t)) return true;
    const age = Date.now() - t;
    if (dateRange === '24h') return age <= 86400000;
    if (dateRange === '7d') return age <= 86400000 * 7;
    if (dateRange === '30d') return age <= 86400000 * 30;
    return true;
  }

  let rows = events;
  if (q.trim()) {
    const qq = q.toLowerCase();
    rows = rows.filter(e =>
      (e.release_title||'').toLowerCase().includes(qq) ||
      (e.message||'').toLowerCase().includes(qq) ||
      (e.media_type||'').toLowerCase().includes(qq)
    );
  }
  rows = rows.filter(e => withinRange(e.created_at || e.date || e.added_at));

  const filteredBlocklist = (blocklist||[]).filter(b => {
    if (!q.trim()) return true;
    const qq = q.toLowerCase();
    return (b.release_title||'').toLowerCase().includes(qq) || (b.reason||'').toLowerCase().includes(qq);
  });

  return (
    <div className="space-y-4 max-w-6xl">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="mr-page-title">History</h1>
          <p className="text-sm opacity-50">Sonarr/Radarr-style — grabs, imports, failures, blocklist</p>
        </div>
        <div className="tabs tabs-boxed tabs-sm">
          <a className={'tab '+(tab==='queue'?'tab-active':'')} onClick={()=>setTab('queue')}>Queue ({active.length})</a>
          <a className={'tab '+(tab==='history'?'tab-active':'')} onClick={()=>setTab('history')}>History</a>
          <a className={'tab '+(tab==='blocklist'?'tab-active':'')} onClick={()=>setTab('blocklist')}>Blocklist</a>
        </div>
      </div>

      {tab==='queue' && (
        <div className="space-y-3">
          <div className="flex justify-between items-center flex-wrap gap-2">
            <h2 className="font-semibold text-sm">Downloading now</h2>
            <button className="btn btn-xs btn-primary" onClick={()=>setPage&&setPage('queue')}>Open full Queue</button>
          </div>
          {active.length===0 ? (
            <p className="text-sm opacity-40">Queue is empty</p>
          ) : (
            <table className="table table-sm">
              <thead><tr><th>Title</th><th>Type</th><th>Status</th><th></th></tr></thead>
              <tbody>
                {active.map(m=>(
                  <tr key={m.id}>
                    <td className="font-medium">{m.title}</td>
                    <td><span className="badge badge-outline badge-sm">{m.media_type||'movie'}</span></td>
                    <td><span className="badge badge-info badge-sm">Downloading</span></td>
                    <td><button className="btn btn-ghost btn-xs" onClick={()=>setPage&&setPage('queue')}>Details</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {tab==='history' && (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2 items-center">
            <select className="select select-bordered select-xs" value={filter} onChange={e=>setFilter(e.target.value)}>
              <option value="all">All events</option>
              <option value="grab">Grabbed</option>
              <option value="import">Imported</option>
              <option value="fail">Failed</option>
              <option value="block">Blocked</option>
              <option value="upgrade">Upgraded</option>
              <option value="search">Searched</option>
            </select>
            <select className="select select-bordered select-xs" value={mediaFilter} onChange={e=>setMediaFilter(e.target.value)}>
              <option value="all">All types</option>
              <option value="movie">Movies</option>
              <option value="tv">TV</option>
              <option value="music">Music</option>
              <option value="book">Books</option>
              <option value="audiobook">Audiobooks</option>
              <option value="comic">Comics</option>
              <option value="manga">Manga</option>
            </select>
            <select className="select select-bordered select-xs" value={dateRange} onChange={e=>setDateRange(e.target.value)}>
              <option value="all">Any time</option>
              <option value="24h">Last 24h</option>
              <option value="7d">Last 7 days</option>
              <option value="30d">Last 30 days</option>
            </select>
            <input className="input input-bordered input-xs w-48" placeholder="Filter title / message…" value={q} onChange={e=>setQ(e.target.value)} />
            <button className="btn btn-xs" onClick={loadHistory}>Refresh</button>
            <span className="text-xs opacity-40">{rows.length} records</span>
          </div>

          {loading ? <span className="loading loading-spinner text-primary"/> : rows.length===0 ? (
            <div className="text-sm opacity-40 py-8">No history yet — grabs and imports appear here</div>
          ) : (
            <div className="overflow-x-auto border border-base-content/10 rounded-lg">
              <table className="table table-sm table-pin-rows">
                <thead>
                  <tr className="bg-base-300">
                    <th className="w-28">Event</th>
                    <th>Source Title</th>
                    <th className="w-20">Type</th>
                    <th className="w-36">Date</th>
                    <th className="w-28">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map(e=>{
                    const kind = e.event_kind || e.event || 'event';
                    const meta = kindMeta[kind] || kindMeta.event;
                    return (
                      <tr key={e.id} className="hover">
                        <td>
                          <span className={'badge badge-sm gap-1 border-0 '+meta.cls}>
                            <span className="opacity-70">{meta.icon}</span> {meta.label}
                          </span>
                        </td>
                        <td>
                          <div className="font-medium text-sm truncate max-w-md" title={e.release_title||e.message}>
                            {e.release_title || e.message || '—'}
                          </div>
                          {e.message && e.release_title && e.message !== e.release_title && (
                            <div className="text-xs opacity-50 truncate max-w-md">{e.message}</div>
                          )}
                        </td>
                        <td><span className="badge badge-outline badge-sm">{e.media_type||'—'}</span></td>
                        <td className="text-xs font-mono whitespace-nowrap">{relTime(e.created_at || e.date)}</td>
                        <td className="flex gap-1">
                          <button className="btn btn-ghost btn-xs" title="Blocklist this release"
                            onClick={async()=>{
                              const title = e.release_title || e.message;
                              if (!title) return;
                              await fetch('/api/blocklist',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({release_title:title,reason:'manual from history'})});
                              if (tab==='blocklist') loadBlocklist();
                            }}>Block</button>
                          {(kind==='failed' || kind==='fail') && (
                            <button className="btn btn-ghost btn-xs" title="Re-run wanted search"
                              onClick={async()=>{
                                await fetch('/api/system/search-all-missing',{method:'POST'}).catch(()=>{});
                              }}>Search</button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab==='blocklist' && (
        <div className="space-y-3">
          <div className="flex flex-wrap justify-between items-center gap-2">
            <p className="text-sm opacity-50">Permanently skipped releases</p>
            <div className="flex gap-2">
              <input className="input input-bordered input-xs w-48" placeholder="Filter blocklist…" value={q} onChange={e=>setQ(e.target.value)} />
              <button className="btn btn-xs" onClick={loadBlocklist}>Refresh</button>
            </div>
          </div>
          <div className="overflow-x-auto border border-base-content/10 rounded-lg">
            <table className="table table-sm">
              <thead>
                <tr className="bg-base-300">
                  <th>Release Title</th>
                  <th>Reason</th>
                  <th>Hash</th>
                  <th>Added</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filteredBlocklist.map(b=>(
                  <tr key={b.id} className="hover">
                    <td className="text-sm font-medium max-w-sm truncate" title={b.release_title}>{b.release_title}</td>
                    <td className="text-xs opacity-60">{b.reason||'—'}</td>
                    <td className="font-mono text-[10px] opacity-40">{(b.torrent_hash||'—').toString().slice(0,12)}</td>
                    <td className="text-xs">{b.added_at ? relTime(b.added_at) : '—'}</td>
                    <td>
                      <button className="btn btn-ghost btn-xs text-error" onClick={async()=>{
                        await fetch('/api/blocklist/'+b.id,{method:'DELETE'}).catch(()=>{});
                        loadBlocklist();
                      }}>Remove</button>
                    </td>
                  </tr>
                ))}
                {!filteredBlocklist.length && <tr><td colSpan={5} className="opacity-40 text-sm">Blocklist empty</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}



function SessionsAdminPage() {
  const [sessions, setSessions] = useState([]);
  const [me, setMe] = useState(null);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const [s, m] = await Promise.all([
        fetch('/api/auth/sessions').then(r => r.ok ? r.json() : []),
        fetch('/api/auth/me').then(r => r.ok ? r.json() : null).catch(()=>null),
      ]);
      setSessions(Array.isArray(s) ? s : []);
      setMe(m);
    } catch (e) {
      setMsg(String(e.message || e));
    }
  }
  useEffect(() => { load(); }, []);

  async function revokeOne(prefix) {
    if (!confirm('Revoke this session?')) return;
    setBusy(true);
    try {
      await fetch('/api/auth/sessions/' + encodeURIComponent(prefix.replace(/…/g,'')), { method: 'DELETE' });
      setMsg('Session revoked');
      await load();
    } catch (e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  async function revokeOthers() {
    if (!confirm('Sign out all other devices?')) return;
    setBusy(true);
    try {
      const r = await fetch('/api/auth/sessions/revoke-others', { method: 'POST' }).then(x=>x.json());
      setMsg(`Revoked ${r.revoked||0} other sessions`);
      await load();
    } catch (e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  function fmt(ts) {
    if (!ts) return '—';
    try { return new Date(ts * 1000).toLocaleString(); } catch { return String(ts); }
  }

  return (
    <div className="space-y-4 max-w-4xl">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-bold tracking-tight flex-1">Sessions</h1>
        <button className="btn btn-sm" onClick={load} disabled={busy}>Refresh</button>
        <button className="btn btn-sm btn-warning" onClick={revokeOthers} disabled={busy}>Revoke other devices</button>
      </div>
      {me && (
        <p className="text-sm opacity-70">Signed in as <span className="font-medium">{me.username}</span>
          {me.role === 'admin' && <span className="badge badge-sm badge-primary ml-2">admin</span>}
          {me.role === 'admin' && '   viewing all users'}
        </p>
      )}
      {msg && <p className="text-xs opacity-70">{msg}</p>}
      <div className="overflow-x-auto border border-base-content/10 rounded-lg">
        <table className="table table-sm">
          <thead className="bg-base-300">
            <tr>
              <th>User</th><th>Role</th><th>Token</th><th>IP</th><th>Client</th><th>Expires</th><th>Source</th><th></th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((s, i) => (
              <tr key={(s.token_prefix||'') + i} className="hover">
                <td className="font-medium">{s.username}</td>
                <td><span className="badge badge-ghost badge-sm">{s.role}</span></td>
                <td className="font-mono text-xs">{s.token_prefix}</td>
                <td className="text-xs">{s.ip || '—'}</td>
                <td className="text-xs max-w-[12rem] truncate" title={s.user_agent||''}>{s.user_agent || '—'}</td>
                <td className="text-xs whitespace-nowrap">{fmt(s.expires_at)}</td>
                <td className="text-xs">{s.source || '—'}</td>
                <td>
                  <button className="btn btn-ghost btn-xs text-error" disabled={busy}
                    onClick={() => revokeOne(s.token_prefix)}>Revoke</button>
                </td>
              </tr>
            ))}
            {!sessions.length && (
              <tr><td colSpan={8} className="opacity-50 text-sm">No active sessions (or not logged in with Bearer token)</td></tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="text-xs opacity-50">Sessions persist in the database across restarts. Admins see every user.</p>
    </div>
  );
}

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
                  placeholder={meta.placeholder || ''}
                  onChange={e=>setVal(key, e.target.value)}
                />
              )}
            </div>
          ))}
          <div className="pt-2">
            <button className="btn btn-primary btn-sm" disabled={saving} onClick={save}>
              {saving ? 'Saving…' : 'Save changes'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function SubtitlesSettingsPage({ setPage }) {
  const [fields, setFields] = useState(null);
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null);
  const [providers, setProviders] = useState([]);
  const [profiles, setProfiles] = useState([]);
  const [wantedCount, setWantedCount] = useState(null);

  const load = () => {
    api.settings.getConfig('subtitles').then(data=>{
      setFields(data);
      const f = {};
      for (const k in data) f[k] = data[k].value ?? '';
      setForm(f);
    }).catch(()=>setFields({}));
    fetch('/api/tools/subtitle-providers').then(r=>r.json()).then(setProviders).catch(()=>setProviders([]));
    setProfiles([
      {id:1,name:'English',languages:['en'],hearing_impaired:'include'},
      {id:2,name:'English + HI prefer',languages:['en'],hearing_impaired:'prefer'},
      {id:3,name:'English + Spanish',languages:['en','es'],hearing_impaired:'include'},
      {id:4,name:'Multi European',languages:['en','fr','de','es','it'],hearing_impaired:'include'},
      {id:5,name:'Any',languages:['en','es','fr','de','pt','it','ja','ko','zh'],hearing_impaired:'include'},
    ]);
    fetch('/api/tools/wanted-subtitles?limit=500').then(r=>r.json()).then(d=>{
      setWantedCount(Array.isArray(d)?d.length:(d.items||[]).length||0);
    }).catch(()=>setWantedCount(null));
  };
  useEffect(() => { load(); }, []);

  function setVal(k, v) { setForm(prev=>({ ...prev, [k]: v })); }

  function toggleProvider(name) {
    const cur = String(form.subtitle_providers || 'sidecar,opensubtitles,subdl')
      .split(',').map(s=>s.trim().toLowerCase()).filter(Boolean);
    const set = new Set(cur);
    if (set.has(name)) set.delete(name); else set.add(name);
    const order = ['sidecar','opensubtitles','opensubtitlescom','subdl','addic7ed','yifysubtitles','subscene'];
    const next = order.filter(x => set.has(x)).concat([...set].filter(x => !order.includes(x)));
    setVal('subtitle_providers', next.join(','));
  }

  async function save() {
    setSaving(true); setMsg(null);
    try {
      const updated = await api.settings.saveConfig('subtitles', form);
      setFields(updated);
      const f = {};
      for (const k in updated) f[k] = updated[k].value ?? '';
      setForm(f);
      setMsg('Saved — takes effect immediately, no restart needed.');
      fetch('/api/tools/subtitle-providers').then(r=>r.json()).then(setProviders).catch(()=>{});
    } catch(e) { setMsg(String(e.message||e)); }
    setSaving(false);
  }

  const activeProviders = String(form.subtitle_providers || '')
    .split(',').map(s=>s.trim().toLowerCase()).filter(Boolean);

  const providerCards = [
    { id:'sidecar', label:'Local sidecar', desc:'Use .srt already next to the video' },
    { id:'opensubtitles', label:'OpenSubtitles.com', desc:'API key required   hash + metadata match' },
    { id:'subdl', label:'SubDL', desc:'SUBDL_API_KEY   fast TMDb match' },
    { id:'addic7ed', label:'Addic7ed', desc:'Best-effort scrape   no key' },
    { id:'yifysubtitles', label:'YIFY Subtitles', desc:'Movies   best-effort' },
    { id:'subscene', label:'Subscene', desc:'Often blocked by Cloudflare' },
  ];

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex flex-wrap justify-between gap-3 items-start">
        <div>
          <h1 className="mr-page-title">Subtitles</h1>
          <p className="text-sm text-base-content/50">Bazarr-style multi-provider subtitles after organize</p>
        </div>
        <div className="flex gap-2">
          <button className="btn btn-sm" onClick={()=>setPage&&setPage('wanted-subtitles')}>
            Wanted {wantedCount!=null ? `(${wantedCount})` : ''}
          </button>
          <button className="btn btn-sm btn-primary" disabled={saving} onClick={save}>
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>

      {msg && <div className="alert alert-info text-sm py-2">{msg}</div>}

      <div className="card mr-panel border-0">
        <div className="card-body gap-3">
          <h2 className="font-semibold text-sm">Providers</h2>
          <p className="text-xs opacity-50">Toggle which sources to try (order: local → OpenSubtitles → SubDL → others)</p>
          <div className="grid sm:grid-cols-2 gap-2">
            {providerCards.map(p => {
              const status = (providers||[]).find(x => x.name === p.id);
              const on = activeProviders.includes(p.id);
              return (
                <label key={p.id} className={"flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition " + (on ? "border-primary/40 bg-primary/5" : "border-base-content/10 bg-base-200")}>
                  <input type="checkbox" className="checkbox checkbox-sm mt-0.5" checked={on} onChange={()=>toggleProvider(p.id)} />
                  <div className="min-w-0">
                    <div className="text-sm font-medium flex items-center gap-2">
                      {p.label}
                      {status && (
                        <span className={"badge badge-xs " + (status.configured ? "badge-success" : "badge-ghost")}>
                          {status.configured ? "ready" : "needs key"}
                        </span>
                      )}
                    </div>
                    <div className="text-xs opacity-50">{p.desc}</div>
                  </div>
                </label>
              );
            })}
          </div>
        </div>
      </div>

      <div className="card mr-panel border-0">
        <div className="card-body gap-3">
          <h2 className="font-semibold text-sm">Credentials & preferences</h2>
          {!fields ? <span className="loading loading-spinner"/> : (
            <div className="space-y-3">
              <div className="form-control">
                <label className="label py-0.5"><span className="label-text text-sm">OpenSubtitles API key</span></label>
                <input type="password" className="input input-bordered input-sm" value={form.opensubtitles_api_key||''} onChange={e=>setVal('opensubtitles_api_key', e.target.value)} placeholder="from opensubtitles.com/consumers" />
              </div>
              <div className="grid sm:grid-cols-2 gap-3">
                <div className="form-control">
                  <label className="label py-0.5"><span className="label-text text-sm">OpenSubtitles username</span></label>
                  <input className="input input-bordered input-sm" value={form.opensubtitles_username||''} onChange={e=>setVal('opensubtitles_username', e.target.value)} />
                </div>
                <div className="form-control">
                  <label className="label py-0.5"><span className="label-text text-sm">OpenSubtitles password</span></label>
                  <input type="password" className="input input-bordered input-sm" value={form.opensubtitles_password||''} onChange={e=>setVal('opensubtitles_password', e.target.value)} />
                </div>
              </div>
              <div className="form-control">
                <label className="label py-0.5"><span className="label-text text-sm">SubDL API key</span></label>
                <input type="password" className="input input-bordered input-sm" value={form.subdl_api_key||''} onChange={e=>setVal('subdl_api_key', e.target.value)} placeholder="optional" />
              </div>
              <div className="grid sm:grid-cols-2 gap-3">
                <div className="form-control">
                  <label className="label py-0.5"><span className="label-text text-sm">Languages (ISO 639-1, priority order)</span></label>
                  <input className="input input-bordered input-sm" value={form.subtitle_languages||'en'} onChange={e=>setVal('subtitle_languages', e.target.value)} placeholder="en,es,fr" />
                </div>
                <div className="form-control">
                  <label className="label py-0.5"><span className="label-text text-sm">Hearing-impaired</span></label>
                  <select className="select select-bordered select-sm" value={form.subtitle_hearing_impaired||'include'} onChange={e=>setVal('subtitle_hearing_impaired', e.target.value)}>
                    <option value="prefer">Prefer HI</option>
                    <option value="include">Include HI</option>
                    <option value="exclude">Exclude HI</option>
                  </select>
                </div>
              </div>
              <div className="form-control">
                <label className="label py-0.5"><span className="label-text text-sm">Provider list (advanced)</span></label>
                <input className="input input-bordered input-sm font-mono text-xs" value={form.subtitle_providers||''} onChange={e=>setVal('subtitle_providers', e.target.value)} />
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="card mr-panel border-0">
        <div className="card-body gap-3">
          <h2 className="font-semibold text-sm">Language profiles</h2>
          <p className="text-xs opacity-50">Quick-apply presets to the languages field</p>
          <div className="flex flex-wrap gap-2">
            {profiles.map(p=>(
              <button key={p.id} type="button" className="btn btn-sm btn-outline"
                onClick={()=>{
                  setVal('subtitle_languages', (p.languages||[]).join(','));
                  if (p.hearing_impaired) setVal('subtitle_hearing_impaired', p.hearing_impaired);
                }}>
                {p.name}
                <span className="opacity-50 text-xs ml-1">{(p.languages||[]).join('+')}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="flex gap-2">
        <button className="btn btn-primary" disabled={saving} onClick={save}>{saving?'Saving…':'Save changes'}</button>
        <button className="btn" onClick={load}>Reset</button>
      </div>
    </div>
  );
}

function WantedSubtitlesPage({ setPage }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState('');
  useEffect(()=>{
    fetch('/api/tools/wanted-subtitles').then(r=>r.json()).then(setItems).catch(()=>setItems([])).finally(()=>setLoading(false));
  }, []);
  async function fetchSubs(row) {
    setMsg('Searching…');
    try {
      const path = row.kind==='movie' ? `/api/movies/${row.id}/subtitles` : `/api/tv/episodes/${row.id}/subtitles`;
      const r = await fetch(path, {method:'POST'}).then(x=>x.json()).catch(()=>({}));
      setMsg(JSON.stringify(r).slice(0,120));
    } catch(e){ setMsg(String(e.message||e)); }
  }
  return (
    <div className="space-y-4 max-w-4xl">
      <div className="flex justify-between items-center">
        <div><h1 className="mr-page-title">Wanted Subtitles</h1>
        <p className="text-sm opacity-50">Bazarr-style wanted list — OpenSubtitles (+ configured providers). Settings → Subtitles for API keys.</p></div>
        <button className="btn btn-sm" onClick={()=>setPage&&setPage('settings-subtitles')}>Subtitle settings</button>
      </div>
      {loading ? <span className="loading loading-spinner"/> : (
        <table className="table table-sm"><thead><tr><th>Type</th><th>Title</th><th>Path</th><th></th></tr></thead><tbody>
          {items.map((row,i)=>(
            <tr key={i}><td className="text-xs">{row.kind}</td><td className="text-sm font-medium">{row.title}</td>
            <td className="text-xs font-mono opacity-50 truncate max-w-xs">{row.file_path||'—'}</td>
            <td><button className="btn btn-xs btn-primary" onClick={()=>fetchSubs(row)}>Fetch</button></td></tr>
          ))}
          {!items.length && <tr><td colSpan={4} className="opacity-40">Nothing listed</td></tr>}
        </tbody></table>
      )}
      {msg && <p className="text-xs opacity-60">{msg}</p>}
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
      await api.tv.grabEpisode(epId, {
        title: rel.title,
        download_url: rel.download_url,
        indexer: rel.indexer,
        size: rel.size,
        seeders: rel.seeders,
        score: rel.score,
        protocol: rel.protocol || 'torrent',
      });
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
  if (!series) return <div className="p-6"><button className="btn btn-sm" onClick={onBack}>Back</button><p className="mt-4 opacity-50">Series not found</p></div>;

  const tvProfiles = (profiles||[]).filter(p=>p.media_type==='tv');
  const dl = series.downloaded_count||0;
  const ep = series.episode_count||0;
  const shownSeasons = seasonTab==='all' ? seasons : seasons.filter(s=>String(s.season)===String(seasonTab));

  return (
    <div className="space-y-4 max-w-6xl">
      <button className="btn btn-ghost btn-sm" onClick={onBack}>← Series</button>
      <div className="flex flex-col md:flex-row gap-4">
        <div className="w-40 shrink-0">
          {series.poster_path
            ? <img src={TMDB+series.poster_path} className="rounded-lg shadow-lg w-full" alt=""/>
            : <div className="aspect-[2/3] bg-base-200 rounded-lg"/>}
        </div>
        <div className="flex-1 space-y-2">
          <h1 className="text-2xl font-bold">{series.title}{series.year?` (${series.year})`:''}</h1>
          <div className="flex flex-wrap gap-2 items-center">
            <button className={"badge badge-lg border-0 "+(series.monitored?'badge-success':'badge-ghost')} onClick={toggleMonitored}>
              {series.monitored?'Monitored':'Not monitored'}
            </button>
            <span className="badge badge-lg badge-outline font-mono">{dl}/{ep}</span>
            <span className="badge badge-outline">{series.series_type||'standard'}</span>
            <select className="select select-bordered select-sm" value={series.quality_profile||''} onChange={e=>setProfile(e.target.value)}>
              <option value="">Default profile</option>
              {tvProfiles.map(p=><option key={p.id} value={p.name}>{p.name}</option>)}
            </select>
          </div>
          <progress className="progress progress-primary w-full max-w-md h-2" value={ep?Math.round(100*dl/ep):0} max="100" />
          {series.overview && <p className="text-sm opacity-70 line-clamp-4 max-w-2xl">{series.overview}</p>}
          <div className="flex flex-wrap gap-2">
            <button className="btn btn-primary btn-sm" disabled={busy} onClick={searchMissing}>Search missing (auto)</button>
            <button className="btn btn-sm" disabled={busy} onClick={refreshMeta}>Refresh metadata</button>
            <button className="btn btn-sm" onClick={load}>Reload</button>
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
                <button className="btn btn-xs" disabled={busy} onClick={()=>openInteractiveSeason(season)}>Interactive search</button>
                <button className="btn btn-xs btn-primary" disabled={busy} onClick={()=>searchSeason(season)}>Auto season</button>
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
                          <button className="btn btn-ghost btn-xs" onClick={()=>openInteractiveEpisode(e)} title="Interactive search">Search</button>
                          {have && <button className="btn btn-ghost btn-xs" onClick={()=>setPlayingEp(e)}>Play</button>}
                          {have && <button className="btn btn-ghost btn-xs" onClick={()=>fileAction(e,'clear')} title="Unlink file">Unlink</button>}
                          {have && <button className="btn btn-ghost btn-xs text-error" onClick={()=>fileAction(e,'delete')} title="Delete file">Del</button>}
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
            <button className="btn btn-xs" onClick={()=>setPlayingEp(null)}>Close</button>
          </div>
          <MediaPlayer episodeId={playingEp.id} title={playingEp.title} onClose={()=>setPlayingEp(null)} />
        </div>
      )}
    </div>
  );
}


function BooksAuthorsTree() {
  const [authors, setAuthors] = useState([]);
  useEffect(()=>{ fetch('/api/books/library/authors').then(r=>r.json()).then(d=>setAuthors(d.authors||[])).catch(()=>{}); }, []);
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

function BooksPage({ setPage }) {
  const [items, setItems] = useState([]);
  const [nav, setNav] = useState('library');
  const [q, setQ] = useState('');
  const [results, setResults] = useState([]);
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState(null);
  const load = () => api.books.list().then(setItems).catch(()=>[]).finally(()=>setLoading(false));
  useEffect(() => { load(); }, []);

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
  const hasFile = b => !!(b.file_path || b.status==='downloaded');
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
            <li key={n.id}><button className={(nav===n.id?'active ':'')+'rounded-lg'} onClick={()=>setNav(n.id)}><n.Icon /> {n.label}</button></li>
          ))}
        </ul>
        <div className="divider my-3"></div>
        <ul className="menu menu-sm gap-0.5 p-0">
          <li><button onClick={()=>setPage&&setPage('queue')}><Ic.Download /> Queue</button></li>
          <li><button onClick={()=>setPage&&setPage('settings-library')}><Ic.Folder /> Library paths</button></li>
          <li><button onClick={()=>setPage&&setPage('audiobooks')}><Ic.Headphones /> Audiobooks</button></li>
        </ul>
        <div className="mt-4 px-2 text-[10px] opacity-40">{items.length} books</div>
      </aside>
      <div className="flex-1 min-w-0 space-y-4 md:pl-4">
        <div className="flex flex-wrap items-center gap-2 justify-between">
          <h1 className="text-xl font-bold tracking-tight">{nav==='library'?'Books':nav==='add'?'Add Book':'Wanted'}</h1>
          <div className="flex gap-1.5 flex-wrap">
            <form onSubmit={doSearch} className="flex gap-1">
              <label className="input input-bordered input-sm flex items-center gap-2 w-48">
                <Ic.Search /><input className="grow bg-transparent outline-none text-sm" placeholder="Search Open Library" value={q} onChange={e=>setQ(e.target.value)} />
              </label>
              <button className="btn btn-sm btn-primary">Search</button>
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
                <button className="btn btn-xs btn-primary" onClick={()=>addBook(r)}>Add</button>
              </div>
            ))}
            {!results.length && <p className="text-sm opacity-50">Search Open Library above</p>}
          </div>
        )}
        {nav==='authors' && <BooksAuthorsTree />}
        {nav==='wanted' && (
          <table className="table table-sm"><thead><tr><th>Title</th><th></th></tr></thead><tbody>
            {items.filter(b=>b.monitored&&!hasFile(b)).map(b=>(
              <tr key={b.id}><td>{b.title}</td><td><button className="btn btn-xs btn-primary" onClick={()=>searchGrab(b.id)}>Search</button></td></tr>
            ))}
          </tbody></table>
        )}
        {nav==='library' && (
          loading ? <span className="loading loading-spinner"/> :
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
            {list.map(b=>{
              const ok = hasFile(b);
              return (
                <div key={b.id} className="group rounded-lg overflow-hidden bg-base-200 shadow-sm hover:ring-2 hover:ring-primary/40">
                  <div className="aspect-[2/3] bg-base-300 relative flex items-center justify-center">
                    {b.poster_path ? <img src={b.poster_path.startsWith('http')?b.poster_path:('https://covers.openlibrary.org/b/id/'+b.poster_path+'-M.jpg')} className="w-full h-full object-cover" alt="" loading="lazy"/> : <Ic.Book />}
                    <div className={"absolute bottom-0 left-0 right-0 h-1.5 "+(ok?'bg-success':b.monitored?'bg-warning':'bg-base-content/20')} />
                    <div className={"absolute bottom-2 left-2 badge badge-sm border-0 text-white "+(ok?'bg-success':'bg-warning')}>{ok?'Have':'Want'}</div>
                  </div>
                  <div className="p-2 space-y-0.5">
                    <div className="text-xs font-semibold line-clamp-2 min-h-[2rem]">{b.title}</div>
                    <span className={"badge badge-xs "+(b.monitored?'badge-success':'badge-ghost')}>{b.monitored?'Monitored':'Off'}</span>
                    <div className="flex gap-1 opacity-0 group-hover:opacity-100">
                      <button className="btn btn-ghost btn-xs" onClick={()=>searchGrab(b.id)}>Search</button>
                      <button className="btn btn-ghost btn-xs text-error" onClick={async()=>{await api.books.remove(b.id); load();}}>Del</button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}



function EpgTimeline() {
  const [grid, setGrid] = useState(null);
  const [hours, setHours] = useState(4);
  const [group, setGroup] = useState('');
  const [loading, setLoading] = useState(true);
  const [groups, setGroups] = useState([]);
  const [mode, setMode] = useState('timeline'); // timeline | now

  const load = () => {
    setLoading(true);
    const q = new URLSearchParams({ hours: String(hours) });
    if (group) q.set('group', group);
    fetch('/api/livetv/epg/grid?' + q.toString()).then(r=>r.json())
      .then(d=>{
        setGrid(d);
        const gs = [...new Set((d.channels||[]).map(c=>c.group).filter(Boolean))].sort();
        setGroups(gs);
      }).catch(()=>setGrid(null)).finally(()=>setLoading(false));
  };
  useEffect(()=>{ load(); const i=setInterval(load, 120000); return ()=>clearInterval(i); }, [hours, group]);

  const channels = grid?.channels || [];
  const slots = grid?.slots || [];
  const fromMs = grid?.from ? new Date(grid.from).getTime() : Date.now();
  const toMs = grid?.to ? new Date(grid.to).getTime() : fromMs + hours*3600000;
  const span = Math.max(1, toMs - fromMs);
  const pxPerMs = 180 / (30*60*1000); // ~180px per 30 min
  const totalWidth = Math.max(600, (span / (30*60*1000)) * 180);

  function blockStyle(prog) {
    const s = prog.start_dt ? new Date(prog.start_dt).getTime() : (prog.start ? new Date(prog.start).getTime() : fromMs);
    const e = prog.stop_dt ? new Date(prog.stop_dt).getTime() : (prog.stop ? new Date(prog.stop).getTime() : s + 30*60*1000);
    const left = Math.max(0, (s - fromMs) / span * totalWidth);
    const width = Math.max(40, (e - s) / span * totalWidth);
    return { left: left + 'px', width: width + 'px' };
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2 items-center justify-between">
        <div>
          <h2 className="font-semibold">EPG Guide</h2>
          <p className="text-xs opacity-50">{channels.length} channels   horizontal timeline</p>
        </div>
        <div className="flex gap-2 items-center flex-wrap">
          <div className="tabs tabs-boxed tabs-xs">
            <a className={'tab '+(mode==='timeline'?'tab-active':'')} onClick={()=>setMode('timeline')}>Timeline</a>
            <a className={'tab '+(mode==='now'?'tab-active':'')} onClick={()=>setMode('now')}>Now/Next</a>
          </div>
          <select className="select select-bordered select-xs" value={hours} onChange={e=>setHours(Number(e.target.value))}>
            {[2,4,6,12].map(h=><option key={h} value={h}>{h}h</option>)}
          </select>
          <select className="select select-bordered select-xs" value={group} onChange={e=>setGroup(e.target.value)}>
            <option value="">All groups</option>
            {groups.map(g=><option key={g} value={g}>{g}</option>)}
          </select>
          <button className="btn btn-xs" onClick={load}>Refresh</button>
          <button className="btn btn-xs btn-ghost" onClick={async()=>{ await fetch('/api/livetv/epg/refresh',{method:'POST'}).catch(()=>{}); load(); }}>Reload XMLTV</button>
        </div>
      </div>
      {loading && !grid ? <span className="loading loading-spinner"/> : mode==='now' ? (
        <div className="overflow-auto max-h-[70vh] border border-base-content/10 rounded-lg">
          <table className="table table-xs table-pin-rows">
            <thead><tr className="bg-base-300"><th>Channel</th><th>Now</th><th>Next</th></tr></thead>
            <tbody>
              {channels.map(ch=>(
                <tr key={ch.id} className="hover">
                  <td className="text-xs font-medium">{ch.name}</td>
                  <td className="text-xs">{ch.now?.title||'—'}</td>
                  <td className="text-xs opacity-70">{ch.next?.title||'—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="overflow-auto max-h-[70vh] border border-base-content/10 rounded-lg">
          {/* time header */}
          <div className="flex sticky top-0 z-20 bg-base-300 border-b border-base-content/10">
            <div className="w-36 shrink-0 p-2 text-xs font-semibold sticky left-0 bg-base-300 z-30">Channel</div>
            <div className="relative h-8" style={{width: totalWidth+'px'}}>
              {slots.map((s,i)=>(
                <div key={i} className="absolute top-0 bottom-0 border-l border-base-content/10 text-[10px] opacity-50 pl-1"
                  style={{left: ((new Date(s).getTime()-fromMs)/span*totalWidth)+'px'}}>
                  {new Date(s).toISOString().slice(11,16)}
                </div>
              ))}
            </div>
          </div>
          {channels.map(ch=>(
            <div key={ch.id} className="flex border-b border-base-content/5 hover:bg-base-200/40">
              <div className="w-36 shrink-0 p-1.5 sticky left-0 bg-base-200 z-10 flex items-center gap-1.5">
                {ch.logo ? <img src={ch.logo} className="w-6 h-6 rounded object-cover" alt=""/> : <div className="w-6 h-6 rounded bg-base-300"/>}
                <span className="text-[11px] font-medium truncate">{ch.name}</span>
              </div>
              <div className="relative h-12" style={{width: totalWidth+'px', minHeight:'3rem'}}>
                {(ch.programmes||[]).map((prog,i)=>(
                  <div key={i} className="absolute top-1 bottom-1 rounded bg-primary/20 border border-primary/30 px-1 overflow-hidden"
                    style={blockStyle(prog)} title={(prog.title||'')+' '+(prog.start||'')}>
                    <div className="text-[10px] font-medium truncate leading-tight pt-0.5">{prog.title||'Programme'}</div>
                  </div>
                ))}
                {!(ch.programmes||[]).length && ch.now && (
                  <div className="absolute top-1 bottom-1 left-0 right-1/2 rounded bg-base-content/10 px-1 text-[10px] truncate pt-1">{ch.now.title}</div>
                )}
              </div>
            </div>
          ))}
          {!channels.length && <p className="p-4 text-sm opacity-40">No channels — add M3U and refresh EPG</p>}
        </div>
      )}
    </div>
  );
}


function LiveTvPage() {
  const [tvTab, setTvTab] = useState('channels'); // channels | epg | nownext
  const [sources, setSources] = useState([]);
  const [channels, setChannels] = useState([]);
  const [q, setQ] = useState('');
  const [groupFilter, setGroupFilter] = useState('');
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [kind, setKind] = useState('m3u');
  const [msg, setMsg] = useState(null);
  const [playing, setPlaying] = useState(null);
  const [lineup, setLineup] = useState(null);
  const load = () => {
    api.livetv.sources().then(setSources).catch(()=>[]);
    api.livetv.channels(q).then(setChannels).catch(()=>[]);
    fetch('/api/overhaul/livetv/now-next').then(r=>r.json()).then(setLineup).catch(()=>null);
  };
  useEffect(() => { load(); }, []);
  const groups = [...new Set((channels||[]).map(c=>c.group_title||c.group).filter(Boolean))].sort();
  const filtered = (channels||[]).filter(c => {
    if (groupFilter && (c.group_title||c.group) !== groupFilter) return false;
    return true;
  });
  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="mr-page-title">Live TV / IPTV</h1>
        <p className="text-sm text-base-content/50">M3U · Xtream · EPG · Now/Next · play in browser</p>
        <div className="flex flex-wrap gap-2 mt-2">
          <button className="btn btn-sm btn-secondary" onClick={async()=>{
            setMsg('Seeding iptv-org defaults (US + Entertainment)…');
            try {
              const r = await fetch('/api/livetv/presets/iptv-org/seed',{method:'POST'}).then(x=>x.json());
              setMsg(`iptv-org: created ${JSON.stringify(r.created||[])} synced ${JSON.stringify(r.synced||[])}`);
              load();
            } catch(e) { setMsg(String(e.message||e)); }
          }}>Add iptv-org defaults</button>
          <button className="btn btn-sm" onClick={async()=>{
            setMsg('Re-syncing iptv-org sources…');
            try {
              const r = await fetch('/api/livetv/presets/iptv-org/resync',{method:'POST'}).then(x=>x.json());
              setMsg('Resync: ' + JSON.stringify(r.results||r));
              load();
            } catch(e) { setMsg(String(e.message||e)); }
          }}>Refresh iptv-org</button>
          <button className="btn btn-sm" onClick={async()=>{
            setMsg('Installing channel logos from playlist URLs…');
            try {
              const r = await fetch('/api/livetv/logos/install-remote',{method:'POST'}).then(x=>x.json());
              setMsg(`Logos: downloaded ${r.downloaded||0}, skipped ${r.skipped||0}, failed ${r.failed||0}`);
              load();
            } catch(e) { setMsg(String(e.message||e)); }
          }}>Install channel logos</button>
          <a className="btn btn-sm btn-ghost" href="https://github.com/iptv-org/iptv" target="_blank" rel="noreferrer">iptv-org on GitHub</a>
        </div>
        <div className="tabs tabs-boxed tabs-sm w-fit mt-2">
          <a className={'tab '+(tvTab==='channels'?'tab-active':'')} onClick={()=>setTvTab('channels')}>Channels</a>
          <a className={'tab '+(tvTab==='epg'?'tab-active':'')} onClick={()=>setTvTab('epg')}>EPG Timeline</a>
          <a className={'tab '+(tvTab==='nownext'?'tab-active':'')} onClick={()=>setTvTab('nownext')}>Now / Next</a>
        </div>
      </div>

      {tvTab==='epg' && <EpgTimeline />}

      {tvTab==='nownext' && (
        <div className="card bg-base-200">
          <div className="card-body p-3 gap-2">
            <div className="flex justify-between items-center">
              <h2 className="font-semibold text-sm">Now / Next</h2>
              <button className="btn btn-xs" onClick={async()=>{
                setMsg('Syncing EPG…');
                await fetch('/api/overhaul/epg/sync',{method:'POST'}).catch(()=>{});
                load(); setMsg('EPG sync requested');
              }}>Sync EPG</button>
            </div>
            <div className="overflow-x-auto max-h-[32rem]">
              <table className="table table-xs">
                <thead><tr><th>Channel</th><th>Now</th><th>Next</th></tr></thead>
                <tbody>
                  {((lineup && lineup.channels) || (lineup && Array.isArray(lineup) ? lineup : []) || []).slice(0,200).map((c,i)=>(
                    <tr key={c.id||c.tvg_id||i}>
                      <td className="font-medium text-xs">{c.name||c.channel||'—'}</td>
                      <td className="text-xs opacity-80">{c.now?.title||c.now_title||'—'}</td>
                      <td className="text-xs opacity-50">{c.next?.title||c.next_title||'—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!lineup && <p className="text-xs opacity-50">No EPG lineup — add XMLTV / sync EPG</p>}
            </div>
          </div>
        </div>
      )}

      {tvTab==='channels' && (
        <>
          <div className="card mr-panel border-0">
            <div className="card-body gap-2">
              <h2 className="font-semibold">Add source</h2>
              <div className="flex flex-wrap gap-2">
                <select className="select select-bordered select-sm" value={kind} onChange={e=>setKind(e.target.value)}>
                  <option value="m3u">M3U</option>
                  <option value="xtream">Xtream</option>
                </select>
                <input className="input input-bordered input-sm" placeholder="Name" value={name} onChange={e=>setName(e.target.value)} />
                <input className="input input-bordered input-sm flex-1 min-w-[16rem]" placeholder="URL / host" value={url} onChange={e=>setUrl(e.target.value)} />
                <button className="btn btn-sm btn-primary" onClick={async()=>{
                  await api.livetv.addSource({name: name||kind.toUpperCase(), kind, url});
                  setName(''); setUrl(''); load();
                }}>Add</button>
              </div>
            </div>
          </div>
          <div className="space-y-2">
            <h2 className="font-semibold">Sources</h2>
            {sources.map(s=>(
              <div key={s.id} className="flex items-center gap-2 text-sm flex-wrap">
                <span className="font-medium">{s.name}</span>
                <span className="badge badge-xs">{s.kind}</span>
                <span className="opacity-50">{s.channel_count} ch</span>
                <button className="btn btn-xs" onClick={async()=>{ setMsg('Syncing…'); const r=await api.livetv.sync(s.id); setMsg(`Synced ${r.synced}`); load(); }}>Sync</button>
              </div>
            ))}
          </div>
          {msg && <div className="alert alert-info text-sm py-2">{msg}</div>}
          <div className="flex flex-wrap gap-2">
            <input className="input input-bordered input-sm flex-1" placeholder="Filter channels…" value={q} onChange={e=>setQ(e.target.value)}
              onKeyDown={e=>{ if(e.key==='Enter') api.livetv.channels(q).then(setChannels); }} />
            <select className="select select-bordered select-sm" value={groupFilter} onChange={e=>setGroupFilter(e.target.value)}>
              <option value="">All groups</option>
              {groups.map(g=><option key={g} value={g}>{g}</option>)}
            </select>
            <button className="btn btn-sm" onClick={()=>api.livetv.channels(q).then(setChannels)}>Search</button>
          </div>
          <div className="overflow-x-auto max-h-[28rem]">
            <table className="table table-xs">
              <thead><tr><th></th><th>Name</th><th>Group</th><th></th></tr></thead>
              <tbody>
                {filtered.map(c=>(
                  <tr key={c.id}>
                    <td className="w-10">
                      {c.logo
                        ? <img src={c.logo} alt="" className="w-8 h-8 rounded object-contain bg-base-300" onError={e=>{ e.currentTarget.style.display='none'; }} />
                        : <div className="w-8 h-8 rounded bg-base-300" />}
                    </td>
                    <td className="font-medium">{c.name}</td>
                    <td className="opacity-60">{c.group_title||c.group||'—'}</td>
                    <td>
                      <button className="btn btn-xs btn-primary" onClick={()=>setPlaying(c)}>Play</button>
                      <a className="btn btn-xs btn-ghost" href={c.stream_url} target="_blank" rel="noreferrer">Open</a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {playing && (
        <div className="modal modal-open">
          <div className="modal-box max-w-3xl">
            <h3 className="font-bold text-sm">{playing.name}</h3>
            <video className="w-full mt-2 bg-black rounded" controls autoPlay src={playing.stream_url} />
            <div className="modal-action">
              <button className="btn btn-sm" onClick={()=>setPlaying(null)}>Close</button>
            </div>
          </div>
          <div className="modal-backdrop" onClick={()=>setPlaying(null)} />
        </div>
      )}
    </div>
  );
}


function AudiobooksPage({ setPage }) {
  const [items, setItems] = useState([]);
  const [detailId, setDetailId] = useState(null);
  const [q, setQ] = useState('');
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = () => api.audiobooks.list().then(setItems).catch(()=>[]);
  useEffect(()=>{ load(); }, []);

  if (detailId) return <AudiobookDetailPage id={detailId} onBack={()=>{ setDetailId(null); load(); }} />;

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
      const r = await api.audiobooks.searchMissing();
      setMsg(`Searched ${r.searched||0}   grabbed ${r.grabbed||0}`);
      load();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }

  const filtered = (items||[]).filter(a => !q || (a.title||'').toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="mr-page-title flex-1">Audiobooks</h1>
        <button className="btn btn-sm btn-primary" disabled={busy} onClick={searchMissing}>Search missing</button>
      </div>
      {msg && <div className="alert alert-info text-xs py-2">{msg}</div>}
      <input className="input input-bordered input-sm" placeholder="Filter…" value={q} onChange={e=>setQ(e.target.value)} />
      <div className="space-y-2 max-w-3xl">
        {filtered.map(a => (
          <div key={a.id} className="mr-row cursor-pointer" onClick={() => setDetailId(a.id)}>
            {a.poster_path
              ? <img className="thumb" src={a.poster_path} alt="" />
              : <div className="thumb flex items-center justify-center text-xs opacity-30">AB</div>}
            <div className="flex-1 min-w-0">
              <div className="font-semibold text-sm truncate">{a.title}</div>
              <div className="text-xs opacity-50 truncate">{a.artist_name || a.series_name || a.status}</div>
            </div>
            <div className="mr-progress"><span style={{ width: a.status==='downloaded' ? '100%' : '40%' }} /></div>
            <span className="text-xs opacity-60 w-10 text-right">{a.status==='downloaded'?'100%':'40%'}</span>
          </div>
        ))}
        {!filtered.length && <div className="opacity-50 text-sm p-8 text-center">No audiobooks yet</div>}
      </div>
      <LibraryLegend showTv={false} showSeries={true} />
    </div>
  );
}

function AudiobookDetailPage({ id, onBack }) {
  const [item, setItem] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const [ixResults, setIxResults] = useState(null);
  const [ixLoading, setIxLoading] = useState(false);
  const load = React.useCallback(() => { api.audiobooks.get(id).then(setItem).catch(e=>setMsg(String(e.message||e))); }, [id]);
  useEffect(()=>{ load(); }, [load]);

  async function autoSearch() {
    setBusy(true);
    try {
      const r = await api.audiobooks.searchNow(id);
      setMsg(r?.title ? `Grabbed: ${r.title}` : (r?.found===false ? 'No release found' : JSON.stringify(r)));
      load();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  async function openIx() {
    setIxLoading(true); setIxResults([]);
    try { setIxResults(await api.audiobooks.interactive(id) || []); }
    catch(e) { setMsg(String(e.message||e)); }
    setIxLoading(false);
  }
  async function grabRel(rel) {
    setBusy(true);
    try {
      await api.audiobooks.grab(id, rel);
      setMsg('Grabbed: '+rel.title); setIxResults(null); load();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  async function toggleMon() {
    setBusy(true);
    try { await api.audiobooks.update(id, { monitored: !item.monitored }); load(); }
    catch(e) { setMsg(String(e.message||e)); }
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
        <button className="btn btn-sm btn-primary" disabled={busy} onClick={autoSearch}>Search & grab</button>
        <button className="btn btn-sm btn-secondary" disabled={busy||ixLoading} onClick={openIx}>Interactive search</button>
        <button className="btn btn-sm" disabled={busy} onClick={toggleMon}>{item.monitored?'Unmonitor':'Monitor'}</button>
        <button className="btn btn-sm btn-ghost text-error" onClick={async()=>{ await api.audiobooks.remove(id); onBack(); }}>Delete</button>
      </>}
    >
      <InteractiveResultsTable results={ixResults} loading={ixLoading} busy={busy} onGrab={grabRel} onClose={()=>setIxResults(null)} />
    </MediaDetailShell>
  );
}


function CalendarPage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [cursor, setCursor] = useState(() => {
    const d = new Date();
    return new Date(d.getFullYear(), d.getMonth(), 1);
  });
  const [selected, setSelected] = useState(null); // YYYY-MM-DD
  const [filter, setFilter] = useState('all'); // all | episode | movie

  const load = () => {
    setLoading(true);
    const start = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
    const end = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0);
    const pad = (n) => String(n).padStart(2,'0');
    const fmt = (d) => `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;
    // expand range slightly for list continuity
    const s = new Date(start); s.setDate(s.getDate() - 7);
    const e = new Date(end); e.setDate(e.getDate() + 7);
    api.calendar.list(fmt(s), fmt(e)).then(setItems).catch(()=>[]).finally(()=>setLoading(false));
  };
  useEffect(() => { load(); }, [cursor]);

  const today = new Date().toISOString().slice(0,10);
  const byDate = {};
  (items||[]).forEach(it => {
    if (filter !== 'all' && it.kind && it.kind !== filter) return;
    // legacy items without kind are episodes
    const kind = it.kind || 'episode';
    if (filter !== 'all' && kind !== filter) return;
    (byDate[it.air_date] = byDate[it.air_date] || []).push({...it, kind});
  });

  // Month grid
  const year = cursor.getFullYear();
  const month = cursor.getMonth();
  const firstDow = new Date(year, month, 1).getDay(); // 0 Sun
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells = [];
  for (let i = 0; i < firstDow; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) {
    const key = `${year}-${String(month+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
    cells.push({ day: d, key, events: byDate[key] || [] });
  }
  while (cells.length % 7 !== 0) cells.push(null);

  const monthLabel = cursor.toLocaleString(undefined, { month: 'long', year: 'numeric' });
  const selectedEvents = selected ? (byDate[selected] || []) : [];

  return (
    <div className="space-y-4 max-w-6xl">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex-1 min-w-[180px]">
          <h1 className="mr-page-title">Calendar</h1>
          <p className="text-xs opacity-50">TV air dates + recent movie adds — dense month grid</p>
        </div>
        <div className="join">
          <button className="btn btn-sm join-item" onClick={()=>setCursor(new Date(year, month-1, 1))}>‹</button>
          <button className="btn btn-sm join-item btn-ghost min-w-[140px]" onClick={()=>setCursor(new Date())}>{monthLabel}</button>
          <button className="btn btn-sm join-item" onClick={()=>setCursor(new Date(year, month+1, 1))}>›</button>
        </div>
        <div className="join">
          <button className={"btn btn-xs join-item "+(filter==='all'?'btn-primary':'')} onClick={()=>setFilter('all')}>All</button>
          <button className={"btn btn-xs join-item "+(filter==='episode'?'btn-primary':'')} onClick={()=>setFilter('episode')}>TV</button>
          <button className={"btn btn-xs join-item "+(filter==='movie'?'btn-primary':'')} onClick={()=>setFilter('movie')}>Movies</button>
        </div>
      </div>

      {loading ? <span className="loading loading-spinner"/> : (
        <div className="grid lg:grid-cols-5 gap-4">
          <div className="lg:col-span-3 card bg-base-200 border border-base-content/5 shadow-sm overflow-hidden">
            <div className="grid grid-cols-7 text-[10px] uppercase tracking-wide opacity-50 border-b border-base-content/10">
              {['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].map(d=>(
                <div key={d} className="p-2 text-center font-medium">{d}</div>
              ))}
            </div>
            <div className="grid grid-cols-7 auto-rows-fr">
              {cells.map((c, i) => {
                if (!c) return <div key={'e'+i} className="min-h-[72px] bg-base-300/20 border border-base-content/5" />;
                const isToday = c.key === today;
                const isSel = c.key === selected;
                const ev = c.events;
                return (
                  <button key={c.key} type="button"
                    className={"min-h-[72px] p-1.5 text-left border border-base-content/5 transition hover:bg-primary/10 "
                      + (isToday ? "bg-primary/15 " : "bg-base-100/40 ")
                      + (isSel ? "ring-2 ring-primary ring-inset " : "")}
                    onClick={()=>setSelected(c.key)}>
                    <div className={"text-xs font-semibold mb-1 "+(isToday?'text-primary':'opacity-70')}>{c.day}</div>
                    <div className="space-y-0.5">
                      {ev.slice(0,3).map((e,j)=>(
                        <div key={j} className={"truncate text-[9px] px-1 rounded "
                          + (e.kind==='movie' ? 'bg-secondary/30 text-secondary-content' : e.has_file ? 'bg-success/25' : 'bg-warning/20')}>
                          {e.kind==='movie' ? (e.movie_title||'Movie') : `${e.series_title||''} S${String(e.season_number||0).padStart(2,'0')}E${String(e.episode_number||0).padStart(2,'0')}`}
                        </div>
                      ))}
                      {ev.length>3 && <div className="text-[9px] opacity-50">+{ev.length-3} more</div>}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="lg:col-span-2 space-y-3">
            <div className="card bg-base-200 border border-base-content/5">
              <div className="card-body p-4 gap-2">
                <h2 className="font-semibold text-sm">{selected || 'Select a day'}</h2>
                {!selected && <p className="text-xs opacity-50">Click a day on the grid to see episodes and movies.</p>}
                {selected && selectedEvents.length===0 && <p className="text-xs opacity-50">Nothing scheduled.</p>}
                <div className="space-y-2 max-h-[420px] overflow-y-auto">
                  {selectedEvents.map((ep,i)=>(
                    <div key={i} className="flex items-start gap-2 p-2 rounded-lg bg-base-300/40">
                      <div className="w-8 h-12 rounded bg-base-300 overflow-hidden shrink-0">
                        {ep.poster_path ? <img src={ep.poster_path} alt="" className="object-cover w-full h-full"/> : null}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-medium truncate">
                          {ep.kind==='movie' ? ep.movie_title : ep.series_title}
                        </div>
                        <div className="text-[11px] opacity-60">
                          {ep.kind==='movie' ? (ep.year || 'Movie') :
                            `S${String(ep.season_number).padStart(2,'0')}E${String(ep.episode_number).padStart(2,'0')}${ep.episode_title?` — ${ep.episode_title}`:''}`}
                        </div>
                      </div>
                      <span className={`badge badge-xs ${ep.has_file?'badge-success':ep.status==='downloading'?'badge-info':'badge-ghost'}`}>
                        {ep.has_file?'have':ep.status}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <div className="card bg-base-200/60 border border-base-content/5">
              <div className="card-body p-3 gap-1 text-[11px] opacity-60">
                <div><span className="inline-block w-2 h-2 rounded bg-warning/60 mr-1"/> Missing episode</div>
                <div><span className="inline-block w-2 h-2 rounded bg-success/50 mr-1"/> On disk</div>
                <div><span className="inline-block w-2 h-2 rounded bg-secondary/50 mr-1"/> Movie add</div>
              </div>
            </div>
          </div>
        </div>
      )}
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
  const [providers, setProviders] = useState(null);
  const [msg, setMsg] = useState('');
  const [form, setForm] = useState({
    vpn_enabled: false,
    vpn_provider: 'gluetun',
    vpn_service_provider: 'protonvpn',
    vpn_gluetun_url: 'http://gluetun:8000',
    vpn_expected_country: '',
    vpn_kill_switch: true,
    vpn_username: '',
    vpn_password: '',
    vpn_server_countries: '',
    vpn_wireguard_private_key: '',
    vpn_port_forwarding: false,
  });

  const load = () => {
    fetch('/api/settings/vpn').then(r=>r.json()).then(d=>{
      setData(d);
      setForm(f=>({
        ...f,
        vpn_enabled: !!d.enabled,
        vpn_provider: d.provider || 'gluetun',
        vpn_gluetun_url: d.gluetun_url || f.vpn_gluetun_url,
        vpn_expected_country: d.expected_country || '',
        vpn_kill_switch: d.kill_switch !== false,
      }));
    }).catch(()=>{});
    fetch('/api/settings/vpn/providers').then(r=>r.json()).then(setProviders).catch(()=>{});
  };
  useEffect(()=>{ load(); }, []);

  async function save() {
    setMsg('');
    try {
      // Persist via setup/apply style settings group if available
      const body = { ...form };
      const r = await fetch('/api/setup/apply', {
        method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body),
      }).then(x=>x.json());
      setMsg(`Saved (${r.count||0} fields). Restart Gluetun after changing provider credentials.`);
      load();
    } catch(e) { setMsg(String(e.message||e)); }
  }

  const st = data?.status || {};
  const preset = (providers?.providers||[]).find(p => p.id === form.vpn_service_provider);

  return (
    <div className="space-y-5 max-w-3xl">
      <div>
        <h1 className="mr-page-title">VPN / Gluetun</h1>
        <p className="text-sm opacity-60">MediaOs never embeds a VPN. Configure Gluetun (or similar) and point health checks here. Credentials are for generating Gluetun env — qBittorrent should use <code className="text-xs">network_mode: service:gluetun</code>.</p>
      </div>

      <div className={"alert text-sm "+(st.healthy?'alert-success':'alert-warning')}>
        <div>
          <div className="font-semibold">{!data?.enabled ? 'Checks disabled' : st.healthy ? 'Tunnel healthy' : 'Tunnel unhealthy / unknown'}</div>
          <div className="text-xs opacity-70">
            IP: {st.public_ip || '—'} · Country: {st.country || '—'} · Provider: {st.service_provider || st.provider || '—'}
          </div>
        </div>
      </div>
      {msg && <div className="alert alert-info text-xs py-2">{msg}</div>}

      <div className="card bg-base-200 border border-base-content/5">
        <div className="card-body p-4 gap-3">
          <label className="label cursor-pointer justify-start gap-3">
            <input type="checkbox" className="toggle toggle-primary" checked={!!form.vpn_enabled}
              onChange={e=>setForm({...form, vpn_enabled:e.target.checked})} />
            <span className="label-text">Enable VPN health checks</span>
          </label>
          <label className="label cursor-pointer justify-start gap-3">
            <input type="checkbox" className="toggle toggle-warning" checked={!!form.vpn_kill_switch}
              onChange={e=>setForm({...form, vpn_kill_switch:e.target.checked})} />
            <span className="label-text">Kill-switch — block new grabs if tunnel unhealthy</span>
          </label>

          <div className="grid sm:grid-cols-2 gap-2">
            <label className="form-control">
              <span className="label-text text-xs">Control provider</span>
              <select className="select select-bordered select-sm" value={form.vpn_provider}
                onChange={e=>setForm({...form, vpn_provider:e.target.value})}>
                <option value="gluetun">Gluetun</option>
                <option value="other">Other / public IP check</option>
              </select>
            </label>
            <label className="form-control">
              <span className="label-text text-xs">Gluetun URL</span>
              <input className="input input-bordered input-sm" value={form.vpn_gluetun_url}
                onChange={e=>setForm({...form, vpn_gluetun_url:e.target.value})} />
            </label>
            <label className="form-control">
              <span className="label-text text-xs">VPN service (credentials)</span>
              <select className="select select-bordered select-sm" value={form.vpn_service_provider}
                onChange={e=>setForm({...form, vpn_service_provider:e.target.value})}>
                {(providers?.providers||[
                  {id:'protonvpn',label:'ProtonVPN'},{id:'surfshark',label:'Surfshark'},
                  {id:'mullvad',label:'Mullvad'},{id:'nordvpn',label:'NordVPN'},
                  {id:'private internet access',label:'PIA'},{id:'expressvpn',label:'ExpressVPN'},
                  {id:'custom',label:'Custom'},
                ]).map(p=><option key={p.id} value={p.id}>{p.label||p.id}</option>)}
              </select>
            </label>
            <label className="form-control">
              <span className="label-text text-xs">Expected country (optional)</span>
              <input className="input input-bordered input-sm" placeholder="NL / Netherlands" value={form.vpn_expected_country}
                onChange={e=>setForm({...form, vpn_expected_country:e.target.value})} />
            </label>
          </div>

          {preset && <p className="text-xs opacity-60">{preset.notes}</p>}

          <div className="divider text-xs opacity-40 my-1">Credentials for Gluetun env</div>
          <div className="grid sm:grid-cols-2 gap-2">
            <label className="form-control">
              <span className="label-text text-xs">Username / account</span>
              <input className="input input-bordered input-sm" value={form.vpn_username}
                onChange={e=>setForm({...form, vpn_username:e.target.value})} autoComplete="off" />
            </label>
            <label className="form-control">
              <span className="label-text text-xs">Password / service password</span>
              <input className="input input-bordered input-sm" type="password" value={form.vpn_password}
                onChange={e=>setForm({...form, vpn_password:e.target.value})} autoComplete="new-password" />
            </label>
            <label className="form-control sm:col-span-2">
              <span className="label-text text-xs">Server countries (comma-separated)</span>
              <input className="input input-bordered input-sm" placeholder="Netherlands,Switzerland" value={form.vpn_server_countries}
                onChange={e=>setForm({...form, vpn_server_countries:e.target.value})} />
            </label>
            <label className="form-control sm:col-span-2">
              <span className="label-text text-xs">WireGuard private key (Mullvad / custom)</span>
              <input className="input input-bordered input-sm font-mono text-xs" value={form.vpn_wireguard_private_key}
                onChange={e=>setForm({...form, vpn_wireguard_private_key:e.target.value})} />
            </label>
            <label className="label cursor-pointer justify-start gap-2 sm:col-span-2">
              <input type="checkbox" className="checkbox checkbox-sm" checked={!!form.vpn_port_forwarding}
                onChange={e=>setForm({...form, vpn_port_forwarding:e.target.checked})} />
              <span className="label-text text-xs">Request port forwarding (PIA / supported providers)</span>
            </label>
          </div>

          <button className="btn btn-primary btn-sm w-fit" onClick={save}>Save VPN settings</button>
        </div>
      </div>

      <div className="card bg-base-200 border border-base-content/5">
        <div className="card-body p-4 gap-2">
          <h3 className="font-semibold text-sm">Gluetun compose snippet</h3>
          <p className="text-xs opacity-50">Copy into your stack. Attach download clients with network_mode: service:gluetun.</p>
          <pre className="bg-base-300 p-3 rounded text-[10px] overflow-x-auto whitespace-pre-wrap">
{(providers?.compose_hint) || `# set provider + OPENVPN_USER / OPENVPN_PASSWORD in gluetun environment`}
          </pre>
        </div>
      </div>
    </div>
  );
}


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
  async function torrentAction(hash, action) {
    if (!hash) return;
    await fetch(`/api/queue/torrent/${encodeURIComponent(hash)}/${action}`, {method:'POST'}).catch(()=>{});
  }
  function TorrentControls({ hash, category }) {
    if (!hash) return null;
    async function setPrio(p) {
      await fetch(`/api/queue/torrent/${encodeURIComponent(hash)}/priority?priority=${p}`, {method:'POST'}).catch(()=>{});
    }
    async function setCat(c) {
      await fetch(`/api/queue/torrent/${encodeURIComponent(hash)}/category?category=${encodeURIComponent(c)}`, {method:'POST'}).catch(()=>{});
    }
    async function forceStart() {
      await fetch(`/api/queue/torrent/${encodeURIComponent(hash)}/force-start?value=true`, {method:'POST'}).catch(()=>{});
    }
    const cats = ['mediaos','mediaos-tv','mediaos-music','mediaos-books','mediaos-audiobooks','mediaos-comics'];
    return (
      <div className="flex flex-wrap gap-1 items-center">
        <div className="join">
          <button className="btn btn-xs join-item" title="Pause" onClick={()=>torrentAction(hash,'pause')}>Pause</button>
          <button className="btn btn-xs join-item" title="Resume" onClick={()=>torrentAction(hash,'resume')}>Resume</button>
          <button className="btn btn-xs join-item" title="Recheck" onClick={()=>torrentAction(hash,'recheck')}>Recheck</button>
          <button className="btn btn-xs join-item" title="Force start" onClick={forceStart}>Force</button>
        </div>
        <select className="select select-bordered select-xs w-24" defaultValue="" title="Priority"
          onChange={e=>{ if(e.target.value) setPrio(Number(e.target.value)); e.target.value=''; }}>
          <option value="" disabled>Priority</option>
          <option value="1">Top</option>
          <option value="2">High</option>
          <option value="3">Normal</option>
          <option value="4">Low</option>
          <option value="5">Bottom</option>
        </select>
        <select className="select select-bordered select-xs w-32" defaultValue={category||''} title="Category"
          onChange={e=>{ if(e.target.value) setCat(e.target.value); }}>
          <option value="" disabled>Category</option>
          {cats.map(c=><option key={c} value={c}>{c}</option>)}
        </select>
      </div>
    );
  }
  const [items, setItems] = useState([]);
  const [hist, setHist] = useState({downloads:[], events:[]});
  const [tab, setTab] = useState('queue');
  const [live, setLive] = useState(false);
  const [mediaFilter, setMediaFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [histStatus, setHistStatus] = useState('all');
  const [histQuery, setHistQuery] = useState('');
  const [groupBy, setGroupBy] = useState('none'); // none | media_type | indexer

  const load = () => {
    api.queue.list().then(setItems).catch(()=>setItems([]));
    api.queue.history().then(setHist).catch(()=>setHist({downloads:[],events:[]}));
  };
  useEffect(() => {
    load();
    let es;
    try {
      es = new EventSource('/api/sse/events');
      setLive(true);
      es.addEventListener('queue', (ev) => {
        try {
          const data = JSON.parse(ev.data || '{}');
          const incoming = data.items || [];
          if (!incoming.length) { load(); return; }
          setItems(prev => {
            const byId = Object.fromEntries(incoming.map(x => [x.download_id, x]));
            const prevIds = new Set(prev.map(p => p.download_id));
            const newIds = incoming.some(x => !prevIds.has(x.download_id));
            if (newIds || prev.length !== incoming.length) {
              load();
              return prev;
            }
            return prev.map(row => {
              const liveRow = byId[row.download_id];
              if (!liveRow) return row;
              return {
                ...row,
                progress: liveRow.progress != null ? liveRow.progress : row.progress,
                status: liveRow.status || row.status,
                qbit_state: liveRow.qbit_state || row.qbit_state,
              };
            });
          });
        } catch (e) {}
      });
      es.onerror = () => setLive(false);
      es.onopen = () => setLive(true);
    } catch (e) { setLive(false); }
    const i = setInterval(load, 30000);
    return () => { try { es && es.close(); } catch(e){} clearInterval(i); };
  }, []);

  const removeItem = async (id, { blocklist = false, deleteFiles = false } = {}) => {
    const qs = new URLSearchParams();
    if (blocklist) qs.set('blocklist', '1');
    if (deleteFiles) qs.set('delete_files', '1');
    const url = `/api/queue/${id}` + (qs.toString() ? '?' + qs.toString() : '');
    try {
      if (api.queue.remove) await api.queue.remove(id);
      else await fetch(url, { method: 'DELETE' });
      // optional blocklist endpoint
      if (blocklist) {
        await fetch(`/api/queue/${id}/blocklist`, { method: 'POST' }).catch(()=>{});
      }
    } catch (e) {}
    load();
  };

  const retryFailed = async (d) => {
    try {
      await fetch(`/api/queue/${d.download_id}/retry`, { method: 'POST' });
    } catch (e) {}
    load();
  };

  const filteredQueue = (items || []).filter(q => {
    if (mediaFilter !== 'all' && (q.media_type || '') !== mediaFilter) return false;
    if (statusFilter !== 'all') {
      const st = (q.qbit_state || q.status || '').toLowerCase();
      if (statusFilter === 'active' && !(st.includes('down') || st.includes('grab') || st.includes('meta'))) return false;
      if (statusFilter === 'stalled' && !st.includes('stall')) return false;
      if (statusFilter === 'done' && !(q.progress >= 0.99 || st.includes('up') || st.includes('seed'))) return false;
    }
    return true;
  });

  // group rows
  const groups = (() => {
    if (groupBy === 'none') return { 'All': filteredQueue };
    const map = {};
    for (const q of filteredQueue) {
      const key = groupBy === 'indexer' ? (q.indexer || 'Unknown indexer') : (q.media_type || 'other');
      (map[key] = map[key] || []).push(q);
    }
    return map;
  })();

  const filteredHist = (hist.downloads || []).filter(d => {
    if (histStatus !== 'all' && (d.status || '') !== histStatus) return false;
    if (histQuery) {
      const q = histQuery.toLowerCase();
      const hay = `${d.title||''} ${d.release_title||''} ${d.indexer||''}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  const filteredEvents = (hist.events || []).filter(e => {
    if (histQuery) {
      const q = histQuery.toLowerCase();
      const hay = `${e.event||''} ${e.message||''} ${e.release_title||''}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  function renderQueueRow(q) {
    const pct = q.progress != null ? Math.round(q.progress * 100) : null;
    const st = (q.qbit_state || q.status || '').toLowerCase();
    const isFailed = st.includes('fail') || st.includes('error');
    return (
      <div key={q.download_id} className="card bg-base-200 shadow-sm">
        <div className="card-body p-3 gap-2">
          <div className="flex justify-between gap-3 items-start">
            <div className="min-w-0">
              <div className="font-medium text-sm truncate">{q.title}</div>
              <div className="text-xs opacity-50 truncate">{q.release_title}</div>
              {q.episode && <div className="text-xs opacity-60">{q.episode}</div>}
            </div>
            <div className="flex flex-wrap items-center gap-2 shrink-0 justify-end">
              <span className="badge badge-sm badge-outline">{q.media_type || '—'}</span>
              {q.indexer && <span className="badge badge-sm badge-ghost">{q.indexer}</span>}
              <span className="text-xs font-mono">{pct != null ? pct + '%' : '—'}</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <progress
              className={"progress h-2 flex-1 " + (pct === 100 ? "progress-success" : isFailed ? "progress-error" : "progress-primary")}
              value={pct != null ? pct : 0}
              max="100"
            />
            <span className="text-xs opacity-60 w-28 text-right truncate">{q.qbit_state || q.status}</span>
            {q.quality_score != null && <span className="text-xs font-mono opacity-50">score {q.quality_score}</span>}
          </div>
          <div className="flex flex-wrap gap-2 items-center">
            <TorrentControls hash={q.torrent_hash} category={q.category} />
            {isFailed && (
              <button className="btn btn-xs btn-warning" onClick={()=>retryFailed(q)}>Retry search</button>
            )}
            <div className="dropdown dropdown-end ml-auto">
              <label tabIndex={0} className="btn btn-ghost btn-xs text-error">Remove ▾</label>
              <ul tabIndex={0} className="dropdown-content z-20 menu p-2 shadow bg-base-100 rounded-box w-52 text-sm">
                <li><button onClick={()=>removeItem(q.download_id)}>Remove from queue</button></li>
                <li><button onClick={()=>removeItem(q.download_id, { deleteFiles: true })}>Remove + delete files</button></li>
                <li><button onClick={()=>removeItem(q.download_id, { blocklist: true })}>Remove + blocklist release</button></li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4 max-w-5xl">
      <div className="flex flex-wrap justify-between gap-3 items-start">
        <div>
          <h1 className="mr-page-title">Queue &amp; History</h1>
          <p className="text-sm text-base-content/50">
            Live download progress via SSE
            <span className={"ml-2 badge badge-sm " + (live ? "badge-success" : "badge-ghost")}>
              {live ? "LIVE" : "polling"}
            </span>
          </p>
        </div>
        <button className="btn btn-sm" onClick={load}>Refresh</button>
      </div>
      <div className="tabs tabs-boxed w-fit flex-wrap">
        <a className={`tab ${tab==='queue'?'tab-active':''}`} onClick={()=>setTab('queue')}>Queue ({filteredQueue.length})</a>
        <a className={`tab ${tab==='history'?'tab-active':''}`} onClick={()=>setTab('history')}>History</a>
        <a className={`tab ${tab==='events'?'tab-active':''}`} onClick={()=>setTab('events')}>Events</a>
      </div>

      {tab==='queue' && (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2 items-center">
            <select className="select select-bordered select-xs" value={mediaFilter} onChange={e=>setMediaFilter(e.target.value)}>
              <option value="all">All types</option>
              <option value="movie">Movies</option>
              <option value="tv">TV</option>
              <option value="music">Music</option>
              <option value="book">Books</option>
              <option value="audiobook">Audiobooks</option>
              <option value="comic">Comics</option>
              <option value="manga">Manga</option>
            </select>
            <select className="select select-bordered select-xs" value={statusFilter} onChange={e=>setStatusFilter(e.target.value)}>
              <option value="all">All states</option>
              <option value="active">Active</option>
              <option value="stalled">Stalled</option>
              <option value="done">Done / seeding</option>
            </select>
            <select className="select select-bordered select-xs" value={groupBy} onChange={e=>setGroupBy(e.target.value)}>
              <option value="none">No grouping</option>
              <option value="media_type">Group by type</option>
              <option value="indexer">Group by indexer</option>
            </select>
          </div>
          {filteredQueue.length===0 ? (
            <div className="opacity-40 text-sm p-4">Queue empty</div>
          ) : Object.entries(groups).map(([gname, rows]) => (
            <div key={gname} className="space-y-2">
              {groupBy !== 'none' && <div className="text-xs font-semibold opacity-60 uppercase tracking-wide pt-2">{gname} ({rows.length})</div>}
              {rows.map(renderQueueRow)}
            </div>
          ))}
        </div>
      )}

      {tab==='history' && (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <input className="input input-bordered input-xs w-48" placeholder="Search title / release…" value={histQuery} onChange={e=>setHistQuery(e.target.value)} />
            <select className="select select-bordered select-xs" value={histStatus} onChange={e=>setHistStatus(e.target.value)}>
              <option value="all">All statuses</option>
              <option value="grabbed">Grabbed</option>
              <option value="organized">Organized</option>
              <option value="failed">Failed</option>
              <option value="downloading">Downloading</option>
            </select>
          </div>
          <div className="overflow-x-auto">
            <table className="table table-sm">
              <thead><tr><th>When</th><th>Title</th><th>Status</th><th>Indexer</th><th>Score</th><th></th></tr></thead>
              <tbody>
                {filteredHist.length===0 ? (
                  <tr><td colSpan={6} className="opacity-40 text-sm">No history yet</td></tr>
                ) : filteredHist.map(d=>(
                  <tr key={d.download_id}>
                    <td className="text-xs font-mono whitespace-nowrap">{d.added_at?new Date(d.added_at).toLocaleString():''}</td>
                    <td className="text-sm">{d.title}<div className="text-xs opacity-50">{d.release_title}</div></td>
                    <td><span className={"badge badge-sm " + (d.status==='failed'?'badge-error':d.status==='organized'?'badge-success':'')}>{d.status}</span></td>
                    <td className="text-xs">{d.indexer||'—'}</td>
                    <td className="font-mono text-xs">{d.quality_score??'—'}</td>
                    <td>
                      {d.status==='failed' && (
                        <button className="btn btn-ghost btn-xs" onClick={()=>retryFailed(d)}>Retry</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab==='events' && (
        <div className="space-y-3">
          <input className="input input-bordered input-xs w-64" placeholder="Filter events…" value={histQuery} onChange={e=>setHistQuery(e.target.value)} />
          <div className="overflow-x-auto">
            <table className="table table-sm">
              <thead><tr><th>When</th><th>Event</th><th>Message</th></tr></thead>
              <tbody>
                {filteredEvents.length===0 ? (
                  <tr><td colSpan={3} className="opacity-40 text-sm">No events</td></tr>
                ) : filteredEvents.map(e=>(
                  <tr key={e.id}>
                    <td className="text-xs font-mono whitespace-nowrap">{e.created_at?new Date(e.created_at).toLocaleString():''}</td>
                    <td><span className="badge badge-sm">{e.event}</span></td>
                    <td className="text-sm">{e.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function IndexersPage() {
  const [items, setItems] = useState([]);
  const [msg, setMsg] = useState(null);
  const [jackett, setJackett] = useState(null);
  const [busy, setBusy] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [catalogQ, setCatalogQ] = useState('');
  const [catalog, setCatalog] = useState([]);
  const [privacy, setPrivacy] = useState('');
  const [picked, setPicked] = useState(null); // catalog detail
  const [form, setForm] = useState({ name:'', url:'', username:'', password:'', cookie:'', api_key:'', use_flaresolverr:false, priority:25 });
  const [manual, setManual] = useState({ name:'', url:'', api_key:'', kind:'torznab' });

  const load = () => {
    api.indexers.list().then(setItems).catch(()=>[]);
    fetch('/api/indexers/jackett/status').then(r=>r.json()).then(setJackett).catch(()=>{});
  };
  useEffect(() => { load(); }, []);

  async function loadCatalog(q, priv) {
    setBusy(true);
    try {
      const params = new URLSearchParams();
      if (q) params.set('q', q);
      if (priv) params.set('privacy', priv);
      const r = await fetch('/api/indexers/catalog?'+params).then(x=>x.json());
      setCatalog(Array.isArray(r)?r:[]);
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }

  function openAdd() {
    setShowAdd(true); setPicked(null); setCatalogQ(''); setPrivacy('');
    loadCatalog('', '');
  }

  async function pickDef(id) {
    setBusy(true);
    try {
      const d = await fetch('/api/indexers/catalog/'+encodeURIComponent(id)).then(x=>x.json());
      setPicked(d);
      setForm({
        name: d.name || id,
        url: d.url || (d.urls && d.urls[0]) || '',
        username:'', password:'', cookie:'', api_key:'',
        use_flaresolverr:false, priority:25,
      });
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }

  async function addPicked() {
    if (!picked) return;
    setBusy(true);
    try {
      const body = {
        def_id: picked.id,
        name: form.name,
        url: form.url || null,
        enabled: true,
        priority: form.priority,
        use_flaresolverr: form.use_flaresolverr,
        username: form.username || null,
        password: form.password || null,
        cookie: form.cookie || null,
        api_key: form.api_key || null,
      };
      const r = await fetch('/api/indexers/catalog/add', {
        method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)
      }).then(x=>x.json());
      if (r.detail) throw new Error(typeof r.detail==='string'?r.detail:JSON.stringify(r.detail));
      setMsg(`Added ${r.name}`);
      setShowAdd(false); setPicked(null); load();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }

  async function testIx(id) {
    setBusy(true);
    try {
      const r = await fetch(`/api/indexers/${id}/test-search?query=ubuntu`, {method:'POST'}).then(x=>x.json());
      setMsg(r.ok ? `Test OK — ${r.count} results` : `Test failed: ${r.error||'unknown'}`);
      load();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }

  const already = new Set((items||[]).map(i => (i.name||'').toLowerCase()));

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex-1">
          <h1 className="mr-page-title">Indexers</h1>
          <p className="text-sm text-base-content/50">Prowlarr-style: find a definition, pick site URL, add credentials, test</p>
        </div>
        <button className="btn btn-primary btn-sm" onClick={openAdd}>+ Add Indexer</button>
        {jackett?.configured && (
          <button className="btn btn-sm" disabled={busy} onClick={async()=>{
            setBusy(true);
            try {
              const r = await fetch('/api/indexers/jackett/sync',{method:'POST'}).then(x=>x.json());
              setMsg(`Jackett sync: ${r.added||0} added`); load();
            } catch(e){ setMsg(String(e.message||e)); }
            setBusy(false);
          }}>Sync Jackett</button>
        )}
      </div>
      {msg && <div className="alert alert-info text-xs py-2">{msg}</div>}

      {/* Added indexers */}
      <div className="card bg-base-200 shadow-sm">
        <div className="card-body p-4 gap-2">
          <h2 className="font-semibold text-sm">Enabled indexers ({(items||[]).length})</h2>
          <div className="overflow-x-auto">
            <table className="table table-sm">
              <thead><tr><th>Name</th><th>URL</th><th>Kind</th><th>Priority</th><th>Status</th><th></th></tr></thead>
              <tbody>
                {(items||[]).map(ix=>(
                  <tr key={ix.id} className="hover">
                    <td className="font-medium">{ix.name}</td>
                    <td className="text-xs font-mono truncate max-w-[14rem]" title={ix.url}>{ix.url}</td>
                    <td><span className="badge badge-xs badge-outline">{ix.kind}</span></td>
                    <td className="text-xs">{ix.priority}</td>
                    <td className="text-xs">
                      {ix.last_error ? <span className="text-error" title={ix.last_error}>error</span>
                        : ix.last_ok_at ? <span className="text-success">ok</span>
                        : <span className="opacity-40">—</span>}
                    </td>
                    <td className="flex gap-1">
                      <button className="btn btn-ghost btn-xs" disabled={busy} onClick={()=>testIx(ix.id)}>Test</button>
                      <button className="btn btn-ghost btn-xs text-error" onClick={async()=>{ await api.indexers.remove(ix.id); load(); }}>Del</button>
                    </td>
                  </tr>
                ))}
                {!(items||[]).length && <tr><td colSpan={6} className="opacity-50 text-sm">No indexers yet — click Add Indexer</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Manual Torznab */}
      <div className="card bg-base-200 shadow-sm">
        <div className="card-body p-4 gap-2">
          <h2 className="font-semibold text-sm">Generic Torznab / Newznab</h2>
          <p className="text-xs opacity-60">Like Prowlarr&apos;s Generic Torznab — paste any indexer API URL (Prowlarr, Jackett, NZBGeek, …).</p>
          <div className="flex flex-wrap gap-2">
            <input className="input input-bordered input-sm" placeholder="Name" value={manual.name} onChange={e=>setManual(m=>({...m,name:e.target.value}))} />
            <input className="input input-bordered input-sm flex-1 min-w-[12rem]" placeholder="https://host/api/v1/indexer/.../api" value={manual.url} onChange={e=>setManual(m=>({...m,url:e.target.value}))} />
            <input className="input input-bordered input-sm" placeholder="API key" value={manual.api_key} onChange={e=>setManual(m=>({...m,api_key:e.target.value}))} />
            <select className="select select-bordered select-sm" value={manual.kind} onChange={e=>setManual(m=>({...m,kind:e.target.value}))}>
              <option value="torznab">Torznab</option>
              <option value="newznab">Newznab</option>
            </select>
            <button className="btn btn-sm btn-primary" onClick={async()=>{
              if(!manual.name||!manual.url) return;
              await api.indexers.add({name:manual.name, url:manual.url, api_key:manual.api_key||null, kind:manual.kind});
              setManual({name:'',url:'',api_key:'',kind:'torznab'}); load();
            }}>Add</button>
          </div>
        </div>
      </div>

      {/* Add modal */}
      {showAdd && (
        <div className="modal modal-open">
          <div className="modal-box max-w-3xl max-h-[90vh] overflow-y-auto">
            <h3 className="font-bold text-lg">{picked ? `Add: ${picked.name}` : 'Add Indexer'}</h3>
            {!picked ? (
              <div className="space-y-3 mt-3">
                <p className="text-sm opacity-70">Search the catalog (Cardigann definitions + built-ins). Same idea as Prowlarr&apos;s indexer list.</p>
                <div className="flex flex-wrap gap-2">
                  <input className="input input-bordered input-sm flex-1" placeholder="Search by name…" value={catalogQ}
                    onChange={e=>setCatalogQ(e.target.value)}
                    onKeyDown={e=>e.key==='Enter'&&loadCatalog(catalogQ, privacy)} />
                  <select className="select select-bordered select-sm" value={privacy} onChange={e=>{ setPrivacy(e.target.value); loadCatalog(catalogQ, e.target.value); }}>
                    <option value="">All</option>
                    <option value="public">Public</option>
                    <option value="semi-private">Semi-private</option>
                    <option value="private">Private</option>
                  </select>
                  <button className="btn btn-sm" disabled={busy} onClick={()=>loadCatalog(catalogQ, privacy)}>Search</button>
                </div>
                <div className="overflow-x-auto border border-base-content/10 rounded-lg max-h-80 overflow-y-auto">
                  <table className="table table-xs">
                    <thead className="sticky top-0 bg-base-300"><tr><th>Name</th><th>Type</th><th>Source</th><th>URL</th><th></th></tr></thead>
                    <tbody>
                      {catalog.map(d=>{
                        const added = already.has((d.name||'').toLowerCase());
                        return (
                          <tr key={d.id} className="hover">
                            <td className="font-medium text-xs">{d.name}</td>
                            <td><span className="badge badge-ghost badge-xs">{d.type||'?'}</span></td>
                            <td className="text-[10px] opacity-60">{d.source}</td>
                            <td className="text-[10px] font-mono truncate max-w-[10rem]">{d.url||'—'}</td>
                            <td>
                              {added
                                ? <span className="text-[10px] opacity-40">Added</span>
                                : <button className="btn btn-xs btn-primary" onClick={()=>pickDef(d.id)}>Select</button>}
                            </td>
                          </tr>
                        );
                      })}
                      {!catalog.length && <tr><td colSpan={5} className="opacity-50 text-sm p-3">No matches — load Cardigann .yml files or try another query</td></tr>}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <div className="space-y-3 mt-3">
                <button className="btn btn-ghost btn-xs" onClick={()=>setPicked(null)}>← Back to list</button>
                <p className="text-xs opacity-60">{picked.description || picked.id}</p>
                <label className="form-control">
                  <span className="label-text text-xs">Name</span>
                  <input className="input input-bordered input-sm" value={form.name} onChange={e=>setForm(f=>({...f,name:e.target.value}))} />
                </label>
                {(picked.urls||[]).length > 0 && (
                  <label className="form-control">
                    <span className="label-text text-xs">Site URL (preconfigured)</span>
                    <select className="select select-bordered select-sm" value={form.url}
                      onChange={e=>setForm(f=>({...f,url:e.target.value}))}>
                      {(picked.urls||[]).map(u=><option key={u} value={u}>{u}</option>)}
                    </select>
                  </label>
                )}
                {!(picked.urls||[]).length && picked.source==='cardigann' && (
                  <label className="form-control">
                    <span className="label-text text-xs">Site URL</span>
                    <input className="input input-bordered input-sm" value={form.url} onChange={e=>setForm(f=>({...f,url:e.target.value}))} placeholder="https://…" />
                  </label>
                )}
                {(picked.has_login || (picked.settings||[]).length>0) && (
                  <div className="grid sm:grid-cols-2 gap-2">
                    {(picked.settings||[]).length ? (picked.settings||[]).map(s=>{
                      const k = s.name==='apikey'?'api_key':s.name;
                      const isSecret = (s.type||'').includes('password') || /pass|key|cookie|token/i.test(s.name||'');
                      if (!['username','password','cookie','api_key','apikey'].includes(k) && k!=='api_key') {
                        // map unknown to extra via cookie field skip - show common only
                      }
                      if (!['username','password','cookie','api_key'].includes(k) && k!=='apikey') return null;
                      const fk = k==='apikey'?'api_key':k;
                      return (
                        <label key={s.name} className="form-control">
                          <span className="label-text text-xs">{s.label||s.name}</span>
                          <input className="input input-bordered input-sm" type={isSecret?'password':'text'}
                            value={form[fk]||''} onChange={e=>setForm(f=>({...f,[fk]:e.target.value}))} />
                        </label>
                      );
                    }) : (
                      <>
                        <label className="form-control"><span className="label-text text-xs">Username</span>
                          <input className="input input-bordered input-sm" value={form.username} onChange={e=>setForm(f=>({...f,username:e.target.value}))} /></label>
                        <label className="form-control"><span className="label-text text-xs">Password</span>
                          <input className="input input-bordered input-sm" type="password" value={form.password} onChange={e=>setForm(f=>({...f,password:e.target.value}))} /></label>
                        <label className="form-control"><span className="label-text text-xs">Cookie</span>
                          <input className="input input-bordered input-sm" value={form.cookie} onChange={e=>setForm(f=>({...f,cookie:e.target.value}))} /></label>
                        <label className="form-control"><span className="label-text text-xs">API key</span>
                          <input className="input input-bordered input-sm" type="password" value={form.api_key} onChange={e=>setForm(f=>({...f,api_key:e.target.value}))} /></label>
                      </>
                    )}
                  </div>
                )}
                <label className="label cursor-pointer justify-start gap-2">
                  <input type="checkbox" className="toggle toggle-sm" checked={form.use_flaresolverr}
                    onChange={e=>setForm(f=>({...f,use_flaresolverr:e.target.checked}))} />
                  <span className="label-text text-xs">Use FlareSolverr / CF bypass</span>
                </label>
                <div className="modal-action">
                  <button className="btn btn-sm" onClick={()=>setPicked(null)}>Back</button>
                  <button className="btn btn-sm btn-primary" disabled={busy||!form.name} onClick={addPicked}>
                    {busy?'Adding…':'Add Indexer'}
                  </button>
                </div>
              </div>
            )}
            {!picked && (
              <div className="modal-action">
                <button className="btn btn-sm" onClick={()=>setShowAdd(false)}>Close</button>
              </div>
            )}
          </div>
          <div className="modal-backdrop bg-black/50" onClick={()=>setShowAdd(false)} />
        </div>
      )}
    </div>
  );
}


function IntegrationsPage() {
  const APPS = [
    { id:'radarr', name:'Radarr', media:'Movies', path:'/api/migrate/radarr', defaultUrl:'http://radarr:7878' },
    { id:'sonarr', name:'Sonarr', media:'TV', path:'/api/migrate/sonarr', defaultUrl:'http://sonarr:8989' },
    { id:'lidarr', name:'Lidarr', media:'Music', path:'/api/migrate/lidarr', defaultUrl:'http://lidarr:8686' },
    { id:'readarr', name:'Readarr', media:'Books', path:'/api/migrate/readarr', defaultUrl:'http://readarr:8787' },
    { id:'prowlarr', name:'Prowlarr', media:'Indexers', path:'/api/migrate/prowlarr/indexers', defaultUrl:'http://prowlarr:9696' },
  ];
  const [forms, setForms] = useState(() => Object.fromEntries(APPS.map(a => [a.id, { url: a.defaultUrl, api_key: '', monitor: true }])));
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(null);
  const [tests, setTests] = useState({});
  const [supported, setSupported] = useState(null);
  const [readarrAudio, setReadarrAudio] = useState(false);

  useEffect(()=>{
    fetch('/api/migrate/supported').then(r=>r.json()).then(setSupported).catch(()=>{});
    fetch('/api/settings/config/integrations').then(r=>r.json()).then(d=>{
      if (!d) return;
      setForms(f => {
        const next = {...f};
        for (const a of APPS) {
          const u = d[a.id+'_url']?.value;
          const k = d[a.id+'_api_key']?.value;
          if (u) next[a.id] = {...next[a.id], url: u};
          if (k && k !== '        ') next[a.id] = {...next[a.id], api_key: ''}; // leave blank if secret set
        }
        return next;
      });
    }).catch(()=>{});
  }, []);

  function setField(id, key, val) {
    setForms(f => ({...f, [id]: {...f[id], [key]: val}}));
  }

  async function test(id) {
    setBusy('test-'+id); setMsg(null);
    try {
      const body = { url: forms[id].url, api_key: forms[id].api_key, kind: id };
      const r = await fetch('/api/migrate/test', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) }).then(x=>x.json());
      setTests(t => ({...t, [id]: r}));
      setMsg(r.ok ? `${id}: connected (${r.version||r.instanceName||'ok'})` : `${id}: ${r.error||r.detail||'failed'}`);
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(null);
  }

  async function saveConn(id) {
    setBusy('save-'+id);
    try {
      const payload = {};
      payload[id+'_url'] = forms[id].url;
      if (forms[id].api_key) payload[id+'_api_key'] = forms[id].api_key;
      await fetch('/api/settings/config/integrations', { method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
      setMsg(`Saved ${id} connection`);
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(null);
  }

  async function runImport(id) {
    setBusy('import-'+id); setMsg(null);
    try {
      const body = { url: forms[id].url, api_key: forms[id].api_key, monitor: forms[id].monitor };
      if (id === 'readarr') body.audiobooks = readarrAudio;
      const r = await fetch(APPS.find(a=>a.id===id).path, {
        method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)
      }).then(x=>x.json());
      if (r.detail) throw new Error(typeof r.detail==='string'?r.detail:JSON.stringify(r.detail));
      setMsg(`${id}: added ${r.added||0}, updated ${r.updated||0}, skipped ${r.skipped||0}`);
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(null);
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="mr-page-title">*arr integrations</h1>
        <p className="text-sm opacity-60">Connect common *arr apps to import libraries into MediaOs, or point Jellyseerr at MediaOs&apos;s built-in Radarr/Sonarr-compatible API.</p>
      </div>
      {msg && <div className="alert alert-info text-xs py-2">{msg}</div>}

      <div className="card bg-base-200 shadow-sm">
        <div className="card-body p-4 gap-2 text-sm">
          <h2 className="font-semibold text-sm">Two directions</h2>
          <ol className="list-decimal list-inside text-xs opacity-80 space-y-1">
            <li><b>Import into MediaOs</b> — pull movies/TV/music/books/indexers from an existing *arr, then retire it.</li>
            <li><b>Apps talk to MediaOs</b> — set Jellyseerr/Overseerr/LunaSea &quot;Radarr&quot; or &quot;Sonarr&quot; host to this MediaOs URL + ARR API key (Settings → Auth).</li>
          </ol>
        </div>
      </div>

      {APPS.map(app => (
        <div key={app.id} className="card bg-base-200 shadow-sm">
          <div className="card-body p-4 gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="font-semibold text-sm flex-1">{app.name} <span className="opacity-50 font-normal">  {app.media}</span></h2>
              {tests[app.id] && (
                <span className={'badge badge-sm '+(tests[app.id].ok?'badge-success':'badge-error')}>
                  {tests[app.id].ok ? (tests[app.id].version || 'ok') : 'failed'}
                </span>
              )}
            </div>
            <div className="grid sm:grid-cols-2 gap-2">
              <label className="form-control">
                <span className="label-text text-xs">URL</span>
                <input className="input input-bordered input-sm" value={forms[app.id].url}
                  onChange={e=>setField(app.id,'url',e.target.value)} placeholder={app.defaultUrl} />
              </label>
              <label className="form-control">
                <span className="label-text text-xs">API key</span>
                <input className="input input-bordered input-sm" type="password" value={forms[app.id].api_key}
                  onChange={e=>setField(app.id,'api_key',e.target.value)} placeholder="X-Api-Key" />
              </label>
            </div>
            {app.id !== 'prowlarr' && (
              <label className="label cursor-pointer justify-start gap-2 py-0">
                <input type="checkbox" className="toggle toggle-sm" checked={forms[app.id].monitor}
                  onChange={e=>setField(app.id,'monitor',e.target.checked)} />
                <span className="label-text text-xs">Keep monitored flags from source</span>
              </label>
            )}
            {app.id === 'readarr' && (
              <label className="label cursor-pointer justify-start gap-2 py-0">
                <input type="checkbox" className="toggle toggle-sm" checked={readarrAudio}
                  onChange={e=>setReadarrAudio(e.target.checked)} />
                <span className="label-text text-xs">Import as audiobooks (instead of ebooks)</span>
              </label>
            )}
            <div className="flex flex-wrap gap-2">
              <button className="btn btn-sm" disabled={!!busy} onClick={()=>test(app.id)}>Test</button>
              <button className="btn btn-sm" disabled={!!busy} onClick={()=>saveConn(app.id)}>Save connection</button>
              <button className="btn btn-sm btn-primary" disabled={!!busy || !forms[app.id].api_key}
                onClick={()=>runImport(app.id)}>
                {busy==='import-'+app.id ? 'Importing…' : (app.id==='prowlarr' ? 'Sync indexers' : 'Import library')}
              </button>
            </div>
          </div>
        </div>
      ))}

      <div className="card bg-base-200 shadow-sm">
        <div className="card-body p-4 gap-2 text-sm">
          <h2 className="font-semibold text-sm">Jellyseerr / Overseerr → MediaOs</h2>
          <p className="text-xs opacity-70">Add a Radarr and/or Sonarr service pointing at this MediaOs base URL. Use the ARR API key from Settings → Auth. MediaOs implements the common <code className="text-xs">/api/v3/movie</code>, <code className="text-xs">/api/v3/series</code>, and command endpoints.</p>
        </div>
      </div>

      {supported && (
        <div className="overflow-x-auto">
          <table className="table table-sm">
            <thead><tr><th>App</th><th>Media</th><th>Import</th><th>API compat</th></tr></thead>
            <tbody>
              {(supported.apps||[]).map(a=>(
                <tr key={a.id}>
                  <td>{a.name}</td>
                  <td className="text-xs">{a.media}</td>
                  <td>{a.import ? '✓' : '—'}</td>
                  <td className="text-xs">{a.compat===true?'✓':(a.compat||'—')}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {supported.notes && <p className="text-xs opacity-50 mt-2">{supported.notes}</p>}
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
          <p className="mr-page-sub">Titles you asked for that are not on disk yet</p>
          <p className="text-xs opacity-50 max-w-xl">No results after Search? Simplest fixes: (1) qBittorrent URL in Setup, (2) try a popular title, (3) wait — public indexers can be slow. Advanced: Indexers / Prowlarr.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn btn-sm btn-ghost" onClick={load} disabled={!!busy}>Refresh</button>
          <button className="btn btn-sm btn-primary" disabled={!!busy} onClick={()=>searchAuto(tab==='episodes'?'tv':tab)}>
            {busy&&String(busy).startsWith('auto')?'Searching…':'Auto-search tab'}
          </button>
          <button className="btn btn-sm btn-secondary" disabled={!!busy} onClick={()=>searchAuto('all')}>Auto-search all</button>
          <button className="btn btn-sm btn-accent" disabled={!!busy} onClick={async()=>{
            setBusy('hunt'); setMsg(null);
            try {
              const r = await fetch('/api/hunt/run', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ limit: 40, only_monitored: true }) }).then(x=>x.json());
              setMsg(r.message || `Hunt: processed ${r.processed||0}, grabbed ${r.grabbed||0}`);
              load();
            } catch(e) { setMsg(String(e.message||e)); }
            setBusy(null);
          }}>{busy==='hunt'?'Hunting…':'Run hunt'}</button>
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



function TrashImportPanel() {
  const [url, setUrl] = useState('');
  const [name, setName] = useState('TRaSH Imported');
  const [mediaType, setMediaType] = useState('movie');
  const [msg, setMsg] = useState('');
  const [presets, setPresets] = useState(null);
  useEffect(()=>{ fetch('/api/migrate/trash/presets').then(r=>r.json()).then(setPresets).catch(()=>{}); }, []);
  async function run() {
    setMsg('Importing…');
    try {
      const r = await fetch('/api/migrate/trash', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ url, profile_name: name, media_type: mediaType, replace_formats: true })
      }).then(x=>x.json());
      setMsg(r.ok ? `Imported ${r.custom_formats} formats → profile "${r.profile_name}"` : (r.detail || r.error || 'failed'));
    } catch(e){ setMsg(String(e.message||e)); }
  }
  return (
    <div className="card mr-panel border-0"><div className="card-body gap-2 text-sm">
      <h2 className="font-semibold">TRaSH Guides import</h2>
      <p className="text-xs opacity-60">Import custom formats JSON (URL or paste TRaSH export) into a quality profile.</p>
      {presets && (
        <div className="flex flex-wrap gap-1">
          <button className="btn btn-xs" onClick={()=>setUrl(presets.movie_hd_bluray_web||'')}>Preset: Movie HD</button>
          <button className="btn btn-xs" onClick={()=>setUrl(presets.tv_hd_bluray_web||'')}>Preset: TV HD</button>
        </div>
      )}
      <input className="input input-bordered input-sm w-full" placeholder="https://…/custom-formats.json" value={url} onChange={e=>setUrl(e.target.value)} />
      <div className="flex gap-2 flex-wrap">
        <input className="input input-bordered input-sm" value={name} onChange={e=>setName(e.target.value)} placeholder="Profile name" />
        <select className="select select-bordered select-sm" value={mediaType} onChange={e=>setMediaType(e.target.value)}>
          <option value="movie">movie</option>
          <option value="tv">tv</option>
        </select>
        <button className="btn btn-sm btn-primary" onClick={run}>Import</button>
      </div>
      {msg && <p className="text-xs opacity-70">{msg}</p>}
    </div></div>
  );
}

function ArrDbMigratePanel() {
  const [kind, setKind] = useState('radarr');
  const [path, setPath] = useState('');
  const [pg, setPg] = useState('');
  const [msg, setMsg] = useState('');
  async function run() {
    setMsg('Importing…');
    try {
      const body = path ? { path, kind } : { postgres_url: pg, kind };
      const r = await fetch('/api/migrate/db', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) }).then(x=>x.json());
      setMsg(JSON.stringify(r));
    } catch(e){ setMsg(String(e.message||e)); }
  }
  return (
    <div className="card mr-panel border-0"><div className="card-body gap-2 text-sm">
      <h2 className="font-semibold">DB migrator (SQLite / Postgres)</h2>
      <p className="text-xs opacity-60">Point at a Sonarr/Radarr .db file path inside the container, or a Postgres URL to a restored *arr database.</p>
      <select className="select select-bordered select-sm w-40" value={kind} onChange={e=>setKind(e.target.value)}>
        <option value="radarr">Radarr</option><option value="sonarr">Sonarr</option>
      </select>
      <input className="input input-bordered input-sm w-full" placeholder="/config/radarr/radarr.db" value={path} onChange={e=>setPath(e.target.value)} />
      <input className="input input-bordered input-sm w-full" placeholder="postgres://user:pass@host:5432/radarr" value={pg} onChange={e=>setPg(e.target.value)} />
      <button className="btn btn-sm btn-primary" onClick={run}>Import from DB</button>
      {msg && <pre className="text-xs opacity-70 overflow-auto max-h-24">{msg}</pre>}
    </div></div>
  );
}

function ArrMigratePanel() {
  const [radarr, setRadarr] = useState({url:'', api_key:''});
  const [sonarr, setSonarr] = useState({url:'', api_key:''});
  const [msg, setMsg] = useState('');
  async function go(kind) {
    setMsg('Migrating…');
    const body = kind==='radarr' ? radarr : sonarr;
    try {
      const r = await fetch('/api/migrate/'+kind, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({...body, monitor:true})
      }).then(x=>x.json());
      setMsg(JSON.stringify(r));
    } catch(e){ setMsg(String(e.message||e)); }
  }
  return (
    <div className="card mr-panel border-0"><div className="card-body gap-2 text-sm">
      <h2 className="font-semibold">Import from Radarr / Sonarr</h2>
      <p className="text-xs opacity-60">Pull library via *arr API (no direct Postgres required). Episodes include absolute numbers when Sonarr provides them.</p>
      <div className="grid sm:grid-cols-2 gap-3">
        <div className="space-y-1">
          <div className="font-medium text-xs">Radarr</div>
          <input className="input input-bordered input-sm w-full" placeholder="http://radarr:7878" value={radarr.url} onChange={e=>setRadarr(s=>({...s,url:e.target.value}))} />
          <input className="input input-bordered input-sm w-full" placeholder="API key" type="password" value={radarr.api_key} onChange={e=>setRadarr(s=>({...s,api_key:e.target.value}))} />
          <button className="btn btn-xs btn-primary" onClick={()=>go('radarr')}>Import movies</button>
        </div>
        <div className="space-y-1">
          <div className="font-medium text-xs">Sonarr</div>
          <input className="input input-bordered input-sm w-full" placeholder="http://sonarr:8989" value={sonarr.url} onChange={e=>setSonarr(s=>({...s,url:e.target.value}))} />
          <input className="input input-bordered input-sm w-full" placeholder="API key" type="password" value={sonarr.api_key} onChange={e=>setSonarr(s=>({...s,api_key:e.target.value}))} />
          <button className="btn btn-xs btn-primary" onClick={()=>go('sonarr')}>Import series + episodes</button>
        </div>
      </div>
      {msg && <pre className="text-xs opacity-70 overflow-auto max-h-24">{msg}</pre>}
    </div></div>
  );
}



function ModuleStorePage({ enabledModules, setEnabledModules, setPage }) {
  const [catalog, setCatalog] = useState([]);
  const [busy, setBusy] = useState(null);
  const [msg, setMsg] = useState('');

  const load = () => {
    fetch('/api/modules').then(r=>r.json()).then(d=>{
      setCatalog(d.catalog||[]);
      if (d.enabled) setEnabledModules(d.enabled);
    }).catch(e=>setMsg(String(e)));
  };
  useEffect(()=>{ load(); }, []);

  const toggle = async (id, currentlyOn, isCore) => {
    if (isCore) return;
    setBusy(id); setMsg('');
    try {
      const path = currentlyOn ? `/api/modules/${id}/disable` : `/api/modules/${id}/enable`;
      const r = await fetch(path, { method:'POST' }).then(x=>x.json());
      if (r.enabled) setEnabledModules(r.enabled);
      load();
      setMsg(currentlyOn ? `Disabled ${id}` : `Enabled ${id}`);
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(null);
  };

  return (
    <div className="space-y-4 max-w-4xl">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Module Store</h1>
          <p className="text-sm opacity-60">Enable or disable library modules. Movies &amp; TV are always available.</p>
        </div>
        <button className="btn btn-sm" onClick={()=>setPage && setPage('settings-hub')}>Settings</button>
      </div>
      {msg && <div className="alert alert-info text-xs py-2">{msg}</div>}
      <div className="grid gap-3 sm:grid-cols-2">
        {catalog.map(m => {
          const on = m.enabled || (enabledModules||[]).includes(m.id);
          return (
            <div key={m.id} className={"card bg-base-200 shadow-sm border " + (on ? "border-primary/40" : "border-transparent")}>
              <div className="card-body p-4 gap-2">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h3 className="font-semibold flex items-center gap-2">
                      {m.label}
                      {m.core && <span className="badge badge-primary badge-xs">Core</span>}
                      {on && !m.core && <span className="badge badge-success badge-xs">On</span>}
                    </h3>
                    <p className="text-xs opacity-60 mt-1">{m.description}</p>
                  </div>
                  <input
                    type="checkbox"
                    className="toggle toggle-primary"
                    checked={!!on}
                    disabled={!!m.core || busy===m.id}
                    onChange={()=>toggle(m.id, on, m.core)}
                  />
                </div>
                {m.requires_path && on && (
                  <p className="text-[10px] opacity-50">Uses path setting: {m.requires_path}</p>
                )}
              </div>
            </div>
          );
        })}
      </div>
      <p className="text-xs opacity-50">You can also change modules during the Setup wizard. Disabling a module hides it from the sidebar; your data stays safe.</p>
    </div>
  );
}

function SetupWizardPage({ onDone }) {
  const STEPS = [
    { id:'welcome', title:'Welcome' },
    { id:'modules', title:'Modules' },
    { id:'metadata', title:'Metadata' },
    { id:'library', title:'Libraries' },
    { id:'downloads', title:'Downloads' },
    { id:'indexers', title:'Indexers' },
    { id:'subtitles', title:'Subtitles' },
    { id:'usenet', title:'Usenet' },
    { id:'vpn', title:'VPN' },
    { id:'youtube', title:'YouTube' },
    { id:'integrations', title:'Integrations' },
    { id:'admin', title:'Admin' },
    { id:'finish', title:'Finish' },
  ];
  const [step, setStep] = useState(0);
  const [st, setSt] = useState(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');
  const [pathCheck, setPathCheck] = useState(null);
  const [prowlarrList, setProwlarrList] = useState(null);
  const [prowlarrSelected, setProwlarrSelected] = useState([]);
  const [prowlarrBusy, setProwlarrBusy] = useState(false);
  const [prowlarrMsg, setProwlarrMsg] = useState('');
  const [selectedModules, setSelectedModules] = useState(['movies','tv']); // core always
  const [moduleCatalog, setModuleCatalog] = useState([]);
  const [form, setForm] = useState({
    tmdb_api_key:'', tvdb_api_key:'', tvdb_pin:'', comicvine_api_key:'', trakt_client_id:'', trakt_access_token:'',
    movies_library_path:'/movies', tv_library_path:'/tv', music_library_path:'/music',
    books_library_path:'/books', audiobooks_library_path:'/audiobooks',
    podcasts_library_path:'/podcasts', comics_library_path:'/comics',
    manga_library_path:'/manga', youtube_library_path:'/youtube', downloads_path:'/downloads',
    movie_naming_folder:'{title} ({year})', episode_naming:'{series} - S{season:00}E{episode:00} - {title}',
    flaresolverr_url:'', cf_bypass_enabled:true, cf_impersonate:'chrome124',
    sabnzbd_category:'mediaos', nzbget_category:'mediaos', usenet_client:'auto', allow_usenet:true,
    vpn_enabled:false, vpn_gluetun_url:'http://gluetun:8000', vpn_expected_country:'', vpn_kill_switch:true,
    auth_api_key:'', youtube_backlog_download:false,
    qbit_url:'http://qbittorrent:8080', qbit_username:'admin', qbit_password:'',
    torrent_client:'qbittorrent',
    transmission_url:'', transmission_username:'', transmission_password:'',
    deluge_url:'', deluge_password:'', rtorrent_url:'', aria2_url:'', aria2_secret:'',
    sabnzbd_url:'', sabnzbd_api_key:'', nzbget_url:'', nzbget_username:'', nzbget_password:'',
    prowlarr_url:'', prowlarr_api_key:'', jackett_url:'', jackett_api_key:'',
    cardigann_enabled:true, min_seeders:3,
    opensubtitles_api_key:'', opensubtitles_username:'', opensubtitles_password:'',
    subdl_api_key:'', subtitle_languages:'en', subtitle_hearing_impaired:'include',
    subtitle_providers:'sidecar,opensubtitles,subdl,addic7ed,subscene',
    nntp_host:'', nntp_port:563, nntp_user:'', nntp_pass:'', nntp_ssl:true,
    vpn_provider:'', vpn_username:'', vpn_password:'', vpn_killswitch:false, vpn_interface:'',
    youtube_ytdlp_path:'yt-dlp', youtube_format:'best[height<=1080]',
    youtube_auto_download_default:true, youtube_cookies_path:'', youtube_cookies_from_browser:'',
    youtube_sponsorblock_remove:'sponsor,selfpromo,interaction,intro,outro,preview,music_offtopic',
    youtube_sponsorblock_mark:'',
    real_debrid_token:'', torbox_api_key:'', alldebrid_api_key:'', premiumize_api_key:'',
    debridlink_api_key:'', putio_token:'', easydebrid_api_key:'', offcloud_api_key:'',
    movie_download_mode:'download',
    jellyfin_url:'', jellyfin_api_key:'', emby_url:'', emby_api_key:'',
    apprise_url:'', discord_webhook_url:'', telegram_bot_token:'', telegram_chat_id:'',
    auth_username:'admin', auth_password:'', arr_api_key:'',
  });
  const set = (k,v)=> setForm(f=>({...f,[k]:v}));
  const Field = ({label, k, type='text', placeholder='', hint}) => (
    <label className="form-control w-full">
      <span className="label-text text-xs opacity-70">{label}</span>
      <input className="input input-bordered input-sm w-full" type={type} value={form[k]===undefined||form[k]===null?'':form[k]}
        placeholder={placeholder} onChange={e=>set(k, type==='number'?Number(e.target.value):e.target.value)} />
      {hint && <span className="label-text-alt opacity-50 text-[10px]">{hint}</span>}
    </label>
  );
  const Toggle = ({label, k}) => (
    <label className="label cursor-pointer justify-start gap-3 py-1">
      <input type="checkbox" className="toggle toggle-sm" checked={!!form[k]} onChange={e=>set(k, e.target.checked)} />
      <span className="label-text text-sm">{label}</span>
    </label>
  );

  useEffect(()=>{
    api.setup.status().then(setSt).catch(()=>{});
    fetch('/api/setup/modules').then(r=>r.json()).then(d=>{
      setModuleCatalog(d.catalog||[]);
      if (d.enabled && d.enabled.length) setSelectedModules(d.enabled);
    }).catch(()=>{});
    fetch('/api/setup/defaults').then(r=>r.json()).then(d=>{
      if (!d || typeof d !== 'object') return;
      setForm(f => {
        const next = {...f};
        Object.keys(d).forEach(k=>{
          if (d[k] === '__SET__') return; // keep blank for secrets already configured
          if (d[k] !== '' && d[k] !== null && d[k] !== undefined) next[k] = d[k];
        });
        return next;
      });
      setMsg('Loaded current settings');
    }).catch(()=>{});
  }, []);

  const applyPartial = async (mark) => {
    setSaving(true); setMsg('');
    try {
      const body = {...form, mark_complete: !!mark};
      // drop empty secrets so we don't wipe existing
      Object.keys(body).forEach(k=>{
        if (body[k] === '' || body[k] === null) delete body[k];
      });
      const url = mark ? '/api/setup/complete' : '/api/setup/apply';
      const r = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)}).then(x=>x.json());
      setMsg(mark ? 'Setup complete' : `Saved ${r.count||0} fields`);
      if (mark && onDone) onDone();
      return r;
    } catch(e) {
      setMsg(String(e.message||e));
    } finally { setSaving(false); }
  };

  const checkPaths = async () => {
    setSaving(true);
    try {
      const r = await fetch('/api/setup/check-paths', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify(form),
      }).then(x=>x.json());
      setPathCheck(r.results||[]);
      setMsg('Path check finished');
    } catch(e) { setMsg(String(e.message||e)); }
    setSaving(false);
  };

  const next = async () => {
    if (STEPS[step]?.id === 'modules') {
      try {
        await fetch('/api/setup/modules', {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({ enabled: selectedModules }),
        });
      } catch(e) { console.warn('modules save', e); }
    }
    if (step < STEPS.length - 1) {
      await applyPartial(false);
      setStep(s=>s+1);
    } else {
      await applyPartial(true);
    }
  };
  const back = () => setStep(s=>Math.max(0, s-1));
  const cur = STEPS[step];

  return (
    <div className="min-h-[70vh] flex items-start justify-center py-6">
      <div className="w-full max-w-3xl space-y-4">
        <div className="text-center space-y-1">
          <h1 className="text-2xl font-bold tracking-tight">Setup wizard</h1>
          <p className="text-sm opacity-60">Full first-run config — paths, clients, logins, integrations. Everything is editable later under Settings.</p>
        </div>
        <ul className="steps steps-horizontal w-full text-[10px] overflow-x-auto">
          {STEPS.map((s,i)=>(
            <li key={s.id} className={'step '+(i<=step?'step-primary':'')} onClick={()=>setStep(i)} style={{cursor:'pointer'}}>{s.title}</li>
          ))}
        </ul>
        <div className="card bg-base-200 shadow-md">
          <div className="card-body gap-4 p-5">
            <h2 className="card-title text-lg">{cur.title}</h2>

            {cur.id==='welcome' && (
              <div className="space-y-3 text-sm opacity-80">
                <p>This wizard configures everything needed to replace Sonarr, Radarr, Lidarr, Readarr, Bazarr, Prowlarr, and Overseerr in one app.</p>
                <ol className="list-decimal list-inside space-y-1 text-xs opacity-70">
                  <li>Metadata API keys (TMDb required)</li>
                  <li>Library folders + incomplete downloads path</li>
                  <li>Torrent / Usenet clients</li>
                  <li>Indexers (builtins work without Prowlarr)</li>
                  <li>Subtitles + YouTube login (optional)</li>
                  <li>Debrid, Jellyfin/Emby, Discord/Telegram</li>
                  <li>Admin account</li>
                </ol>
                {st && !st.complete && st.steps?.length>0 && (
                  <div className="alert alert-warning text-xs"><span>Suggested: {st.steps.join('   ')}</span></div>
                )}
              </div>
            )}


            {cur.id==='modules' && (
              <div className="space-y-4">
                <p className="text-sm opacity-80">Choose which library types to enable. <strong>Movies</strong> and <strong>TV</strong> are always on (core). You can add more later from the Module Store.</p>
                <div className="grid gap-3 sm:grid-cols-2">
                  {(moduleCatalog.length ? moduleCatalog : [
                    {id:'movies',label:'Movies',description:'Movie library — always enabled',core:true,enabled:true},
                    {id:'tv',label:'TV Shows',description:'Series & episodes — always enabled',core:true,enabled:true},
                    {id:'music',label:'Music',description:'Artists, albums, tracks + completeness',core:false},
                    {id:'books',label:'Books',description:'eBooks with organize & monitoring',core:false},
                    {id:'audiobooks',label:'Audiobooks',description:'Audiobook library + Audnexus',core:false},
                    {id:'comics',label:'Comics / Manga',description:'Pull-list, story arcs, metatagging',core:false},
                    {id:'livetv',label:'Live TV',description:'Channels, EPG, portal scan',core:false},
                  ]).map(m => {
                    const on = selectedModules.includes(m.id);
                    const locked = !!m.core;
                    return (
                      <label key={m.id} className={"flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition " + (on ? "border-primary bg-primary/10" : "border-base-content/10 bg-base-300/30")}>
                        <input
                          type="checkbox"
                          className="checkbox checkbox-primary mt-1"
                          checked={on}
                          disabled={locked}
                          onChange={(e)=>{
                            if (locked) return;
                            setSelectedModules(prev => e.target.checked
                              ? [...new Set([...prev, m.id])]
                              : prev.filter(x => x !== m.id));
                          }}
                        />
                        <div className="min-w-0">
                          <div className="font-medium text-sm flex items-center gap-2">
                            {m.label}
                            {locked && <span className="badge badge-xs badge-primary">Core</span>}
                          </div>
                          <div className="text-xs opacity-60 mt-0.5">{m.description}</div>
                        </div>
                      </label>
                    );
                  })}
                </div>
                <p className="text-xs opacity-50">Tip: start with Movies + TV only for the simplest experience. Enable Music, Books, Comics, etc. when you need them.</p>
              </div>
            )}

            {cur.id==='metadata' && (
              <div className="space-y-3">
                <p className="text-sm opacity-70">API keys for metadata providers. TMDb is required for movies and TV.</p>
                <div className="grid gap-2 sm:grid-cols-2">
                  <Field label="TMDb API key *" k="tmdb_api_key" type="password" hint="themoviedb.org → Settings → API" />
                  <Field label="TVDb API key" k="tvdb_api_key" type="password" hint="Optional; TMDb covers most TV" />
                  <Field label="TVDb PIN" k="tvdb_pin" type="password" hint="Required by some TVDb v4 apps" />
                  <Field label="ComicVine API key" k="comicvine_api_key" type="password" hint="comicvine.gamespot.com for comics" />
                  <Field label="Trakt client ID" k="trakt_client_id" hint="Smart lists / watchlist import" />
                  <Field label="Trakt access token" k="trakt_access_token" type="password" />
                </div>
              </div>
            )}

            {cur.id==='library' && (
              <div className="space-y-4">
                <p className="text-sm opacity-70">Where finished media is stored, and where incomplete downloads land. Map these to host folders in Docker compose.</p>
                <div className="alert alert-info text-xs py-2">Downloads path is the incomplete / staging folder (qBittorrent save path). Library paths are the final organized libraries.</div>
                <div className="grid gap-2 sm:grid-cols-2">
                  <Field label="Downloads (incomplete) *" k="downloads_path" placeholder="/downloads" hint="qB / SABnzbd incomplete folder" />
                </div>
                <div className="divider text-xs opacity-50 my-1">Movie & TV</div>
                <div className="grid gap-2 sm:grid-cols-2">
                  <Field label="Movies library *" k="movies_library_path" placeholder="/movies" />
                  <Field label="TV library *" k="tv_library_path" placeholder="/tv" />
                </div>
                <div className="divider text-xs opacity-50 my-1">Music & reading</div>
                <div className="grid gap-2 sm:grid-cols-2">
                  <Field label="Music" k="music_library_path" placeholder="/music" />
                  <Field label="Books" k="books_library_path" placeholder="/books" />
                  <Field label="Audiobooks" k="audiobooks_library_path" placeholder="/audiobooks" />
                  <Field label="Podcasts" k="podcasts_library_path" placeholder="/podcasts" />
                </div>
                <div className="divider text-xs opacity-50 my-1">Comics & YouTube</div>
                <div className="grid gap-2 sm:grid-cols-2">
                  <Field label="Comics" k="comics_library_path" placeholder="/comics" />
                  <Field label="Manga" k="manga_library_path" placeholder="/manga" />
                  <Field label="YouTube" k="youtube_library_path" placeholder="/youtube" />
                </div>
                <div className="divider text-xs opacity-50 my-1">Naming templates</div>
                <div className="grid gap-2 sm:grid-cols-1">
                  <Field label="Movie folder template" k="movie_naming_folder" placeholder="{title} ({year})" hint="Tokens: {title} {year} {tmdb_id}" />
                  <Field label="Episode file template" k="episode_naming" placeholder="{series} - S{season:00}E{episode:00} - {title}" />
                </div>
                <button type="button" className="btn btn-sm btn-outline" disabled={saving} onClick={checkPaths}>Verify paths (create if missing)</button>
                {pathCheck && (
                  <div className="overflow-x-auto">
                    <table className="table table-xs">
                      <thead><tr><th>Path</th><th>Exists</th><th>Writable</th><th>Note</th></tr></thead>
                      <tbody>
                        {pathCheck.map(r=>(
                          <tr key={r.key}>
                            <td className="font-mono text-[10px]">{r.path||'—'}</td>
                            <td>{r.exists?'✓':'✗'}</td>
                            <td>{r.writable?'✓':'✗'}</td>
                            <td className="text-[10px] opacity-60">{r.note||r.key}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {cur.id==='downloads' && (
              <div className="space-y-3">
                <p className="text-sm opacity-70">Primary torrent client and optional Usenet downloaders. Category defaults are set automatically (mediaos-tv, mediaos-comics, …).</p>
                <div className="grid gap-2 sm:grid-cols-2">
                  <Field label="Active torrent client" k="torrent_client" placeholder="qbittorrent" hint="qbittorrent | transmission | deluge | rtorrent | aria2" />
                  <Field label="Downloads path" k="downloads_path" placeholder="/downloads" />
                  <Field label="qBittorrent URL" k="qbit_url" placeholder="http://qbittorrent:8080" />
                  <Field label="qB username" k="qbit_username" />
                  <Field label="qB password" k="qbit_password" type="password" />
                  <Field label="Transmission URL" k="transmission_url" placeholder="http://transmission:9091" />
                  <Field label="Deluge URL" k="deluge_url" placeholder="http://deluge:8112" />
                  <Field label="Deluge password" k="deluge_password" type="password" />
                  <Field label="rTorrent URL" k="rtorrent_url" placeholder="http://rtorrent:8080" />
                  <Field label="aria2 URL" k="aria2_url" placeholder="http://aria2:6800/jsonrpc" />
                  <Field label="aria2 secret" k="aria2_secret" type="password" />
                  <Field label="SABnzbd URL" k="sabnzbd_url" placeholder="http://sabnzbd:8080" />
                  <Field label="SABnzbd API key" k="sabnzbd_api_key" type="password" />
                  <Field label="NZBGet URL" k="nzbget_url" placeholder="http://nzbget:6789" />
                  <Field label="NZBGet user" k="nzbget_username" />
                  <Field label="NZBGet password" k="nzbget_password" type="password" />
                </div>
              </div>
            )}

            {cur.id==='indexers' && (
              <div className="space-y-3">
                <p className="text-sm opacity-70">Builtin public indexers work out of the box. Connect <strong>Prowlarr</strong> to pick which indexers to import, or Jackett / Cardigann for extras.</p>
                <div className="grid gap-2 sm:grid-cols-2">
                  <Field label="Prowlarr URL" k="prowlarr_url" placeholder="http://prowlarr:9696" />
                  <Field label="Prowlarr API key" k="prowlarr_api_key" type="password" />
                  <Field label="Jackett URL" k="jackett_url" placeholder="http://jackett:9117" />
                  <Field label="Jackett API key" k="jackett_api_key" type="password" />
                  <Field label="Min seeders" k="min_seeders" type="number" />
                  <Toggle label="Enable Cardigann definitions" k="cardigann_enabled" />
                  <Field label="FlareSolverr URL" k="flaresolverr_url" placeholder="http://flaresolverr:8191" />
                  <Toggle label="Built-in CF bypass (curl_cffi)" k="cf_bypass_enabled" />
                  <Field label="CF impersonate profile" k="cf_impersonate" placeholder="chrome124" />
                </div>
                <div className="divider text-xs opacity-50 my-1">Pick indexers from Prowlarr</div>
                <div className="flex flex-wrap gap-2 items-center">
                  <button type="button" className="btn btn-sm btn-primary" disabled={prowlarrBusy || !form.prowlarr_url || !form.prowlarr_api_key}
                    onClick={async ()=>{
                      setProwlarrBusy(true); setProwlarrMsg('');
                      try {
                        const q = new URLSearchParams({ url: form.prowlarr_url, api_key: form.prowlarr_api_key });
                        const r = await fetch('/api/setup/prowlarr/indexers?'+q).then(x=>x.json());
                        if (!r.ok) { setProwlarrMsg(r.error || 'Failed to list'); setProwlarrList([]); }
                        else {
                          setProwlarrList(r.indexers || []);
                          setProwlarrSelected((r.indexers||[]).filter(i=>i.enable).map(i=>i.id));
                          setProwlarrMsg((r.count||0)+' indexer(s) found — select which to import');
                        }
                      } catch(e) { setProwlarrMsg(String(e)); }
                      finally { setProwlarrBusy(false); }
                    }}>Load from Prowlarr</button>
                  <button type="button" className="btn btn-sm btn-outline" disabled={prowlarrBusy || !prowlarrSelected.length}
                    onClick={async ()=>{
                      setProwlarrBusy(true); setProwlarrMsg('');
                      try {
                        const r = await fetch('/api/setup/prowlarr/import', {
                          method:'POST', headers:{'Content-Type':'application/json'},
                          body: JSON.stringify({
                            url: form.prowlarr_url, api_key: form.prowlarr_api_key,
                            indexer_ids: prowlarrSelected, enable_all: false,
                          }),
                        }).then(x=>x.json());
                        setProwlarrMsg(r.ok
                          ? `Imported: +${r.added||0} ~${r.updated||0} (skipped ${r.skipped||0})`
                          : (r.error || 'Import failed'));
                      } catch(e) { setProwlarrMsg(String(e)); }
                      finally { setProwlarrBusy(false); }
                    }}>Import selected</button>
                  <button type="button" className="btn btn-sm btn-ghost" disabled={!prowlarrList?.length}
                    onClick={()=>setProwlarrSelected((prowlarrList||[]).map(i=>i.id))}>Select all</button>
                  <button type="button" className="btn btn-sm btn-ghost" disabled={!prowlarrSelected.length}
                    onClick={()=>setProwlarrSelected([])}>Clear</button>
                </div>
                {prowlarrMsg && <p className="text-xs opacity-70">{prowlarrMsg}</p>}
                {prowlarrList && prowlarrList.length > 0 && (
                  <div className="max-h-56 overflow-y-auto border border-base-content/10 rounded-lg">
                    <table className="table table-xs">
                      <thead><tr><th></th><th>Name</th><th>Protocol</th><th>Priority</th><th>Enabled in Prowlarr</th></tr></thead>
                      <tbody>
                        {prowlarrList.map(ix=>(
                          <tr key={ix.id} className="hover">
                            <td>
                              <input type="checkbox" className="checkbox checkbox-xs"
                                checked={prowlarrSelected.includes(ix.id)}
                                onChange={e=>{
                                  setProwlarrSelected(prev => e.target.checked
                                    ? [...prev, ix.id]
                                    : prev.filter(id=>id!==ix.id));
                                }} />
                            </td>
                            <td className="font-medium">{ix.name}</td>
                            <td><span className="badge badge-ghost badge-xs">{ix.protocol}</span></td>
                            <td>{ix.priority ?? '—'}</td>
                            <td>{ix.enable ? '✓' : '○'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                <p className="text-[11px] opacity-50">On Finish, any remaining enabled Prowlarr indexers are also synced in the background. Built-ins (YTS, EZTV, 1337x…) always work without Prowlarr.</p>
              </div>
            )}

            {cur.id==='subtitles' && (
              <div className="space-y-3">
                <p className="text-sm opacity-70">Bazarr-style multi-provider subtitles after organize. OpenSubtitles login recommended.</p>
                <div className="grid gap-2 sm:grid-cols-2">
                  <Field label="OpenSubtitles API key" k="opensubtitles_api_key" type="password" hint="opensubtitles.com consumer key" />
                  <Field label="OpenSubtitles username" k="opensubtitles_username" />
                  <Field label="OpenSubtitles password" k="opensubtitles_password" type="password" />
                  <Field label="SubDL API key" k="subdl_api_key" type="password" />
                  <Field label="Languages (comma ISO)" k="subtitle_languages" placeholder="en,es,fr" />
                  <Field label="Hearing-impaired" k="subtitle_hearing_impaired" placeholder="prefer | include | exclude" />
                  <Field label="Providers (comma)" k="subtitle_providers" placeholder="sidecar,opensubtitles,subdl,addic7ed,subscene" hint="Order = preference" />
                </div>
              </div>
            )}

            {cur.id==='usenet' && (
              <div className="space-y-3">
                <p className="text-sm opacity-70">Optional NNTP for seekable Usenet streaming. SABnzbd/NZBGet above handle classic NZB downloads.</p>
                <div className="grid gap-2 sm:grid-cols-2">
                  <Field label="NNTP host" k="nntp_host" />
                  <Field label="NNTP port" k="nntp_port" type="number" placeholder="563" />
                  <Field label="NNTP user" k="nntp_user" />
                  <Field label="NNTP password" k="nntp_pass" type="password" />
                  <Toggle label="SSL / TLS" k="nntp_ssl" />
                </div>
              </div>
            )}

            {cur.id==='vpn' && (
              <div className="space-y-3">
                <p className="text-sm opacity-70">Optional Gluetun / VPN awareness (kill-switch hints for health checks).</p>
                <div className="grid gap-2 sm:grid-cols-2">
                  <Toggle label="Enable VPN health checks" k="vpn_enabled" />
                  <Field label="Provider" k="vpn_provider" placeholder="gluetun / mullvad / ..." />
                  <Field label="Gluetun control URL" k="vpn_gluetun_url" placeholder="http://gluetun:8000" />
                  <Field label="Expected country" k="vpn_expected_country" placeholder="NL" />
                  <Field label="Interface" k="vpn_interface" placeholder="tun0" />
                  <Field label="Username" k="vpn_username" />
                  <Field label="Password" k="vpn_password" type="password" />
                  <Toggle label="Kill-switch (block grabs if VPN down)" k="vpn_kill_switch" />
                </div>
              </div>
            )}

            {cur.id==='youtube' && (
              <div className="space-y-3">
                <p className="text-sm opacity-70">Creator tracking uses public RSS (no Google API). Cookies unlock age-restricted / members videos.</p>
                <div className="grid gap-2 sm:grid-cols-2">
                  <Field label="YouTube library path" k="youtube_library_path" placeholder="/youtube" />
                  <Field label="yt-dlp path" k="youtube_ytdlp_path" placeholder="yt-dlp" />
                  <Field label="Format" k="youtube_format" placeholder="best[height<=1080]" />
                  <Toggle label="Auto-download new uploads" k="youtube_auto_download_default" />
                  <Field label="Cookies file (Netscape path)" k="youtube_cookies_path" placeholder="/config/youtube-cookies.txt" hint="Export from browser extension" />
                  <Field label="Cookies from browser" k="youtube_cookies_from_browser" placeholder="chrome | firefox | brave | edge" hint="Alternative to cookies file" />
                  <Field label="SponsorBlock remove" k="youtube_sponsorblock_remove" placeholder="sponsor,selfpromo,..." />
                  <Field label="SponsorBlock mark only" k="youtube_sponsorblock_mark" placeholder="optional" />
                </div>
                <div className="alert alert-info text-xs">Tip: place a Netscape cookies.txt at the path above, or set cookies-from-browser if yt-dlp can reach your browser profile.</div>
              </div>
            )}

            {cur.id==='integrations' && (
              <div className="space-y-4">
                <p className="text-sm opacity-70">Debrid providers, media servers, and notification channels.</p>
                <div className="divider text-xs opacity-50 my-1">Debrid</div>
                <div className="grid gap-2 sm:grid-cols-2">
                  <Field label="Real-Debrid token" k="real_debrid_token" type="password" />
                  <Field label="TorBox API key" k="torbox_api_key" type="password" />
                  <Field label="AllDebrid API key" k="alldebrid_api_key" type="password" />
                  <Field label="Premiumize API key" k="premiumize_api_key" type="password" />
                  <Field label="Debrid-Link API key" k="debridlink_api_key" type="password" />
                  <Field label="put.io token" k="putio_token" type="password" />
                  <Field label="EasyDebrid API key" k="easydebrid_api_key" type="password" />
                  <Field label="Offcloud API key" k="offcloud_api_key" type="password" />
                  <Field label="Movie mode" k="movie_download_mode" placeholder="download | strm" hint="strm = stream via debrid without local file" />
                </div>
                <div className="divider text-xs opacity-50 my-1">Media servers</div>
                <div className="grid gap-2 sm:grid-cols-2">
                  <Field label="Jellyfin URL" k="jellyfin_url" placeholder="http://jellyfin:8096" />
                  <Field label="Jellyfin API key" k="jellyfin_api_key" type="password" />
                  <Field label="Emby URL" k="emby_url" placeholder="http://emby:8096" />
                  <Field label="Emby API key" k="emby_api_key" type="password" />
                </div>
                <div className="divider text-xs opacity-50 my-1">Notifications</div>
                <div className="grid gap-2 sm:grid-cols-2">
                  <Field label="Discord webhook URL" k="discord_webhook_url" type="password" placeholder="https://discord.com/api/webhooks/..." />
                  <Field label="Telegram bot token" k="telegram_bot_token" type="password" />
                  <Field label="Telegram chat ID" k="telegram_chat_id" />
                  <Field label="Apprise URL" k="apprise_url" type="password" placeholder="discord://... or other Apprise URI" />
                </div>
              </div>
            )}

            {cur.id==='admin' && (
              <div className="space-y-3">
                <p className="text-sm opacity-70">Optional login for the UI and *arr-compat API. Leave blank to keep auth disabled.</p>
                <div className="grid gap-2 sm:grid-cols-2">
                  <Field label="Admin username" k="auth_username" placeholder="admin" />
                  <Field label="Admin password" k="auth_password" type="password" />
                  <Field label="ARR / request API key" k="arr_api_key" type="password" hint="Jellyseerr-compatible X-Api-Key" />
                  <Field label="Auth X-API-Key" k="auth_api_key" type="password" hint="Optional header auth for API clients" />
                </div>
              </div>
            )}

            {cur.id==='finish' && (
              <div className="space-y-3 text-sm">
                <p>Click <strong>Finish</strong> to save everything and mark setup complete. You can re-open this wizard anytime from Settings → Setup.</p>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
                  {[
                    ['TMDb', st?.has_tmdb], ['qBittorrent', st?.has_qbit], ['Indexer', st?.has_indexer],
                    ['NNTP', st?.has_nntp], ['VPN', st?.has_vpn], ['Jellyfin', st?.has_jellyfin],
                    ['Movies path', st?.movies_path_ok], ['TV path', st?.tv_path_ok],
                  ].map(([label, ok])=>(
                    <div key={label} className={'badge badge-lg gap-1 '+(ok?'badge-success':'badge-ghost')}>
                      {ok?'✓':'○'} {label}
                    </div>
                  ))}
                </div>
                <button type="button" className="btn btn-sm btn-outline" disabled={saving} onClick={checkPaths}>Re-check library paths</button>
                {pathCheck && (
                  <ul className="text-xs space-y-1">
                    {pathCheck.map(r=>(
                      <li key={r.key} className={r.writable?'text-success':'text-warning'}>
                        {r.writable?'✓':'!'} {r.key}: {r.path||'(empty)'} {r.note && `(${r.note})`}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            <div className="card-actions justify-between items-center mt-2">
              <button className="btn btn-ghost btn-sm" disabled={step===0 || saving} onClick={back}>Back</button>
              <div className="flex gap-2 items-center">
                {msg && <span className="text-xs opacity-60 max-w-[14rem] truncate">{msg}</span>}
                <button className="btn btn-ghost btn-sm" onClick={()=>onDone && onDone()}>Skip</button>
                <button className="btn btn-primary btn-sm" disabled={saving} onClick={next}>
                  {saving?'Saving…':(step===STEPS.length-1?'Finish':'Save & continue')}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}



function OverhaulDashboardPage({ setPage }) {
  const [data, setData] = useState(null);
  const [msg, setMsg] = useState(null);
  useEffect(() => {
    fetch('/api/overhaul/dashboard').then(r=>r.json()).then(setData).catch(e=>setMsg(String(e)));
  }, []);
  return (
    <div className="p-4 max-w-6xl mx-auto space-y-4">
      <div className="flex items-center gap-2">
        <h1 className="mr-page-title flex-1">Dashboard</h1>
        <button className="btn btn-sm" onClick={()=>setPage && setPage('settings-hub')}>Settings</button>
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
            <button className="btn btn-xs" onClick={()=>setPage && setPage('settings-quality-matrix')}>Quality matrices</button>
            <button className="btn btn-xs" onClick={()=>setPage && setPage('comics')}>Comics</button>
            <button className="btn btn-xs" onClick={()=>setPage && setPage('music')}>Music</button>
            <button className="btn btn-xs" onClick={()=>setPage && setPage('livetv')}>Live TV</button>
          </div>
        </>
      )}
    </div>
  );
}


function QualityMatrixPage({ setPage }) {
  const families = [
    { id: 'resolution', label: 'Resolution', hint: '2160p / 1080p / 720p …' },
    { id: 'source', label: 'Source', hint: 'Remux, BluRay, WEB-DL …' },
    { id: 'codec', label: 'Codec', hint: 'AV1, x265, x264 …' },
    { id: 'hdr', label: 'HDR', hint: 'DV, HDR10+, HDR …' },
    { id: 'audio', label: 'Audio', hint: 'Atmos, TrueHD, DTS …' },
    { id: 'groups', label: 'Release groups', hint: 'Editable reputation table' },
    { id: 'edition', label: 'Edition', hint: 'IMAX, Director\'s Cut …' },
  ];
  const [family, setFamily] = useState('groups');
  const [cells, setCells] = useState({});
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState(null);
  const [filter, setFilter] = useState('');
  const [newName, setNewName] = useState('');
  const [newScore, setNewScore] = useState(100);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    fetch(`/api/quality-ui/matrix/${family}`)
      .then(r => r.json())
      .then(d => setCells(d.cells || {}))
      .catch(e => setMsg(String(e)))
      .finally(() => setLoading(false));
  }, [family]);
  useEffect(() => { load(); }, [load]);

  const rows = Object.entries(cells)
    .filter(([k]) => !filter || k.toLowerCase().includes(filter.toLowerCase()))
    .sort((a,b) => b[1] - a[1] || a[0].localeCompare(b[0]));

  async function saveCell(name, score) {
    setBusy(true); setMsg(null);
    try {
      await fetch(`/api/quality-ui/matrix/${family}/${encodeURIComponent(name)}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, score: Number(score) }),
      }).then(async r => { if (!r.ok) throw new Error((await r.json()).detail || r.statusText); return r.json(); });
      setMsg(`Saved ${name} = ${score}`);
      load();
    } catch (e) { setMsg(String(e.message || e)); }
    setBusy(false);
  }
  async function removeCell(name) {
    if (!confirm(`Remove override for "${name}"?`)) return;
    setBusy(true);
    try {
      await fetch(`/api/quality-ui/matrix/${family}/${encodeURIComponent(name)}`, { method: 'DELETE' });
      load();
    } catch (e) { setMsg(String(e.message || e)); }
    setBusy(false);
  }
  async function addCell() {
    if (!newName.trim()) return;
    await saveCell(newName.trim().toLowerCase(), newScore);
    setNewName('');
  }
  async function resetFamily() {
    if (!confirm(`Reset ${family} overrides to built-in defaults?`)) return;
    setBusy(true);
    try {
      await fetch(`/api/quality-ui/matrix/reset?family=${family}`, { method: 'POST' });
      setMsg('Reset — restart app for full factory defaults on built-in keys');
      load();
    } catch (e) { setMsg(String(e.message || e)); }
    setBusy(false);
  }

  return (
    <div className="p-4 max-w-5xl mx-auto space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setPage && setPage('settings-hub')}>← Settings</button>
        <h1 className="mr-page-title flex-1">Quality matrices</h1>
        <button type="button" className="btn btn-sm" disabled={busy} onClick={async()=>{
          setBusy(true); setMsg('Fetching guide…');
          try {
            const r = await fetch('/api/overhaul/trash/fetch',{method:'POST'}).then(x=>x.json());
            setMsg('Guide: ' + (r.source||'?') + ' ' + JSON.stringify(r.applied||{}));
            load();
          } catch(e) { setMsg(String(e)); }
          setBusy(false);
        }}>Fetch TRaSH / guide</button>
        <button type="button" className="btn btn-sm" disabled={busy} onClick={resetFamily}>Reset family</button>
      </div>
      <p className="text-sm opacity-60">Every scoring cell is editable. Groups is the release-group reputation table used by interactive search and auto-grab.</p>
      <div className="tabs tabs-boxed flex-wrap w-fit gap-1">
        {families.map(f => (
          <a key={f.id} className={'tab ' + (family === f.id ? 'tab-active' : '')} onClick={() => setFamily(f.id)} title={f.hint}>{f.label}</a>
        ))}
      </div>
      {msg && <div className="alert alert-info text-xs py-2">{msg}</div>}
      <div className="flex flex-wrap gap-2 items-end">
        <label className="form-control">
          <span className="label-text text-xs">Filter</span>
          <input className="input input-bordered input-sm" value={filter} onChange={e => setFilter(e.target.value)} placeholder="name…" />
        </label>
        <label className="form-control">
          <span className="label-text text-xs">Add name</span>
          <input className="input input-bordered input-sm" value={newName} onChange={e => setNewName(e.target.value)} placeholder={family === 'groups' ? 'ctrlhd' : 'key'} />
        </label>
        <label className="form-control">
          <span className="label-text text-xs">Score</span>
          <input type="number" className="input input-bordered input-sm w-24" value={newScore} onChange={e => setNewScore(e.target.value)} />
        </label>
        <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={addCell}>Add / update</button>
      </div>
      {loading ? <span className="loading loading-spinner" /> : (
        <div className="overflow-x-auto border border-base-300 rounded-lg">
          <table className="table table-sm">
            <thead><tr><th>Key</th><th className="w-32">Score</th><th className="w-40"></th></tr></thead>
            <tbody>
              {rows.map(([name, score]) => (
                <MatrixRow key={name} name={name} score={score} busy={busy} onSave={saveCell} onRemove={removeCell} />
              ))}
              {!rows.length && <tr><td colSpan={3} className="opacity-50">No cells</td></tr>}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-xs opacity-50">{rows.length} cells in <code>{family}</code></p>
    </div>
  );
}

function MatrixRow({ name, score, busy, onSave, onRemove }) {
  const [val, setVal] = useState(score);
  useEffect(() => { setVal(score); }, [score]);
  return (
    <tr>
      <td className="font-mono text-xs">{name}</td>
      <td>
        <input type="number" className="input input-bordered input-xs w-28" value={val} onChange={e => setVal(e.target.value)} />
      </td>
      <td className="flex gap-1">
        <button type="button" className="btn btn-xs btn-primary" disabled={busy || Number(val) === score} onClick={() => onSave(name, val)}>Save</button>
        <button type="button" className="btn btn-xs btn-ghost" disabled={busy} onClick={() => onRemove(name)}>Del</button>
      </td>
    </tr>
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
      <p className="mr-page-sub">Dictionarry-class factors   score tester   language profiles</p></div>
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
            <li key={p.id}>{p.name}: {(p.languages||[]).join(', ')}   HI {p.hearing_impaired}</li>
          ))}</ul>
        </div>
      )}
    </div>
  );
}


/* ── Tdarr-style Converter ───────────────────────────────────────────────── */

function ConverterGpuWizard() {
  const [hw, setHw] = useState(null);
  const [copied, setCopied] = useState('');
  const load = () => fetch('/api/converter/hw').then(r=>r.json()).then(setHw).catch(()=>setHw(null));
  useEffect(()=>{ load(); }, []);
  const copy = (text, id) => {
    navigator.clipboard?.writeText(text).then(()=>{ setCopied(id); setTimeout(()=>setCopied(''), 2000); }).catch(()=>{});
  };
  if (!hw) return <div className="p-8 opacity-50">Detecting GPU / ffmpeg…</div>;
  const rec = hw.recommended || 'software';
  const profiles = hw.profiles || {};
  const order = ['nvidia', 'intel', 'amd', 'software'];
  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="mr-page-title">GPU setup wizard</h1>
        <p className="mr-page-sub">HandBrake × Tdarr — detect encoders, copy the right compose command</p>
      </div>

      <div className="card bg-base-200 shadow">
        <div className="card-body gap-3">
          <h2 className="font-semibold text-sm">Live detection</h2>
          <div className="flex flex-wrap gap-2">
            <span className={"badge "+(hw.ffmpeg?'badge-success':'badge-error')}>ffmpeg {hw.ffmpeg?'ok':'missing'}</span>
            <span className={"badge "+(hw.nvenc?'badge-success':'badge-ghost')}>NVENC {hw.nvenc?'yes':'no'}</span>
            <span className={"badge "+(hw.qsv?'badge-success':'badge-ghost')}>QSV {hw.qsv?'yes':'no'}</span>
            <span className={"badge "+(hw.vaapi?'badge-success':'badge-ghost')}>VAAPI {hw.vaapi?'yes':'no'}</span>
            <span className={"badge "+(hw.amf?'badge-success':'badge-ghost')}>AMF {hw.amf?'yes':'no'}</span>
          </div>
          {hw.encoders?.length > 0 && (
            <div className="text-xs font-mono opacity-70 break-all">{hw.encoders.join(', ')}</div>
          )}
          <div className="alert alert-info text-sm py-2">
            Recommended: <strong>{(profiles[rec]||{}).label || rec}</strong>
            {rec==='software' && ' — no GPU encoders seen inside this container yet. CPU presets still work.'}
          </div>
          <button className="btn btn-sm btn-ghost w-fit" onClick={load}>Re-detect</button>
        </div>
      </div>

      {order.map(id => {
        const p = profiles[id];
        if (!p) return null;
        const isRec = id === rec;
        return (
          <div key={id} className={"card shadow-sm "+(isRec?'border border-primary bg-primary/5':'bg-base-200')}>
            <div className="card-body gap-2 p-4">
              <div className="flex items-center gap-2">
                <h3 className="font-semibold">{p.label}</h3>
                {isRec && <span className="badge badge-primary badge-sm">recommended</span>}
              </div>
              <p className="text-xs opacity-60">{p.notes}</p>
              {p.checklist && (
                <ul className="text-sm space-y-1 list-disc list-inside opacity-80">
                  {p.checklist.map((c,i)=><li key={i}>{c}</li>)}
                </ul>
              )}
              <div className="relative">
                <pre className="bg-base-300 text-xs p-3 rounded overflow-x-auto font-mono whitespace-pre-wrap">{p.compose}</pre>
                <button className="btn btn-xs absolute top-2 right-2" onClick={()=>copy(p.compose, id)}>
                  {copied===id?'Copied':'Copy'}
                </button>
              </div>
            </div>
          </div>
        );
      })}

      <p className="text-xs opacity-50">Full notes: <code className="text-xs">docs/GPU.md</code>. After changing compose, open this page again and hit Re-detect. Software presets never require a GPU.</p>
    </div>
  );
}

function ConverterDashboard({ setPage }) {
  const [stats, setStats] = useState({});
  const [jobs, setJobs] = useState([]);
  const [hw, setHw] = useState(null);
  const load = () => {
    fetch('/api/converter/stats').then(r=>r.json()).then(setStats).catch(()=>{});
    fetch('/api/converter/jobs?limit=8').then(r=>r.json()).then(setJobs).catch(()=>[]);
    fetch('/api/converter/hw').then(r=>r.json()).then(setHw).catch(()=>{});
  };
  useEffect(()=>{ load(); const id=setInterval(load, 4000); return ()=>clearInterval(id); }, []);
  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="mr-page-title">Converter</h1>
        <p className="mr-page-sub">HandBrake × Tdarr — GPU   parallel workers   schedule   savings</p>
      </div>
      {hw && (
        <div className="card bg-base-200 shadow-sm">
          <div className="card-body p-4 gap-2">
            <h2 className="font-semibold text-sm">Hardware encode</h2>
            <div className="flex flex-wrap gap-2 text-xs">
              <span className={"badge "+(hw.ffmpeg?'badge-success':'badge-error')}>ffmpeg {hw.ffmpeg?'ok':'missing'}</span>
              <span className={"badge "+(hw.nvenc?'badge-success':'badge-ghost')}>NVENC {hw.nvenc?'available':'n/a'}</span>
              <span className={"badge "+(hw.qsv?'badge-success':'badge-ghost')}>QSV {hw.qsv?'available':'n/a'}</span>
              <span className={"badge "+(hw.vaapi?'badge-success':'badge-ghost')}>VAAPI {hw.vaapi?'available':'n/a'}</span>
              <span className={"badge "+(hw.amf?'badge-success':'badge-ghost')}>AMF {hw.amf?'available':'n/a'}</span>
            </div>
            {hw.encoders?.length > 0 && <div className="text-xs font-mono opacity-60">{hw.encoders.join(', ')}</div>}
            {hw.max_workers && <div className="text-xs opacity-60">Workers: {hw.max_workers}   schedule {hw.schedule_ok===false?'paused':'active'}</div>}
            <div className="text-xs opacity-60">Watch folders: {hw.watch_folders || '(none — set CONVERTER_WATCH_FOLDERS)'}   every {hw.watch_interval_minutes}m</div>
            {setPage ? (
              <button type="button" className="btn btn-xs btn-primary w-fit" onClick={()=>setPage('converter-gpu')}>Open GPU setup wizard</button>
            ) : (
              <p className="text-xs opacity-70">Sidebar → Converter → GPU setup</p>
            )}
          </div>
        </div>
      )}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        {['queued','running','done','failed','cancelled'].map(k=>(
          <div key={k} className="card bg-base-200 shadow-sm">
            <div className="card-body p-3 items-center">
              <div className="text-2xl font-bold">{stats[k]||0}</div>
              <div className="text-xs uppercase opacity-60">{k}</div>
            </div>
          </div>
        ))}
      </div>
      {stats.active_job_id && <div className="alert alert-info text-sm">Active job #{stats.active_job_id}</div>}
      {stats.savings && stats.savings.jobs_with_sizes > 0 && (
        <div className="card bg-gradient-to-br from-primary/20 to-base-200 shadow">
          <div className="card-body p-4 gap-3">
            <div className="flex flex-wrap items-end justify-between gap-2">
              <div>
                <h2 className="font-semibold">Space savings</h2>
                <p className="text-xs opacity-60">HandBrake math   Tdarr queue — completed jobs with size data</p>
              </div>
              <div className="text-right">
                <div className="text-3xl font-bold text-success">{stats.savings.saved_human}</div>
                <div className="text-xs opacity-60">{stats.savings.saved_pct}% smaller   {stats.savings.jobs_with_sizes} files</div>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-2 text-center text-sm">
              <div className="p-2 rounded bg-base-300/50">
                <div className="font-mono font-semibold">{stats.savings.source_human}</div>
                <div className="text-xs opacity-50">before</div>
              </div>
              <div className="p-2 rounded bg-base-300/50">
                <div className="font-mono font-semibold">{stats.savings.output_human}</div>
                <div className="text-xs opacity-50">after</div>
              </div>
              <div className="p-2 rounded bg-success/20">
                <div className="font-mono font-semibold text-success">{stats.savings.saved_human}</div>
                <div className="text-xs opacity-50">saved</div>
              </div>
            </div>
            {stats.savings.top_savers?.length > 0 && (
              <div>
                <h3 className="text-xs font-semibold opacity-60 mb-1">Top savers</h3>
                <div className="space-y-1 max-h-40 overflow-auto">
                  {stats.savings.top_savers.map(s=>(
                    <div key={s.id} className="flex justify-between gap-2 text-xs font-mono">
                      <span className="truncate opacity-70">{(s.source_path||'').split('/').pop()}</span>
                      <span className="shrink-0 text-success">{s.saved_human} ({s.saved_pct}%)</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
      <div>
        <h2 className="font-semibold mb-2">Recent jobs</h2>
        <div className="space-y-1">
          {jobs.map(j=>(
            <div key={j.id} className="flex justify-between gap-2 p-2 bg-base-200 rounded text-sm">
              <div className="min-w-0 truncate font-mono text-xs">{j.source_path}</div>
              <div className="shrink-0 flex gap-2 items-center">
                <span className="badge badge-sm">{j.status}</span>
                <span className="text-xs opacity-60">{Math.round(j.progress)}%</span>
              </div>
            </div>
          ))}
          {!jobs.length && <p className="text-sm opacity-50">No jobs yet — scan a library or enqueue a file.</p>}
        </div>
      </div>
      <button className="btn btn-sm btn-primary" onClick={async()=>{ await fetch('/api/converter/worker/tick',{method:'POST'}); load(); }}>Run worker tick</button>
    </div>
  );
}

function ConverterQueue() {
  const [jobs, setJobs] = useState([]);
  const [filter, setFilter] = useState('');
  const load = () => fetch('/api/converter/jobs?limit=200'+(filter?'&status='+filter:'')).then(r=>r.json()).then(setJobs).catch(()=>[]);
  useEffect(()=>{ load(); const id=setInterval(load, 3000); return ()=>clearInterval(id); }, [filter]);
  return (
    <div className="space-y-4 max-w-5xl">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="mr-page-title">Conversion queue</h1>
          <p className="text-sm opacity-60">FFmpeg jobs — auto-processed every ~45s</p>
        </div>
        <div className="flex gap-2">
          <select className="select select-sm select-bordered" value={filter} onChange={e=>setFilter(e.target.value)}>
            <option value="">All</option>
            {['queued','running','done','failed','cancelled'].map(s=><option key={s} value={s}>{s}</option>)}
          </select>
          <button className="btn btn-sm" onClick={async()=>{ await fetch('/api/converter/jobs/clear?status=done',{method:'POST'}); load(); }}>Clear done</button>
          <button className="btn btn-sm btn-primary" onClick={async()=>{ await fetch('/api/converter/worker/tick',{method:'POST'}); load(); }}>Process next</button>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="table table-sm">
          <thead><tr><th>ID</th><th>Source</th><th>Preset</th><th>Codec</th><th>Status</th><th>Progress</th><th>Size</th><th></th></tr></thead>
          <tbody>
            {jobs.map(j=>(
              <tr key={j.id}>
                <td className="font-mono text-xs">{j.id}</td>
                <td className="font-mono text-xs max-w-xs truncate" title={j.source_path}>{j.source_path}</td>
                <td className="text-xs">{j.preset_name||'—'}</td>
                <td className="text-xs">{j.source_codec||'—'}</td>
                <td><span className={"badge badge-sm "+(j.status==='done'?'badge-success':j.status==='failed'?'badge-error':j.status==='running'?'badge-info':'')}>{j.status}</span></td>
                <td className="min-w-[6rem]">
                  <progress className="progress progress-primary h-2 w-full" value={j.progress} max="100" />
                  <span className="text-[10px] opacity-50">{Math.round(j.progress)}% {j.message||''}</span>
                </td>
                <td className="text-xs font-mono opacity-70 whitespace-nowrap">
                  {j.status==='done' && j.source_size && j.output_size
                    ? `${(j.output_size/1e9).toFixed(2)}G / ${(j.source_size/1e9).toFixed(2)}G`
                    : (j.source_size ? `${(j.source_size/1e9).toFixed(2)}G` : '—')}
                </td>
                <td className="flex gap-1">
                  {(j.status==='queued'||j.status==='running') && (
                    <button className="btn btn-xs" onClick={async()=>{ await fetch('/api/converter/jobs/'+j.id+'/cancel',{method:'POST'}); load(); }}>Cancel</button>
                  )}
                  {j.status!=='running' && (
                    <button className="btn btn-xs btn-ghost text-error" onClick={async()=>{ await fetch('/api/converter/jobs/'+j.id,{method:'DELETE'}); load(); }}>Del</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}


function WatchFolderMapper({ busy, setBusy, setMsg, presets }) {
  const [folders, setFolders] = useState([]);
  const [path, setPath] = useState('');
  const [presetId, setPresetId] = useState('');
  const load = () => fetch('/api/converter/watch-folders').then(r=>r.json()).then(setFolders).catch(()=>[]);
  useEffect(()=>{ load(); }, []);
  const add = async () => {
    if (!path.trim()) return;
    setBusy(true);
    try {
      await fetch('/api/converter/watch-folders',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:path.trim(), preset_id: presetId?Number(presetId):null, enabled:true})});
      setPath(''); load(); setMsg('Folder mapping added');
    } catch(e){ setMsg(String(e)); }
    setBusy(false);
  };
  return (
    <div className="card bg-base-200">
      <div className="card-body gap-3">
        <h2 className="font-semibold text-sm">Per-folder preset mapping</h2>
        <p className="text-xs opacity-60">Each path can use its own preset (NVENC / QSV / AMF / software). Scheduler scans enabled folders on an interval. Env <code className="text-xs">CONVERTER_WATCH_FOLDERS</code> is fallback when this list is empty.</p>
        <div className="flex flex-wrap gap-2">
          <input className="input input-bordered input-sm flex-1 min-w-[12rem] font-mono text-xs" placeholder="/movies/incoming" value={path} onChange={e=>setPath(e.target.value)} />
          <select className="select select-bordered select-sm" value={presetId} onChange={e=>setPresetId(e.target.value)}>
            <option value="">Default preset</option>
            {(presets||[]).map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <button className="btn btn-sm btn-primary" disabled={busy||!path.trim()} onClick={add}>Add mapping</button>
        </div>
        <div className="space-y-1">
          {folders.map(f=>(
            <div key={f.id} className="flex flex-wrap items-center gap-2 text-sm p-2 bg-base-300 rounded">
              <span className="font-mono text-xs flex-1 min-w-[8rem] truncate">{f.path}</span>
              <span className="badge badge-xs">{(presets||[]).find(p=>p.id===f.preset_id)?.name || 'default'}</span>
              <span className="text-xs opacity-50">last +{f.last_queued||0}</span>
              <button className="btn btn-xs" onClick={async()=>{
                await fetch('/api/converter/watch-folders/'+f.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...f, enabled:!f.enabled})});
                load();
              }}>{f.enabled?'On':'Off'}</button>
              <button className="btn btn-xs btn-ghost text-error" onClick={async()=>{ await fetch('/api/converter/watch-folders/'+f.id,{method:'DELETE'}); load(); }}>Del</button>
            </div>
          ))}
          {!folders.length && <p className="text-xs opacity-50">No mappings yet — add paths above.</p>}
        </div>
        <button className="btn btn-sm btn-secondary" disabled={busy} onClick={async()=>{
          setBusy(true);
          try {
            const r = await fetch('/api/converter/watch/scan',{method:'POST'}).then(x=>x.json());
            setMsg(r.enabled ? `Watch scan (${r.source}): queued ${r.queued}, scanned ${r.scanned}` : 'No watch folders configured');
          } catch(e){ setMsg(String(e)); }
          setBusy(false);
        }}>Scan watch folders now</button>
      </div>
    </div>
  );
}

function ConverterScan() {
  const [presets, setPresets] = useState([]);
  const [presetId, setPresetId] = useState('');
  const [limit, setLimit] = useState(50);
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);
  const [path, setPath] = useState('');
  useEffect(()=>{ fetch('/api/converter/presets').then(r=>r.json()).then(p=>{ setPresets(p); const d=p.find(x=>x.is_default); if(d) setPresetId(String(d.id)); }).catch(()=>{}); }, []);
  const scan = async () => {
    setBusy(true); setMsg('');
    try {
      const r = await fetch('/api/converter/scan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({preset_id: presetId?Number(presetId):null, limit:Number(limit)})}).then(x=>x.json());
      setMsg(`Scanned ${r.scanned}, queued ${r.queued}, skipped ${r.skipped} (preset: ${r.preset})`);
    } catch(e){ setMsg(String(e)); }
    setBusy(false);
  };
  const enqueue = async () => {
    setBusy(true);
    try {
      const r = await fetch('/api/converter/jobs/enqueue',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path, preset_id: presetId?Number(presetId):null})}).then(x=>x.json());
      setMsg(`Enqueued job #${r.id}`);
      setPath('');
    } catch(e){ setMsg(String(e)); }
    setBusy(false);
  };
  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="mr-page-title">Scan libraries</h1>
        <p className="text-sm opacity-60">Walk movie/TV/… roots and queue files that need conversion (Tdarr-style)</p>
      </div>
      <div className="card bg-base-200">
        <div className="card-body gap-3">
          <label className="form-control">
            <span className="label-text text-xs">Preset</span>
            <select className="select select-bordered select-sm" value={presetId} onChange={e=>setPresetId(e.target.value)}>
              {presets.map(p=><option key={p.id} value={p.id}>{p.name}{p.is_default?' (default)':''}</option>)}
            </select>
          </label>
          <label className="form-control">
            <span className="label-text text-xs">Max files to queue</span>
            <input type="number" className="input input-bordered input-sm" value={limit} onChange={e=>setLimit(e.target.value)} />
          </label>
          <button className="btn btn-primary btn-sm" disabled={busy} onClick={scan}>{busy?'Scanning…':'Scan all libraries'}</button>
        </div>
      </div>
      <div className="card bg-base-200">
        <div className="card-body gap-3">
          <h2 className="font-semibold text-sm">Enqueue single file</h2>
          <input className="input input-bordered input-sm font-mono text-xs" placeholder="/movies/Film (2020)/Film.mkv" value={path} onChange={e=>setPath(e.target.value)} />
          <button className="btn btn-sm" disabled={busy||!path.trim()} onClick={enqueue}>Enqueue path</button>
        </div>
      </div>
      <WatchFolderMapper busy={busy} setBusy={setBusy} setMsg={setMsg} presets={presets} />
      {msg && <div className="alert alert-info text-sm">{msg}</div>}
    </div>
  );
}

function ConverterPresets() {
  const [presets, setPresets] = useState([]);
  const load = () => fetch('/api/converter/presets').then(r=>r.json()).then(setPresets).catch(()=>[]);
  useEffect(()=>{ load(); }, []);
  const setMode = async (p, output_mode) => {
    const body = { ...p, output_mode };
    await fetch('/api/converter/presets/'+p.id, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    load();
  };
  return (
    <div className="space-y-4 max-w-4xl">
      <div>
        <h1 className="mr-page-title">Conversion presets</h1>
        <p className="text-sm opacity-60">Codec / container / quality — and what to do with the original file after convert</p>
      </div>
      <div className="grid gap-3">
        {presets.map(p=>(
          <div key={p.id} className="card bg-base-200 shadow-sm">
            <div className="card-body p-4 gap-2">
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="font-semibold">{p.name} {p.is_default && <span className="badge badge-primary badge-sm">default</span>}</h3>
                  <p className="text-xs opacity-60">{p.description}</p>
                </div>
                <span className={"badge badge-sm "+(p.enabled?'badge-success':'badge-ghost')}>{p.enabled?'on':'off'}</span>
              </div>
              <div className="text-xs font-mono opacity-70">
                {p.video_codec} crf{p.video_crf} / {p.audio_codec} {p.audio_bitrate} → .{p.container}
                {p.hwaccel && p.hwaccel!=='none' ? `   HW ${p.hwaccel}` : ''}
                {p.skip_codecs ? `   skip ${p.skip_codecs}` : ''}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs opacity-60">After convert:</span>
                <select className="select select-bordered select-xs" value={p.output_mode||'new_file'} onChange={e=>setMode(p, e.target.value)}>
                  <option value="new_file">Keep original (new file alongside)</option>
                  <option value="rename_old">Rename original (.original) + write converted</option>
                  <option value="replace">Replace original (delete old)</option>
                </select>
              </div>
            </div>
          </div>
        ))}
      </div>
      <p className="text-xs opacity-50">
        <strong>new_file</strong> — original stays; writes <code className="text-xs">name.converted.mp4</code>.{" "}
        <strong>rename_old</strong> — original becomes <code className="text-xs">name.original.mkv</code>, converted takes the main name.{" "}
        <strong>replace</strong> — original is deleted after a successful encode.
      </p>
    </div>
  );
}


function MusicPage({ setPage }) {
  const [items, setItems] = useState([]);
  const [tree, setTree] = useState([]);
  const [view, setView] = useState('hierarchy'); // hierarchy | grid | incomplete
  const [detailId, setDetailId] = useState(null);
  const [expanded, setExpanded] = useState({});
  const [incomplete, setIncomplete] = useState([]);
  const [q, setQ] = useState('');
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);

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

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex-1 min-w-[160px]">
          <h1 className="mr-page-title">Music</h1>
          <p className="text-xs opacity-50">Artist → album → track hierarchy</p>
        </div>
        <div className="join">
          <button className={"btn btn-sm join-item "+(view==='hierarchy'?'btn-primary':'')} onClick={()=>setView('hierarchy')}>Hierarchy</button>
          <button className={"btn btn-sm join-item "+(view==='grid'?'btn-primary':'')} onClick={()=>setView('grid')}>Albums</button>
          <button className={"btn btn-sm join-item "+(view==='incomplete'?'btn-primary':'')} onClick={()=>setView('incomplete')}>Incomplete</button>
        </div>
        <button className="btn btn-sm btn-secondary" disabled={busy} onClick={searchMissing}>Search missing</button>
        <button className="btn btn-sm" onClick={()=>setPage && setPage('discover')}>Discover</button>
      </div>
      {msg && <div className="alert alert-info text-xs py-2">{msg}</div>}
      <input className="input input-bordered input-sm w-full max-w-md" placeholder="Filter artist or album…" value={q} onChange={e=>setQ(e.target.value)} />

      {view === 'hierarchy' && (
        <div className="space-y-1">
          {filteredTree.map(artist => {
            const open = expanded[artist.name];
            const dl = (artist.albums||[]).filter(a=>a.status==='downloaded').length;
            return (
              <div key={artist.name} className="card bg-base-200/80 border border-base-content/5 overflow-hidden">
                <button type="button" className="flex items-center gap-3 p-3 w-full text-left hover:bg-base-300/40"
                  onClick={()=>setExpanded(e=>({...e, [artist.name]: !open}))}>
                  <span className="text-xs opacity-40 w-4">{open?'▼':'▶'}</span>
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-sm truncate">{artist.name}</div>
                    <div className="text-[10px] opacity-50">{artist.album_count} albums · {dl} on disk</div>
                  </div>
                  <span className="badge badge-sm badge-ghost">{artist.album_count}</span>
                </button>
                {open && (
                  <div className="border-t border-base-content/5 divide-y divide-base-content/5">
                    {(artist.albums||[]).map(al => (
                      <button key={al.id} type="button"
                        className="flex items-center gap-3 px-4 py-2 w-full text-left hover:bg-primary/10"
                        onClick={()=>setDetailId(al.id)}>
                        <div className="w-10 h-10 rounded bg-base-300 overflow-hidden shrink-0">
                          {al.poster_path ? <img src={al.poster_path} alt="" className="object-cover w-full h-full"/> : null}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium truncate">{al.title}</div>
                          <div className="text-[10px] opacity-50">{al.year||'—'} · {al.monitored?'monitored':'unmonitored'}</div>
                        </div>
                        <span className={'badge badge-xs '+(al.status==='downloaded'?'badge-success':al.status==='wanted'?'badge-warning':'badge-ghost')}>{al.status}</span>
                      </button>
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
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
          {filteredGrid.map(a=>(
            <div key={a.id} className="card bg-base-200 shadow-sm cursor-pointer hover:ring-1 hover:ring-primary/40" onClick={()=>setDetailId(a.id)}>
              <figure className="aspect-square bg-base-300 overflow-hidden">
                {a.poster_path ? <img src={a.poster_path} alt="" className="object-cover w-full h-full" /> : <div className="flex items-center justify-center h-full opacity-30 text-xs">No art</div>}
              </figure>
              <div className="card-body p-2 gap-0.5">
                <div className="text-xs font-semibold line-clamp-1">{a.title}</div>
                <div className="text-[10px] opacity-60 line-clamp-1">{a.artist_name||''}</div>
                <span className={'badge badge-xs '+(a.status==='downloaded'?'badge-success':'badge-warning')}>{a.status}</span>
              </div>
            </div>
          ))}
          {!filteredGrid.length && <div className="col-span-full opacity-50 text-sm p-6">No albums yet</div>}
        </div>
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
                  <button className="btn btn-xs btn-primary" onClick={()=>setDetailId(c.album_id)}>Open</button>
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
  const load = React.useCallback(() => {
    api.music.get(id).then(setItem).catch(e=>setMsg(String(e.message||e)));
    fetch(`/api/music/album/${id}/tracks`).then(r=>r.json()).then(d=>setTracks(Array.isArray(d)?d:[])).catch(()=>[]);
    fetch(`/api/music/album/${id}/completeness`).then(r=>r.json()).then(setCompleteness).catch(()=>setCompleteness(null));
  }, [id]);
  useEffect(()=>{ load(); }, [load]);

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
    try { setIxResults(await api.music.interactive(id) || []); }
    catch(e) { setMsg(String(e.message||e)); }
    setIxLoading(false);
  }
  async function grabRel(rel) {
    setBusy(true);
    try {
      await api.music.grab(id, rel);
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
        <button className="btn btn-sm btn-primary" disabled={busy} onClick={autoSearch}>Search & grab</button>
        <button className="btn btn-sm btn-secondary" disabled={busy||ixLoading} onClick={openIx}>Interactive search</button>
        <button className="btn btn-sm" disabled={busy} onClick={toggleMon}>{item.monitored?'Unmonitor':'Monitor'}</button>
        <button className="btn btn-sm btn-ghost text-error" onClick={async()=>{ await api.music.remove(id); onBack(); }}>Delete</button>
      </>}
    >
      <InteractiveResultsTable results={ixResults} loading={ixLoading} busy={busy} onGrab={grabRel} onClose={()=>setIxResults(null)} />
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
      {(tracks.length>0 || completeness) && (
        <div className="card bg-base-200"><div className="card-body p-4 gap-2">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-sm">Tracks ({tracks.length})</h3>
            <button className="btn btn-ghost btn-xs" onClick={async()=>{
              try {
                await fetch(`/api/music/album/${id}/tracks/refresh`, {method:'POST'});
                const d = await fetch(`/api/music/album/${id}/tracks`).then(r=>r.json());
                setTracks(Array.isArray(d)?d:[]);
                const c = await fetch(`/api/music/album/${id}/completeness`).then(r=>r.json());
                setCompleteness(c);
              } catch(e) { setMsg(String(e.message||e)); }
            }}>Refresh from MusicBrainz</button>
          </div>
          <div className="overflow-x-auto max-h-64">
            <table className="table table-xs">
              <thead><tr><th>#</th><th>Title</th><th>Disc</th><th>Status</th></tr></thead>
              <tbody>
                {tracks.map((tr,i)=>(
                  <tr key={tr.id||i} className={tr.file_path || tr.status==='downloaded' ? 'opacity-100' : 'opacity-70'}>
                    <td className="tabular-nums opacity-50">{tr.track_number||i+1}</td>
                    <td className="truncate max-w-[220px]">{tr.title||tr.name}</td>
                    <td className="opacity-50">{tr.disc_number||1}</td>
                    <td><span className={'badge badge-xs '+(tr.file_path||tr.status==='downloaded'?'badge-success':'badge-ghost')}>{tr.file_path||tr.status==='downloaded'?'have':(tr.status||'wanted')}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div></div>
      )}
    </MediaDetailShell>
  );
}



function SettingsHubPage({ setPage, advanced, setAdvanced, enabledModules }) {
  const em = enabledModules || ['movies','tv'];
  const groups = [
    { title: "Library", desc: "Where files live and how they are named (Jellyfin-compatible)", items: [
      { key: "settings-library", label: "Paths & naming", hint: "Movies / TV / Music folders, episode templates" },
      { key: "settings-quality", label: "Quality profiles", hint: "Scoring, custom formats, upgrades" },
      { key: "settings-quality-matrix", label: "Quality matrices", hint: "Resolution / source / codec / groups tables" },
    ]},
    { title: "Downloads", desc: "Clients, indexers, and queue cleanup", items: [
      { key: "settings-downloads", label: "Download clients", hint: "qBittorrent, SABnzbd, Transmission…" },
      { key: "settings-indexers", label: "Indexers", hint: "Prowlarr, Jackett, Cardigann, builtins" },
      { key: "settings-indexers-cfg", label: "Indexer connection", hint: "URLs and API keys" },
      { key: "settings-cleanup", label: "Queue cleaner", hint: "Stalls, seed limits, orphans" },
    ]},
    { title: "Media tools", desc: "Subtitles and HandBrake×Tdarr converter", items: [
      { key: "settings-subtitles", label: "Subtitles", hint: "OpenSubtitles, language profiles" },
      { key: "converter", label: "Converter queue", hint: "Transcode presets, watch folders, GPU" },
      { key: "converter-presets", label: "Converter presets", hint: "H.264 / HEVC / NVENC / QSV / AMF" },
    ]},
    { title: "Modules", desc: "Enable library types and power features", items: [
      { key: "modules", label: "Module Store", hint: "Music, Books, Comics, Live TV, Converter…" },
    ]},
    { title: "Access", desc: "Who can use MediaOs and what they can do", items: [
      { key: "settings-users", label: "Users & permissions", hint: "Admin grants roles and fine-grained rights" },
      { key: "settings-auth", label: "Auth / API keys", hint: "Login, X-API-Key" },
      { key: "settings-sessions", label: "Sessions", hint: "Active tokens" },
    ]},
    { title: "Integrations", desc: "Metadata, debrid, notifications, media servers", items: [
      { key: "settings-metadata", label: "Metadata APIs", hint: "TMDb, TVDb, ComicVine, Trakt" },
      { key: "settings-debrid", label: "Debrid", hint: "Real-Debrid, TorBox, AllDebrid…" },
      { key: "settings-integrations", label: "Notifications & servers", hint: "Discord, Telegram, Jellyfin refresh" },
      { key: "settings-youtube", label: "YouTube", hint: "Creators, cookies, SponsorBlock" },
      { key: "settings-vpn", label: "VPN", hint: "Gluetun health / kill-switch" },
      { key: "settings-usenet", label: "Usenet / NNTP", hint: "NNTP streaming" },
    ]},
    { title: "Appearance & system", desc: "Look and feel, logs, wizard", items: [
      { key: "settings-themes", label: "Themes", hint: "mediaos purple and DaisyUI themes" },
      { key: "settings-system", label: "System", hint: "Search interval, upgrades, logs" },
      { key: "settings-setup", label: "Setup wizard", hint: "Re-run first-run bootstrap" },
    ]},
  ];
  // Filter groups by advanced mode + enabled modules
  const filtered = groups.map(g => {
    let items = g.items.filter(it => {
      if (it.key === 'settings-quality-matrix' && !advanced) return false;
      if ((it.key === 'converter' || it.key === 'converter-presets') && !em.includes('converter') && !advanced) return false;
      return true;
    });
    return { ...g, items };
  }).filter(g => g.items.length > 0);

  return (
    <div className="space-y-5 max-w-5xl">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="mr-page-title">Settings</h1>
          <p className="mr-page-sub">Grouped by area — changes apply immediately (no restart).</p>
        </div>
        <div className="card bg-base-200 border border-base-content/10 shadow-sm">
          <div className="card-body p-3 flex-row items-center gap-3">
            <div className="text-xs">
              <div className="font-semibold">{advanced ? 'Advanced' : 'Basic'} mode</div>
              <div className="opacity-50">Power tools &amp; extra modules</div>
            </div>
            <input type="checkbox" className="toggle toggle-primary" checked={!!advanced}
              onChange={e=>{ const v=e.target.checked; setAdvancedFlag(v); setAdvanced && setAdvanced(v); }} />
          </div>
        </div>
      </div>
      {filtered.map(g=>(
        <div key={g.title} className="space-y-2">
          <div>
            <h2 className="font-semibold text-sm tracking-wide uppercase opacity-70">{g.title}</h2>
            <p className="text-xs opacity-50">{g.desc}</p>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {g.items.map(it=>(
              <button key={it.key} type="button"
                className="card bg-base-200 hover:bg-base-300 text-left border border-base-content/5 hover:border-primary/40 transition-all hover:shadow-md"
                onClick={()=>setPage && setPage(it.key)}>
                <div className="card-body p-3 gap-0.5">
                  <div className="font-medium text-sm">{it.label}</div>
                  <div className="text-[11px] opacity-50 leading-snug">{it.hint}</div>
                </div>
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function UsersPermissionsPage() {
  const [users, setUsers] = useState([]);
  const [catalog, setCatalog] = useState([]);
  const [msg, setMsg] = useState("");
  const [form, setForm] = useState({ username:"", password:"", role:"user", permissions:[] });
  const [editId, setEditId] = useState(null);

  function load() {
    fetch("/api/users").then(r=>r.json()).then(setUsers).catch(()=>setUsers([]));
    fetch("/api/users/permissions/catalog").then(r=>r.json()).then(d=>{
      setCatalog(d.permissions||[]);
      if (!form.permissions.length && d.role_defaults?.user) {
        setForm(f=>({...f, permissions: d.role_defaults.user}));
      }
    }).catch(()=>{});
  }
  useEffect(()=>{ load(); }, []);

  async function createUser() {
    setMsg("");
    const r = await fetch("/api/users", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(form) }).then(x=>x.json());
    if (r.id) { setMsg("Created "+r.username); setForm({ username:"", password:"", role:"user", permissions: form.permissions }); load(); }
    else setMsg(r.detail || r.error || JSON.stringify(r));
  }
  async function saveUser(u) {
    const r = await fetch("/api/users/"+u.id, { method:"PATCH", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ role: u.role, is_active: u.is_active, permissions: u.permissions }) }).then(x=>x.json());
    if (r.id) { setMsg("Updated "+r.username); load(); setEditId(null); }
    else setMsg(JSON.stringify(r));
  }
  async function removeUser(id) {
    if (!confirm("Delete user?")) return;
    await fetch("/api/users/"+id, { method:"DELETE" });
    load();
  }

  const groups = {};
  (catalog||[]).forEach(p=>{ (groups[p.group]=groups[p.group]||[]).push(p); });

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="mr-page-title">Users & permissions</h1>
        <p className="mr-page-sub">Admin creates accounts and grants fine-grained rights. Role defaults apply when permissions are left empty.</p>
      </div>
      {msg && <div className="alert alert-info text-sm py-2">{msg}</div>}

      <div className="card bg-base-200"><div className="card-body p-4 space-y-3">
        <h2 className="font-semibold text-sm">Create user</h2>
        <div className="grid sm:grid-cols-3 gap-2">
          <input className="input input-bordered input-sm" placeholder="Username" value={form.username} onChange={e=>setForm({...form, username:e.target.value})} />
          <input className="input input-bordered input-sm" type="password" placeholder="Password" value={form.password} onChange={e=>setForm({...form, password:e.target.value})} />
          <select className="select select-bordered select-sm" value={form.role} onChange={e=>setForm({...form, role:e.target.value})}>
            <option value="user">User</option>
            <option value="admin">Admin</option>
          </select>
        </div>
        <div className="space-y-2">
          {Object.entries(groups).map(([g, items])=>(
            <div key={g}>
              <div className="text-[10px] uppercase opacity-40 font-semibold mb-1">{g}</div>
              <div className="flex flex-wrap gap-2">
                {items.map(p=>(
                  <label key={p.id} className="label cursor-pointer gap-1 py-0">
                    <input type="checkbox" className="checkbox checkbox-xs"
                      checked={form.permissions.includes(p.id)}
                      onChange={e=>{
                        setForm(f=>({...f, permissions: e.target.checked
                          ? [...f.permissions, p.id]
                          : f.permissions.filter(x=>x!==p.id)}));
                      }} />
                    <span className="label-text text-xs">{p.label}</span>
                  </label>
                ))}
              </div>
            </div>
          ))}
        </div>
        <button className="btn btn-primary btn-sm w-fit" onClick={createUser}>Create</button>
      </div></div>

      <div className="space-y-2">
        <h2 className="font-semibold text-sm">Accounts</h2>
        {(users||[]).map(u=>(
          <div key={u.id} className="card bg-base-200"><div className="card-body p-3 gap-2">
            <div className="flex flex-wrap items-center gap-2 justify-between">
              <div>
                <span className="font-medium">{u.username}</span>
                <span className={"badge badge-sm ml-2 "+(u.role==="admin"?"badge-primary":"badge-ghost")}>{u.role}</span>
                {!u.is_active && <span className="badge badge-sm badge-error ml-1">disabled</span>}
              </div>
              <div className="flex gap-1">
                <button className="btn btn-xs" onClick={()=>setEditId(editId===u.id?null:u.id)}>Permissions</button>
                <button className="btn btn-xs btn-ghost text-error" onClick={()=>removeUser(u.id)}>Delete</button>
              </div>
            </div>
            {editId===u.id && (
              <div className="space-y-2 border-t border-base-content/10 pt-2">
                <select className="select select-bordered select-xs" value={u.role}
                  onChange={e=>{ u.role=e.target.value; setUsers([...users]); }}>
                  <option value="user">User</option>
                  <option value="admin">Admin</option>
                </select>
                <label className="label cursor-pointer gap-2 justify-start py-0">
                  <input type="checkbox" className="checkbox checkbox-xs" checked={u.is_active}
                    onChange={e=>{ u.is_active=e.target.checked; setUsers([...users]); }} />
                  <span className="text-xs">Active</span>
                </label>
                {Object.entries(groups).map(([g, items])=>(
                  <div key={g}>
                    <div className="text-[10px] uppercase opacity-40">{g}</div>
                    <div className="flex flex-wrap gap-2">
                      {items.map(p=>(
                        <label key={p.id} className="label cursor-pointer gap-1 py-0">
                          <input type="checkbox" className="checkbox checkbox-xs"
                            checked={(u.permissions||[]).includes(p.id)}
                            onChange={e=>{
                              const perms = new Set(u.permissions||[]);
                              if (e.target.checked) perms.add(p.id); else perms.delete(p.id);
                              u.permissions = [...perms];
                              setUsers([...users]);
                            }} />
                          <span className="label-text text-xs">{p.label}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                ))}
                <button className="btn btn-primary btn-xs" onClick={()=>saveUser(u)}>Save</button>
              </div>
            )}
          </div></div>
        ))}
        {!users.length && <p className="text-sm opacity-50">No DB users yet — env admin still works. Create the first account above.</p>}
      </div>
    </div>
  );
}


function PageContent({ page, movies, series, music=[], books=[], audiobooks=[], refreshMovies, refreshSeries, setPage, theme, setTheme, setMiniPlayer, enabledModules=['movies','tv'], setEnabledModules, advanced, setAdvanced }) {
  switch(page) {
    case 'widgets': return <OverhaulDashboardPage setPage={setPage} />;
    case 'dashboard':    return <><DashboardPage movies={movies} series={series} setPage={setPage} /><CollectionProgressWidget setPage={setPage} /></>;
    case 'comics':       return <ComicsPage setPage={setPage} />;
    case 'youtube':      return <YouTubePage />;
    case 'collections':  return <CollectionsPage />;
    case 'podcasts':     return <PodcastsPage />;
    case 'movies':       return <MoviesPage movies={movies} refreshMovies={refreshMovies} setMiniPlayer={setMiniPlayer} setPage={setPage} />;
    case 'tv':           return <TvPage series={series} refreshSeries={refreshSeries} setMiniPlayer={setMiniPlayer} setPage={setPage} />;
    case 'discover':     return <DiscoverPage movies={movies} series={series} refreshMovies={refreshMovies} refreshSeries={refreshSeries} />;
    case 'requests':     return <RequestsPage />;
    case 'import':       return <ImportPage movies={movies} series={series} />;
    case 'quality-lab': return <QualityLabPage />;
    case 'workers': return <div className="p-6 space-y-3 max-w-3xl"><h1 className="mr-page-title">Workers</h1><p className="text-sm opacity-60">Background schedulers: missing search, library watch, Jackett sync (6h), EPG refresh, cleanup, converter watch. Live progress is on Queue (SSE) and History.</p><div className="flex gap-2"><button className="btn btn-sm" onClick={()=>setPage&&setPage('queue')}>Queue</button><button className="btn btn-sm" onClick={()=>setPage&&setPage('activity')}>History</button><button className="btn btn-sm" onClick={()=>setPage&&setPage('logs')}>Logs</button></div></div>;
    case 'parity': return <div className='p-6'><h1 className='mr-page-title'>Stack parity</h1><p className='text-sm opacity-60'>mediaos replaces Sonarr/Radarr/Lidarr/Readarr/Bazarr/Prowlarr for day-to-day. Use Settings → Integrations for migrators, TRaSH, and Jackett sync.</p><ul className='list-disc ml-5 text-sm mt-3 space-y-1'><li>Movies + TV + quality + indexers ✅</li><li>Music artists/albums/tracks ✅</li><li>Books + audiobooks ✅</li><li>Subtitles wanted ✅</li><li>Cleanuparr-style cleaner ✅</li></ul></div>;
    case 'settings-hub': return <SettingsHubPage setPage={setPage} advanced={advanced} setAdvanced={setAdvanced} enabledModules={enabledModules} />;
    case 'settings-users': return <UsersPermissionsPage />;
    case 'modules': return <ModuleStorePage enabledModules={enabledModules} setEnabledModules={setEnabledModules} setPage={setPage} />;
    case 'settings-setup': return <SetupWizardPage onDone={()=>{ if(setPage) setPage('dashboard'); }} />;
    case 'setup': return <SetupWizardPage onDone={()=>{ if(setPage) setPage('dashboard'); }} />;
    case 'glossary': return <GlossaryPage />;
    case 'wanted-subtitles': return <WantedSubtitlesPage setPage={setPage} />;
    case 'wanted': return <WantedPage />;
    case 'queue':        return <QueuePage />;
    case 'logs': return <LogsPage />;
    case 'activity':     return <ActivityPage movies={movies} setPage={setPage} />;
    case 'settings-quality': return <QualityProfilesPage />;
    case 'settings-quality-matrix': return <QualityMatrixPage setPage={setPage} />;
    case 'settings-vpn':     return <VpnSettingsPage />;
    case 'settings-youtube': return <ConfigGroupPage group="youtube" title="YouTube / Login" Icon={Ic.Compass} description="Creator downloads, cookies login for age-restricted content, and SponsorBlock ad/sponsor removal. Changes apply immediately." />;
    case 'settings-themes': return <ThemesPage currentTheme={theme} setTheme={setTheme} />;
    case 'settings-indexers':  return <IndexersPage />;
    case 'settings-downloads': return <ConfigGroupPage group="downloads" title="Download Clients" Icon={Ic.Download} description="qBittorrent, SABnzbd, NZBGet — changes apply immediately, no restart." />;
    case 'settings-library':   return <ConfigGroupPage group="library" title="Library Storage" Icon={Ic.Folder} description="Library and downloads paths — changes apply immediately, no restart." />;
    case 'settings-indexers-cfg': return <ConfigGroupPage group="indexers" title="Indexers / Prowlarr / Jackett" Icon={Ic.Server} description="Prowlarr optional. Jackett sync + Cardigann builtins replace most indexer management." />;
    case 'settings-subtitles': return <SubtitlesSettingsPage setPage={setPage} />;
    case 'settings-cleanup': return <ConfigGroupPage group="cleanup" title="Queue cleaner" Icon={Ic.AlertTri} description="Cleanuparr-style strikes, stall detection, seed ratio." />;
    case 'settings-system':    return <ConfigGroupPage group="system" title="System" Icon={Ic.Server} description="Search, upgrades, and notification settings — changes apply immediately, no restart." />;
    case 'settings-metadata': return <ConfigGroupPage group="metadata" title="Metadata APIs" Icon={Ic.Compass} description="TMDb, TVDb, ComicVine, Trakt — changes apply immediately." />;
    case 'settings-debrid': return <ConfigGroupPage group="debrid" title="Debrid providers" Icon={Ic.Download} description="Real-Debrid, TorBox, AllDebrid, Premiumize, put.io, and more." />;
    
    case 'settings-usenet': return <ConfigGroupPage group="usenet" title="Usenet / NNTP" Icon={Ic.Server} description="NNTP for seekable streaming (SABnzbd/NZBGet are under Downloads)." />;
    case 'settings-auth': return <ConfigGroupPage group="auth" title="Authentication" Icon={Ic.Users} description="Admin login, API keys, ARR-compat key." />;
    case 'settings-sessions':  return <SessionsAdminPage />;
    case 'settings-integrations': return <IntegrationsPage />;
    case 'music':        return <MusicPage setPage={setPage} />;
    case 'books':        return <BooksPage setPage={setPage} />;
    case 'audiobooks':   return <AudiobooksPage setPage={setPage} />;
    case 'calendar':     return <CalendarPage />;
    case 'livetv': return <LiveTvPage />;
    case 'converter-dashboard': return <ConverterDashboard setPage={setPage} />;
    case 'converter-gpu': return <ConverterGpuWizard />;
    case 'converter-queue': return <ConverterQueue />;
    case 'converter-scan': return <ConverterScan />;
    case 'converter-presets': return <ConverterPresets />;
    case 'converter': return <ConverterDashboard />;
    case 'livetv_old':       return <LiveTvPage />;
    case 'smartlists':   return <SmartListsPage />;
    default:             return <><DashboardPage movies={movies} series={series} music={music} books={books} audiobooks={audiobooks} setPage={setPage} /><CollectionProgressWidget setPage={setPage} /></>;
  }
}

/* ── App Root ────────────────────────────────────────────────────────────── */
function MobileBottomNav({ page, setPage, enabledModules }) {
  const em = enabledModules || ['movies','tv'];
  const items = [
    { key:'dashboard', label:'Home', Icon:Ic.Home },
    { key:'movies', label:'Movies', Icon:Ic.Film },
    { key:'tv', label:'TV', Icon:Ic.Tv },
    ...(em.includes('music') ? [{ key:'music', label:'Music', Icon:Ic.Music }] : []),
    { key:'queue', label:'Queue', Icon:Ic.Download },
    { key:'activity', label:'History', Icon:Ic.Activity },
  ];
  return (
    <nav className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-base-200 border-t border-base-content/10 flex justify-around py-1 safe-bottom">
      {items.map(it=>(
        <button key={it.key} className={"flex flex-col items-center gap-0.5 px-2 py-1 text-[10px] "+(page===it.key?'text-primary':'opacity-60')}
          onClick={()=>setPage(it.key)}>
          <it.Icon /><span>{it.label}</span>
        </button>
      ))}
    </nav>
  );
}

function App() {
  const [splash, setSplash] = useState(true);
  const [page, setPage] = useState('dashboard');
  const [miniPlayer, setMiniPlayer] = useState(null); // {itemId,episodeId,videoId,path,title}
  const [advanced, setAdvanced] = useState(() => getAdvanced());
  const [enabledModules, setEnabledModules] = useState(['movies','tv']);
  useEffect(()=>{
    fetch('/api/modules/enabled').then(r=>r.json()).then(d=>{
      if (d.enabled && d.enabled.length) setEnabledModules(d.enabled);
    }).catch(()=>{});
  }, []);

  const [theme, setThemeState] = useState(storedTheme());
  const [mobileOpen, setMobileOpen] = useState(false);
  const [movies, setMovies] = useState([]);
  const [series, setSeries] = useState([]);
  const [music, setMusic] = useState([]);
  const [books, setBooks] = useState([]);
  const [audiobooks, setAudiobooks] = useState([]);
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
  const refreshMusic = useCallback(async()=>{
    try { setMusic(await api.music.list()); } catch(e){}
  }, []);
  const refreshBooks = useCallback(async()=>{
    try { setBooks(await api.books.list()); } catch(e){}
  }, []);
  const refreshAudiobooks = useCallback(async()=>{
    try { setAudiobooks(await api.audiobooks.list()); } catch(e){}
  }, []);
  const refreshRequests = useCallback(async()=>{
    try { setPendingRequests((await api.requests.list('pending')).length); } catch(e){}
  }, []);

  useEffect(()=>{
    // Live SSE updates (queue/activity/workers)
    let es;
    try {
      es = new EventSource('/api/sse/events');
      es.addEventListener('worker', ()=>{});
      es.addEventListener('activity', ()=>{});
      es.addEventListener('queue', ()=>{ refreshRequests(); });
    } catch(e) {}
    refreshMovies(); refreshSeries(); refreshMusic(); refreshBooks(); refreshAudiobooks(); refreshRequests();
    api.setup.status().then(s=>{ setSetupNeeded(!s.complete); setSetupChecked(true); if(!s.complete) setPage('setup'); }).catch(()=>setSetupChecked(true));
    const t = setTimeout(()=>setSplash(false), 1200);
    const i = setInterval(refreshRequests, 30000);
    return ()=>{ clearInterval(i); clearTimeout(t); try{ es && es.close(); }catch(e){} };
  }, []);

  const counts = {
    movies: movies.length,
    tv: series.length,
    music: music.length,
    books: books.length,
    audiobooks: audiobooks.length,
    requests: pendingRequests,
  };

  return (
    <>
    <SplashScreen visible={splash} />
    <div className="drawer lg:drawer-open min-h-screen mr-shell">
      <input id="mr-drawer" type="checkbox" className="drawer-toggle"
        checked={mobileOpen} onChange={e=>setMobileOpen(e.target.checked)} readOnly />

      <div className="drawer-content flex flex-col mr-main">
        <div className="navbar mr-topbar lg:hidden">
          <label htmlFor="mr-drawer" className="btn btn-ghost btn-square btn-sm" onClick={()=>setMobileOpen(!mobileOpen)}>
            <span className="w-5 h-5"><Ic.Menu /></span>
          </label>
          <div className="mr-brand-mark !w-7 !h-7">
            <LogoMark size={22} />
          </div>
          <span className="font-bold ml-1 tracking-tight bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">MediaOs</span>
        </div>
        <main className="flex-1 mr-content mos-page">
          <MobileBottomNav page={page} setPage={setPage} enabledModules={enabledModules} />
          <PageContent page={page} movies={movies} series={series}
            music={music} books={books} audiobooks={audiobooks}
            refreshMovies={refreshMovies} refreshSeries={refreshSeries}
            setPage={setPage} theme={theme} setTheme={setTheme} setMiniPlayer={setMiniPlayer}
            enabledModules={enabledModules} setEnabledModules={setEnabledModules}
            advanced={advanced} setAdvanced={setAdvanced} />
        </main>
        {miniPlayer && (
          <div className="fixed inset-x-0 bottom-16 lg:bottom-0 z-40 p-2 bg-base-300/95 border-t border-primary/40 backdrop-blur shadow-lg">
            <MediaPlayer
              compact
              itemId={miniPlayer.itemId}
              episodeId={miniPlayer.episodeId}
              videoId={miniPlayer.videoId}
              path={miniPlayer.path}
              title={miniPlayer.title}
              onClose={()=>setMiniPlayer(null)}
            />
          </div>
        )}
        <nav className="mr-bottom-nav lg:hidden">
          {[
            {k:'dashboard', label:'Home', Icon:Ic.Home},
            {k:'wanted', label:'Wanted', Icon:Ic.AlertTri},
            {k:'queue', label:'Queue', Icon:Ic.Download},
            {k:'discover', label:'Discover', Icon:Ic.Compass},
            {k:'widgets', label:'Widgets', Icon:Ic.Home},
            {k:'settings-hub', label:'Settings', Icon:Ic.Settings},
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
        <Sidebar page={page} setPage={p=>{setPage(p);}} counts={counts} onClose={()=>setMobileOpen(false)} advanced={advanced} enabledModules={enabledModules} />
      </div>
    </div>
    </>
  );
}

export function mount(el) {
  createRoot(el).render(<App />);
}

if (typeof document !== "undefined") {
  try { document.documentElement.setAttribute('data-theme', localStorage.getItem('mediaos-theme') || 'mediaos'); } catch (e) {}

  const root = document.getElementById("root");
  if (root) mount(root);
}
