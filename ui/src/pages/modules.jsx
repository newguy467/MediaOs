import React, { useState, useEffect, useMemo } from "react";

function ModuleStorePage({ enabledModules, setEnabledModules, setPage }) {
  const [tab, setTab] = useState("modules"); // modules | marketplace | installed | github
  const [catalog, setCatalog] = useState([]);
  const [market, setMarket] = useState(null);
  const [busy, setBusy] = useState(null);
  const [msg, setMsg] = useState("");
  const [ghRepo, setGhRepo] = useState("");
  const [ghRef, setGhRef] = useState("main");
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("all");
  const [showInstalledOnly, setShowInstalledOnly] = useState(false);
  const [conflicts, setConflicts] = useState([]);
  const [modFilter, setModFilter] = useState("all"); // all | on | off
  const [modCategory, setModCategory] = useState("all");
  const [modQuery, setModQuery] = useState("");

  const loadModules = () => {
    fetch("/api/modules")
      .then((r) => r.json())
      .then((d) => {
        setCatalog(d.catalog || []);
        if (d.enabled) setEnabledModules(d.enabled);
        setConflicts(d.conflicts || []);
      })
      .catch((e) => setMsg(String(e)));
  };

  const loadMarket = () => {
    fetch("/api/plugins/marketplace")
      .then((r) => r.json())
      .then((d) => setMarket(d))
      .catch((e) => setMsg(String(e)));
  };

  useEffect(() => {
    loadModules();
    loadMarket();
  }, []);

  const toggleModule = async (id, currentlyOn, isCore) => {
    if (isCore) return;
    setBusy(id);
    setMsg("");
    try {
      const path = currentlyOn ? `/api/modules/${id}/disable` : `/api/modules/${id}/enable`;
      const r = await fetch(path, { method: "POST" }).then((x) => x.json());
      if (r.enabled) setEnabledModules(r.enabled);
      loadModules();
      setMsg(currentlyOn ? `Disabled ${id}` : `Enabled ${id}`);
    } catch (e) {
      setMsg(String(e.message || e));
    }
    setBusy(null);
  };

  const installCatalog = async (id) => {
    setBusy(id);
    setMsg("");
    try {
      const r = await fetch(`/api/plugins/marketplace/${encodeURIComponent(id)}/install`, {
        method: "POST",
      }).then(async (x) => {
        const j = await x.json().catch(() => ({}));
        if (!x.ok) throw new Error(j.detail || x.statusText);
        return j;
      });
      setMsg(`Installed ${r.id} → ${r.path}${r.loaded ? " (loaded)" : ""}`);
      loadMarket();
    } catch (e) {
      setMsg(String(e.message || e));
    }
    setBusy(null);
  };

  const installGithub = async () => {
    if (!ghRepo.trim()) return;
    setBusy("github");
    setMsg("");
    try {
      const r = await fetch("/api/plugins/install/github", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo: ghRepo.trim(), ref: ghRef.trim() || "main" }),
      }).then(async (x) => {
        const j = await x.json().catch(() => ({}));
        if (!x.ok) throw new Error(j.detail || x.statusText);
        return j;
      });
      setMsg(`Installed from GitHub: ${r.id || r.path || "ok"}`);
      setGhRepo("");
      loadMarket();
    } catch (e) {
      setMsg(String(e.message || e));
    }
    setBusy(null);
  };

  const togglePluginEnabled = async (id, currentlyEnabled) => {
    setBusy(id);
    setMsg("");
    try {
      const path = currentlyEnabled
        ? `/api/plugins/${encodeURIComponent(id)}/disable`
        : `/api/plugins/${encodeURIComponent(id)}/enable`;
      const r = await fetch(path, { method: "POST" }).then(async (x) => {
        const j = await x.json().catch(() => ({}));
        if (!x.ok) throw new Error(j.detail || x.statusText);
        return j;
      });
      setMsg(`${id} ${r.enabled ? "enabled" : "disabled"}`);
      loadMarket();
    } catch (e) {
      setMsg(String(e.message || e));
    }
    setBusy(null);
  };

  const reinstallCatalog = async (id) => {
    setBusy(id);
    setMsg("");
    try {
      const r = await fetch(`/api/plugins/marketplace/${encodeURIComponent(id)}/reinstall`, {
        method: "POST",
      }).then(async (x) => {
        const j = await x.json().catch(() => ({}));
        if (!x.ok) throw new Error(j.detail || x.statusText);
        return j;
      });
      setMsg(`Reinstalled ${r.id}${r.loaded ? " (loaded)" : ""}`);
      loadMarket();
    } catch (e) {
      setMsg(String(e.message || e));
    }
    setBusy(null);
  };

  const uninstall = async (id) => {
    if (!confirm(`Remove plugin ${id}?`)) return;
    setBusy(id);
    try {
      await fetch(`/api/plugins/${encodeURIComponent(id)}`, { method: "DELETE" }).then((x) => x.json());
      setMsg(`Removed ${id}`);
      loadMarket();
    } catch (e) {
      setMsg(String(e.message || e));
    }
    setBusy(null);
  };

  const refreshCatalog = async () => {
    setBusy("refresh");
    setMsg("");
    try {
      const r = await fetch("/api/plugins/marketplace/refresh", { method: "POST" }).then(async (x) => {
        const j = await x.json().catch(() => ({}));
        if (!x.ok) throw new Error(j.detail || x.statusText);
        return j;
      });
      setMarket(r);
      setMsg(`Catalog refreshed · ${(r.items || []).length} plugins · source: ${r.catalog_source || "?"}`);
    } catch (e) {
      setMsg(String(e.message || e));
    }
    setBusy(null);
  };

  const core = catalog.filter((m) => m.core);
  const optional = catalog.filter((m) => !m.core);

  const marketItems = useMemo(() => {
    let items = market?.items || [];
    if (showInstalledOnly) {
      items = items.filter((p) => p.installed);
    }
    if (category !== "all") {
      items = items.filter((p) => (p.category || "other") === category);
    }
    if (q.trim()) {
      const s = q.trim().toLowerCase();
      items = items.filter(
        (p) =>
          (p.name || "").toLowerCase().includes(s) ||
          (p.description || "").toLowerCase().includes(s) ||
          (p.id || "").toLowerCase().includes(s) ||
          (p.tags || []).some((t) => String(t).toLowerCase().includes(s))
      );
    }
    return items;
  }, [market, q, category, showInstalledOnly]);

  const renderModuleCard = (m) => {
    const on = m.enabled || (enabledModules || []).includes(m.id);
    const needsPath = on && m.needs_path_setup;
    return (
      <div
        key={m.id}
        className={
          "card bg-base-200 shadow-sm border " +
          (needsPath ? "border-warning/50 " : on ? "border-primary/40 " : "border-transparent ")
        }
      >
        <div className="card-body p-4 gap-2">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <h3 className="font-semibold flex items-center gap-2 flex-wrap text-sm">
                {m.label}
                {m.core && <span className="badge badge-primary badge-xs">Required</span>}
                {on && !m.core && <span className="badge badge-success badge-xs">On</span>}
                {!on && !m.core && <span className="badge badge-ghost badge-xs">Off</span>}
                {m.category && m.category !== "core" && (
                  <span className="badge badge-outline badge-xs opacity-70">{m.category}</span>
                )}
              </h3>
              <p className="text-xs opacity-60 mt-1">{m.description}</p>
              {(m.tags || []).length > 0 && (
                <p className="text-[10px] opacity-40 mt-1 flex flex-wrap gap-1">
                  {(m.tags || []).map((tag) => (
                    <span key={tag} className="badge badge-ghost badge-xs">{tag}</span>
                  ))}
                </p>
              )}
            </div>
            <input
              type="checkbox"
              className="toggle toggle-primary shrink-0"
              checked={!!on}
              disabled={!!m.core || busy === m.id}
              title={m.core ? "Movies and TV cannot be disabled" : on ? "Disable" : "Enable"}
              onChange={() => toggleModule(m.id, on, m.core)}
            />
          </div>
          {m.requires_path && (
            <div className={"text-[10px] rounded px-2 py-1 " + (needsPath ? "bg-warning/20 text-warning-content" : "opacity-50")}>
              {needsPath ? "⚠ Set path: " : "Path: "}
              <code>{m.path_label || m.requires_path}</code>
              {needsPath && setPage && (
                <button type="button" className="btn btn-ghost btn-xs ml-2" onClick={() => setPage("settings")}>
                  Settings
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    );
  };

  const renderMarketCard = (p) => (
    <div
      key={p.id}
      className={
        "card bg-base-200 shadow-sm border " + (p.installed ? "border-success/40" : "border-transparent")
      }
    >
      <div className="card-body p-4 gap-2">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="font-semibold flex items-center gap-2 flex-wrap text-sm">
              {p.name}
              {p.official && <span className="badge badge-info badge-xs">Official</span>}
              {p.installed && <span className="badge badge-success badge-xs">Installed</span>}
              {p.loaded && <span className="badge badge-primary badge-xs">Loaded</span>}
              {p.online_required === false && <span className="badge badge-accent badge-xs">Offline OK</span>}
              {p.online_required && !p.installed && <span className="badge badge-ghost badge-xs">Needs GitHub</span>}
              {p.update_available && <span className="badge badge-warning badge-xs">Update</span>}
              {p.enabled === false && <span className="badge badge-ghost badge-xs">Disabled</span>}
              {p.trust_allowlist_active && p.trusted === false && (
                <span className="badge badge-error badge-xs">Untrusted owner</span>
              )}
              {p.category && <span className="badge badge-ghost badge-xs">{p.category}</span>}
            </h3>
            <p className="text-xs opacity-60 mt-1">{p.description}</p>
            <p className="text-[10px] opacity-40 mt-1">
              {p.id} · v{p.installed_version || p.version || "?"}
              {p.author ? ` · ${p.author}` : ""}
            </p>
            {p.tags?.length > 0 && (
              <p className="text-[10px] opacity-40 mt-0.5">{p.tags.join(" · ")}</p>
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-2 mt-1">
          {p.install_type === "builtin" || p.status === "builtin" ? (
            <button
              type="button"
              className="btn btn-primary btn-xs"
              onClick={() => setPage && setPage("homelab")}
            >
              Open Homelab
            </button>
          ) : !p.installed ? (
            <button
              type="button"
              className="btn btn-primary btn-xs"
              disabled={busy === p.id || (p.trust_allowlist_active && p.trusted === false)}
              onClick={() => installCatalog(p.id)}
            >
              {busy === p.id ? "Installing…" : "Install"}
            </button>
          ) : (
            <>
              <button
                type="button"
                className="btn btn-ghost btn-xs"
                disabled={busy === p.id || (p.id || "").startsWith("core.")}
                onClick={() => togglePluginEnabled(p.id, p.enabled !== false)}
              >
                {p.enabled === false ? "Enable" : "Disable"}
              </button>
              {p.update_available && (
                <button
                  type="button"
                  className="btn btn-warning btn-xs"
                  disabled={busy === p.id}
                  onClick={() => reinstallCatalog(p.id)}
                >
                  Update
                </button>
              )}
              <button
                type="button"
                className="btn btn-ghost btn-xs"
                disabled={busy === p.id || (p.id || "").startsWith("core.")}
                onClick={() => reinstallCatalog(p.id)}
              >
                Reinstall
              </button>
              <button
                type="button"
                className="btn btn-ghost btn-xs"
                disabled={busy === p.id || (p.id || "").startsWith("core.")}
                onClick={() => uninstall(p.id)}
              >
                Uninstall
              </button>
            </>
          )}
          {p.github && (
            <a className="btn btn-ghost btn-xs" href={p.github} target="_blank" rel="noreferrer">
              GitHub
            </a>
          )}
        </div>
      </div>
    </div>
  );

  return (
    <div className="space-y-4 max-w-5xl">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="mr-page-title">Module &amp; Plugin Store</h1>
          <p className="text-sm opacity-60">
            Built-in libraries (Movies/TV required) plus community plugins from a GitHub-backed catalog.
          </p>
        </div>
        <div className="flex gap-2">
          <button type="button" className="btn btn-sm btn-ghost" onClick={() => { loadModules(); loadMarket(); }}>
            Reload
          </button>
          <button type="button" className="btn btn-sm" onClick={() => setPage && setPage("settings-hub")}>
            Settings
          </button>
        </div>
      </div>

      <div className="tabs tabs-boxed w-fit flex-wrap">
        <button type="button" className={"tab " + (tab === "modules" ? "tab-active" : "")} onClick={() => setTab("modules")}>
          Built-in modules
        </button>
        <button type="button" className={"tab " + (tab === "marketplace" ? "tab-active" : "")} onClick={() => setTab("marketplace")}>
          Community plugins
        </button>
        <button type="button" className={"tab " + (tab === "installed" ? "tab-active" : "")} onClick={() => setTab("installed")}>
          Installed
          {market?.installed_count != null && (
            <span className="badge badge-sm ml-1">{market.installed_count}</span>
          )}
        </button>
        <button type="button" className={"tab " + (tab === "github" ? "tab-active" : "")} onClick={() => setTab("github")}>
          Install from GitHub
        </button>
      </div>

      {msg && <div className="alert alert-info text-xs py-2">{msg}</div>}

      {tab === "modules" && (
        <div className="space-y-4">
          <p className="text-sm opacity-60">
            Add or remove capabilities in one control plane — Movies &amp; TV stay on. Toggle optional modules like a store shelf.
          </p>
          {conflicts.length > 0 && (
            <div className="alert alert-warning text-xs py-2">
              <div>
                <p className="font-semibold">Conflicts</p>
                <ul className="list-disc pl-4 mt-1">
                  {conflicts.map((c, i) => (
                    <li key={i}>{c.message || JSON.stringify(c)}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}
          <div className="flex flex-wrap gap-2 items-center">
            <input
              className="input input-bordered input-sm flex-1 min-w-[10rem]"
              placeholder="Search modules…"
              value={modQuery}
              onChange={(e) => setModQuery(e.target.value)}
            />
            {["all", "on", "off"].map((f) => (
              <button
                key={f}
                type="button"
                className={"btn btn-xs " + (modFilter === f ? "btn-primary" : "btn-ghost")}
                onClick={() => setModFilter(f)}
              >
                {f === "all" ? "All" : f === "on" ? "Enabled" : "Disabled"}
              </button>
            ))}
            <button
              type="button"
              className={"btn btn-xs " + (modCategory === "all" ? "btn-primary" : "btn-ghost")}
              onClick={() => setModCategory("all")}
            >
              All categories
            </button>
            {[...new Set(catalog.map((m) => m.category).filter(Boolean))].map((c) => (
              <button
                key={c}
                type="button"
                className={"btn btn-xs " + (modCategory === c ? "btn-primary" : "btn-ghost")}
                onClick={() => setModCategory(c)}
              >
                {c}
              </button>
            ))}
          </div>
          {core.length > 0 && (
            <div className="space-y-2">
              <h2 className="text-sm font-semibold opacity-70 uppercase tracking-wide">Core (always on)</h2>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{core.map(renderModuleCard)}</div>
            </div>
          )}
          <div className="space-y-2">
            <h2 className="text-sm font-semibold opacity-70 uppercase tracking-wide">Store — add or remove</h2>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {optional
                .filter((m) => {
                  const on = m.enabled || (enabledModules || []).includes(m.id);
                  if (modFilter === "on" && !on) return false;
                  if (modFilter === "off" && on) return false;
                  if (modCategory !== "all" && (m.category || "") !== modCategory) return false;
                  if (modQuery.trim()) {
                    const s = modQuery.trim().toLowerCase();
                    const blob = `${m.label} ${m.description} ${m.id} ${(m.tags || []).join(" ")}`.toLowerCase();
                    if (!blob.includes(s)) return false;
                  }
                  return true;
                })
                .map(renderModuleCard)}
            </div>
          </div>
          <p className="text-xs opacity-50">
            Disabling only hides the module from the sidebar; library data stays on disk. Set library paths under Settings when a card warns. Plugins (community) live on the other tabs.
          </p>
        </div>
      )}

      {tab === "marketplace" && (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2 items-center justify-between">
            <p className="text-xs opacity-60">
              Catalog: <strong>{market?.catalog_name || "—"}</strong>
              {market?.catalog_updated && <> · updated {market.catalog_updated}</>}
              {market?.plugins_path && (
                <>
                  {" "}
                  · install path: <code className="text-[10px]">{market.plugins_path}</code>
                </>
              )}
              {market?.catalog_source && (
                <span className="block sm:inline sm:ml-1 opacity-50 truncate max-w-md">
                  source: {market.catalog_source}
                </span>
              )}
            </p>
            <button
              type="button"
              className="btn btn-xs"
              disabled={busy === "refresh"}
              onClick={refreshCatalog}
            >
              {busy === "refresh" ? "Refreshing…" : "Refresh catalog"}
            </button>
          </div>

          <div className="flex flex-wrap gap-2 items-center">
            <input
              className="input input-bordered input-sm flex-1 min-w-[12rem]"
              placeholder="Search plugins…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
            <label className="flex items-center gap-1 text-xs opacity-70 cursor-pointer">
              <input
                type="checkbox"
                className="checkbox checkbox-xs"
                checked={showInstalledOnly}
                onChange={(e) => setShowInstalledOnly(e.target.checked)}
              />
              Installed only
            </label>
            <div className="flex flex-wrap gap-1">
              <button
                type="button"
                className={"btn btn-xs " + (category === "all" ? "btn-primary" : "btn-ghost")}
                onClick={() => setCategory("all")}
              >
                All
              </button>
              {(market?.categories || []).map((c) => (
                <button
                  key={c}
                  type="button"
                  className={"btn btn-xs " + (category === c ? "btn-primary" : "btn-ghost")}
                  onClick={() => setCategory(c)}
                >
                  {c}
                </button>
              ))}
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">{marketItems.map(renderMarketCard)}</div>
          {!marketItems.length && (
            <p className="text-sm opacity-50">
              No matching plugins. Set <code>plugin_registry_url</code> to a GitHub raw JSON catalog, or ship{" "}
              <code>data/plugin_catalog/catalog.json</code>.
            </p>
          )}
          <p className="text-xs opacity-50">
            Plugins need <code>mediaos.plugin.json</code> + <code>plugin.py</code> with{" "}
            <code>register_plugin()</code>. Spec: <code>data/plugin_catalog/PLUGIN_SPEC.md</code>.
            Only install plugins you trust — they run in-process.
            Catalog entries marked <strong>Needs GitHub</strong> require network and a real repo;
            <strong> Offline OK</strong> (bundled example) works without internet.
            Set <code>plugin_registry_url</code> in Settings for your own GitHub raw catalog.
          </p>
        </div>
      )}

      {tab === "github" && (
        <div className="card bg-base-200 border border-base-content/10 max-w-xl">
          <div className="card-body gap-3">
            <h2 className="card-title text-base">Install from any GitHub repo</h2>
            <p className="text-xs opacity-60">
              Downloads the repo zip and loads it when a MediaOS plugin manifest is present. Public GitHub works without a token; set <code>GITHUB_TOKEN</code> for rate limits / private repos. Optional allowlist: Settings → <code>plugin_trusted_owners</code> (comma-separated GitHub orgs/users).
            </p>
            <label className="form-control">
              <span className="label-text text-xs">Repository</span>
              <input
                className="input input-bordered input-sm font-mono"
                placeholder="owner/repo or https://github.com/owner/repo"
                value={ghRepo}
                onChange={(e) => setGhRepo(e.target.value)}
              />
            </label>
            <label className="form-control">
              <span className="label-text text-xs">Branch / tag</span>
              <input
                className="input input-bordered input-sm font-mono"
                value={ghRef}
                onChange={(e) => setGhRef(e.target.value)}
              />
            </label>
            <button
              type="button"
              className="btn btn-primary btn-sm w-fit"
              disabled={!ghRepo.trim() || busy === "github"}
              onClick={installGithub}
            >
              {busy === "github" ? "Installing…" : "Install plugin"}
            </button>
            <div className="text-xs opacity-50 space-y-1">
              <p>Expected layout in the repo:</p>
              <pre className="bg-base-300 p-2 rounded text-[10px] overflow-auto">{`my-plugin/
  mediaos.plugin.json
  plugin.py`}</pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export { ModuleStorePage };
