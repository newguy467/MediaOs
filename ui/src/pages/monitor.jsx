import { useState, useEffect } from "react";

function fmtBytes(n) {
  if (n == null) return '—';
  const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB'];
  let u = 0, v = n;
  while (v >= 1024 && u < units.length - 1) { v /= 1024; u++; }
  return `${v.toFixed(v < 10 && u > 0 ? 1 : 0)} ${units[u]}`;
}

function fmtNum(n) {
  if (n == null) return '—';
  return n.toLocaleString();
}

function fmtAgo(iso) {
  if (!iso) return '—';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '—';
  const days = Math.floor((Date.now() - then) / 86400000);
  if (days <= 0) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 14) return `${days} days ago`;
  return `${Math.floor(days / 7)} weeks ago`;
}

function StatCard({ label, value, sub, Icon }) {
  return (
    <div className="card bg-base-200 border border-base-content/5">
      <div className="card-body p-4 flex-row items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs opacity-60">{label}</div>
          <div className="text-2xl font-bold tabular-nums">{fmtNum(value)}</div>
          {sub && <div className="text-xs opacity-50 mt-0.5">{sub}</div>}
        </div>
        {Icon && <Icon className="w-6 h-6 opacity-30 shrink-0" />}
      </div>
    </div>
  );
}

function UsageBar({ label, sub, percent, usedLabel }) {
  const pct = Math.max(0, Math.min(100, percent || 0));
  const warn = pct >= 90;
  const caution = pct >= 75 && pct < 90;
  const barClass = warn ? 'progress-error' : caution ? 'progress-warning' : 'progress-primary';
  return (
    <div className="text-xs">
      <div className="flex justify-between items-baseline gap-2">
        <span className="font-medium truncate">{label}</span>
        {sub && <span className="opacity-50 truncate">{sub}</span>}
      </div>
      <div className="flex items-center gap-2 mt-0.5">
        <progress className={"progress w-full h-2 " + barClass} value={pct} max="100" />
        <span className="tabular-nums opacity-70 shrink-0 w-28 text-right">{usedLabel}</span>
      </div>
    </div>
  );
}

