import { useState, useEffect } from "react";
function HomelabLinksPage() {
  const [tab, setTab] = useState("links"); // links | announce
  const [links, setLinks] = useState([]);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [group, setGroup] = useState("Services");
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  // Announce lab
  const [announce, setAnnounce] = useState(null);
  const [fName, setFName] = useState("");
  const [fMatch, setFMatch] = useState("");
  const [fExcept, setFExcept] = useState("");

  const load = () => {
    fetch("/api/homelab/links")
      .then((r) => r.json())
      .then((d) => setLinks(d.items || d.links || []))
      .catch((e) => setErr(String(e)));
  };
  const loadAnnounce = () => {
    fetch("/api/homelab/announce")
      .then((r) => r.json())
      .then((d) => setAnnounce(d))
      .catch((e) => setErr(String(e)));
  };
  useEffect(() => {
    load();
    loadAnnounce();
  }, []);

  const add = async () => {
    if (!name.trim() || !url.trim()) return;
    setBusy(true);
    setErr("");
    try {
      await fetch("/api/homelab/links", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: name.trim(), url: url.trim(), group_name: group || "Services" }),
      }).then(async (r) => {
        if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
      });
      setName("");
      setUrl("");
      load();
    } catch (e) {
      setErr(String(e.message || e));
    }
    setBusy(false);
  };

  const remove = async (id) => {
    if (id == null) return;
    await fetch("/api/homelab/links/" + id, { method: "DELETE" }).catch(e => { console.warn(e); if (typeof setMsg === 'function') setMsg(String(e.message || e)); });
    load();
  };

  const runHealth = async () => {
    setBusy(true);
    await fetch("/api/homelab/links/health-check", { method: "POST" }).catch(e => { console.warn(e); if (typeof setMsg === 'function') setMsg(String(e.message || e)); });
    load();
    setBusy(false);
  };

  const addFilter = async () => {
    if (!fName.trim() || !fMatch.trim()) return;
    const filters = [...(announce?.filters || [])];
    const id = fName.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 40);
    filters.push({
      id,
      name: fName.trim(),
      enabled: true,
      match_regex: fMatch.trim(),
      except_regex: fExcept.trim(),
      actions: ["download"],
      priority: 0,
    });
    setBusy(true);
    try {
      const r = await fetch("/api/homelab/announce/filters", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filters }),
      }).then((x) => x.json());
      setAnnounce((a) => ({ ...a, filters: r.filters || filters }));
      setFName("");
      setFMatch("");
      setFExcept("");
      loadAnnounce();
    } catch (e) {
      setErr(String(e.message || e));
    }
    setBusy(false);
  };

  const toggleFilter = async (fid, enabled) => {
    const filters = (announce?.filters || []).map((f) =>
      f.id === fid ? { ...f, enabled: !enabled } : f
    );
    await fetch("/api/homelab/announce/filters", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filters }),
    });
    loadAnnounce();
  };

  const removeFilter = async (fid) => {
    const filters = (announce?.filters || []).filter((f) => f.id !== fid);
    await fetch("/api/homelab/announce/filters", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filters }),
    });
    loadAnnounce();
  };

  const runAnnounce = async () => {
    setBusy(true);
    setErr("");
    try {
      const r = await fetch("/api/homelab/announce/run", { method: "POST" }).then((x) => x.json());
      setErr("");
      alert(`Announce cycle: checked ${r.checked || 0}, matched ${r.matched || 0}`);
      loadAnnounce();
    } catch (e) {
      setErr(String(e.message || e));
    }
    setBusy(false);
  };

  const filtered = (() => {
    const q = filter.trim().toLowerCase();
    const items = links || [];
    const byGroup = {};
    for (const l of items) {
      const title = l.title || l.name || "";
      if (q && !title.toLowerCase().includes(q) && !(l.url || "").toLowerCase().includes(q)) continue;
      const g = l.group_name || l.group || "Services";
      (byGroup[g] = byGroup[g] || []).push(l);
    }
    return Object.entries(byGroup);
  })();

  return (
    <div className="space-y-4 max-w-5xl">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="mr-page-title mb-0">Homelab</h1>
          <p className="text-sm opacity-60">
            Service links and in-app labs (Announce filters) — no extra containers required.
          </p>
        </div>
      </div>

      <div className="tabs tabs-boxed w-fit">
        <button type="button" className={"tab " + (tab === "links" ? "tab-active" : "")} onClick={() => setTab("links")}>
          Service links
        </button>
        <button type="button" className={"tab " + (tab === "announce" ? "tab-active" : "")} onClick={() => setTab("announce")}>
          Announce Lab
        </button>
      </div>

      {err && <div className="alert alert-error text-xs">{err}</div>}

      {tab === "links" && (
        <>
          <div className="flex gap-2 flex-wrap">
            <input className="input input-sm input-bordered" placeholder="Filter…" value={filter} onChange={(e) => setFilter(e.target.value)} />
            <button type="button" className="btn btn-sm" disabled={busy} onClick={runHealth}>
              Health check
            </button>
            <button type="button" className="btn btn-sm btn-ghost" onClick={load}>
              Refresh
            </button>
          </div>
          <div className="card bg-base-200 p-3">
            <div className="grid md:grid-cols-5 gap-2">
              <input className="input input-sm input-bordered" placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} />
              <input className="input input-sm input-bordered md:col-span-2" placeholder="https://…" value={url} onChange={(e) => setUrl(e.target.value)} />
              <input className="input input-sm input-bordered" placeholder="Group" value={group} onChange={(e) => setGroup(e.target.value)} />
              <button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={add}>
                Add link
              </button>
            </div>
          </div>
          {filtered.map(([g, items]) => (
            <div key={g}>
              <h2 className="text-sm font-semibold opacity-70 mb-2">{g}</h2>
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
                {items.map((l) => (
                  <a
                    key={l.id || l.url}
                    href={l.url}
                    target="_blank"
                    rel="noreferrer"
                    className="card bg-base-300 hover:bg-base-100 transition shadow-sm p-3 no-underline text-inherit"
                  >
                    <div className="flex items-start justify-between gap-1">
                      <div className="font-medium text-sm line-clamp-2">{l.title || l.name}</div>
                      <button
                        type="button"
                        className="btn btn-ghost btn-xs"
                        onClick={(e) => {
                          e.preventDefault();
                          remove(l.id);
                        }}
                      >
                        ×
                      </button>
                    </div>
                    <div className="text-[10px] opacity-40 truncate mt-1">{l.url}</div>
                    {l.last_status != null && (
                      <div
                        className={
                          "badge badge-xs mt-2 " +
                          (l.last_status === "up" || l.last_status === true ? "badge-success" : "badge-warning")
                        }
                      >
                        {String(l.last_status)}
                      </div>
                    )}
                  </a>
                ))}
              </div>
            </div>
          ))}
          {!links.length && <p className="text-sm opacity-50">No links yet — add Jellyfin, qBittorrent, etc.</p>}
        </>
      )}

      {tab === "announce" && (
        <div className="space-y-4">
          <div className="alert bg-base-200 text-xs">
            <div>
              <strong>Announce Lab</strong> is an autobrr-style filter engine <em>inside</em> MediaOS.
              It polls your Torznab indexers, matches release titles, and sends hits to qBittorrent —
              no separate autobrr container. Full IRC announce clients can still be linked under Service links if you prefer.
            </div>
          </div>
          <div className="flex flex-wrap gap-2 items-center">
            <button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={runAnnounce}>
              {busy ? "Running…" : "Run cycle now"}
            </button>
            <button type="button" className="btn btn-sm btn-ghost" onClick={loadAnnounce}>
              Refresh
            </button>
            <span className="text-xs opacity-50">
              Last run: {announce?.last_run_at || "never"} · seen {announce?.seen_count || 0} ·
              filters {announce?.enabled_count || 0}/{announce?.filter_count || 0} enabled
            </span>
          </div>

          <div className="card bg-base-200 border border-base-content/10">
            <div className="card-body gap-2 p-4">
              <h3 className="font-semibold text-sm">Add filter</h3>
              <div className="grid md:grid-cols-3 gap-2">
                <input
                  className="input input-sm input-bordered"
                  placeholder="Name (e.g. 2160p WEB)"
                  value={fName}
                  onChange={(e) => setFName(e.target.value)}
                />
                <input
                  className="input input-sm input-bordered font-mono"
                  placeholder="Match regex (required)"
                  value={fMatch}
                  onChange={(e) => setFMatch(e.target.value)}
                />
                <input
                  className="input input-sm input-bordered font-mono"
                  placeholder="Except regex (optional)"
                  value={fExcept}
                  onChange={(e) => setFExcept(e.target.value)}
                />
              </div>
              <button type="button" className="btn btn-sm btn-primary w-fit" disabled={busy} onClick={addFilter}>
                Save filter
              </button>
              <p className="text-[10px] opacity-50">
                Example match: <code>2160p.*WEB-DL</code> · except: <code>x265|HEVC</code>
              </p>
            </div>
          </div>

          <div className="space-y-2">
            <h3 className="text-sm font-semibold opacity-70">Filters</h3>
            {(announce?.filters || []).map((f) => (
              <div key={f.id} className="card bg-base-200 p-3 flex flex-row items-center justify-between gap-2">
                <div className="min-w-0">
                  <div className="font-medium text-sm flex items-center gap-2">
                    {f.name}
                    {f.enabled ? (
                      <span className="badge badge-success badge-xs">On</span>
                    ) : (
                      <span className="badge badge-ghost badge-xs">Off</span>
                    )}
                  </div>
                  <div className="text-[10px] opacity-50 font-mono truncate">
                    match: {f.match_regex}
                    {f.except_regex ? ` · except: ${f.except_regex}` : ""}
                  </div>
                </div>
                <div className="flex gap-1">
                  <button type="button" className="btn btn-xs" onClick={() => toggleFilter(f.id, f.enabled)}>
                    {f.enabled ? "Disable" : "Enable"}
                  </button>
                  <button type="button" className="btn btn-xs btn-ghost" onClick={() => removeFilter(f.id)}>
                    Delete
                  </button>
                </div>
              </div>
            ))}
            {!(announce?.filters || []).length && (
              <p className="text-sm opacity-50">No filters yet — add one above, then run a cycle.</p>
            )}
          </div>

          <div className="space-y-2">
            <h3 className="text-sm font-semibold opacity-70">Recent hits</h3>
            <div className="overflow-x-auto">
              <table className="table table-xs">
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Title</th>
                    <th>Filter</th>
                    <th>Indexer</th>
                  </tr>
                </thead>
                <tbody>
                  {(announce?.recent_hits || []).map((h, i) => (
                    <tr key={i}>
                      <td className="whitespace-nowrap opacity-50">{(h.at || "").replace("T", " ").slice(0, 19)}</td>
                      <td className="max-w-xs truncate">{h.title}</td>
                      <td>{h.filter_name}</td>
                      <td>{h.indexer}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!(announce?.recent_hits || []).length && (
                <p className="text-sm opacity-50 p-2">No hits yet.</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default HomelabLinksPage;
