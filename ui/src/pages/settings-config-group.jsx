import React, { useState, useEffect, useCallback } from "react";
import { PageChrome } from "../components/ui.jsx";
import Ic from "../icons.jsx";
import { api } from "../api.js";

function ConfigGroupPage({ group, title, Icon, description, setPage, hideBack }) {
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
            <button type="button" className="btn btn-primary btn-sm" disabled={saving} onClick={save}>
              {saving ? 'Saving…' : 'Save changes'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}


export default ConfigGroupPage;
export { ConfigGroupPage };
