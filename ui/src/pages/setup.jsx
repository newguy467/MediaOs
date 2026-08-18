import { useState, useEffect } from "react";
import { api } from "../api.js";
import { LogoMark } from "../components/ui.jsx";
function SetupWizardPage({ onDone }) {
  /* Simple first-run: Welcome → Admin → Modules → Paths → Finish (everything else automatic) */
  const STEPS = [
    { id: "welcome", title: "Welcome" },
    { id: "admin", title: "Admin & users" },
    { id: "modules", title: "Libraries" },
    { id: "paths", title: "Folders" },
    { id: "finish", title: "Finish" },
  ];
  // Movies + TV are core (always on). Everything else is opt-in via click.
  const OPTIONAL_MODULES = [
    { id: "music", label: "Music", hint: "Artists, albums, tracks (Lidarr-style)" },
    { id: "books", label: "Books", hint: "eBooks (Readarr-style)" },
    { id: "audiobooks", label: "Audiobooks", hint: "M4B / chaptered books" },
    { id: "comics", label: "Comics", hint: "CBZ/CBR pull-list" },
    { id: "manga", label: "Manga", hint: "Manga library path" },
    { id: "games", label: "Games", hint: "Platforms, releases, wanted (Questarr)" },
    { id: "podcasts", label: "Podcasts", hint: "Subscriptions & episodes" },
    { id: "youtube", label: "YouTube", hint: "Channels & playlists (yt-dlp)" },
    { id: "livetv", label: "Live TV", hint: "IPTV + EPG + virtual channels" },
    { id: "converter", label: "Converter", hint: "Transcode queue (GPU/CPU)" },
    { id: "adult", label: "Adult", hint: "Requires 5-digit passcode" },
  ];
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [pathCheck, setPathCheck] = useState(null);
  const [selectedModules, setSelectedModules] = useState(["movies", "tv"]);
  const [adultPin, setAdultPin] = useState("");
  const [adultPin2, setAdultPin2] = useState("");
  const [admin, setAdmin] = useState({ username: "admin", password: "", password2: "", role: "admin" });
  const [extraUsers, setExtraUsers] = useState([]); // {username,password,role}
  const [form, setForm] = useState({
    movies_library_path: "/movies",
    tv_library_path: "/tv",
    music_library_path: "/music",
    books_library_path: "/books",
    audiobooks_library_path: "/audiobooks",
    comics_library_path: "/comics",
    manga_library_path: "/manga",
    youtube_library_path: "/youtube",
    adult_library_path: "/adult",
    downloads_path: "/downloads",
    podcasts_library_path: "/podcasts",
    games_library_path: "/games",
  });
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  useEffect(() => {
    api.setup.status().catch(() => null);
    fetch("/api/setup/defaults").then(r => r.json()).then(d => {
      if (d && typeof d === "object") {
        setForm(f => ({
          ...f,
          movies_library_path: d.movies_library_path || f.movies_library_path,
          tv_library_path: d.tv_library_path || f.tv_library_path,
          music_library_path: d.music_library_path || f.music_library_path,
          downloads_path: d.downloads_path || f.downloads_path,
        }));
      }
    }).catch(e => { console.warn(e); if (typeof setMsg === 'function') setMsg(String(e.message || e)); });
  }, []);

  function toggleMod(id) {
    if (id === "movies" || id === "tv") return; // mandatory
    setSelectedModules(m => m.includes(id) ? m.filter(x => x !== id) : [...m, id]);
  }

  function validateStep() {
    if (step === 1) {
      if (!admin.username.trim()) return "Admin username required";
      if ((admin.password || "").length < 4) return "Admin password (min 4 characters)";
      if (admin.password !== admin.password2) return "Passwords do not match";
    }
    if (step === 2) {
      if (selectedModules.includes("adult")) {
        if (!/^\d{5}$/.test(adultPin)) return "Adult module needs a 5-digit passcode";
        if (adultPin !== adultPin2) return "Passcodes do not match";
      }
    }
    if (step === 3) {
      if (!(form.movies_library_path || "").trim()) return "Movies path required";
      if (!(form.tv_library_path || "").trim()) return "TV path required";
    }
    return null;
  }

  async function checkPaths() {
    setMsg("Checking folders…");
    try {
      const body = {
        movies_library_path: form.movies_library_path,
        tv_library_path: form.tv_library_path,
        downloads_path: form.downloads_path,
      };
      if (selectedModules.includes("music")) body.music_library_path = form.music_library_path;
      if (selectedModules.includes("books")) body.books_library_path = form.books_library_path;
      if (selectedModules.includes("adult")) body.adult_library_path = form.adult_library_path;
      const r = await fetch("/api/setup/check-paths", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }).then(x => x.json());
      setPathCheck(r);
      setMsg(r.ok ? "Paths look good (missing folders can be created by mounts)." : "Some paths need attention — you can still continue if Docker volumes will create them.");
    } catch (e) {
      setMsg(String(e.message || e));
    }
  }

  async function finish(mark) {
    const err = validateStep();
    if (err) { setMsg(err); return; }
    setSaving(true); setMsg("");
    try {
      const payload = {
        mark_complete: !!mark,
        auto_defaults: true,
        auth_username: admin.username.trim(),
        auth_password: admin.password,
        admin_role: admin.role || "admin",
        enabled_modules: selectedModules,
        extra_users: extraUsers.filter(u => u.username && u.password),
        movies_library_path: form.movies_library_path,
        tv_library_path: form.tv_library_path,
        downloads_path: form.downloads_path,
        music_library_path: form.music_library_path,
        books_library_path: form.books_library_path,
        audiobooks_library_path: form.audiobooks_library_path,
        comics_library_path: form.comics_library_path,
        manga_library_path: form.manga_library_path,
        youtube_library_path: form.youtube_library_path,
        podcasts_library_path: form.podcasts_library_path,
        games_library_path: form.games_library_path,
        adult_library_path: form.adult_library_path,
      };
      if (selectedModules.includes("adult") && adultPin) {
        payload.adult_passcode = adultPin;
      }
      const url = mark ? "/api/setup/complete" : "/api/setup/apply";
      const r = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }).then(x => x.json());
      if (!r.ok && r.detail) throw new Error(typeof r.detail === "string" ? r.detail : JSON.stringify(r.detail));
      setMsg(r.message || "Saved. Indexers, Live TV EPG, and definitions sync in the background.");
      if (mark && onDone) setTimeout(() => onDone(), 600);
    } catch (e) {
      setMsg(String(e.message || e));
    }
    setSaving(false);
  }

  function next() {
    const err = validateStep();
    if (err) { setMsg(err); return; }
    setMsg("");
    setStep(s => Math.min(s + 1, STEPS.length - 1));
  }
  function back() {
    setMsg("");
    setStep(s => Math.max(s - 1, 0));
  }

  const id = STEPS[step].id;

  return (
    <div className="max-w-2xl mx-auto space-y-6 py-4">
      <div className="flex items-center gap-3">
        <LogoMark size={40} />
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Get started</h1>
          <p className="text-sm opacity-50">A few choices — downloads, indexers, and APIs configure themselves.</p>
        </div>
      </div>

      <ul className="steps steps-horizontal w-full text-xs">
        {STEPS.map((s, i) => (
          <li key={s.id} className={"step " + (i <= step ? "step-primary" : "")}>{s.title}</li>
        ))}
      </ul>

      {msg && <div className="alert alert-info text-sm py-2">{msg}</div>}

      {id === "welcome" && (
        <div className="card bg-base-200 border border-base-content/10">
          <div className="card-body gap-3">
            <h2 className="card-title text-lg">Welcome to MediaOs</h2>
            <p className="text-sm opacity-70">
              One app for Movies &amp; TV (required), plus optional Music, Books, Live TV, Adult, and more.
              After this wizard, MediaOs will automatically seed indexers, Live TV guides, and quality profiles.
            </p>
            <ul className="text-sm opacity-70 list-disc ml-5 space-y-1">
              <li>No need to configure Prowlarr/Jackett on day one — built-in indexers work immediately</li>
              <li>Point folders at your disks (or keep Docker defaults)</li>
              <li>Advanced clients (qBittorrent, VPN, Jellyfin) stay available under Settings later</li>
            </ul>
          </div>
        </div>
      )}

      {id === "admin" && (
        <div className="card bg-base-200 border border-base-content/10">
          <div className="card-body gap-3">
            <h2 className="card-title text-lg">Admin account</h2>
            <p className="text-xs opacity-50">This is the main login. You can add more users below.</p>
            <label className="form-control">
              <span className="label-text">Username</span>
              <input className="input input-bordered" value={admin.username}
                onChange={e => setAdmin(a => ({ ...a, username: e.target.value }))} />
            </label>
            <label className="form-control">
              <span className="label-text">Password</span>
              <input type="password" className="input input-bordered" value={admin.password}
                onChange={e => setAdmin(a => ({ ...a, password: e.target.value }))} />
            </label>
            <label className="form-control">
              <span className="label-text">Confirm password</span>
              <input type="password" className="input input-bordered" value={admin.password2}
                onChange={e => setAdmin(a => ({ ...a, password2: e.target.value }))} />
            </label>
            <label className="form-control">
              <span className="label-text">Role</span>
              <select className="select select-bordered" value={admin.role}
                onChange={e => setAdmin(a => ({ ...a, role: e.target.value }))}>
                <option value="admin">Admin (full access)</option>
                <option value="user">User</option>
              </select>
            </label>

            <div className="divider text-xs">Optional extra users</div>
            {extraUsers.map((u, i) => (
              <div key={i} className="grid grid-cols-3 gap-2">
                <input className="input input-bordered input-sm" placeholder="Username" value={u.username}
                  onChange={e => setExtraUsers(list => list.map((x, j) => j === i ? { ...x, username: e.target.value } : x))} />
                <input type="password" className="input input-bordered input-sm" placeholder="Password" value={u.password}
                  onChange={e => setExtraUsers(list => list.map((x, j) => j === i ? { ...x, password: e.target.value } : x))} />
                <select className="select select-bordered select-sm" value={u.role || "user"}
                  onChange={e => setExtraUsers(list => list.map((x, j) => j === i ? { ...x, role: e.target.value } : x))}>
                  <option value="user">User</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
            ))}
            <button type="button" className="btn btn-sm btn-ghost w-fit"
              onClick={() => setExtraUsers(x => [...x, { username: "", password: "", role: "user" }])}>
              + Add user
            </button>
          </div>
        </div>
      )}

      {id === "modules" && (
        <div className="card bg-base-200 border border-base-content/10">
          <div className="card-body gap-3">
            <h2 className="card-title text-lg">What do you want to manage?</h2>
            <p className="text-xs opacity-50">
              <strong>Movies</strong> and <strong>TV</strong> are required and always enabled.
              Click any other module below to enable it — you can change this later in Module Store.
            </p>
            <div className="grid sm:grid-cols-2 gap-2">
              {[
                { id: "movies", label: "Movies", hint: "Required — always on" },
                { id: "tv", label: "TV Shows", hint: "Required — always on" },
              ].map(m => (
                <div key={m.id} className="flex items-start gap-3 p-3 rounded-lg border border-primary/40 bg-primary/5 opacity-90">
                  <input type="checkbox" className="checkbox checkbox-primary mt-0.5" checked disabled readOnly />
                  <span>
                    <span className="font-medium text-sm">{m.label}</span>
                    <span className="badge badge-primary badge-xs ml-2">Required</span>
                    <span className="block text-xs opacity-50">{m.hint}</span>
                  </span>
                </div>
              ))}
            </div>
            <div className="divider text-xs my-1">Optional — click to enable</div>
            <div className="grid sm:grid-cols-2 gap-2">
              {OPTIONAL_MODULES.map(m => (
                <label key={m.id} className={"flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors "
                  + (selectedModules.includes(m.id) ? "border-primary bg-primary/10" : "border-base-content/10 hover:border-base-content/30")}>
                  <input type="checkbox" className="checkbox checkbox-primary mt-0.5"
                    checked={selectedModules.includes(m.id)} onChange={() => toggleMod(m.id)} />
                  <span>
                    <span className="font-medium text-sm">{m.label}</span>
                    {m.hint && <span className="block text-xs opacity-50">{m.hint}</span>}
                  </span>
                </label>
              ))}
            </div>
            {selectedModules.includes("adult") && (
              <div className="alert bg-base-300 mt-2 flex-col items-stretch gap-2">
                <div className="font-semibold text-sm">Adult passcode (required — 5 digits)</div>
                <div className="grid sm:grid-cols-2 gap-2">
                  <input type="password" inputMode="numeric" maxLength={5} className="input input-bordered"
                    placeholder="•••••" value={adultPin} onChange={e => setAdultPin(e.target.value.replace(/\D/g, "").slice(0, 5))} />
                  <input type="password" inputMode="numeric" maxLength={5} className="input input-bordered"
                    placeholder="Confirm" value={adultPin2} onChange={e => setAdultPin2(e.target.value.replace(/\D/g, "").slice(0, 5))} />
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {id === "paths" && (
        <div className="card bg-base-200 border border-base-content/10">
          <div className="card-body gap-3">
            <h2 className="card-title text-lg">Where is media stored?</h2>
            <p className="text-xs opacity-50">These are paths <em>inside</em> the container. Map them to your disks in Docker Compose.</p>
            {[
              ["movies_library_path", "Movies", true],
              ["tv_library_path", "TV shows", true],
              ["downloads_path", "Downloads (incomplete / client)", true],
              selectedModules.includes("music") && ["music_library_path", "Music", false],
              selectedModules.includes("books") && ["books_library_path", "Books", false],
              selectedModules.includes("audiobooks") && ["audiobooks_library_path", "Audiobooks", false],
              selectedModules.includes("comics") && ["comics_library_path", "Comics", false],
              selectedModules.includes("manga") && ["manga_library_path", "Manga", false],
              selectedModules.includes("games") && ["games_library_path", "Games", false],
              selectedModules.includes("podcasts") && ["podcasts_library_path", "Podcasts", false],
              selectedModules.includes("youtube") && ["youtube_library_path", "YouTube", false],
              selectedModules.includes("adult") && ["adult_library_path", "Adult", false],
            ].filter(Boolean).map(([key, label, req]) => (
              <label key={key} className="form-control">
                <span className="label-text">{label}{req ? " *" : ""}</span>
                <input className="input input-bordered font-mono text-sm" value={form[key] || ""}
                  onChange={e => set(key, e.target.value)} />
              </label>
            ))}
            <button type="button" className="btn btn-sm w-fit" onClick={checkPaths}>Check paths</button>
            {pathCheck && (
              <pre className="text-[10px] opacity-60 overflow-auto max-h-32 bg-base-300 p-2 rounded">
                {JSON.stringify(pathCheck, null, 2)}
              </pre>
            )}
          </div>
        </div>
      )}

      {id === "finish" && (
        <div className="card bg-base-200 border border-base-content/10">
          <div className="card-body gap-3">
            <h2 className="card-title text-lg">You are ready</h2>
            <p className="text-sm opacity-70">
              Finish will save your admin account, modules, and folders, then start background setup:
              indexers, quality profiles, Live TV (if enabled), and definitions — no extra steps required.
            </p>
            <ul className="text-sm space-y-1">
              <li><strong>Admin:</strong> {admin.username}</li>
              <li><strong>Modules:</strong> {selectedModules.join(", ")}</li>
              <li><strong>Movies:</strong> {form.movies_library_path}</li>
              <li><strong>TV:</strong> {form.tv_library_path}</li>
            </ul>
            <p className="text-xs opacity-50">
              Later: Settings → Clients / Indexers / Integrations for qBittorrent, Prowlarr, Jellyfin, VPN.
              Live TV EPG uses iptv-org automatically; optional Node grabber via <code>docker compose --profile full</code>.
            </p>
          </div>
        </div>
      )}

      <div className="flex flex-wrap gap-2 justify-between">
        <button type="button" className="btn btn-ghost" disabled={step === 0 || saving} onClick={back}>Back</button>
        <div className="flex gap-2">
          {step < STEPS.length - 1 ? (
            <button type="button" className="btn btn-primary" onClick={next}>Continue</button>
          ) : (
            <button type="button" className="btn btn-primary" disabled={saving} onClick={() => finish(true)}>
              {saving ? "Saving…" : "Finish & open MediaOs"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}




export { SetupWizardPage };
