import React, { useState, useEffect, useCallback } from "react";
import { PageChrome } from "../components/ui.jsx";
import Ic from "../icons.jsx";
import { setAdvancedFlag } from "../storage.js";

function QualityPacksCard({ setPage }) {
  const [packs, setPacks] = React.useState([]);
  const [msg, setMsg] = React.useState("");
  React.useEffect(() => {
    fetch("/api/quality-ui/presets").then(r=>r.json()).then(d=>setPacks(d.packs||[])).catch(()=>{});
  }, []);
  async function apply(id) {
    setMsg("");
    try {
      const r = await fetch(`/api/quality-ui/presets/${id}/apply`, { method: "POST" }).then(async x => {
        const j = await x.json().catch(()=>({}));
        if (!x.ok) throw new Error(j.detail || x.statusText);
        return j;
      });
      setMsg("Applied " + (r.pack?.label || id));
    } catch (e) { setMsg(String(e.message || e)); }
  }
  return (
    <div className="card border border-base-content/10 bg-base-200 mb-4">
      <div className="card-body p-4 gap-2">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <h2 className="font-semibold text-sm settings-section-title" style={{textTransform:"none",letterSpacing:"normal",opacity:1}}>Quality packs</h2>
          {setPage && (
            <button type="button" className="btn btn-ghost btn-xs" onClick={() => setPage("settings-quality")}>
              Full quality
            </button>
          )}
        </div>
        <p className="text-xs opacity-60">HD / 4K / Anime presets — one app, not a second Radarr.</p>
        <div className="flex flex-wrap gap-2">
          {packs.map((p) => (
            <button key={p.id} type="button" className="btn btn-xs" onClick={() => apply(p.id)} title={p.description}>
              {p.label}
            </button>
          ))}
        </div>
        {msg && <p className="text-xs opacity-70">{msg}</p>}
      </div>
    </div>
  );
}

