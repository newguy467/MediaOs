import React, { useState, useEffect } from "react";
import { LibraryModuleShell, TeachEmpty, SkeletonLoader } from "../components/ui.jsx";

function YouTubeCookiesPanel() {
  const [text, setText] = useState("");
  const [status, setStatus] = useState(null);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    fetch("/api/youtube/cookies/status").then(r => r.json()).then(setStatus).catch(() => {});
  }, []);
  const save = async () => {
    setBusy(true); setMsg(null);
    try {
      const r = await fetch("/api/youtube/cookies", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cookies: text }),
      });
      if (!r.ok) throw new Error("Save failed");
      setMsg("Cookies saved");
      const s = await fetch("/api/youtube/cookies/status").then(x => x.json());
      setStatus(s);
    } catch (e) { setMsg(String(e.message || e)); }
    finally { setBusy(false); }
  };
  return (
    <div className="card bg-base-200 shadow mt-4">
      <div className="card-body space-y-3">
        <h2 className="card-title text-lg">YouTube login / cookies</h2>
        <p className="text-sm opacity-70">Public RSS works without login. For age-restricted videos, paste a Netscape cookies export.</p>
        <textarea className="textarea textarea-bordered font-mono text-xs h-32" placeholder="# Netscape HTTP Cookie File" value={text} onChange={e => setText(e.target.value)} />
        <div className="flex gap-2 items-center">
          <button type="button" className="btn btn-sm btn-primary" disabled={busy || !text.trim()} onClick={save}>{busy ? "Saving…" : "Save cookies"}</button>
          {status && <span className="text-xs opacity-60">{status.exists ? `On disk (${status.size} bytes)` : "No cookies file yet"}</span>}
        </div>
        {msg && <div className="text-sm">{msg}</div>}
      </div>
    </div>
  );
}

function YouTubePage() {
  const [channels, setChannels] = useState([]);
  const [videos, setVideos] = useState([]);
  const [selected, setSelected] = useState(null);
  const [q, setQ] = useState("");
  const [tab, setTab] = useState("channels");
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = () => {
    setLoading(true);
    fetch("/api/youtube")
      .then(r => { if (!r.ok) throw new Error("Load failed"); return r.json(); })
      .then(d => setChannels(Array.isArray(d) ? d : (d.items || d.channels || [])))
      .catch(e => setMsg(String(e.message || e)))
      .finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  const loadVideos = (id) => {
    fetch("/api/youtube/" + id + "/videos")
      .then(r => r.ok ? r.json() : [])
      .then(d => setVideos(Array.isArray(d) ? d : (d.items || [])))
      .catch(() => setVideos([]));
  };

  const add = async () => {
    if (!q.trim()) return;
    setBusy(true); setMsg(null);
    try {
      const r = await fetch("/api/youtube", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q }),
      });
      if (!r.ok) throw new Error("Add failed");
      setQ("");
      load();
    } catch (e) { setMsg(String(e.message || e)); }
    finally { setBusy(false); }
  };

  return (
    <LibraryModuleShell
      title="YouTube"
      active={tab}
      onNav={setTab}
      nav={[
        { id: "channels", label: "Channels" },
        { id: "videos", label: "Videos" },
        { id: "cookies", label: "Cookies" },
      ]}
      tools={<>
        <input className="mr-search" placeholder="Channel URL or search…" value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === "Enter" && add()} />
        <button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={add}>Add</button>
        <button type="button" className="btn btn-sm btn-ghost" onClick={load}>Refresh</button>
      </>}
    >
      {msg && <div className="alert alert-info text-xs py-2 mb-3">{msg}</div>}
      {tab === "cookies" && <YouTubeCookiesPanel />}
      {loading && tab !== "cookies" && <SkeletonLoader rows={8} />}
      {tab === "channels" && !loading && (
        <>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {(channels || []).map(c => (
              <div key={c.id} className="card bg-base-200 shadow-sm cursor-pointer" onClick={() => { setSelected(c); loadVideos(c.id); setTab("videos"); }}>
                <div className="card-body p-3">
                  <div className="font-medium text-sm">{c.title || c.name}</div>
                  <div className="text-xs opacity-50">{c.channel_id || c.url || ""}</div>
                </div>
              </div>
            ))}
          </div>
          {!channels.length && (
            <TeachEmpty title="No channels yet" actionLabel="Add a channel" onAction={add}>
              <p>Track YouTube channels for download with optional SponsorBlock cleaning.</p>
            </TeachEmpty>
          )}
        </>
      )}
      {tab === "videos" && !loading && (
        <div className="overflow-x-auto">
          <table className="table table-sm">
            <thead><tr><th>Title</th><th>Status</th><th>Channel</th></tr></thead>
            <tbody>
              {(videos || []).map(v => (
                <tr key={v.id}>
                  <td className="text-sm">{v.title}</td>
                  <td><span className="badge badge-xs">{v.status || "—"}</span></td>
                  <td className="text-xs opacity-50">{selected?.title || ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!videos.length && (
            <TeachEmpty title="Select a channel" actionLabel="Channels" onAction={() => setTab("channels")}>
              <p>Open a channel to list and download videos.</p>
            </TeachEmpty>
          )}
        </div>
      )}
    </LibraryModuleShell>
  );
}

export { YouTubePage };
