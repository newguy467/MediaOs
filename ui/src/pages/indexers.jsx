import { useState, useEffect } from "react";
import { api } from "../api.js";
function IndexersPage() {
  const [defsHealth, setDefsHealth] = useState(null);
  useEffect(()=>{ fetch('/api/indexers/definitions/health').then(r=>r.json()).then(setDefsHealth).catch(e => { try { setMsg(String(e.message||e)); } catch(_) { console.warn(e); } }); }, []);

  /* Prowlarr-style: browse catalog / Prowlarr / Jackett → pick URL → Test → Add (FlareSolverr tag) */
  const [tab, setTab] = useState("added"); // added | catalog | prowlarr | jackett
  const [items, setItems] = useState([]);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [catalogQ, setCatalogQ] = useState("");
  const [catalog, setCatalog] = useState([]);
  const [privacy, setPrivacy] = useState("");
  const [picked, setPicked] = useState(null);
  const [form, setForm] = useState({ name: "", url: "", username: "", password: "", cookie: "", api_key: "", use_flaresolverr: false, priority: 25 });
  const [prowlarr, setProwlarr] = useState({ indexers: [], ok: false });
  const [jackett, setJackett] = useState({ indexers: [], ok: false });
  const [statusP, setStatusP] = useState(null);
  const [statusJ, setStatusJ] = useState(null);
  const [filter, setFilter] = useState("");
  const [testResult, setTestResult] = useState(null);

  const loadAdded = () => api.indexers.list().then(setItems).catch(() => setItems([]));
  useEffect(() => { loadAdded(); }, []);

  async function loadCatalog(q, priv) {
    setBusy(true);
    try {
      const params = new URLSearchParams();
      if (q) params.set("q", q);
      if (priv) params.set("privacy", priv);
      const r = await fetch("/api/indexers/catalog?" + params).then(x => x.json());
      setCatalog(Array.isArray(r) ? r : (r.results || []));
    } catch (e) { setMsg(String(e.message || e)); }
    setBusy(false);
  }

  async function loadProwlarr() {
    setBusy(true); setMsg(null);
    try {
      const st = await fetch("/api/indexers/prowlarr/status").then(x => x.json());
      setStatusP(st);
      const r = await fetch("/api/indexers/prowlarr/indexers").then(x => x.json());
      setProwlarr(r);
      if (!r.ok) setMsg(r.error || "Prowlarr unavailable");
    } catch (e) { setMsg(String(e.message || e)); }
    setBusy(false);
  }

  async function loadJackett() {
    setBusy(true); setMsg(null);
    try {
      const st = await fetch("/api/indexers/jackett/status").then(x => x.json());
      setStatusJ(st);
      const r = await fetch("/api/indexers/jackett/indexers").then(x => x.json());
      setJackett(r);
      if (!r.ok) setMsg(r.error || "Jackett unavailable");
    } catch (e) { setMsg(String(e.message || e)); }
    setBusy(false);
  }

  useEffect(() => {
    if (tab === "catalog") loadCatalog(catalogQ, privacy);
    if (tab === "prowlarr") loadProwlarr();
    if (tab === "jackett") loadJackett();
  }, [tab]);

  async function pickCatalog(id) {
    setBusy(true); setTestResult(null);
    try {
      const d = await fetch("/api/indexers/catalog/" + encodeURIComponent(id)).then(x => x.json());
      setPicked({ source: "catalog", ...d });
      const urls = d.urls || (d.url ? [d.url] : []);
      setForm({
        name: d.name || id,
        url: urls[0] || d.url || "",
        urls,
        username: "", password: "", cookie: "", api_key: "",
        use_flaresolverr: !!(d.extra_tags && d.extra_tags.includes("flaresolverr")),
        priority: 25,
      });
    } catch (e) { setMsg(String(e.message || e)); }
    setBusy(false);
  }

  function pickProwlarr(ix) {
    setTestResult(null);
    setPicked({ source: "prowlarr", ...ix });
    setForm({
      name: ix.name,
      url: ix.torznab_url || "",
      urls: [ix.torznab_url, ix.base_url].filter(Boolean),
      username: "", password: "", cookie: "", api_key: "",
      use_flaresolverr: !!ix.needs_flaresolverr,
      priority: ix.priority || 25,
      prowlarr_id: ix.id,
      tags: ix.tags || [],
    });
  }

  function pickJackett(ix) {
    setTestResult(null);
    setPicked({ source: "jackett", ...ix });
    setForm({
      name: ix.name,
      url: ix.torznab_url || "",
      urls: [ix.torznab_url].filter(Boolean),
      username: "", password: "", cookie: "", api_key: ix.api_key || "",
      use_flaresolverr: !!ix.needs_flaresolverr,
      priority: 25,
      jackett_id: ix.id,
      tags: ix.tags || [],
    });
  }

  async function testPicked() {
    if (!picked) return;
    setBusy(true); setTestResult(null);
    try {
      if (picked.source === "prowlarr" && form.prowlarr_id != null) {
        const r = await fetch("/api/indexers/prowlarr/indexers/" + form.prowlarr_id + "/test", { method: "POST" }).then(x => x.json());
        setTestResult(r);
      } else if (picked.source === "catalog" && picked.id) {
        const r = await fetch("/api/indexers/catalog/" + encodeURIComponent(picked.id) + "/test?query=ubuntu", { method: "POST" }).then(x => x.json()).catch(async () => {
          // fallback test-search after add pattern
          return { ok: false, error: "Catalog test endpoint unavailable — Add then Test on the row" };
        });
        setTestResult(r);
      } else if (picked.source === "jackett") {
        // Torznab caps ping via temporary test after add is safer; try jackett status
        setTestResult({ ok: true, note: "Jackett indexer selected — will use Torznab URL. Click Add, then Test on the added row." });
      } else {
        setTestResult({ ok: false, error: "Nothing to test" });
      }
    } catch (e) { setTestResult({ ok: false, error: String(e.message || e) }); }
    setBusy(false);
  }

  async function addPicked() {
    if (!picked) return;
    setBusy(true); setMsg(null);
    try {
      let r;
      if (picked.source === "prowlarr") {
        r = await fetch("/api/indexers/prowlarr/indexers/add", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            indexer_id: form.prowlarr_id,
            name: form.name,
            use_flaresolverr: form.use_flaresolverr,
            enabled: true,
            priority: form.priority,
          }),
        }).then(x => x.json());
      } else if (picked.source === "jackett") {
        r = await fetch("/api/indexers/jackett/indexers/add", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            indexer_id: String(form.jackett_id),
            name: form.name,
            use_flaresolverr: form.use_flaresolverr,
            enabled: true,
            priority: form.priority,
          }),
        }).then(x => x.json());
      } else {
        r = await fetch("/api/indexers/catalog/add", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
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
          }),
        }).then(x => x.json());
      }
      if (r.detail) throw new Error(typeof r.detail === "string" ? r.detail : JSON.stringify(r.detail));
      setMsg("Added: " + (r.name || form.name));
      setPicked(null);
      loadAdded();
      setTab("added");
    } catch (e) { setMsg(String(e.message || e)); }
    setBusy(false);
  }

  async function testAdded(id) {
    setBusy(true);
    try {
      const r = await fetch("/api/indexers/" + id + "/test-search?query=ubuntu", { method: "POST" }).then(x => x.json());
      setMsg(r.ok ? `Test OK — ${r.count} results` : `Test failed: ${r.error || JSON.stringify(r)}`);
      loadAdded();
    } catch (e) { setMsg(String(e.message || e)); }
    setBusy(false);
  }


  async function testAllAdded() {
    const rows = items || [];
    if (!rows.length) { setMsg('No indexers to test'); return; }
    setBusy(true); setMsg(null);
    let ok = 0, fail = 0;
    for (const r of rows) {
      try {
        const res = await fetch("/api/indexers/" + r.id + "/test-search?query=ubuntu", { method: "POST" }).then(x => x.json());
        if (res.ok) ok += 1; else fail += 1;
      } catch { fail += 1; }
    }
    setMsg(`Test all: ${ok} ok, ${fail} failed`);
    loadAdded();
    setBusy(false);
  }

  async function removeIndexer(id) {
    if (!confirm("Remove this indexer?")) return;
    await fetch("/api/indexers/" + id, { method: "DELETE" });
    loadAdded();
  }

  async function toggleFlare(row) {
    await fetch("/api/indexers/" + row.id, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: row.name, url: row.url, kind: row.kind, enabled: row.enabled,
        priority: row.priority, use_flaresolverr: !row.use_flaresolverr,
        categories: row.categories, api_key: null,
      }),
    });
    loadAdded();
  }

  const filt = (name) => !filter || (name || "").toLowerCase().includes(filter.toLowerCase());

  return (
    <div className="space-y-4 max-w-5xl">
      <div>
        {defsHealth && (
        <div className="alert text-xs py-2 mb-2">
          Cardigann definitions: <b>{defsHealth.count ?? 0}</b> at <code className="text-[10px]">{defsHealth.path}</code>
          {defsHealth.enabled ? " · enabled" : " · disabled"}
          {defsHealth.auto_sync ? " · auto-sync" : ""}
        </div>
      )}
      <h1 className="mr-page-title">Indexers</h1>
        <p className="mr-page-sub">Prowlarr is optional (private trackers only). Public = builtins + full Jackett Cardigann sync. Tag FlareSolverr when needed.</p>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="btn btn-sm" disabled={busy} onClick={async()=>{
          setBusy(true);
          try {
            const r = await fetch('/api/indexers/health/run',{method:'POST'}).then(x=>x.json());
            setMsg('Health: '+JSON.stringify(r)); loadAdded();
          } catch(e){ setMsg(String(e.message||e)); }
          setBusy(false);
        }}>Run health check</button>
        <button type="button" className="btn btn-sm" disabled={busy} onClick={async()=>{
          setBusy(true);
          try {
            const r = await fetch('/api/setup/bootstrap?force=true',{method:'POST'}).then(x=>x.json());
            setMsg('Def sync started: '+JSON.stringify(r));
          } catch(e){ setMsg(String(e.message||e)); }
          setBusy(false);
        }}>Sync all Jackett defs</button>
      </div>
      </div>

      <div className="tabs tabs-boxed w-fit flex-wrap">
        {[
          ["added", "Added"],
          ["catalog", "Cardigann catalog"],
          ["prowlarr", "Prowlarr"],
          ["jackett", "Jackett"],
        ].map(([k, label]) => (
          <button key={k} type="button" className={"tab " + (tab === k ? "tab-active" : "")} onClick={() => setTab(k)}>{label}</button>
        ))}
      </div>

      {msg && <div className="alert alert-info text-sm py-2">{msg}</div>}

      <input className="input input-bordered input-sm w-full max-w-md" placeholder="Filter list…" value={filter} onChange={e => setFilter(e.target.value)} />

      {tab === "added" && (
        <div className="overflow-x-auto">
          <table className="table table-sm">
            <thead>
              <tr>
                <th>Name</th><th>Kind</th><th>URL</th><th>Tags</th><th>Status</th><th></th>
              </tr>
            </thead>
            <tbody>
              {(items || []).filter(r => filt(r.name)).map(r => (
                <tr key={r.id}>
                  <td className="font-medium">{r.name}</td>
                  <td><span className="badge badge-ghost badge-sm">{r.kind}</span></td>
                  <td className="font-mono text-[10px] max-w-[12rem] truncate">{r.url}</td>
                  <td>
                    {r.use_flaresolverr && <span className="badge badge-warning badge-sm">FlareSolverr</span>}
                    {r.kind === "cardigann" && <span className="badge badge-info badge-sm ml-1">Cardigann</span>}
                  </td>
                  <td className="text-xs">
                    {r.last_error ? <span className="text-error">{r.last_error.slice(0, 40)}</span> :
                      r.last_ok_at ? <span className="text-success">OK</span> : "—"}
                  </td>
                  <td className="flex gap-1">
                    <button type="button" className="btn btn-xs" disabled={busy} onClick={() => testAdded(r.id)}>Test</button>
                    <button type="button" className="btn btn-xs" onClick={() => toggleFlare(r)} title="Toggle FlareSolverr">
                      {r.use_flaresolverr ? "Unflare" : "Flare"}
                    </button>
                    <button type="button" className="btn btn-xs btn-ghost text-error" onClick={() => removeIndexer(r.id)}>Del</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!items.length && (
            <div className="p-6 text-center space-y-2">
              <p className="text-sm opacity-50">No indexers yet — use Catalog, Prowlarr, or Jackett tab to add Torznab / cardigann sources.</p>
              <button type="button" className="btn btn-sm btn-primary" onClick={() => setTab("catalog")}>Browse catalog</button>
            </div>
          )}
        </div>
      )}

      {tab === "catalog" && (
        <div className="grid lg:grid-cols-2 gap-4">
          <div className="space-y-2">
            <div className="flex gap-2 flex-wrap">
              <input className="input input-bordered input-sm flex-1" placeholder="Search definitions…" value={catalogQ}
                onChange={e => setCatalogQ(e.target.value)}
                onKeyDown={e => e.key === "Enter" && loadCatalog(catalogQ, privacy)} />
              <select className="select select-bordered select-sm" value={privacy} onChange={e => { setPrivacy(e.target.value); loadCatalog(catalogQ, e.target.value); }}>
                <option value="">All</option>
                <option value="public">Public</option>
                <option value="private">Private</option>
              </select>
              <button type="button" className="btn btn-sm" disabled={busy} onClick={() => loadCatalog(catalogQ, privacy)}>Search</button>
            </div>
            <div className="max-h-[28rem] overflow-auto border border-base-content/10 rounded-lg">
              {(catalog || []).filter(c => filt(c.name || c.id)).map(c => (
                <button key={c.id || c.name} type="button"
                  className={"w-full text-left px-3 py-2 text-sm border-b border-base-content/5 hover:bg-base-200 "
                    + (picked && picked.id === c.id ? "bg-primary/15" : "")}
                  onClick={() => pickCatalog(c.id)}>
                  <span className="font-medium">{c.name || c.id}</span>
                  {c.privacy && <span className="badge badge-ghost badge-xs ml-2">{c.privacy}</span>}
                </button>
              ))}
            </div>
          </div>
          <IndexerAddPanel form={form} setForm={setForm} picked={picked} testResult={testResult}
            busy={busy} onTest={testPicked} onAdd={addPicked} />
        </div>
      )}

      {tab === "prowlarr" && (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2 items-center text-sm">
            <span className={"badge " + (statusP?.test?.ok ? "badge-success" : "badge-warning")}>
              {statusP?.configured ? (statusP?.test?.ok ? "Connected" : "Configured, unreachable") : "Not configured"}
            </span>
            <span className="opacity-50 text-xs">{statusP?.url || "Set URL + API key in Settings → Indexer connection"}</span>
            <button type="button" className="btn btn-xs" disabled={busy} onClick={loadProwlarr}>Refresh</button>
          </div>
          <div className="grid lg:grid-cols-2 gap-4">
            <div className="max-h-[28rem] overflow-auto border border-base-content/10 rounded-lg">
              {(prowlarr.indexers || []).filter(ix => filt(ix.name)).map(ix => (
                <button key={ix.id} type="button"
                  className={"w-full text-left px-3 py-2 text-sm border-b border-base-content/5 hover:bg-base-200 "
                    + (picked && picked.source === "prowlarr" && picked.id === ix.id ? "bg-primary/15" : "")}
                  onClick={() => pickProwlarr(ix)}>
                  <div className="font-medium flex flex-wrap gap-1 items-center">
                    {ix.name}
                    {!ix.enable && <span className="badge badge-ghost badge-xs">disabled in Prowlarr</span>}
                    {ix.needs_flaresolverr && <span className="badge badge-warning badge-xs">FlareSolverr</span>}
                    {(ix.tags || []).slice(0, 3).map(t => <span key={t} className="badge badge-outline badge-xs">{t}</span>)}
                  </div>
                  <div className="text-[10px] opacity-50 font-mono truncate">{ix.torznab_url}</div>
                </button>
              ))}
              {!prowlarr.indexers?.length && <p className="p-3 text-sm opacity-50">No indexers from Prowlarr yet.</p>}
            </div>
            <IndexerAddPanel form={form} setForm={setForm} picked={picked} testResult={testResult}
              busy={busy} onTest={testPicked} onAdd={addPicked} />
          </div>
        </div>
      )}

      {tab === "jackett" && (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2 items-center text-sm">
            <span className={"badge " + (statusJ?.configured ? "badge-success" : "badge-warning")}>
              {statusJ?.configured ? "Jackett configured" : "Not configured"}
            </span>
            <button type="button" className="btn btn-xs" disabled={busy} onClick={loadJackett}>Refresh</button>
            <button type="button" className="btn btn-xs" disabled={busy} onClick={async () => {
              setBusy(true);
              try {
                const r = await fetch("/api/indexers/jackett/sync", { method: "POST" }).then(x => x.json());
                setMsg("Jackett sync: " + JSON.stringify(r));
                loadAdded();
              } catch (e) { setMsg(String(e.message || e)); }
              setBusy(false);
            }}>Sync all configured</button>
          </div>
          <div className="grid lg:grid-cols-2 gap-4">
            <div className="max-h-[28rem] overflow-auto border border-base-content/10 rounded-lg">
              {(jackett.indexers || []).filter(ix => filt(ix.name)).map(ix => (
                <button key={ix.id} type="button"
                  className={"w-full text-left px-3 py-2 text-sm border-b border-base-content/5 hover:bg-base-200 "
                    + (picked && picked.source === "jackett" && picked.id === ix.id ? "bg-primary/15" : "")}
                  onClick={() => pickJackett(ix)}>
                  <div className="font-medium">
                    {ix.name}
                    {ix.needs_flaresolverr && <span className="badge badge-warning badge-xs ml-1">FlareSolverr</span>}
                  </div>
                  <div className="text-[10px] opacity-50 font-mono truncate">{ix.torznab_url}</div>
                </button>
              ))}
            </div>
            <IndexerAddPanel form={form} setForm={setForm} picked={picked} testResult={testResult}
              busy={busy} onTest={testPicked} onAdd={addPicked} />
          </div>
        </div>
      )}
    </div>
  );
}

function IndexerAddPanel({ form, setForm, picked, testResult, busy, onTest, onAdd }) {
  if (!picked) {
    return (
      <div className="card bg-base-200 border border-base-content/10 h-fit">
        <div className="card-body text-sm opacity-50">Select an indexer from the list to configure URL, tags, Test, and Add.</div>
      </div>
    );
  }
  const urls = form.urls || (form.url ? [form.url] : []);
  return (
    <div className="card bg-base-200 border border-base-content/10 h-fit">
      <div className="card-body gap-2 p-4">
        <h3 className="font-semibold">{form.name || picked.name}</h3>
        <p className="text-xs opacity-50">Source: {picked.source || "catalog"}</p>
        {(form.tags || []).length > 0 && (
          <div className="flex flex-wrap gap-1">
            {form.tags.map(t => <span key={t} className="badge badge-outline badge-sm">{t}</span>)}
          </div>
        )}
        <label className="form-control">
          <span className="label-text text-xs">Display name</span>
          <input className="input input-bordered input-sm" value={form.name || ""}
            onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
        </label>
        <label className="form-control">
          <span className="label-text text-xs">Base / Torznab URL</span>
          {urls.length > 1 ? (
            <select className="select select-bordered select-sm font-mono text-xs" value={form.url}
              onChange={e => setForm(f => ({ ...f, url: e.target.value }))}>
              {urls.map(u => <option key={u} value={u}>{u}</option>)}
            </select>
          ) : (
            <input className="input input-bordered input-sm font-mono text-xs" value={form.url || ""}
              onChange={e => setForm(f => ({ ...f, url: e.target.value }))} />
          )}
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" className="checkbox checkbox-sm checkbox-warning"
            checked={!!form.use_flaresolverr}
            onChange={e => setForm(f => ({ ...f, use_flaresolverr: e.target.checked }))} />
          <span className="text-sm">FlareSolverr / Cloudflare tag</span>
        </label>
        <label className="form-control">
          <span className="label-text text-xs">Priority</span>
          <input type="number" className="input input-bordered input-sm w-24" value={form.priority}
            onChange={e => setForm(f => ({ ...f, priority: Number(e.target.value) || 25 }))} />
        </label>
        {picked.source === "catalog" && (
          <div className="grid grid-cols-2 gap-2">
            <input className="input input-bordered input-sm" placeholder="Username" value={form.username || ""}
              onChange={e => setForm(f => ({ ...f, username: e.target.value }))} />
            <input type="password" className="input input-bordered input-sm" placeholder="Password" value={form.password || ""}
              onChange={e => setForm(f => ({ ...f, password: e.target.value }))} />
            <input className="input input-bordered input-sm col-span-2" placeholder="Cookie (optional)" value={form.cookie || ""}
              onChange={e => setForm(f => ({ ...f, cookie: e.target.value }))} />
            <input className="input input-bordered input-sm col-span-2" placeholder="API key (optional)" value={form.api_key || ""}
              onChange={e => setForm(f => ({ ...f, api_key: e.target.value }))} />
          </div>
        )}
        {testResult && (
          <div className={"alert text-xs py-2 " + (testResult.ok ? "alert-success" : "alert-warning")}>
            {testResult.ok ? (testResult.note || "Test OK") : (testResult.error || "Test failed")}
          </div>
        )}
        <div className="flex gap-2 mt-1">
          <button type="button" className="btn btn-sm" disabled={busy} onClick={onTest}>Test</button>
          <button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={onAdd}>Add to MediaOs</button>
        </div>
      </div>
    </div>
  );
}




export { IndexersPage, IndexerAddPanel };
