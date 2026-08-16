import React, { useState, useEffect, useCallback, useRef } from "react";
import Ic, { Icons, P } from "../icons.jsx";
import { getToken, setToken, getAdvanced, setAdvancedFlag, AUTH_TOKEN_KEY } from "../storage.js";
import { api, TMDB, adultFetch } from "../api.js";
import { PageChrome, PosterTile, LibraryModuleShell, MediaDetailShell, LibraryLegend, LibraryHeader, MediaCard, StatusBadgeStack, libraryStatuses, CollectionProgressWidget, TeachEmpty, AddModal } from "../components/ui.jsx";
import { InteractiveResultsPanel, InteractiveResultsTable, MediaPlayer, HlsVideo } from "../components/media.jsx";

function ConverterGpuWizard() {
  const [hw, setHw] = useState(null);
  const [copied, setCopied] = useState('');
  const load = () => fetch('/api/converter/hw').then(r=>r.json()).then(setHw).catch(()=>setHw(null));
  useEffect(()=>{ load(); }, []);
  const copy = (text, id) => {
    navigator.clipboard?.writeText(text).then(()=>{ setCopied(id); setTimeout(()=>setCopied(''), 2000); }).catch(e => { try { setMsg(String(e.message||e)); } catch(_) { console.warn(e); } });
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
          <button type="button" className="btn btn-sm btn-ghost w-fit" onClick={load}>Re-detect</button>
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
                <button type="button" className="btn btn-xs absolute top-2 right-2" onClick={()=>copy(p.compose, id)}>
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
    fetch('/api/converter/stats').then(r=>r.json()).then(setStats).catch(e => { try { setMsg(String(e.message||e)); } catch(_) { console.warn(e); } });
    fetch('/api/converter/jobs?limit=8').then(r=>r.json()).then(setJobs).catch(()=>[]);
    fetch('/api/converter/hw').then(r=>r.json()).then(setHw).catch(e => { try { setMsg(String(e.message||e)); } catch(_) { console.warn(e); } });
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
          {!jobs.length && (
            <tr><td colSpan={9} className="text-sm opacity-50 py-8 text-center">No conversion jobs — scan a library folder or enqueue a file. Failed jobs can be selected and retried.</td></tr>
          )}
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
      <button type="button" className="btn btn-sm btn-primary" onClick={async()=>{ await fetch('/api/converter/worker/tick',{method:'POST'}); load(); }}>Run worker tick</button>
    </div>
  );
}

function ConverterQueue() {
  const [jobs, setJobs] = useState([]);
  const [filter, setFilter] = useState('');
  const [jobSel, setJobSel] = useState({});
  const jobSelIds = Object.keys(jobSel);
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
          <button type="button" className="btn btn-sm" onClick={async()=>{ await fetch('/api/converter/jobs/clear?status=done',{method:'POST'}); load(); }}>Clear done</button>
          {jobSelIds.length > 0 && (
            <>
              <span className="text-xs opacity-60 self-center">{jobSelIds.length} selected</span>
              <button type="button" className="btn btn-sm btn-primary" onClick={async()=>{
                for (const id of jobSelIds) {
                  await fetch('/api/converter/jobs/'+id+'/retry',{method:'POST'}).catch(()=>{});
                }
                setJobSel({}); load();
              }}>Retry selected</button>
              <button type="button" className="btn btn-sm btn-ghost" onClick={()=>setJobSel({})}>Clear selection</button>
            </>
          )}
          <button type="button" className="btn btn-sm btn-primary" onClick={async()=>{ await fetch('/api/converter/worker/tick',{method:'POST'}); load(); }}>Process next</button>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="table table-sm">
          <thead><tr><th className="w-8"></th><th>ID</th><th>Source</th><th>Preset</th><th>Codec</th><th>Status</th><th>Progress</th><th>Size</th><th></th></tr></thead>
          <tbody>
            {!jobs.length && (
            <tr><td colSpan={8} className="text-sm opacity-50 py-8 text-center">No conversion jobs — scan a library folder or enqueue a file. Failed jobs can be selected and retried.</td></tr>
          )}
          {jobs.map(j=>(
              <tr key={j.id}>
                <td>
                  <input type="checkbox" className="checkbox checkbox-xs checkbox-primary" checked={!!jobSel[j.id]}
                    onChange={e=>{ setJobSel(prev=>{ const n={...prev}; if(e.target.checked) n[j.id]=true; else delete n[j.id]; return n; }); }} />
                </td>
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
                    <button type="button" className="btn btn-xs" onClick={async()=>{ await fetch('/api/converter/jobs/'+j.id+'/cancel',{method:'POST'}); load(); }}>Cancel</button>
                  )}
                  {j.status!=='running' && (
                    <button type="button" className="btn btn-xs btn-ghost text-error" onClick={async()=>{ if(!window.confirm('Delete this job?')) return; await fetch('/api/converter/jobs/'+j.id,{method:'DELETE'}); load(); }}>Del</button>
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
          <button type="button" className="btn btn-sm btn-primary" disabled={busy||!path.trim()} onClick={add}>Add mapping</button>
        </div>
        <div className="space-y-1">
          {folders.map(f=>(
            <div key={f.id} className="flex flex-wrap items-center gap-2 text-sm p-2 bg-base-300 rounded">
              <span className="font-mono text-xs flex-1 min-w-[8rem] truncate">{f.path}</span>
              <span className="badge badge-xs">{(presets||[]).find(p=>p.id===f.preset_id)?.name || 'default'}</span>
              <span className="text-xs opacity-50">last +{f.last_queued||0}</span>
              <button type="button" className="btn btn-xs" onClick={async()=>{
                await fetch('/api/converter/watch-folders/'+f.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...f, enabled:!f.enabled})});
                load();
              }}>{f.enabled?'On':'Off'}</button>
              <button type="button" className="btn btn-xs btn-ghost text-error" onClick={async()=>{ if(!window.confirm('Remove this watch folder?')) return; await fetch('/api/converter/watch-folders/'+f.id,{method:'DELETE'}); load(); }}>Del</button>
            </div>
          ))}
          {!folders.length && <p className="text-xs opacity-50">No mappings yet — add paths above.</p>}
        </div>
        <button type="button" className="btn btn-sm btn-secondary" disabled={busy} onClick={async()=>{
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
  useEffect(()=>{ fetch('/api/converter/presets').then(r=>r.json()).then(p=>{ setPresets(p); const d=p.find(x=>x.is_default); if(d) setPresetId(String(d.id)); }).catch(e => { try { setMsg(String(e.message||e)); } catch(_) { console.warn(e); } }); }, []);
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
          <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={scan}>{busy?'Scanning…':'Scan all libraries'}</button>
        </div>
      </div>
      <div className="card bg-base-200">
        <div className="card-body gap-3">
          <h2 className="font-semibold text-sm">Enqueue single file</h2>
          <input className="input input-bordered input-sm font-mono text-xs" placeholder="/movies/Film (2020)/Film.mkv" value={path} onChange={e=>setPath(e.target.value)} />
          <button type="button" className="btn btn-sm" disabled={busy||!path.trim()} onClick={enqueue}>Enqueue path</button>
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




export { ConverterGpuWizard, ConverterDashboard, ConverterQueue, WatchFolderMapper, ConverterScan, ConverterPresets };
