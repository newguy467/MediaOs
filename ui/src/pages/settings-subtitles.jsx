import React, { useState, useEffect, useCallback } from "react";
import { PageChrome } from "../components/ui.jsx";
import Ic from "../icons.jsx";
import { api } from "../api.js";

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
      fetch('/api/tools/subtitle-providers').then(r=>r.json()).then(setProviders).catch(e => { console.warn(e); if (typeof setMsg === 'function') setMsg(String(e.message || e)); });
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
          <button type="button" className="btn btn-sm" onClick={()=>setPage&&setPage('wanted-subtitles')}>
            Wanted {wantedCount!=null ? `(${wantedCount})` : ''}
          </button>
          <button type="button" className="btn btn-sm btn-primary" disabled={saving} onClick={save}>
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
        <button type="button" className="btn btn-primary" disabled={saving} onClick={save}>{saving?'Saving…':'Save changes'}</button>
        <button type="button" className="btn" onClick={load}>Reset</button>
      </div>
    </div>
  );
}


export default SubtitlesSettingsPage;
export { SubtitlesSettingsPage };
