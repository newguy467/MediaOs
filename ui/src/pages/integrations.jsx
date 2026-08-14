import React, { useState, useEffect, useCallback, useRef } from "react";
import Ic, { Icons, P } from "../icons.jsx";
import { getToken, setToken, getAdvanced, setAdvancedFlag, AUTH_TOKEN_KEY } from "../storage.js";
import { api, TMDB, adultFetch } from "../api.js";
import { PageChrome, PosterTile, LibraryModuleShell, MediaDetailShell, LibraryLegend, LibraryHeader, MediaCard, StatusBadgeStack, libraryStatuses, CollectionProgressWidget, TeachEmpty, AddModal } from "../components/ui.jsx";
import { InteractiveResultsPanel, InteractiveResultsTable, MediaPlayer, HlsVideo } from "../components/media.jsx";

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
    fetch('/api/migrate/supported').then(r=>r.json()).then(setSupported).catch(e => { try { setMsg(String(e.message||e)); } catch(_) { console.warn(e); } });
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
    }).catch(e => { try { setMsg(String(e.message||e)); } catch(_) { console.warn(e); } });
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
              <button type="button" className="btn btn-sm" disabled={!!busy} onClick={()=>test(app.id)}>Test</button>
              <button type="button" className="btn btn-sm" disabled={!!busy} onClick={()=>saveConn(app.id)}>Save connection</button>
              <button type="button" className="btn btn-sm btn-primary" disabled={!!busy || !forms[app.id].api_key}
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




export { IntegrationsPage };
