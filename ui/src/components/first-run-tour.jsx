import { useState, useEffect } from "react";
const STEPS = [
  {
    id: "dashboard",
    title: "Dashboard",
    body: "Widgets for queue, calendar, wanted, and continue watching. Edit layout anytime.",
  },
  {
    id: "modules",
    title: "Module Store",
    body: "Add or remove Music, Games, Live TV, Comics… Movies & TV stay on. Cards show path needs and tags.",
  },
  {
    id: "paths",
    title: "Paths",
    body: "Library folders should be container paths in Docker. Use Path maps if host paths differ. Watch for conflict warnings.",
  },
  {
    id: "quality",
    title: "Quality packs",
    body: "Pick HD, 4K, or Anime presets — one app, not a second Radarr.",
  },
  {
    id: "migrate",
    title: "Migration",
    body: "Import from Sonarr/Radarr/Hubstarr stacks via preflight → import. Don’t double-grab.",
  },
];

function FirstRunTour({ setPage, onDone }) {
  const [open, setOpen] = useState(false);
  const [i, setI] = useState(0);

  useEffect(() => {
    try {
      if (localStorage.getItem("mediaos.tour.done") === "1") return;
      setOpen(true);
    } catch {
      setOpen(true);
    }
  }, []);

  if (!open) return null;
  const step = STEPS[i];

  const finish = () => {
    try {
      localStorage.setItem("mediaos.tour.done", "1");
    } catch {}
    setOpen(false);
    onDone && onDone();
  };

  return (
    <div className="modal modal-open">
      <div className="modal-box max-w-md">
        <p className="text-xs opacity-50 mb-1">
          Tour {i + 1}/{STEPS.length}
        </p>
        <h3 className="font-bold text-lg">{step.title}</h3>
        <p className="py-3 text-sm opacity-80">{step.body}</p>
        <div className="modal-action flex-wrap gap-2">
          <button type="button" className="btn btn-ghost btn-sm" onClick={finish}>
            Skip
          </button>
          {i < STEPS.length - 1 ? (
            <button type="button" className="btn btn-primary btn-sm" onClick={() => setI((x) => x + 1)}>
              Next
            </button>
          ) : (
            <button type="button" className="btn btn-primary btn-sm" onClick={finish}>
              Done
            </button>
          )}
          {setPage && step.id === "modules" && (
            <button type="button" className="btn btn-outline btn-sm" onClick={() => setPage("modules")}>
              Open store
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export { FirstRunTour };