function SystemMonitorPage({ setPage }) {
  const [data, setData] = useState(null);
  const [msg, setMsg] = useState(null);
  const load = () => {
    fetch('/api/monitor').then(r => r.json()).then(setData).catch(e => setMsg(String(e.message || e)));
  };
  useEffect(() => { load(); const i = setInterval(load, 30000); return () => clearInterval(i); }, []);

  const lib = data?.library || {};
  const folders = data?.storage?.folders || [];
  const host = data?.host || {};
  const cpuMem = host.cpu_mem || {};
  const mounts = host.mounts || [];
  const smart = host.smart || {};

  return (
    <div className="page-shell space-y-6 max-w-5xl">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="mr-page-title">System Monitor</h1>
          <p className="mr-page-sub">Library size, storage, and container health in one place</p>
        </div>
        <button type="button" className="btn btn-sm btn-ghost" onClick={load}>Refresh</button>
      </div>

      {msg && <div className="alert alert-warning text-xs py-2">{msg}</div>}
      {!data && !msg && <span className="loading loading-spinner" />}

      {data && (
        <>
          {/* ── Library overview ─────────────────────────────────────────── */}
          <section className="space-y-2">
            <h2 className="text-sm font-semibold opacity-70">Library</h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
              <StatCard label="Movies" value={lib.movies} />
              <StatCard label="Series" value={lib.series} sub={lib.episodes != null ? `${fmtNum(lib.episodes)} episodes` : null} />
              <StatCard label="Episodes" value={lib.episodes} />
              <StatCard label="Albums" value={lib.albums} sub={lib.songs != null ? `${fmtNum(lib.songs)} songs` : null} />
              <StatCard label="Songs" value={lib.songs} />
              <StatCard label="Collections" value={lib.collections} />
            </div>
          </section>

          {/* ── Storage ──────────────────────────────────────────────────── */}
          <section className="space-y-2">
            <div className="flex justify-between items-center">
              <h2 className="text-sm font-semibold opacity-70">Storage</h2>
              <button type="button" className="btn btn-xs btn-ghost" onClick={() => setPage && setPage('backup')}>Manage</button>
            </div>
            <div className="card bg-base-200 border border-base-content/5">
              <div className="card-body p-4 gap-3">
                {!folders.length && <p className="text-xs opacity-50">No library folders mounted yet</p>}
                {folders.map(f => (
                  <UsageBar
                    key={f.id}
                    label={f.label}
                    sub={f.path}
                    percent={f.total ? (f.used / f.total) * 100 : 0}
                    usedLabel={`${fmtBytes(f.used)} / ${fmtBytes(f.total)}`}
                  />
                ))}
              </div>
            </div>
          </section>

          {/* ── Host health ──────────────────────────────────────────────── */}
          <section className="space-y-2">
            <h2 className="text-sm font-semibold opacity-70">
              {cpuMem.source === 'host' ? 'Host health' : 'Container health'}
            </h2>
            {!cpuMem.available && (
              <p className="text-xs opacity-50">CPU/memory stats unavailable in this environment.</p>
            )}
            {cpuMem.available && cpuMem.source !== 'host' && (
              <p className="text-xs opacity-50">
                Showing MediaOS's own container view. For real host-level numbers, mount host
                <code className="mx-1">/proc</code> and <code className="mx-1">/sys</code> read-only —
                see the commented block in <code>docker-compose.yml</code>.
              </p>
            )}
            {cpuMem.available && (
              <div className="grid sm:grid-cols-2 gap-3">
                <div className="card bg-base-200 border border-base-content/5">
                  <div className="card-body p-4 gap-2">
                    <UsageBar label="CPU load" percent={cpuMem.cpu_percent} usedLabel={`${(cpuMem.cpu_percent ?? 0).toFixed(0)}%`} />
                    <UsageBar label="Memory" percent={cpuMem.memory_percent} usedLabel={`${fmtBytes(cpuMem.memory_used)} / ${fmtBytes(cpuMem.memory_total)}`} />
                    {cpuMem.cpu_temp_c != null && (
                      <div className="text-xs flex justify-between"><span className="opacity-70">CPU temp</span><span className="tabular-nums">{cpuMem.cpu_temp_c.toFixed(1)} °C</span></div>
                    )}
                    <div className="text-xs flex justify-between"><span className="opacity-70">Last boot</span><span>{fmtAgo(cpuMem.last_boot)}</span></div>
                  </div>
                </div>
                <div className="card bg-base-200 border border-base-content/5">
                  <div className="card-body p-4 gap-2">
                    <div className="text-xs font-medium opacity-70 mb-1">Mounts</div>
                    {mounts.map(m => (
                      <UsageBar key={m.path} label={m.label} sub={m.path} percent={m.percent} usedLabel={`${fmtBytes(m.used)} / ${fmtBytes(m.total)}`} />
                    ))}
                    {!mounts.length && <p className="text-xs opacity-50">No mount data</p>}
                  </div>
                </div>
              </div>
            )}
          </section>

          {/* ── SMART ────────────────────────────────────────────────────── */}
          <section className="space-y-2">
            <h2 className="text-sm font-semibold opacity-70">Disk SMART</h2>
            <div className="card bg-base-200 border border-base-content/5">
              <div className="card-body p-4 gap-2 text-xs">
                {!smart.configured && (
                  <p className="opacity-50">
                    Not configured — set <code>SMART_DEVICES</code> in <code>.env</code> and uncomment the device
                    mappings under the mediaos service in <code>docker-compose.yml</code> to enable.
                  </p>
                )}
                {smart.configured && !smart.disks?.length && (
                  <p className="opacity-50">{smart.reason || 'No disk data'}</p>
                )}
                {(smart.disks || []).map(d => (
                  <div key={d.device} className="flex flex-wrap items-center gap-3 py-1 border-b border-base-content/5 last:border-0">
                    <span className="font-mono w-24 shrink-0">{d.device}</span>
                    <span className={"badge badge-sm " + (d.status === 'OK' ? 'badge-success' : d.status === 'Problem' ? 'badge-error' : 'badge-ghost')}>
                      {d.status}
                    </span>
                    {d.bad_sectors != null && <span className="opacity-70">Bad sectors: {fmtNum(d.bad_sectors)}</span>}
                    {d.temp_c != null && <span className="opacity-70">{d.temp_c.toFixed(0)} °C</span>}
                    {d.reason && <span className="opacity-40 truncate">{d.reason}</span>}
                  </div>
                ))}
              </div>
            </div>
          </section>
        </>
      )}
    </div>
  );
}

export default SystemMonitorPage;
