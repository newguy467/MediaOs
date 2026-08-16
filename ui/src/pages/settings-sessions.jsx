import React, { useState, useEffect, useCallback } from "react";
import { PageChrome } from "../components/ui.jsx";
import Ic from "../icons.jsx";

function SessionsAdminPage() {
  const [sessions, setSessions] = useState([]);
  const [me, setMe] = useState(null);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const [s, m] = await Promise.all([
        fetch('/api/auth/sessions').then(r => r.ok ? r.json() : []),
        fetch('/api/auth/me').then(r => r.ok ? r.json() : null).catch(()=>null),
      ]);
      setSessions(Array.isArray(s) ? s : (s.sessions || []));
      setMe(m);
    } catch (e) {
      setMsg(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); }, []);

  async function revokeOne(prefix) {
    if (!confirm('Revoke this session?')) return;
    setBusy(true);
    try {
      await fetch('/api/auth/sessions/' + encodeURIComponent(prefix.replace(/…/g,'')), { method: 'DELETE' });
      setMsg('Session revoked');
      await load();
    } catch (e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  async function revokeOthers() {
    if (!confirm('Sign out all other devices?')) return;
    setBusy(true);
    try {
      const r = await fetch('/api/auth/sessions/revoke-others', { method: 'POST' }).then(x=>x.json());
      setMsg(`Revoked ${r.revoked||0} other sessions`);
      await load();
    } catch (e) { setMsg(String(e.message||e)); }
    setBusy(false);
  }
  function fmt(ts) {
    if (!ts) return '—';
    try { return new Date(ts * 1000).toLocaleString(); } catch { return String(ts); }
  }

  if (loading) {
    return (
      <div className="p-6 space-y-3 max-w-3xl">
        <div className="alert alert-info text-xs py-2 mb-2">Kids / restricted profiles: disable Adult and limit modules under Users & permissions. Sessions below show active logins.</div>
      <h1 className="mr-page-title">Sessions</h1>
        <p className="text-sm opacity-50">Active auth tokens</p>
        <div className="skeleton h-10 w-full" />
        <div className="skeleton h-32 w-full" />
        <div className="skeleton h-32 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-4 max-w-4xl">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="mr-page-title flex-1">Sessions</h1>
        <button type="button" className="btn btn-sm" onClick={load} disabled={busy}>Refresh</button>
        <button type="button" className="btn btn-sm btn-warning" onClick={revokeOthers} disabled={busy}>Revoke other devices</button>
      </div>
      {me && (
        <p className="text-sm opacity-70">Signed in as <span className="font-medium">{me.username}</span>
          {me.role === 'admin' && <span className="badge badge-sm badge-primary ml-2">admin</span>}
          {me.role === 'admin' && '   viewing all users'}
        </p>
      )}
      {msg && <p className="text-xs opacity-70">{msg}</p>}
      <div className="overflow-x-auto border border-base-content/10 rounded-lg">
        <table className="table table-sm">
          <thead className="bg-base-300">
            <tr>
              <th>User</th><th>Role</th><th>Token</th><th>IP</th><th>Client</th><th>Expires</th><th>Source</th><th></th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((s, i) => (
              <tr key={(s.token_prefix||'') + i} className="hover">
                <td className="font-medium">{s.username}</td>
                <td><span className="badge badge-ghost badge-sm">{s.role}</span></td>
                <td className="font-mono text-xs">{s.token_prefix}</td>
                <td className="text-xs">{s.ip || '—'}</td>
                <td className="text-xs max-w-[12rem] truncate" title={s.user_agent||''}>{s.user_agent || '—'}</td>
                <td className="text-xs whitespace-nowrap">{fmt(s.expires_at)}</td>
                <td className="text-xs">{s.source || '—'}</td>
                <td>
                  <button type="button" className="btn btn-ghost btn-xs text-error" disabled={busy}
                    onClick={() => revokeOne(s.token_prefix)}>Revoke</button>
                </td>
              </tr>
            ))}
            {!sessions.length && (
              <tr><td colSpan={8} className="opacity-50 text-sm">No active sessions (or not logged in with Bearer token)</td></tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="text-xs opacity-50">Sessions persist in the database across restarts. Admins see every user.</p>
    </div>
  );
}


export default SessionsAdminPage;
export { SessionsAdminPage };
