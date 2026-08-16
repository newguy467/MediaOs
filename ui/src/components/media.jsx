import React, { useState, useEffect, useCallback, useRef } from "react";
import Ic, { Icons, P } from "../icons.jsx";
import { getToken, setToken, getAdvanced, setAdvancedFlag, AUTH_TOKEN_KEY } from "../storage.js";
import { api } from "../api.js";

function useHlsVideo(videoRef, src, { enabled = true } = {}) {
  useEffect(() => {
    const el = videoRef && videoRef.current;
    if (!el || !src || !enabled) return undefined;
    let hls = null;
    const isHls = /\.m3u8(\?|$)/i.test(src) || src.includes("m3u8");
    const native = el.canPlayType("application/vnd.apple.mpegurl");
    if (isHls && !native) {
      import("hls.js").then((mod) => {
        const Hls = mod.default;
        if (!Hls.isSupported()) {
          el.src = src;
          return;
        }
        hls = new Hls({ enableWorker: true, lowLatencyMode: true });
        hls.loadSource(src);
        hls.attachMedia(el);
        hls.on(Hls.Events.ERROR, (_, data) => {
          if (data?.fatal) {
            try { hls.destroy(); } catch (_) {}
            el.src = src;
          }
        });
      }).catch(() => { el.src = src; });
    } else {
      el.src = src;
    }
    return () => {
      try { if (hls) hls.destroy(); } catch (_) {}
    };
  }, [src, enabled]);
}

function HlsVideo({ src, className, autoPlay, controls, poster }) {
  const ref = useRef(null);
  useHlsVideo(ref, src);
  return (
    <video
      ref={ref}
      className={className}
      controls={controls !== false}
      autoPlay={!!autoPlay}
      playsInline
      poster={poster}
    />
  );
}


/** Prefer download_url, then magnet/link for grab/stream payloads. */
function releaseDownloadUrl(r) {
  if (!r || typeof r !== "object") return "";
  return (r.download_url || r.magnet || r.magnetUrl || r.link || r.uri || "").trim();
}

function grabPayload(r) {
  return {
    title: r.title || r.name || "release",
    download_url: releaseDownloadUrl(r),
    indexer: r.indexer || null,
    size: r.size ?? r.size_bytes ?? null,
    seeders: r.seeders ?? null,
    protocol: r.protocol || "torrent",
    score: r.score ?? r._score ?? null,
    quality_score: r.score ?? r._score ?? null,
    info_hash: r.info_hash || null,
  };
}

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
      await fetch('/api/blocklist', {
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
                  <td className="tabular-nums font-mono text-xs">
                      {r.score ?? '—'}
                      {(r.score_breakdown || r._score_breakdown || r.quality_breakdown) && (
                        <details className="text-[10px] opacity-70">
                          <summary className="cursor-pointer">Explain</summary>
                          <pre className="whitespace-pre-wrap max-w-[14rem]">{typeof (r.score_breakdown||r._score_breakdown||r.quality_breakdown)==='string'
                            ? (r.score_breakdown||r._score_breakdown||r.quality_breakdown)
                            : JSON.stringify(r.score_breakdown||r._score_breakdown||r.quality_breakdown, null, 1)}</pre>
                        </details>
                      )}
                    </td>
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
                    {r.rejected && (r.rejections||[]).length > 0 && (
                      <details className="inline-block ml-1 text-[10px] opacity-70">
                        <summary className="cursor-pointer">Why</summary>
                        <ul className="list-disc pl-3 max-w-[12rem]">{(r.rejections||[]).map((x,i)=><li key={i}>{x}</li>)}</ul>
                      </details>
                    )}
                    {(r.matched_formats||[]).slice(0,2).map(f=><span key={f} className="badge badge-xs badge-ghost">{f}</span>)}
                  </td>
                  <td className="whitespace-nowrap">
                    {!r.rejected && (r.download_url || r.magnet || r.link) && (
                      <button type="button" className="btn btn-xs" disabled={busy} onClick={()=>onGrab(r)}>Grab</button>
                    )}
                    {!r.rejected && (r.download_url || r.magnet || r.stream_url) && (
                      <button type="button" className="btn btn-accent btn-xs mr-1" disabled={busy}
                        title="Prefer stream / .strm without downloading"
                        onClick={async ()=>{
                          try {
                            const url = r.stream_url || r.download_url || r.magnet;
                            const res = await fetch('/api/overhaul/streams', {
                              method: 'POST',
                              headers: {'Content-Type':'application/json'},
                              body: JSON.stringify({
                                title: r.title,
                                stream_url: url,
                                media_item_id: mediaItemId || null,
                                provider: r.indexer || 'interactive',
                              }),
                            });
                            if (!res.ok) throw new Error((await res.json().catch(()=>({}))).detail || res.statusText);
                            setMsg('Stream link added: ' + (r.title||''));
                          } catch(e) { setMsg(String(e.message||e)); }
                        }}>Stream</button>
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
  // Built-in library player — direct or ffmpeg transcode

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
            {introChapter && <button type="button" className="btn btn-xs btn-secondary" onClick={skipIntro}>Skip intro</button>}
            {outroChapter && <button type="button" className="btn btn-xs btn-ghost" onClick={skipOutro}>Skip to outro</button>}
            <button type="button" className={"btn btn-xs " + (mode==='direct'?'btn-primary':'btn-ghost')} onClick={()=>setMode('direct')}>Direct</button>
            <button type="button" className={"btn btn-xs " + (mode==='transcode'?'btn-primary':'btn-ghost')} onClick={()=>setMode('transcode')}>Transcode</button>
            {onClose && <button type="button" className="btn btn-xs btn-ghost" onClick={onClose}>Close</button>}
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
              <button type="button" key={i} className="btn btn-xs btn-ghost border border-base-content/10" onClick={()=>seekTo(c.start)} title={c.title}>
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


function InteractiveResultsTable({ results, loading, busy, onGrab, onClose }) {
  if (!loading && !results) return null;
  return (
    <div className="card bg-base-200 shadow-sm">
      <div className="card-body p-4 gap-2">
        <div className="flex items-center gap-2">
          <h2 className="font-semibold text-sm flex-1">Interactive search</h2>
          {onClose && <button type="button" className="btn btn-xs btn-ghost" onClick={onClose}>Close</button>}
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
                    <td className="whitespace-nowrap">
                      <button type="button" className="btn btn-xs btn-primary" disabled={busy} onClick={()=>onGrab(r)}>Grab</button>
                      <button type="button" className="btn btn-xs btn-accent ml-1" disabled={busy} title="Add as stream (.strm)"
                        onClick={async ()=>{
                          try {
                            const mediaItemId = r.media_item_id || r.item_id || null;
                            await fetch('/api/overhaul/streams', {
                              method:'POST', headers:{'Content-Type':'application/json'},
                              body: JSON.stringify({
                                title: r.title || 'stream',
                                stream_url: r.download_url || r.magnet || r.link || '',
                                media_item_id: mediaItemId,
                                provider: r.indexer || 'interactive',
                              })
                            });
                          } catch(e) { console.warn(e); }
                        }}>Stream</button>
                    </td>
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



export {
  releaseDownloadUrl, grabPayload,
  useHlsVideo, HlsVideo, InteractiveResultsPanel, InteractiveResultsTable,
  playbackKey, loadResume, saveResume, MediaPlayer,
};