function PathConflictsCard({ setPage }) {
  const [data, setData] = React.useState(null);
  React.useEffect(() => {
    fetch("/api/library/path-conflicts")
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData({ issues: [], ok: true }));
  }, []);
  if (!data) return null;
  const issues = data.issues || [];
  return (
    <div className={"card border mb-4 " + (data.ok ? "border-base-content/10 bg-base-200" : "border-warning/40 bg-warning/10")}>
      <div className="card-body p-4 gap-2">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <h2 className="font-semibold text-sm settings-section-title" style={{textTransform:"none",letterSpacing:"normal",opacity:1}}>Path health</h2>
          <span className="text-xs opacity-60">
            {data.counts ? `${data.counts.error || 0} errors · ${data.counts.warning || 0} warnings` : ""}
          </span>
        </div>
        {issues.length === 0 ? (
          <p className="text-xs opacity-60">No path conflicts detected.</p>
        ) : (
          <ul className="text-xs space-y-1 list-disc pl-4">
            {issues.slice(0, 12).map((i, idx) => (
              <li key={idx} className={i.severity === "error" ? "text-error" : ""}>
                {i.message}
              </li>
            ))}
          </ul>
        )}
        <div className="flex gap-2 flex-wrap">
          {setPage && (
            <button type="button" className="btn btn-xs" onClick={() => setPage("settings-library")}>
              Paths
            </button>
          )}
          {setPage && (
            <button type="button" className="btn btn-xs btn-ghost" onClick={() => setPage("migrate")}>
              Migrate
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function SettingsHubPage({ setPage, advanced, setAdvanced, enabledModules }) {
  const em = enabledModules || ['movies','tv'];
  const groups = [
    { title: "Library", desc: "Where files live and how they are named (Jellyfin-compatible)", items: [
      { key: "settings-library", label: "Paths & naming", hint: "Library folders + movie/episode naming templates" },
      { key: "settings-quality", label: "Quality profiles", hint: "Scoring, custom formats, upgrades" },
      { key: "settings-quality-matrix", label: "Quality matrices", hint: "Resolution / source / codec / groups tables" },
    ]},
    { title: "Downloads", desc: "Clients, indexers, and queue cleanup", items: [
      { key: "settings-downloads", label: "Download clients", hint: "qBittorrent, SABnzbd, Transmission…" },
      { key: "settings-indexers", label: "Indexers", hint: "Prowlarr, Jackett, Cardigann, builtins" },
      { key: "settings-indexers-cfg", label: "Indexer connection", hint: "URLs and API keys" },
      { key: "settings-cleanup", label: "Queue cleaner", hint: "Stalls, seed limits, orphans" },
    ]},
    { title: "Media tools", desc: "Subtitles and HandBrake×Tdarr converter", items: [
      { key: "settings-subtitles", label: "Subtitles", hint: "OpenSubtitles, language profiles" },
      { key: "converter", label: "Converter queue", hint: "Transcode presets, watch folders, GPU" },
      { key: "converter-presets", label: "Converter presets", hint: "H.264 / HEVC / NVENC / QSV / AMF" },
    ]},
    { title: "Modules", desc: "Enable library types and power features", items: [
      { key: "modules", label: "Module Store", hint: "Music, Books, Comics, Live TV, Converter…" },
      { key: "settings-adult", label: "Adult library", hint: "Path, passcode, ThePornDB API key" },
      { key: "settings-hunt", label: "Hunt engine", hint: "Aggressive missing + upgrades (NeutArr-class)" },
    ]},
    { title: "Access", desc: "Who can use MediaOs and what they can do", items: [
      { key: "settings-users", label: "Users & permissions", hint: "Admin grants roles and fine-grained rights" },
      { key: "settings-auth", label: "Auth / API keys", hint: "Login, X-API-Key" },
      { key: "settings-sessions", label: "Sessions", hint: "Active tokens" },
    ]},
    { title: "Integrations", desc: "Metadata, debrid, notifications, media servers", items: [
      { key: "settings-metadata", label: "Metadata APIs", hint: "TMDb, TVDb, ComicVine, Trakt" },
      { key: "settings-debrid", label: "Debrid", hint: "Real-Debrid, TorBox, AllDebrid…" },
      { key: "settings-integrations", label: "Notifications & servers", hint: "Discord, Telegram, Jellyfin refresh" },
      { key: "settings-youtube", label: "YouTube", hint: "Creators, cookies, SponsorBlock" },
      { key: "settings-vpn", label: "VPN", hint: "Gluetun health / kill-switch" },
      { key: "settings-usenet", label: "Usenet / NNTP", hint: "NNTP streaming" },
    ]},
    { title: "Appearance & system", desc: "Look and feel, logs, wizard", items: [
      { key: "settings-themes", label: "Themes", hint: "mediaos purple and DaisyUI themes" },
      { key: "settings-system", label: "System", hint: "Search interval, upgrades, logs" },
      { key: "settings-setup", label: "Setup wizard", hint: "Re-run first-run bootstrap" },
    ]},
  ];
  // Filter groups by advanced mode + enabled modules
  const [settingsQuery, setSettingsQuery] = useState('');
  const q = (settingsQuery || '').trim().toLowerCase();
  const filtered = groups.map(g => {
    let items = g.items.filter(it => {
      if (it.key === 'settings-quality-matrix' && !advanced) return false;
      if ((it.key === 'converter' || it.key === 'converter-presets') && !em.includes('converter') && !advanced) return false;
      if (it.key === 'settings-adult' && !em.includes('adult')) return false;
      if (it.key === 'settings-youtube' && !em.includes('youtube')) return false;
      return true;
    });
    return { ...g, items };
  }).filter(g => g.items.length > 0);

  return (
    <div className="space-y-5 max-w-5xl">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1 space-y-2">
          <h1 className="mr-page-title">Settings</h1>
          <p className="mr-page-sub">Grouped by area — changes apply immediately (no restart).</p>
          <input
            className="input input-bordered input-sm w-full max-w-sm"
            placeholder="Filter settings…"
            value={settingsQuery}
            onChange={(e) => setSettingsQuery(e.target.value)}
          />
        </div>
        <div className="card bg-base-200 border border-base-content/10 shadow-sm">
          <div className="card-body p-3 flex-row items-center gap-3">
            <div className="text-xs">
              <div className="font-semibold">{advanced ? 'Advanced' : 'Basic'} mode</div>
              <div className="opacity-50">Power tools &amp; extra modules</div>
            </div>
            <input type="checkbox" className="toggle toggle-primary" checked={!!advanced}
              onChange={e=>{ const v=e.target.checked; setAdvancedFlag(v); setAdvanced && setAdvanced(v); }} />
          </div>
        </div>
      </div>
      <QualityPacksCard setPage={setPage} />
      <PathConflictsCard setPage={setPage} />
      {(q ? filtered.map(g => ({...g, items: (g.items||[]).filter(it =>
      !q || (it.label||"").toLowerCase().includes(q) || (it.hint||"").toLowerCase().includes(q) || (g.title||"").toLowerCase().includes(q)
    )})).filter(g => (g.items||[]).length) : filtered).map(g=>(
        <div key={g.title} className="space-y-2">
          <div>
            <h2 className="font-semibold text-sm tracking-wide uppercase opacity-70">{g.title}</h2>
            <p className="text-xs opacity-50">{g.desc}</p>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {g.items.map(it=>(
              <button key={it.key} type="button"
                className="card bg-base-200 hover:bg-base-300 text-left border border-base-content/5 hover:border-primary/40 transition-all hover:shadow-md"
                onClick={()=>setPage && setPage(it.key)}>
                <div className="card-body p-3 gap-0.5">
                  <div className="font-medium text-sm">{it.label}</div>
                  <div className="text-xs opacity-50 leading-snug settings-hint">{it.hint}</div>
                </div>
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}


export default SettingsHubPage;
export { SettingsHubPage };
