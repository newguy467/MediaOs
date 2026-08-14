import React, { useState, useEffect, useCallback, useRef } from "react";
import Ic, { Icons, P } from "../icons.jsx";
import { getToken, setToken, getAdvanced, setAdvancedFlag, AUTH_TOKEN_KEY } from "../storage.js";
import { api, TMDB, adultFetch } from "../api.js";
import { PageChrome, PosterTile, LibraryModuleShell, MediaDetailShell, LibraryLegend, LibraryHeader, MediaCard, StatusBadgeStack, libraryStatuses, CollectionProgressWidget, TeachEmpty, AddModal } from "../components/ui.jsx";
import { InteractiveResultsPanel, InteractiveResultsTable, MediaPlayer, HlsVideo } from "../components/media.jsx";

function EpgTimeline() {
  const [grid, setGrid] = useState(null);
  const [hours, setHours] = useState(4);
  const [group, setGroup] = useState('');
  const [loading, setLoading] = useState(true);
  const [groups, setGroups] = useState([]);
  const [mode, setMode] = useState('timeline'); // timeline | now | recordings | rules
  const [recs, setRecs] = useState([]);
  const [rules, setRules] = useState([]);
  const [ruleForm, setRuleForm] = useState({ title_match: '', match_mode: 'contains', keep_episodes: 0 });
  const [msg, setMsg] = useState('');
  const loadRecs = () => fetch('/api/livetv/recordings').then(r=>r.json()).then(d=>setRecs(d.items||d||[])).catch(e => { try { setMsg(String(e.message||e)); } catch(_) { console.warn(e); } });
  const loadRules = () => fetch('/api/livetv/series-rules').then(r=>r.json()).then(d=>setRules(d.items||[])).catch(e => { try { setMsg(String(e.message||e)); } catch(_) { console.warn(e); } });
  const recordProg = async (ch, prog, allowConflict=false) => {
    try {
      const res = await fetch('/api/livetv/epg/record', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({
          channel_id: ch.id,
          title: prog.title || 'EPG Recording',
          subtitle: prog.desc || prog.subtitle,
          tvg_id: ch.tvg_id || ch.epg_tvg_id,
          starts_at: prog.start || prog.starts_at,
          ends_at: prog.stop || prog.ends_at,
          stream_url: ch.stream_url,
          allow_conflict: allowConflict,
        })
      });
      const r = await res.json().catch(()=>({}));
      if (!res.ok || r.detail) {
        const err = r.detail || r.error || JSON.stringify(r);
        if (String(err).toLowerCase().includes('conflict') || String(err).toLowerCase().includes('multi-tuner')) {
          if (window.confirm(String(err) + '\n\nOverride and schedule anyway?')) {
            return recordProg(ch, prog, true);
          }
        }
        setMsg(String(err));
        return;
      }
      setMsg(r.ok ? `Scheduled: ${r.title} (${r.status})` : JSON.stringify(r));
      loadRecs();
    } catch(e) { setMsg(String(e.message||e)); }
  };

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
          <button type="button" className="btn btn-xs" onClick={load}>Refresh</button>
          <button type="button" className="btn btn-xs btn-ghost" onClick={async()=>{ await fetch('/api/livetv/epg/refresh',{method:'POST'}).catch(e => { try { setMsg(String(e.message||e)); } catch(_) { console.warn(e); } }); load(); }}>Reload XMLTV</button>
          <button type="button" className={"btn btn-xs "+(mode==='recordings'?'btn-primary':'')} onClick={()=>{ setMode('recordings'); loadRecs(); }}>Recordings</button>
          <button type="button" className={"btn btn-xs "+(mode==='rules'?'btn-primary':'')} onClick={()=>{ setMode('rules'); loadRules(); }}>Series rules</button>
        </div>
        {msg && <div className="alert alert-info text-xs py-1">{msg}</div>}
      </div>
      {mode==='rules' ? (
        <div className="space-y-3">
          <p className="text-xs opacity-60">Auto-record matching EPG titles (series-record). Applied on schedule and via Apply.</p>
          <div className="flex flex-wrap gap-2 items-end">
            <label className="form-control"><span className="label-text text-xs">Title match</span>
              <input className="input input-bordered input-sm" value={ruleForm.title_match} onChange={e=>setRuleForm(f=>({...f,title_match:e.target.value}))} placeholder="Show name" /></label>
            <label className="form-control"><span className="label-text text-xs">Mode</span>
              <select className="select select-bordered select-sm" value={ruleForm.match_mode} onChange={e=>setRuleForm(f=>({...f,match_mode:e.target.value}))}>
                <option value="contains">contains</option>
                <option value="exact">exact</option>
                <option value="startswith">startswith</option>
              </select></label>
            <label className="form-control"><span className="label-text text-xs">Keep N</span>
              <input type="number" className="input input-bordered input-sm w-20" value={ruleForm.keep_episodes} onChange={e=>setRuleForm(f=>({...f,keep_episodes:Number(e.target.value)||0}))} /></label>
            <button type="button" className="btn btn-sm btn-primary" onClick={async()=>{
              if(!ruleForm.title_match.trim()) return;
              await fetch('/api/livetv/series-rules',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(ruleForm)});
              setRuleForm({title_match:'',match_mode:'contains',keep_episodes:0});
              loadRules();
            }}>Add rule</button>
            <button type="button" className="btn btn-sm" onClick={loadRules}>Refresh</button>
          </div>
          <table className="table table-xs">
            <thead><tr><th>Match</th><th>Mode</th><th>Keep</th><th>Priority</th><th></th></tr></thead>
            <tbody>
              {(rules||[]).map(r=>(
                <tr key={r.id}>
                  <td className="text-xs">{r.title_match}</td>
                  <td className="text-xs">{r.match_mode}</td>
                  <td className="text-xs">{r.keep_episodes||'∞'}</td>
                  <td className="text-xs">{r.priority}</td>
                  <td><button type="button" className="btn btn-ghost btn-xs text-error" onClick={async()=>{ await fetch('/api/livetv/series-rules/'+r.id,{method:'DELETE'}); loadRules(); }}>Delete</button></td>
                </tr>
              ))}
            </tbody>
          </table>
          {!rules.length && <p className="text-sm opacity-50">No series rules yet.</p>}
        </div>
      ) : mode==='recordings' ? (
        <div className="space-y-2">
          <p className="text-xs opacity-60">DVR jobs from EPG click-to-record (ffmpeg copy when on-air). Conflicts prompt for override.</p>
          <button type="button" className="btn btn-xs btn-ghost" onClick={loadRecs}>Refresh</button>
          <table className="table table-xs">
            <thead><tr><th>Title</th><th>Channel</th><th>Start</th><th>Status</th><th></th></tr></thead>
            <tbody>
              {(recs||[]).map(r=>(
                <tr key={r.id}>
                  <td className="text-xs">{r.title}</td>
                  <td className="text-xs opacity-60">{r.channel_name||r.channel_id||'—'}</td>
                  <td className="text-xs opacity-50">{(r.starts_at||'').slice(0,19)}</td>
                  <td><span className={"badge badge-xs "+(r.status==='completed'?'badge-success':r.status==='failed'?'badge-error':r.status==='recording'?'badge-warning':'badge-ghost')}>{r.status}</span></td>
                  <td><button type="button" className="btn btn-ghost btn-xs text-error" onClick={async()=>{ await fetch('/api/livetv/recordings/'+r.id,{method:'DELETE'}); loadRecs(); }}>Cancel</button></td>
                </tr>
              ))}
            </tbody>
          </table>
          {!recs.length && <p className="text-sm opacity-50">No recordings yet — click a programme on the timeline.</p>}
        </div>
      ) : loading && !grid ? <span className="loading loading-spinner"/> : mode==='now' ? (
        <div className="overflow-auto max-h-[70vh] border border-base-content/10 rounded-lg">
          <table className="table table-xs table-pin-rows">
            <thead><tr className="bg-base-300"><th>Channel</th><th>Now</th><th>Next</th></tr></thead>
            <tbody>
              {channels.map(ch=>(
                <tr key={ch.id} className="hover">
                  <td className="text-xs font-medium">{ch.name}</td>
                  <td className="text-xs">{ch.now?.title||'—'}
                    {ch.now?.title && <button type="button" className="btn btn-ghost btn-xs ml-1" onClick={()=>recordProg(ch, {title: ch.now.title, start: ch.now.start, stop: ch.now.stop})}>Rec</button>}
                  </td>
                  <td className="text-xs opacity-70">{ch.next?.title||'—'}
                    {ch.next?.title && <button type="button" className="btn btn-ghost btn-xs ml-1" onClick={()=>recordProg(ch, {title: ch.next.title, start: ch.next.start, stop: ch.next.stop})}>Rec</button>}
                  </td>
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
                  <div key={i}
                    className="absolute top-1 bottom-1 rounded bg-primary/20 border border-primary/30 px-1 overflow-hidden cursor-pointer hover:bg-primary/40 hover:ring-1 hover:ring-accent"
                    style={blockStyle(prog)}
                    title={(prog.title||'')+' '+(prog.start||'')+' — click to record'}
                    onClick={()=>recordProg(ch, prog)}
                  >
                    <div className="text-[10px] font-medium truncate leading-tight pt-0.5">{prog.title||'Programme'}</div>
                    <div className="text-[9px] opacity-60 truncate">Rec</div>
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




function VirtualChannelsPanel({ setMsg }) {
  const [list, setList] = useState([]);
  const [nowNext, setNowNext] = useState({});
  const [form, setForm] = useState({
    number: '', name: '', media_types: ['movie'], genre_filter: '', title_filter: '',
    randomize: true, repeat_protection_days: 7, prime_time_movies: false, group_title: 'Personal Media',
  });
  const [busyId, setBusyId] = useState(null);

  const load = () => {
    fetch('/api/livetv/virtual/channels').then(r=>r.json()).then(rows=>{
      setList(rows||[]);
      (rows||[]).forEach(ch => {
        fetch(`/api/livetv/virtual/channels/${ch.id}/now-next`).then(r=>r.json())
          .then(nn => setNowNext(prev => ({...prev, [ch.id]: nn}))).catch(e => { try { setMsg(String(e.message||e)); } catch(_) { console.warn(e); } });
      });
    }).catch(()=>setList([]));
  };
  useEffect(() => { load(); const i = setInterval(load, 60000); return () => clearInterval(i); }, []);

  const toggleType = (t) => setForm(f => ({
    ...f,
    media_types: f.media_types.includes(t) ? f.media_types.filter(x=>x!==t) : [...f.media_types, t],
  }));

  const create = async () => {
    if (!form.number || !form.name) { setMsg('Channel number and name are required'); return; }
    if (!form.media_types.length) { setMsg('Pick at least one content type (Movies / TV Episodes)'); return; }
    try {
      const body = { ...form, number: parseInt(form.number, 10), repeat_protection_days: parseInt(form.repeat_protection_days, 10) || 0 };
      const res = await fetch('/api/livetv/virtual/channels', {
        method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body),
      });
      const r = await res.json();
      if (!res.ok) { setMsg(r.detail || 'Failed to create channel'); return; }
      setMsg(`Created channel ${r.number} — ${r.name}. Building schedule…`);
      setForm({ number: '', name: '', media_types: ['movie'], genre_filter: '', title_filter: '', randomize: true, repeat_protection_days: 7, prime_time_movies: false, group_title: 'Personal Media' });
      load();
    } catch(e) { setMsg(String(e.message||e)); }
  };

  const toggleEnabled = async (ch) => {
    await fetch(`/api/livetv/virtual/channels/${ch.id}`, { method:'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ enabled: !ch.enabled }) });
    load();
  };

  const rebuild = async (ch) => {
    setBusyId(ch.id);
    try {
      const r = await fetch(`/api/livetv/virtual/channels/${ch.id}/rebuild`, { method:'POST' }).then(x=>x.json());
      setMsg(`${ch.name}: schedule +${r.schedule?.added ?? 0} · stream ${r.stream?.ok ? 'started' : (r.stream?.error||'not started')}`);
      load();
    } catch(e) { setMsg(String(e.message||e)); } finally { setBusyId(null); }
  };

  const remove = async (ch) => {
    if (!window.confirm(`Delete virtual channel "${ch.name}"? This removes its schedule and HLS files.`)) return;
    await fetch(`/api/livetv/virtual/channels/${ch.id}`, { method:'DELETE' });
    load();
  };

  return (
    <div className="space-y-4">
      <div className="card bg-base-200 border border-base-content/10">
        <div className="card-body p-3 gap-2 text-sm">
          <div className="font-semibold text-sm">Channel Builder</div>
          <p className="text-xs opacity-60">Turns your own movie/TV library into a 24/7 channel with a continuously-generated schedule. It's automatically merged into the unified playlist/EPG Jellyfin already pulls from.</p>
          <div className="flex flex-wrap gap-2 items-center">
            <input className="input input-bordered input-sm w-24" type="number" placeholder="No." value={form.number} onChange={e=>setForm(f=>({...f, number: e.target.value}))} />
            <input className="input input-bordered input-sm flex-1 min-w-[12rem]" placeholder="Channel name (e.g. Randall Action)" value={form.name} onChange={e=>setForm(f=>({...f, name: e.target.value}))} />
            <input className="input input-bordered input-sm w-40" placeholder="Group (e.g. Personal Media)" value={form.group_title} onChange={e=>setForm(f=>({...f, group_title: e.target.value}))} />
          </div>
          <div className="flex flex-wrap gap-4 items-center">
            <label className="label cursor-pointer gap-1 p-0"><input type="checkbox" className="checkbox checkbox-xs" checked={form.media_types.includes('movie')} onChange={()=>toggleType('movie')} /> Movies</label>
            <label className="label cursor-pointer gap-1 p-0"><input type="checkbox" className="checkbox checkbox-xs" checked={form.media_types.includes('tv')} onChange={()=>toggleType('tv')} /> TV Episodes</label>
            <label className="label cursor-pointer gap-1 p-0"><input type="checkbox" className="checkbox checkbox-xs" checked={form.randomize} onChange={e=>setForm(f=>({...f, randomize: e.target.checked}))} /> Randomize</label>
            <label className="label cursor-pointer gap-1 p-0"><input type="checkbox" className="checkbox checkbox-xs" checked={form.prime_time_movies} onChange={e=>setForm(f=>({...f, prime_time_movies: e.target.checked}))} /> Prime-time movies</label>
          </div>
          <div className="flex flex-wrap gap-2 items-center">
            <input className="input input-bordered input-sm w-48" placeholder="Genre filter (matches title/overview, comma = OR)" value={form.genre_filter} onChange={e=>setForm(f=>({...f, genre_filter: e.target.value}))} />
            <input className="input input-bordered input-sm w-48" placeholder="Title contains…" value={form.title_filter} onChange={e=>setForm(f=>({...f, title_filter: e.target.value}))} />
            <label className="text-xs opacity-70 flex items-center gap-1">Don't repeat for
              <input className="input input-bordered input-xs w-14" type="number" value={form.repeat_protection_days} onChange={e=>setForm(f=>({...f, repeat_protection_days: e.target.value}))} /> days
            </label>
            <button type="button" className="btn btn-sm btn-primary" onClick={create}>Create channel</button>
          </div>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="table table-xs">
          <thead><tr><th>#</th><th>Name</th><th>Content</th><th>Now playing</th><th>Stream</th><th></th></tr></thead>
          <tbody>
            {list.map(ch => {
              const nn = nowNext[ch.id];
              return (
                <tr key={ch.id}>
                  <td className="font-mono">{ch.number}</td>
                  <td className="font-medium">{ch.name}<div className="text-[10px] opacity-50">{ch.group_title}</div></td>
                  <td className="text-xs opacity-70">{(ch.media_types||[]).join(', ')}{ch.genre_filter ? ` · ${ch.genre_filter}` : ''}</td>
                  <td className="text-xs opacity-80">{nn?.now?.title || '—'}</td>
                  <td>
                    <span className={'badge badge-xs ' + (ch.stream_status==='running' ? 'badge-success' : ch.stream_status==='error' ? 'badge-error' : 'badge-ghost')}>
                      {ch.stream_status}{ch.stream_error ? `: ${ch.stream_error}` : ''}
                    </span>
                  </td>
                  <td className="flex gap-1 justify-end">
                    <button type="button" className="btn btn-2xs" disabled={busyId===ch.id} onClick={()=>rebuild(ch)}>Rebuild</button>
                    <button type="button" className="btn btn-2xs" onClick={()=>toggleEnabled(ch)}>{ch.enabled ? 'Disable' : 'Enable'}</button>
                    <button type="button" className="btn btn-2xs btn-error btn-outline" onClick={()=>remove(ch)}>Delete</button>
                  </td>
                </tr>
              );
            })}
            {!list.length && <tr><td colSpan={6} className="text-xs opacity-50 text-center py-4">No virtual channels yet — build one above from your movie or TV library.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function LiveTvPage() {
  const advanced = typeof getAdvanced === 'function' ? !!getAdvanced() : true;
  // jellyfin pipeline panel below
  const [tvTab, setTvTab] = useState('channels'); // channels | epg | nownext | virtual
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
    // Editor list includes disabled channels for lineup management
    (api.livetv.channelsEditor ? api.livetv.channelsEditor() : api.livetv.channels(q))
      .then(setChannels).catch(()=>api.livetv.channels(q).then(setChannels).catch(()=>[]));
    fetch('/api/overhaul/livetv/now-next').then(r=>r.json()).then(setLineup).catch(()=>null);
  };
  const toggleChannel = async (c, enabled) => {
    try {
      await api.livetv.patchChannel(c.id, { enabled });
      setChannels(prev => (prev||[]).map(x => x.id===c.id ? {...x, enabled} : x));
    } catch(e) { setMsg(String(e.message||e)); }
  };
  const bulkEnable = async (enabled) => {
    const ids = (filtered||[]).map(c=>c.id);
    if (!ids.length) return;
    try {
      await api.livetv.bulkChannels({ channel_ids: ids, enabled });
      setMsg((enabled?'Enabled':'Disabled')+' '+ids.length+' channels');
      load();
    } catch(e) { setMsg(String(e.message||e)); }
  };
  const reorderSave = async (orderedIds) => {
    try {
      await fetch('/api/livetv/channels/reorder', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ channel_ids: orderedIds }) });
      setMsg('Order saved'); load();
    } catch(e) { setMsg(String(e.message||e)); }
  };
  const moveChannel = (id, dir) => {
    const list = [...(filtered||[])];
    const idx = list.findIndex(c=>c.id===id);
    if (idx<0) return;
    const j = idx + dir;
    if (j<0 || j>=list.length) return;
    const tmp = list[idx]; list[idx]=list[j]; list[j]=tmp;
    reorderSave(list.map(c=>c.id));
  };
  const [selected, setSelected] = useState(() => new Set());
  const [bulkGroup, setBulkGroup] = useState('');
  const [editCh, setEditCh] = useState(null);
  const [editForm, setEditForm] = useState({ name: '', group_title: '', logo: '', tvg_id: '' });
  const toggleSelect = (id) => {
    setSelected(prev => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id); else n.add(id);
      return n;
    });
  };
  const selectAllFiltered = () => {
    setSelected(new Set((filtered||[]).map(c => c.id)));
  };
  const clearSelection = () => setSelected(new Set());
  const bulkSetGroup = async () => {
    const ids = [...selected];
    if (!ids.length) return;
    const group_title = (bulkGroup || '').trim() || null;
    try {
      await api.livetv.bulkChannels({ channel_ids: ids, group_title });
      setMsg(`Set group "${group_title || '(none)'}" on ${ids.length} channels`);
      clearSelection();
      load();
    } catch (e) { setMsg(String(e.message || e)); }
  };
  const openEdit = (c) => {
    setEditCh(c);
    setEditForm({
      name: c.name || '',
      group_title: c.group_title || c.group || '',
      logo: c.logo || '',
      tvg_id: c.tvg_id || c.epg_tvg_id || '',
    });
  };
  const saveEdit = async () => {
    if (!editCh) return;
    try {
      const body = {
        name: editForm.name.trim() || editCh.name,
        group_title: editForm.group_title.trim() || null,
        logo: editForm.logo.trim() || null,
        tvg_id: editForm.tvg_id.trim() || null,
      };
      await api.livetv.patchChannel(editCh.id, body);
      setMsg('Updated ' + body.name);
      setEditCh(null);
      load();
    } catch (e) { setMsg(String(e.message || e)); }
  };
  useEffect(() => { load(); }, []);
  const groups = [...new Set((channels||[]).map(c=>c.group_title||c.group).filter(Boolean))].sort();
  const filtered = (channels||[]).filter(c => {
    if (groupFilter && (c.group_title||c.group) !== groupFilter) return false;
    if (q && !(c.name||'').toLowerCase().includes(q.toLowerCase())) return false;
    return true;
  });
  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="mr-page-title">Live TV / IPTV</h1>
        <p className="text-sm text-base-content/50">M3U · Xtream · EPG · health · Jellyfin · full IPTV</p>
        <p className="text-xs opacity-50 mt-1">Lineup editor: multi-select, enable/disable, bulk group, reorder (↑↓ / Save order), logos, inline Edit (name/group/logo/tvg-id), Map EPG.</p>
        <div className="card bg-base-200 border border-base-content/10 my-3">
          <div className="card-body p-3 gap-2 text-sm">
            <div className="font-semibold text-sm">EPG guides (iptv-org / epg-grabber)</div>
            <p className="text-xs opacity-60">Published XMLTV from iptv-org.github.io — auto-bound when you seed country playlists. Multi-URL merge on refresh.</p>
            <div className="flex flex-wrap gap-1">
              <button type="button" className="btn btn-xs" onClick={async()=>{
                try {
                  const r = await fetch('/api/livetv/epg/presets').then(x=>x.json());
                  setMsg((r.presets||[]).map(p=>p.name+': '+p.url).join(' | '));
                } catch(e){ setMsg(String(e.message||e)); }
              }}>List EPG presets</button>
              <button type="button" className="btn btn-xs" onClick={async()=>{
                try {
                  const r = await fetch('/api/livetv/epg/presets/epg-us-tvtv/bind',{method:'POST'}).then(x=>x.json());
                  setMsg('Bound US tvtv: '+JSON.stringify(r));
                } catch(e){ setMsg(String(e.message||e)); }
              }}>Bind US guide to all sources</button>
              <button type="button" className="btn btn-xs" onClick={async()=>{
                try {
                  const r = await fetch('/api/livetv/epg/presets/epg-uk-sky/bind',{method:'POST'}).then(x=>x.json());
                  setMsg('Bound UK sky: '+JSON.stringify(r));
                } catch(e){ setMsg(String(e.message||e)); }
              }}>Bind UK guide</button>
            </div>
            <p className="text-[10px] opacity-40">Offline channels are removed after 12h (Settings → System · livetv_offline_*).</p>
          </div>
        </div>

        <div className="card bg-base-200 border border-base-content/10 my-3">
          <div className="card-body p-3 gap-1 text-sm">
            <div className="font-semibold text-sm">Jellyfin Live TV pipeline</div>
            <p className="text-xs opacity-60">In Jellyfin: Live TV → M3U Tuner + XMLTV guide. Streams proxy through MediaOs.</p>
            <code className="text-[11px] break-all">/api/livetv/export/playlist.m3u</code>
            <code className="text-[11px] break-all">/api/livetv/export/guide.xml</code>
            <button type="button" className="btn btn-xs w-fit mt-1" onClick={async()=>{
              try {
                const r = await fetch('/api/livetv/jellyfin-setup').then(x=>x.json());
                setMsg((r.steps||[]).join(' | '));
              } catch(e){ setMsg(String(e.message||e)); }
            }}>Show setup steps</button>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 mt-2">
          <button type="button" className="btn btn-sm btn-secondary" onClick={async()=>{
            setMsg('Seeding iptv-org defaults + EPG guides…');
            try {
              const r = await fetch('/api/livetv/presets/iptv-org/seed',{method:'POST'}).then(x=>x.json());
              setMsg(`Seeded ${JSON.stringify(r.created||[])} · EPG ${JSON.stringify(r.epg_bound||[])} · index ${JSON.stringify(r.epg_index||{})}`);
              load();
            } catch(e) { setMsg(String(e.message||e)); }
          }}>Add iptv-org defaults + EPG</button>
          <button type="button" className="btn btn-sm" onClick={async()=>{
            setMsg('Refreshing EPG (all XMLTV URLs)…');
            try {
              const r = await fetch('/api/livetv/epg/refresh',{method:'POST'}).then(x=>x.json());
              setMsg('EPG: '+JSON.stringify(r));
            } catch(e){ setMsg(String(e.message||e)); }
          }}>Refresh EPG</button>
          {advanced && (
          <>
          <button type="button" className="btn btn-sm" onClick={async()=>{
            setMsg('Probing channel health…');
            try {
              const r = await fetch('/api/livetv/health/run',{method:'POST'}).then(x=>x.json());
              setMsg(`Health: checked ${r.checked} ok ${r.ok} fail ${r.failed} deleted ${r.deleted} disabled ${r.disabled}`);
              load();
            } catch(e){ setMsg(String(e.message||e)); }
          }}>Health check</button>
          <button type="button" className="btn btn-sm" onClick={async()=>{
            setMsg('Re-syncing iptv-org sources…');
            try {
              const r = await fetch('/api/livetv/presets/iptv-org/resync',{method:'POST'}).then(x=>x.json());
              setMsg('Resync: ' + JSON.stringify(r.results||r));
              load();
            } catch(e) { setMsg(String(e.message||e)); }
          }}>Refresh iptv-org</button>
          <button type="button" className="btn btn-sm" onClick={async()=>{
            setMsg('Installing channel logos from playlist URLs…');
            try {
              const r = await fetch('/api/livetv/logos/install-remote',{method:'POST'}).then(x=>x.json());
              setMsg(`Logos: downloaded ${r.downloaded||0}, skipped ${r.skipped||0}, failed ${r.failed||0}`);
              load();
            } catch(e) { setMsg(String(e.message||e)); }
          }}>Install channel logos</button>
          </>
        )}
          <a className="btn btn-sm btn-ghost" href="https://github.com/iptv-org/iptv" target="_blank" rel="noreferrer">iptv-org on GitHub</a>
        </div>
        <div className="tabs tabs-boxed tabs-sm w-fit mt-2">
          <a className={'tab '+(tvTab==='channels'?'tab-active':'')} onClick={()=>setTvTab('channels')}>Channels</a>
          {advanced && <a className={'tab '+(tvTab==='virtual'?'tab-active':'')} onClick={()=>setTvTab('virtual')}>Virtual Channels</a>}
          <a className={'tab '+(tvTab==='epg'?'tab-active':'')} onClick={()=>setTvTab('epg')}>EPG Timeline</a>
          <a className={'tab '+(tvTab==='nownext'?'tab-active':'')} onClick={()=>setTvTab('nownext')}>Now / Next</a>
        </div>
      </div>

      {tvTab==='virtual' && (advanced ? <VirtualChannelsPanel setMsg={setMsg} /> : <p className="text-sm opacity-60 p-4">Virtual channels are available in Advanced mode.</p>)}

      {tvTab==='epg' && <EpgTimeline />}

      {tvTab==='nownext' && (
        <div className="card bg-base-200">
          <div className="card-body p-3 gap-2">
            <div className="flex justify-between items-center">
              <h2 className="font-semibold text-sm">Now / Next</h2>
              <button type="button" className="btn btn-xs" onClick={async()=>{
                setMsg('Syncing EPG…');
                await fetch('/api/overhaul/epg/sync',{method:'POST'}).catch(e => { try { setMsg(String(e.message||e)); } catch(_) { console.warn(e); } });
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
                <button type="button" className="btn btn-sm btn-primary" onClick={async()=>{
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
                <button type="button" className="btn btn-xs" onClick={async()=>{ setMsg('Syncing…'); const r=await api.livetv.sync(s.id); setMsg(`Synced ${r.synced}`); load(); }}>Sync</button>
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
            <button type="button" className="btn btn-sm" onClick={()=>api.livetv.channels(q).then(setChannels)}>Search</button>
            <button type="button" className="btn btn-sm btn-success" title="Enable all filtered" onClick={()=>bulkEnable(true)}>Enable filtered</button>
            <button type="button" className="btn btn-sm btn-warning" title="Disable all filtered" onClick={()=>bulkEnable(false)}>Disable filtered</button>
            <button type="button" className="btn btn-sm btn-ghost" onClick={()=>reorderSave((filtered||[]).map(c=>c.id))}>Save order</button>
            <button type="button" className="btn btn-sm btn-ghost" onClick={async()=>{ try { await fetch('/api/livetv/logos/match',{method:'POST'}); setMsg('Logos matched'); load(); } catch(e){ setMsg(String(e)); } }}>Match logos</button>
            <span className="text-xs opacity-50 self-center ml-1">{selected.size ? selected.size+' selected' : ''}</span>
            <button type="button" className="btn btn-sm" onClick={selectAllFiltered} disabled={!filtered.length}>Select all</button>
            <button type="button" className="btn btn-sm" onClick={clearSelection} disabled={!selected.size}>Clear</button>
            <input className="input input-bordered input-sm w-32" placeholder="New group" value={bulkGroup} onChange={e=>setBulkGroup(e.target.value)} />
            <button type="button" className="btn btn-sm btn-primary" disabled={!selected.size} onClick={bulkSetGroup}>Set group</button>
            <button type="button" className="btn btn-sm btn-success" disabled={!selected.size} onClick={async()=>{ try { await api.livetv.bulkChannels({ channel_ids:[...selected], enabled:true }); setMsg('Enabled '+selected.size); clearSelection(); load(); } catch(e){ setMsg(String(e.message||e)); } }}>Enable sel</button>
            <button type="button" className="btn btn-sm btn-warning" disabled={!selected.size} onClick={async()=>{ try { await api.livetv.bulkChannels({ channel_ids:[...selected], enabled:false }); setMsg('Disabled '+selected.size); clearSelection(); load(); } catch(e){ setMsg(String(e.message||e)); } }}>Disable sel</button>
            <button type="button" className="btn btn-sm btn-ghost" onClick={load}>Reload editor</button>
          </div>
          <div className="overflow-x-auto max-h-[28rem]">
            <table className="table table-xs">
              <thead><tr><th className="w-8"></th><th>On</th><th></th><th>Name</th><th>Group</th><th></th></tr></thead>
              <tbody>
                {filtered.map(c=>(
                  <tr key={c.id} className={(c.enabled===false ? 'opacity-40 ' : '') + (selected.has(c.id) ? 'bg-primary/10' : '')}>
                    <td className="w-8">
                      <input type="checkbox" className="checkbox checkbox-xs"
                        checked={selected.has(c.id)}
                        onChange={()=>toggleSelect(c.id)}
                        title="Select for bulk actions" />
                    </td>
                    <td className="w-10">
                      <input type="checkbox" className="toggle toggle-xs toggle-success"
                        checked={c.enabled!==false}
                        onChange={e=>toggleChannel(c, e.target.checked)}
                        title={c.enabled===false?'Enable channel':'Disable channel'} />
                    </td>
                    <td className="w-10">
                      {c.logo
                        ? <img src={c.logo} alt="" className="w-8 h-8 rounded object-contain bg-base-300" onError={e=>{ e.currentTarget.style.display='none'; }} />
                        : <div className="w-8 h-8 rounded bg-base-300" />}
                    </td>
                    <td className="font-medium">{c.name}</td>
                    <td className="opacity-60">{c.group_title||c.group||'—'}</td>
                    <td className="whitespace-nowrap">
                      <button type="button" className="btn btn-xs" title="Move up" onClick={()=>moveChannel(c.id,-1)}>↑</button>
                      <button type="button" className="btn btn-xs" title="Move down" onClick={()=>moveChannel(c.id,1)}>↓</button>
                      <button type="button" className="btn btn-xs btn-primary" onClick={()=>setPlaying(c)}>Play</button>
                      <button type="button" className="btn btn-xs" title="Edit name/group/logo" onClick={()=>openEdit(c)}>Edit</button>
                      <button type="button" className="btn btn-xs" title="Map EPG" onClick={async()=>{
                        try {
                          const r = await fetch('/api/livetv/channels/'+c.id+'/suggest-epg').then(x=>x.json());
                          const s = (r.suggestions||[])[0];
                          if (!s) { setMsg('No EPG suggestions for '+c.name); return; }
                          await fetch('/api/livetv/channels/'+c.id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({epg_tvg_id:s.tvg_id})});
                          setMsg('Mapped '+c.name+' → '+s.tvg_id);
                        } catch(e){ setMsg(String(e.message||e)); }
                      }}>Map EPG</button>
                      <a className="btn btn-xs btn-ghost" href={c.stream_url} target="_blank" rel="noreferrer">Open</a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {editCh && (
        <div className="modal modal-open">
          <div className="modal-box max-w-md">
            <h3 className="font-bold text-sm">Edit channel</h3>
            <div className="form-control gap-2 mt-3">
              <label className="label py-0"><span className="label-text text-xs">Name</span></label>
              <input className="input input-bordered input-sm" value={editForm.name} onChange={e=>setEditForm(f=>({...f, name:e.target.value}))} />
              <label className="label py-0"><span className="label-text text-xs">Group</span></label>
              <input className="input input-bordered input-sm" value={editForm.group_title} onChange={e=>setEditForm(f=>({...f, group_title:e.target.value}))} list="livetv-groups" />
              <datalist id="livetv-groups">{groups.map(g=><option key={g} value={g} />)}</datalist>
              <label className="label py-0"><span className="label-text text-xs">Logo URL</span></label>
              <input className="input input-bordered input-sm" value={editForm.logo} onChange={e=>setEditForm(f=>({...f, logo:e.target.value}))} placeholder="https://..." />
              <label className="label py-0"><span className="label-text text-xs">EPG / tvg-id</span></label>
              <input className="input input-bordered input-sm" value={editForm.tvg_id} onChange={e=>setEditForm(f=>({...f, tvg_id:e.target.value}))} />
            </div>
            <div className="modal-action">
              <button type="button" className="btn btn-sm" onClick={()=>setEditCh(null)}>Cancel</button>
              <button type="button" className="btn btn-sm btn-primary" onClick={saveEdit}>Save</button>
            </div>
          </div>
          <div className="modal-backdrop" onClick={()=>setEditCh(null)} />
        </div>
      )}

      {playing && (
        <div className="modal modal-open">
          <div className="modal-box max-w-3xl">
            <h3 className="font-bold text-sm">{playing.name}</h3>
            <HlsVideo className="w-full mt-2 bg-black rounded" autoPlay src={playing.id ? `/api/livetv/stream/${playing.id}` : playing.stream_url} />
            <div className="modal-action">
              <button type="button" className="btn btn-sm" onClick={()=>setPlaying(null)}>Close</button>
            </div>
          </div>
          <div className="modal-backdrop" onClick={()=>setPlaying(null)} />
        </div>
      )}
    </div>
  );
}




export { EpgTimeline, LiveTvPage };
