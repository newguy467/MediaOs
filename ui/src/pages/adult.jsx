import React, { useState, useEffect, useCallback, useRef } from "react";
import Ic, { Icons, P } from "../icons.jsx";
import { getToken, setToken, getAdvanced, setAdvancedFlag, AUTH_TOKEN_KEY } from "../storage.js";
import { api, TMDB, adultFetch, getAdultUnlock, setAdultUnlock } from "../api.js";
import { PageChrome, PosterTile, LibraryModuleShell, MediaDetailShell, LibraryLegend, LibraryHeader, MediaCard, StatusBadgeStack, libraryStatuses, CollectionProgressWidget, TeachEmpty, AddModal } from "../components/ui.jsx";
import { InteractiveResultsPanel, InteractiveResultsTable, MediaPlayer, HlsVideo, grabPayload, releaseDownloadUrl } from "../components/media.jsx";

function AdultPage() {
  const [locked, setLocked] = useState(true);
  const [pass, setPass] = useState('');
  const [err, setErr] = useState('');
  const [items, setItems] = useState([]);
  const [busy, setBusy] = useState(false);
  const [detailId, setDetailId] = useState(null);
  const [q, setQ] = useState('');
  const [filter, setFilter] = useState('all');
  const [msg, setMsg] = useState(null);
  const [addTitle, setAddTitle] = useState('');
  const [addYear, setAddYear] = useState('');
  const [showAdd, setShowAdd] = useState(false);

  const loadList = useCallback(async () => {
    try {
      const rows = await api.adult.list();
      if (Array.isArray(rows)) { setItems(rows); return true; }
      return false;
    } catch { return false; }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const s = await api.adult.status();
        if (cancelled) return;
        if (!s.locked) {
          setLocked(false);
          await loadList();
        } else if (getAdultUnlock()) {
          const ok = await loadList();
          if (ok) setLocked(false);
        }
      } catch {}
    })();
    return () => { cancelled = true; };
  }, [loadList]);

  const unlock = async (e) => {
    e && e.preventDefault();
    setErr(''); setBusy(true);
    try {
      const r = await api.adult.unlock(pass);
      if (r.unlock_token) {
        setAdultUnlock(r.unlock_token);
        setLocked(false);
        await loadList();
      } else setErr(r.detail || r.message || 'Unlock failed');
    } catch { setErr('Unlock failed'); }
    finally { setBusy(false); }
  };

  if (locked) {
    return (
      <div className="p-6 max-w-md mx-auto">
        <div className="card bg-base-200 shadow-xl">
          <div className="card-body">
            <h2 className="card-title"><Ic.Shield /> Adult library</h2>
            <p className="text-sm opacity-70">Passcode protected (Whisparr-class). Enter the passcode to continue.</p>
            <form onSubmit={unlock} className="space-y-3">
              <input type="password" className="input input-bordered w-full" placeholder="Passcode"
                value={pass} onChange={e=>setPass(e.target.value)} autoFocus />
              {err && <p className="text-error text-sm">{err}</p>}
              <button type="submit" className="btn btn-primary w-full" disabled={busy || !pass}>Unlock</button>
            </form>
            <p className="text-xs opacity-50 mt-2">Set the passcode under Settings → Adult.</p>
          </div>
        </div>
      </div>
    );
  }

  if (detailId) {
    return <AdultDetailPage itemId={detailId} onBack={()=>setDetailId(null)} refresh={loadList} />;
  }

  const filtered = (items||[]).filter(m => {
    if (q && !(m.title||'').toLowerCase().includes(q.toLowerCase())) return false;
    if (filter==='monitored' && !m.monitored) return false;
    if (filter==='missing' && !(['wanted','missing','failed'].includes(m.status))) return false;
    if (filter==='downloaded' && m.status!=='downloaded' && !m.file_path) return false;
    return true;
  });

  async function searchAllMissing() {
    setBusy(true); setMsg(null);
    try {
      const r = await api.adult.searchMissing();
      setMsg(`Searched ${r.searched||0} · grabbed ${r.grabbed||0}`);
      await loadList();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }

  async function addItem(e) {
    e && e.preventDefault();
    if (!addTitle.trim()) return;
    setBusy(true);
    try {
      await api.adult.add({ title: addTitle.trim(), year: addYear ? parseInt(addYear,10) : null });
      setAddTitle(''); setAddYear(''); setShowAdd(false);
      await loadList();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }

  return (
    <LibraryModuleShell
      title="Adult"
      active={filter}
      onNav={(id) => { if (['all','monitored','missing','downloaded'].includes(id)) setFilter(id); }}
      nav={[
        { id: 'all', label: 'Library' },
        { id: 'monitored', label: 'Monitored' },
        { id: 'missing', label: 'Missing' },
        { id: 'downloaded', label: 'Downloaded' },
      ]}
      tools={<>
        <input className="mr-search" placeholder="Search adult…" value={q} onChange={e=>setQ(e.target.value)} />
        <button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={searchAllMissing}>Search missing</button>
        <button type="button" className="btn btn-sm" onClick={()=>setShowAdd(v=>!v)}>Add</button>
        <button type="button" className="btn btn-ghost btn-xs" onClick={()=>{ setAdultUnlock(null); setLocked(true); }}>Lock</button>
      </>}
    >
      {msg && <div className="alert alert-info text-xs py-2 mb-3">{msg}</div>}
      {showAdd && (
        <div className="mb-4 p-3 rounded-lg bg-base-200 space-y-3">
          <form onSubmit={async (e)=>{
            e.preventDefault();
            if (!addTitle.trim()) return;
            setBusy(true); setMsg(null);
            try {
              const rows = await api.adult.metadataSearch(addTitle.trim());
              setMetaResults(Array.isArray(rows)?rows:[]);
              if (!rows || !rows.length) setMsg('No TPDB hits — you can still Add by title below (set TPDB_API_KEY for metadata).');
            } catch(ex) { setMsg(String(ex.message||ex)); setMetaResults([]); }
            setBusy(false);
          }} className="flex flex-wrap gap-2 items-end">
            <label className="form-control flex-1 min-w-[12rem]"><span className="label-text text-xs">Search metadata (TPDB)</span>
              <input className="input input-bordered input-sm" value={addTitle} onChange={e=>setAddTitle(e.target.value)} placeholder="Title…" autoFocus />
            </label>
            <button type="submit" className="btn btn-primary btn-sm" disabled={busy || !addTitle.trim()}>Search</button>
            <button type="button" className="btn btn-sm" disabled={busy || !addTitle.trim()} onClick={addItem}>Add title only</button>
          </form>
          {(metaResults||[]).length>0 && (
            <div className="grid sm:grid-cols-2 gap-2 max-h-72 overflow-y-auto">
              {metaResults.map((r,i)=>(
                <button key={r.external_id||i} type="button" className="card bg-base-100 text-left hover:border-primary border border-base-content/10"
                  onClick={async()=>{
                    setBusy(true);
                    try {
                      await api.adult.add({
                        title: r.title,
                        year: r.year,
                        external_id: r.external_id,
                        overview: r.overview,
                        poster_path: r.poster_path,
                        search_now: false,
                      });
                      setShowAdd(false); setMetaResults([]); setAddTitle('');
                      await loadList();
                    } catch(ex) { setMsg(String(ex.message||ex)); }
                    setBusy(false);
                  }}>
                  <div className="card-body p-2 flex-row gap-2 items-center">
                    {r.poster_path ? <img src={r.poster_path} alt="" className="w-12 h-16 object-cover rounded" /> : <div className="w-12 h-16 bg-base-300 rounded" />}
                    <div className="min-w-0">
                      <div className="font-medium text-sm truncate">{r.title}</div>
                      <div className="text-xs opacity-50">{[r.year||'—', r.site].filter(Boolean).join(' · ')}</div>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
          <form onSubmit={addItem} className="flex flex-wrap gap-2 items-end border-t border-base-content/10 pt-2">
            <label className="form-control"><span className="label-text text-xs">Year (manual)</span>
              <input className="input input-bordered input-sm w-24" value={addYear} onChange={e=>setAddYear(e.target.value)} placeholder="2024" />
            </label>
            <span className="text-xs opacity-50 self-center">Manual add uses the search box title + year</span>
          </form>
        </div>
      )}
      <div className="poster-grid">
        {filtered.map(m => (
          <PosterTile
            key={m.id}
            title={m.title}
            year={m.year}
            poster={m.poster_path}
            status={m.status}
            monitored={m.monitored}
            onClick={()=>setDetailId(m.id)}
          />
        ))}
        {!filtered.length && <p className="opacity-50 text-sm col-span-full">No titles — use Add or enable the Adult module path.</p>}
      </div>
    </LibraryModuleShell>
  );
}

function AdultDetailPage({ itemId, onBack, refresh }) {
  const [item, setItem] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const [ixResults, setIxResults] = useState(null);
  const [ixLoading, setIxLoading] = useState(false);

  const load = useCallback(() => {
    api.adult.get(itemId).then(setItem).catch(e=>setMsg(String(e.message||e)));
  }, [itemId]);
  useEffect(()=>{ load(); }, [load]);

  async function toggleMonitor() {
    if (!item) return;
    setBusy(true);
    try {
      await api.adult.update(item.id, { monitored: !item.monitored });
      load(); refresh && refresh();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  async function autoSearch() {
    setBusy(true); setMsg(null);
    try {
      const body = await api.adult.searchNow(itemId);
      setMsg(body?.title ? `Grabbed: ${body.title}` : 'Search finished (no grab)');
      load(); refresh && refresh();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  async function openInteractive() {
    setIxLoading(true); setIxResults([]); setMsg(null);
    try {
      const data = await api.adult.interactive(itemId);
      const rows = data?.results || (Array.isArray(data) ? data : []);
      setIxResults(rows);
    } catch(e) { setMsg(String(e.message||e)); }
    setIxLoading(false);
  }
  async function grabRel(rel) {
    setBusy(true);
    try {
      await api.adult.grab(itemId, grabPayload(rel));
      setMsg(`Grabbed: ${rel.title}`);
      setIxResults(null);
      load(); refresh && refresh();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  async function doRefresh() {
    setBusy(true);
    try {
      await api.adult.refresh(itemId);
      load(); refresh && refresh();
      setMsg('Refreshed');
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  async function clearFile() {
    setBusy(true);
    try {
      await api.adult.file(itemId, { clear: true });
      load(); refresh && refresh();
    } catch(e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  async function doDelete() {
    if (!confirm('Remove from adult library?')) return;
    await api.adult.remove(itemId);
    onBack();
    refresh && refresh();
  }

  if (!item) return <div className="p-6 opacity-50">Loading…</div>;

  return (
    <MediaDetailShell
      title={item.title} year={item.year} poster={item.poster_path}
      status={item.status} monitored={item.monitored}
      overview={item.overview}
      filePath={item.file_path} qualityProfile={item.quality_profile}
      msg={msg} busy={busy} onBack={onBack}
      actions={<>
        <button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={autoSearch}>Search & grab</button>
        <button type="button" className="btn btn-sm btn-secondary" disabled={busy||ixLoading} onClick={openInteractive}>Interactive search</button>
        <button type="button" className="btn btn-sm" disabled={busy} onClick={toggleMonitor}>{item.monitored?'Unmonitor':'Monitor'}</button>
        <button type="button" className="btn btn-sm" disabled={busy} onClick={doRefresh}>Refresh</button>
        {item.file_path && <button type="button" className="btn btn-sm btn-ghost" disabled={busy} onClick={clearFile}>Clear file</button>}
        <button type="button" className="btn btn-sm btn-ghost text-error" onClick={doDelete}>Delete</button>
      </>}
    >
      <InteractiveResultsTable results={ixResults} loading={ixLoading} busy={busy} onGrab={grabRel} onClose={()=>setIxResults(null)} />
    </MediaDetailShell>
  );
}



function AdultSettingsPage({ setPage }) {
  const [pass, setPass] = useState('');
  const [cur, setCur] = useState('');
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState(null);
  useEffect(()=>{
    fetch('/api/adult/status').then(r=>r.json()).then(setStatus).catch(e => { try { setMsg(String(e.message||e)); } catch(_) { console.warn(e); } });
  }, []);
  async function savePass(e) {
    e && e.preventDefault();
    if (!pass || pass.length < 4) { setMsg('Passcode must be at least 4 characters'); return; }
    setBusy(true); setMsg(null);
    try {
      const body = { passcode: pass };
      if (status?.passcode_set) body.current_passcode = cur;
      const r = await fetch('/api/adult/passcode', {
        method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)
      }).then(x=>x.json());
      if (r.ok || r.passcode_set) {
        setMsg('Passcode saved'); setPass(''); setCur('');
        setStatus(s=>({...(s||{}), passcode_set: true}));
      } else setMsg(r.detail || r.message || JSON.stringify(r));
    } catch(ex) { setMsg(String(ex.message||ex)); }
    setBusy(false);
  }
  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center gap-2">
        <button type="button" className="btn btn-ghost btn-sm" onClick={()=>setPage && setPage('settings-hub')}>← Settings</button>
      </div>
      <div>
        <h1 className="mr-page-title">Adult library</h1>
        <p className="mr-page-sub">Whisparr-class module — path, passcode gate, and ThePornDB metadata.</p>
      </div>
      {msg && <div className="alert alert-info text-sm py-2">{msg}</div>}
      <div className="card bg-base-200"><div className="card-body gap-3">
        <h2 className="font-semibold text-sm">Passcode</h2>
        <p className="text-xs opacity-60">
          {status?.passcode_set ? 'Passcode is set. Enter current passcode to change it.' : 'No passcode yet — set one to lock the Adult module.'}
          {status?.passcode_enabled === false && ' (Passcode currently disabled in config.)'}
        </p>
        <form onSubmit={savePass} className="flex flex-col gap-2 max-w-sm">
          {status?.passcode_set && (
            <input type="password" className="input input-bordered input-sm" placeholder="Current passcode"
              value={cur} onChange={e=>setCur(e.target.value)} />
          )}
          <input type="password" className="input input-bordered input-sm" placeholder="New passcode (min 4)"
            value={pass} onChange={e=>setPass(e.target.value)} />
          <button type="submit" className="btn btn-primary btn-sm w-fit" disabled={busy}>{busy?'Saving…':'Save passcode'}</button>
        </form>
      </div></div>
      <ConfigGroupPage group="adult" title="Adult paths & TPDB" Icon={Ic.Shield}
        description="Library path and ThePornDB API key. Changes apply immediately." hideBack />
    </div>
  );
}



export { AdultPage, AdultDetailPage, AdultSettingsPage };
