import React, { useState, useEffect, useCallback } from "react";
import { PageChrome } from "../components/ui.jsx";

function UsersPermissionsPage() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [catalog, setCatalog] = useState([]);
  const [msg, setMsg] = useState("");
  const [form, setForm] = useState({ username:"", password:"", role:"user", permissions:[] });
  const [editId, setEditId] = useState(null);

  function load() {
    setLoading(true);
    fetch("/api/users").then(r=>r.json()).then(d=>setUsers(Array.isArray(d)?d:(d.users||[]))).catch(()=>setUsers([])).finally(()=>setLoading(false));
    fetch("/api/users/permissions/catalog").then(r=>r.json()).then(d=>{
      setCatalog(d.permissions||[]);
      setForm(f => (!f.permissions.length && d.role_defaults?.user) ? ({...f, permissions: d.role_defaults.user}) : f);
    }).catch(e => { console.warn(e); if (typeof setMsg === 'function') setMsg(String(e.message || e)); });
  }
  useEffect(()=>{ load(); }, []);

  async function createUser() {
    setMsg("");
    const r = await fetch("/api/users", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(form) }).then(x=>x.json());
    if (r.id) { setMsg("Created "+r.username); setForm({ username:"", password:"", role:"user", permissions: form.permissions }); load(); }
    else setMsg(r.detail || r.error || JSON.stringify(r));
  }
  async function saveUser(u) {
    const r = await fetch("/api/users/"+u.id, { method:"PATCH", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ role: u.role, is_active: u.is_active, permissions: u.permissions }) }).then(x=>x.json());
    if (r.id) { setMsg("Updated "+r.username); load(); setEditId(null); }
    else setMsg(JSON.stringify(r));
  }
  async function removeUser(id) {
    if (!confirm("Delete user?")) return;
    await fetch("/api/users/"+id, { method:"DELETE" });
    load();
  }

  const groups = {};
  (catalog||[]).forEach(p=>{ (groups[p.group]=groups[p.group]||[]).push(p); });

  if (loading && !users.length) {
    return (
      <div className="p-6 space-y-3 max-w-3xl">
        <h1 className="mr-page-title">Users & permissions</h1>
        <div className="skeleton h-8 w-56" />
        <div className="skeleton h-24 w-full" />
        <div className="skeleton h-24 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="mr-page-title">Users & permissions</h1>
        <p className="mr-page-sub">Admin creates accounts and grants fine-grained rights. Role defaults apply when permissions are left empty.</p>
      </div>
      {msg && <div className="alert alert-info text-sm py-2">{msg}</div>}

      <div className="card bg-base-200"><div className="card-body p-4 space-y-3">
        <h2 className="font-semibold text-sm">Create user</h2>
        <div className="grid sm:grid-cols-3 gap-2">
          <input className="input input-bordered input-sm" placeholder="Username" value={form.username} onChange={e=>setForm({...form, username:e.target.value})} />
          <input className="input input-bordered input-sm" type="password" placeholder="Password" value={form.password} onChange={e=>setForm({...form, password:e.target.value})} />
          <select className="select select-bordered select-sm" value={form.role} onChange={e=>setForm({...form, role:e.target.value})}>
            <option value="user">User</option>
            <option value="admin">Admin</option>
          </select>
        </div>
        <div className="space-y-2">
          {Object.entries(groups).map(([g, items])=>(
            <div key={g}>
              <div className="text-[10px] uppercase opacity-40 font-semibold mb-1">{g}</div>
              <div className="flex flex-wrap gap-2">
                {items.map(p=>(
                  <label key={p.id} className="label cursor-pointer gap-1 py-0">
                    <input type="checkbox" className="checkbox checkbox-xs"
                      checked={form.permissions.includes(p.id)}
                      onChange={e=>{
                        setForm(f=>({...f, permissions: e.target.checked
                          ? [...f.permissions, p.id]
                          : f.permissions.filter(x=>x!==p.id)}));
                      }} />
                    <span className="label-text text-xs">{p.label}</span>
                  </label>
                ))}
              </div>
            </div>
          ))}
        </div>
        <button type="button" className="btn btn-primary btn-sm w-fit" onClick={createUser}>Create</button>
      </div></div>

      <div className="space-y-2">
        <h2 className="font-semibold text-sm">Accounts</h2>
        {(users||[]).map(u=>(
          <div key={u.id} className="card bg-base-200"><div className="card-body p-3 gap-2">
            <div className="flex flex-wrap items-center gap-2 justify-between">
              <div>
                <span className="font-medium">{u.username}</span>
                <span className={"badge badge-sm ml-2 "+(u.role==="admin"?"badge-primary":"badge-ghost")}>{u.role}</span>
                {!u.is_active && <span className="badge badge-sm badge-error ml-1">disabled</span>}
              </div>
              <div className="flex gap-1">
                <button type="button" className="btn btn-xs" onClick={()=>setEditId(editId===u.id?null:u.id)}>Permissions</button>
                <button type="button" className="btn btn-xs btn-ghost text-error" onClick={()=>removeUser(u.id)}>Delete</button>
              </div>
            </div>
            {editId===u.id && (
              <div className="space-y-2 border-t border-base-content/10 pt-2">
                <select className="select select-bordered select-xs" value={u.role}
                  onChange={e=>{ u.role=e.target.value; setUsers([...users]); }}>
                  <option value="user">User</option>
                  <option value="admin">Admin</option>
                </select>
                <label className="label cursor-pointer gap-2 justify-start py-0">
                  <input type="checkbox" className="checkbox checkbox-xs" checked={u.is_active}
                    onChange={e=>{ u.is_active=e.target.checked; setUsers([...users]); }} />
                  <span className="text-xs">Active</span>
                </label>
                {Object.entries(groups).map(([g, items])=>(
                  <div key={g}>
                    <div className="text-[10px] uppercase opacity-40">{g}</div>
                    <div className="flex flex-wrap gap-2">
                      {items.map(p=>(
                        <label key={p.id} className="label cursor-pointer gap-1 py-0">
                          <input type="checkbox" className="checkbox checkbox-xs"
                            checked={(u.permissions||[]).includes(p.id)}
                            onChange={e=>{
                              const perms = new Set(u.permissions||[]);
                              if (e.target.checked) perms.add(p.id); else perms.delete(p.id);
                              u.permissions = [...perms];
                              setUsers([...users]);
                            }} />
                          <span className="label-text text-xs">{p.label}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                ))}
                <button type="button" className="btn btn-primary btn-xs" onClick={()=>saveUser(u)}>Save</button>
              </div>
            )}
          </div></div>
        ))}
        {!users.length && <p className="text-sm opacity-50">No DB users yet — env admin still works. Create the first account above.</p>}
      </div>
    </div>
  );
}






export default UsersPermissionsPage;
export { UsersPermissionsPage };
