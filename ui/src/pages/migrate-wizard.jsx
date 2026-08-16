import React, { useState } from "react";

/** P5 Migration wizard — validate then import from *arr (Hubstarr stacks welcome). */
function MigrateWizardPage({ setPage }) {
  const [kind, setKind] = useState("radarr");
  const [url, setUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [report, setReport] = useState(null);
  const [step, setStep] = useState(0);

  const kinds = [
    { id: "radarr", label: "Radarr (movies)" },
    { id: "sonarr", label: "Sonarr (TV)" },
    { id: "lidarr", label: "Lidarr (music)" },
    { id: "readarr", label: "Readarr (books)" },
    { id: "prowlarr", label: "Prowlarr (indexers)" },
  ];

  const runValidate = async () => {
    setBusy(true);
    setMsg("");
    setReport(null);
    try {
      const r = await fetch("/api/migrate/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, api_key: apiKey, kind }),
      }).then(async (x) => {
        const j = await x.json().catch(() => ({}));
        if (!x.ok) throw new Error(j.detail || x.statusText);
        return j;
      });
      setReport(r);
      setMsg("Preflight complete — review before import");
      setStep(1);
    } catch (e) {
      setMsg(String(e.message || e));
    }
    setBusy(false);
  };

  const runImport = async () => {
    if (!confirm(`Import ${kind} library from ${url}?`)) return;
    setBusy(true);
    setMsg("");
    try {
      const path =
        kind === "prowlarr"
          ? "/api/migrate/prowlarr/indexers"
          : `/api/migrate/${kind}`;
      const r = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, api_key: apiKey, monitor: true }),
      }).then(async (x) => {
        const j = await x.json().catch(() => ({}));
        if (!x.ok) throw new Error(j.detail || JSON.stringify(j));
        return j;
      });
      setMsg(`Import finished: ${JSON.stringify(r).slice(0, 240)}…`);
      setStep(2);
    } catch (e) {
      setMsg(String(e.message || e));
    }
    setBusy(false);
  };

  return (
    <div className="p-4 md:p-6 max-w-3xl space-y-4">
      <div>
        <h1 className="mr-page-title">Migration wizard</h1>
        <p className="text-sm opacity-60">
          Pull a Hubstarr / classic *arr library into MediaOS. Preflight first — no writes until you confirm.
        </p>
      </div>

      <ul className="steps steps-horizontal w-full text-xs">
        <li className={"step " + (step >= 0 ? "step-primary" : "")}>Connect</li>
        <li className={"step " + (step >= 1 ? "step-primary" : "")}>Preflight</li>
        <li className={"step " + (step >= 2 ? "step-primary" : "")}>Import</li>
      </ul>

      <div className="card bg-base-200 border border-base-content/10">
        <div className="card-body gap-3">
          <label className="form-control">
            <span className="label-text text-xs">Source</span>
            <select className="select select-bordered select-sm" value={kind} onChange={(e) => setKind(e.target.value)}>
              {kinds.map((k) => (
                <option key={k.id} value={k.id}>
                  {k.label}
                </option>
              ))}
            </select>
          </label>
          <label className="form-control">
            <span className="label-text text-xs">URL (API base, not only nginx UI path)</span>
            <input
              className="input input-bordered input-sm font-mono"
              placeholder="http://radarr:7878"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
            <span className="label-text-alt opacity-50">
              Prefer the port the API answers on. Subpath-only UI URLs often fail.
            </span>
          </label>
          <label className="form-control">
            <span className="label-text text-xs">API key</span>
            <input
              className="input input-bordered input-sm font-mono"
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn btn-primary btn-sm" disabled={busy || !url || !apiKey} onClick={runValidate}>
              {busy ? "Working…" : "1. Preflight"}
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              disabled={busy || step < 1}
              onClick={runImport}
            >
              2. Import
            </button>
            {setPage && (
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setPage("library-tools")}>
                Path maps
              </button>
            )}
          </div>
        </div>
      </div>

      {msg && <div className="alert text-sm">{msg}</div>}
      {report && (
        <pre className="bg-base-300 p-3 rounded text-[10px] overflow-auto max-h-80">
          {JSON.stringify(report, null, 2)}
        </pre>
      )}

      <div className="card bg-base-200 border border-base-content/10">
        <div className="card-body p-3 gap-2">
          <h2 className="font-semibold text-sm">3. Path health</h2>
          <button
            type="button"
            className="btn btn-sm w-fit"
            onClick={async () => {
              setBusy(true);
              try {
                const r = await fetch("/api/library/path-conflicts").then((x) => x.json());
                setReport(r);
                setMsg(r.ok ? "Paths look OK" : "Path issues found — review report");
              } catch (e) {
                setMsg(String(e.message || e));
              }
              setBusy(false);
            }}
          >
            Scan path conflicts
          </button>
        </div>
      </div>

      <div className="text-xs opacity-50 space-y-1">
        <p>After import: Path conflicts report → test one grab → optional TRaSH/quality preset.</p>
        <p>
          API: <code>POST /api/migrate/validate</code> then <code>POST /api/migrate/&#123;kind&#125;</code>
        </p>
      </div>
    </div>
  );
}

export { MigrateWizardPage };
