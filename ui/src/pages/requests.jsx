import { useState, useEffect } from "react";
import Ic from "../icons.jsx";
import { api, TMDB } from "../api.js";
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
          <button type="button" className="btn btn-ghost btn-xs btn-square" onClick={onClose}><Ic.X /></button>
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
              <button type="button" className="btn btn-sm btn-outline" disabled={busyId===r.external_id} onClick={()=>submit(r)}>
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
        <button type="button" className="btn btn-sm btn-primary" onClick={()=>setModal(true)}>
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
                  <button type="button" className="btn btn-success btn-xs" onClick={()=>approve(r)}>Approve</button>
                  <button type="button" className="btn btn-ghost btn-xs text-error" onClick={()=>deny(r)}>Deny</button>
                </div>
              ) : (
                <button type="button" className="btn btn-ghost btn-xs text-error" onClick={()=>cancel(r)}>Remove</button>
              )}
            </div>
          ))}
        </div>
      )}

      {modal && <NewRequestModal onClose={()=>setModal(false)} onRequested={()=>{ setModal(false); setTab('pending'); load(); }} />}
    </div>
  );
}



export { RequestStatusBadge, NewRequestModal, RequestsPage };
