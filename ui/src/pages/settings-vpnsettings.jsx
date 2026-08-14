import React, { useState, useEffect, useCallback } from "react";
import { PageChrome } from "../components/ui.jsx";

function VpnSettingsPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [providers, setProviders] = useState(null);
  const [msg, setMsg] = useState('');
  const [form, setForm] = useState({
    vpn_enabled: false,
    vpn_provider: 'gluetun',
    vpn_service_provider: 'protonvpn',
    vpn_gluetun_url: 'http://gluetun:8000',
    vpn_expected_country: '',
    vpn_kill_switch: true,
    vpn_username: '',
    vpn_password: '',
    vpn_server_countries: '',
    vpn_wireguard_private_key: '',
    vpn_port_forwarding: false,
  });

  const load = () => {
    setLoading(true);
    fetch('/api/settings/vpn').then(r=>r.json()).then(d=>{
      setData(d); setLoading(false);
      setForm(f=>({
        ...f,
        vpn_enabled: !!d.enabled,
        vpn_provider: d.provider || 'gluetun',
        vpn_gluetun_url: d.gluetun_url || f.vpn_gluetun_url,
        vpn_expected_country: d.expected_country || '',
        vpn_kill_switch: d.kill_switch !== false,
      }));
    }).catch(e => { console.warn(e); if (typeof setMsg === 'function') setMsg(String(e.message || e)); });
    fetch('/api/settings/vpn/providers').then(r=>r.json()).then(setProviders).catch(e => { console.warn(e); if (typeof setMsg === 'function') setMsg(String(e.message || e)); });
  };
  useEffect(()=>{ load(); }, []);

  async function save() {
    setMsg('');
    try {
      // Persist via setup/apply style settings group if available
      const body = { ...form };
      const r = await fetch('/api/setup/apply', {
        method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body),
      }).then(x=>x.json());
      setMsg(`Saved (${r.count||0} fields). Restart Gluetun after changing provider credentials.`);
      load();
    } catch(e) { setMsg(String(e.message||e)); }
  }

  const st = data?.status || {};
  const preset = (providers?.providers||[]).find(p => p.id === form.vpn_service_provider);

  if (loading && !data) {
    return (
      <div className="p-6 space-y-3 max-w-3xl">
        <h1 className="mr-page-title">VPN</h1>
        <div className="skeleton h-8 w-48" />
        <div className="skeleton h-32 w-full" />
        <div className="skeleton h-32 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-5 max-w-3xl">
      <div>
        <h1 className="mr-page-title">VPN / Gluetun</h1>
        <p className="text-sm opacity-60">MediaOs never embeds a VPN. Configure Gluetun (or similar) and point health checks here. Credentials are for generating Gluetun env — qBittorrent should use <code className="text-xs">network_mode: service:gluetun</code>.</p>
      </div>

      <div className={"alert text-sm "+(st.healthy?'alert-success':'alert-warning')}>
        <div>
          <div className="font-semibold">{!data?.enabled ? 'Checks disabled' : st.healthy ? 'Tunnel healthy' : 'Tunnel unhealthy / unknown'}</div>
          <div className="text-xs opacity-70">
            IP: {st.public_ip || '—'} · Country: {st.country || '—'} · Provider: {st.service_provider || st.provider || '—'}
          </div>
        </div>
      </div>
      {msg && <div className="alert alert-info text-xs py-2">{msg}</div>}

      <div className="card bg-base-200 border border-base-content/5">
        <div className="card-body p-4 gap-3">
          <label className="label cursor-pointer justify-start gap-3">
            <input type="checkbox" className="toggle toggle-primary" checked={!!form.vpn_enabled}
              onChange={e=>setForm({...form, vpn_enabled:e.target.checked})} />
            <span className="label-text">Enable VPN health checks</span>
          </label>
          <label className="label cursor-pointer justify-start gap-3">
            <input type="checkbox" className="toggle toggle-warning" checked={!!form.vpn_kill_switch}
              onChange={e=>setForm({...form, vpn_kill_switch:e.target.checked})} />
            <span className="label-text">Kill-switch — block new grabs if tunnel unhealthy</span>
          </label>

          <div className="grid sm:grid-cols-2 gap-2">
            <label className="form-control">
              <span className="label-text text-xs">Control provider</span>
              <select className="select select-bordered select-sm" value={form.vpn_provider}
                onChange={e=>setForm({...form, vpn_provider:e.target.value})}>
                <option value="gluetun">Gluetun</option>
                <option value="other">Other / public IP check</option>
              </select>
            </label>
            <label className="form-control">
              <span className="label-text text-xs">Gluetun URL</span>
              <input className="input input-bordered input-sm" value={form.vpn_gluetun_url}
                onChange={e=>setForm({...form, vpn_gluetun_url:e.target.value})} />
            </label>
            <label className="form-control">
              <span className="label-text text-xs">VPN service (credentials)</span>
              <select className="select select-bordered select-sm" value={form.vpn_service_provider}
                onChange={e=>setForm({...form, vpn_service_provider:e.target.value})}>
                {(providers?.providers||[
                  {id:'protonvpn',label:'ProtonVPN'},{id:'surfshark',label:'Surfshark'},
                  {id:'mullvad',label:'Mullvad'},{id:'nordvpn',label:'NordVPN'},
                  {id:'private internet access',label:'PIA'},{id:'expressvpn',label:'ExpressVPN'},
                  {id:'custom',label:'Custom'},
                ]).map(p=><option key={p.id} value={p.id}>{p.label||p.id}</option>)}
              </select>
            </label>
            <label className="form-control">
              <span className="label-text text-xs">Expected country (optional)</span>
              <input className="input input-bordered input-sm" placeholder="NL / Netherlands" value={form.vpn_expected_country}
                onChange={e=>setForm({...form, vpn_expected_country:e.target.value})} />
            </label>
          </div>

          {preset && <p className="text-xs opacity-60">{preset.notes}</p>}

          <div className="divider text-xs opacity-40 my-1">Credentials for Gluetun env</div>
          <div className="grid sm:grid-cols-2 gap-2">
            <label className="form-control">
              <span className="label-text text-xs">Username / account</span>
              <input className="input input-bordered input-sm" value={form.vpn_username}
                onChange={e=>setForm({...form, vpn_username:e.target.value})} autoComplete="off" />
            </label>
            <label className="form-control">
              <span className="label-text text-xs">Password / service password</span>
              <input className="input input-bordered input-sm" type="password" value={form.vpn_password}
                onChange={e=>setForm({...form, vpn_password:e.target.value})} autoComplete="new-password" />
            </label>
            <label className="form-control sm:col-span-2">
              <span className="label-text text-xs">Server countries (comma-separated)</span>
              <input className="input input-bordered input-sm" placeholder="Netherlands,Switzerland" value={form.vpn_server_countries}
                onChange={e=>setForm({...form, vpn_server_countries:e.target.value})} />
            </label>
            <label className="form-control sm:col-span-2">
              <span className="label-text text-xs">WireGuard private key (Mullvad / custom)</span>
              <input className="input input-bordered input-sm font-mono text-xs" value={form.vpn_wireguard_private_key}
                onChange={e=>setForm({...form, vpn_wireguard_private_key:e.target.value})} />
            </label>
            <label className="label cursor-pointer justify-start gap-2 sm:col-span-2">
              <input type="checkbox" className="checkbox checkbox-sm" checked={!!form.vpn_port_forwarding}
                onChange={e=>setForm({...form, vpn_port_forwarding:e.target.checked})} />
              <span className="label-text text-xs">Request port forwarding (PIA / supported providers)</span>
            </label>
          </div>

          <button type="button" className="btn btn-primary btn-sm w-fit" onClick={save}>Save VPN settings</button>
        </div>
      </div>

      <div className="card bg-base-200 border border-base-content/5">
        <div className="card-body p-4 gap-2">
          <h3 className="font-semibold text-sm">Gluetun compose snippet</h3>
          <p className="text-xs opacity-50">Copy into your stack. Attach download clients with network_mode: service:gluetun.</p>
          <pre className="bg-base-300 p-3 rounded text-[10px] overflow-x-auto whitespace-pre-wrap">
{(providers?.compose_hint) || `# set provider + OPENVPN_USER / OPENVPN_PASSWORD in gluetun environment`}
          </pre>
        </div>
      </div>
    </div>
  );
}




export default VpnSettingsPage;
export { VpnSettingsPage };
