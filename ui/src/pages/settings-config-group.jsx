import { useState, useEffect } from "react";
import { api } from "../api.js";

function ConfigGroupPage({ group, title, Icon, description, setPage, hideBack }) {
  const [fields, setFields] = useState(null);
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null);
  const [helpMap, setHelpMap] = useState({});

  const load = () => {
    api.settings.getConfig(group).then(data=>{
      setFields(data);
      const f = {};
      for (const k in data) f[k] = data[k].value ?? '';
      setForm(f);
    }).catch(()=>setFields({}));
  };
  useEffect(() => { load(); }, [group]);
  useEffect(() => {
    fetch("/api/tools/settings-help")
      .then((r) => r.json())
      .then((d) => {
        const m = { ...(d.paths || {}), ...(d.clients || {}) };
        // paths is keyed by field id with {label, help}
        const flat = {};
        for (const [k, v] of Object.entries(d.paths || {})) {
          flat[k] = typeof v === "object" ? v.help : v;
        }
        setHelpMap(flat);
      })
      .catch(() => {});
  }, []);

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
      {!fields ? (
        <div className="space-y-3">
          <div className="skeleton h-10 w-full max-w-md" />
          <div className="skeleton h-10 w-full max-w-md" />
          <div className="skeleton h-10 w-3/4 max-w-sm" />
          <div className="skeleton h-24 w-full max-w-md" />
        </div>
      ) : Object.keys(fields).length===0 ? (
        <div className="card bg-base-200 border border-dashed border-base-content/20 max-w-md">
          <div className="card-body items-center text-center py-12 gap-4">
            <div className="w-12 h-12 text-base-content/20"><Icon /></div>
            <p className="text-base-content/50 text-sm">Nothing configurable in this group.</p>
          </div>
        </div>
      ) : (
        <div className="mr-panel p-5 space-y-4">
          {msg && <div className="alert alert-info text-sm py-2">{msg}</div>}
          {(() => {
            const entries = Object.entries(fields);
            const isLib = group === "library";
            const pathKeys = new Set([
              "movies_library_path","tv_library_path","music_library_path","books_library_path",
              "audiobooks_library_path","podcasts_library_path","comics_library_path","manga_library_path",
              "youtube_library_path","adult_library_path","downloads_path","games_library_path",
            ]);
            const namingKeys = new Set(["movie_naming_folder","episode_naming","library_prefer_hardlink"]);
            const renderField = ([key, meta]) => (
              <div key={key} className="form-control">
                <label className="label py-1 gap-2 items-center flex-wrap">
                  <span className="label-text text-sm">{meta.label}</span>
                  <span className="tooltip tooltip-right max-w-xs" data-tip={meta.help || helpMap[key] || "Applies immediately, no restart."}>
                    <button type="button" className="btn btn-ghost btn-xs btn-circle" aria-label="Help">?</button>
                  </span>
                </label>
                {typeof meta.value === "boolean" || form[key] === true || form[key] === false ? (
                  <input type="checkbox" className="toggle toggle-sm"
                    checked={!!form[key]} onChange={(e) => setVal(key, e.target.checked)} />
                ) : (
                  <input
                    type={meta.secret ? "password" : "text"}
                    className="input input-bordered input-sm w-full font-mono text-sm"
                    value={form[key] ?? ""}
                    placeholder={meta.placeholder || ""}
                    onChange={(e) => setVal(key, e.target.value)}
                  />
                )}
              </div>
            );
            if (!isLib) {
              return <div className="grid gap-4 sm:grid-cols-2">{entries.map(renderField)}</div>;
            }
            const paths = entries.filter(([k]) => pathKeys.has(k));
            const naming = entries.filter(([k]) => namingKeys.has(k));
            const rest = entries.filter(([k]) => !pathKeys.has(k) && !namingKeys.has(k));
            return (
              <>
                <h3 className="text-xs font-semibold uppercase opacity-60 tracking-wide">Library paths</h3>
                <div className="grid gap-4 sm:grid-cols-2">{paths.map(renderField)}</div>
                <h3 className="text-xs font-semibold uppercase opacity-60 tracking-wide pt-2">Naming templates</h3>
                <div className="grid gap-4 sm:grid-cols-1">{naming.map(renderField)}</div>
                {rest.length > 0 && (
                  <>
                    <h3 className="text-xs font-semibold uppercase opacity-60 tracking-wide pt-2">Other</h3>
                    <div className="grid gap-4 sm:grid-cols-2">{rest.map(renderField)}</div>
                  </>
                )}
              </>
            );
          })()}
          <div className="pt-2 flex flex-wrap gap-2 items-center">
            <button type="button" className="btn btn-primary btn-sm" disabled={saving} onClick={save}>
              {saving ? 'Saving…' : 'Save changes'}
            </button>
            {group === "downloads" && (
              <button
                type="button"
                className="btn btn-outline btn-sm"
                disabled={saving}
                onClick={async () => {
                  setSaving(true); setMsg(null);
                  try {
                    const r = await fetch("/api/tools/clients/apply", {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({
                        qbit_url: form.qbit_url,
                        qbit_user: form.qbit_username,
                        qbit_pass: form.qbit_password,
                        sab_url: form.sabnzbd_url,
                        sab_api_key: form.sabnzbd_api_key,
                        push_qb_categories: true,
                      }),
                    }).then(async (x) => {
                      const j = await x.json().catch(() => ({}));
                      if (!x.ok) throw new Error(j.detail || x.statusText);
                      return j;
                    });
                    setMsg("Client apply: " + (r.ok ? "OK" : "check response") + (r.qb?.error ? " — qB: " + r.qb.error : ""));
                  } catch (e) {
                    setMsg(String(e.message || e));
                  }
                  setSaving(false);
                }}
              >
                Apply client categories
              </button>
            )}
            {setPage && !hideBack && (
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setPage("settings-hub")}>
                Back to Settings
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}


export default ConfigGroupPage;
export { ConfigGroupPage };
