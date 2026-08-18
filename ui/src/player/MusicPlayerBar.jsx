import { useEffect, useRef } from "react";
import Ic from "../icons.jsx";
import useMusicPlayer from "./useMusicPlayer.js";
import engine from "./engine.js";
import Visualizer from "./Visualizer.jsx";
import Equalizer from "./Equalizer.jsx";
import Lyrics from "./Lyrics.jsx";

function fmt(sec) {
  if (!isFinite(sec) || sec < 0) return "0:00";
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return m + ":" + String(s).padStart(2, "0");
}

export default function MusicPlayerBar() {
  const p = useMusicPlayer();
  const { store, current } = p;
  const seekRef = useRef(null);

  // keyboard shortcuts
  useEffect(() => {
    const onKey = (e) => {
      const tag = (e.target && e.target.tagName) || "";
      if (/INPUT|TEXTAREA|SELECT/.test(tag)) return;
      if (e.shiftKey && e.code === "Space") { e.preventDefault(); store.toggle(); }
      else if (e.shiftKey && e.code === "ArrowRight") { e.preventDefault(); store.seekBy(10); }
      else if (e.shiftKey && e.code === "ArrowLeft") { e.preventDefault(); store.seekBy(-10); }
      else if (e.key === ">") store.next();
      else if (e.key === "<") store.prev();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [store]);

  if (!current) return null;

  const liked = store.isLiked(current);
  const pct = p.duration ? (p.currentTime / p.duration) * 100 : 0;

  return (
    <>
      {/* ── Persistent bottom bar ── */}
      <div className="fixed inset-x-0 bottom-16 lg:bottom-0 z-40 bg-base-300/95 border-t border-primary/40 backdrop-blur shadow-lg">
        {/* seek bar */}
        <div
          className="group relative h-1.5 w-full bg-base-content/10 cursor-pointer"
          onClick={(e) => {
            const r = e.currentTarget.getBoundingClientRect();
            const ratio = (e.clientX - r.left) / r.width;
            store.seek(ratio * p.duration);
          }}
        >
          <div className="absolute inset-y-0 left-0 bg-primary" style={{ width: pct + "%" }} />
          <div
            className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-3 h-3 rounded-full bg-primary opacity-0 group-hover:opacity-100 transition"
            style={{ left: pct + "%" }}
          />
        </div>

        <div className="flex items-center gap-2 sm:gap-3 px-2 sm:px-3 py-1.5">
          {/* art + title */}
          <button
            type="button"
            className="flex items-center gap-2 min-w-0 flex-1 sm:flex-none sm:w-56 text-left"
            onClick={() => store.setExpanded(true)}
            title="Open Now Playing"
          >
            <div className="w-10 h-10 rounded bg-base-100 overflow-hidden shrink-0 flex items-center justify-center">
              {current.poster_path
                ? <img src={current.poster_path} alt="" className="object-cover w-full h-full" />
                : <span className="w-5 h-5 opacity-40"><Ic.Music /></span>}
            </div>
            <div className="min-w-0">
              <div className="text-xs font-semibold truncate">{current.title || current.name || "Unknown"}</div>
              <div className="text-[10px] opacity-60 truncate">{current.artist || current.artist_name || ""}</div>
            </div>
          </button>

          {/* mini visualizer */}
          <div className="hidden md:block w-24 shrink-0"><Visualizer height={28} barCount={24} /></div>

          {/* transport */}
          <div className="flex items-center gap-0.5 sm:gap-1 mx-auto sm:mx-0">
            <button type="button" className={"btn btn-ghost btn-xs btn-circle " + (p.shuffle ? "text-primary" : "")} onClick={() => store.toggleShuffle()} title="Shuffle">
              <span className="w-4 h-4"><Ic.Shuffle /></span>
            </button>
            <button type="button" className="btn btn-ghost btn-sm btn-circle" onClick={() => store.prev()} title="Previous">
              <span className="w-5 h-5"><Ic.SkipBack /></span>
            </button>
            <button type="button" className="btn btn-primary btn-sm btn-circle !w-9 !h-9" onClick={() => store.toggle()} title={p.playing ? "Pause" : "Play"}>
              <span className="w-6 h-6">{p.playing ? <Ic.Pause /> : <Ic.Play />}</span>
            </button>
            <button type="button" className="btn btn-ghost btn-sm btn-circle" onClick={() => store.next()} title="Next">
              <span className="w-5 h-5"><Ic.SkipForward /></span>
            </button>
            <button type="button" className={"btn btn-ghost btn-xs btn-circle " + (p.repeat !== "off" ? "text-primary" : "")} onClick={() => store.cycleRepeat()} title={"Repeat: " + p.repeat}>
              <span className="w-4 h-4">{p.repeat === "one" ? <Ic.RepeatOne /> : <Ic.Repeat />}</span>
            </button>
            <button type="button" className={"btn btn-ghost btn-xs btn-circle " + (p.radioEnabled ? "text-primary" : "")} onClick={() => store.toggleRadio()} title={"Radio mode: " + (p.radioEnabled ? "on — keeps playing similar tracks" : "off")}>
              <span className="w-4 h-4"><Ic.Radio /></span>
            </button>
          </div>

          {/* time */}
          <span className="hidden sm:block text-[10px] tabular-nums opacity-60 shrink-0">
            {fmt(p.currentTime)} / {fmt(p.duration)}
          </span>

          {/* actions */}
          <div className="flex items-center gap-0.5 shrink-0">
            <button type="button" className={"btn btn-ghost btn-xs btn-circle " + (liked ? "text-error" : "")} onClick={() => store.toggleLike(current)} title="Like">
              <span className="w-4 h-4">{liked ? <Ic.HeartFill /> : <Ic.Heart />}</span>
            </button>
            <button type="button" className="btn btn-ghost btn-xs btn-circle" title="Lyrics"
              onClick={() => { store.setActiveTab("lyrics"); store.setExpanded(true); }}>
              <span className="w-4 h-4"><Ic.Lyrics /></span>
            </button>
            <button type="button" className="btn btn-ghost btn-xs btn-circle" title="Equalizer"
              onClick={() => { store.setActiveTab("eq"); store.setExpanded(true); }}>
              <span className="w-4 h-4"><Ic.Sliders /></span>
            </button>

            {/* volume */}
            <div className="hidden lg:flex items-center gap-1 ml-1">
              <button type="button" className="btn btn-ghost btn-xs btn-circle" onClick={() => engine.toggleMute()} title="Mute">
                <span className="w-4 h-4">{engine.muted || engine.volume === 0 ? <Ic.VolumeMute /> : <Ic.Volume />}</span>
              </button>
              <input
                type="range" min="0" max="1" step="0.01"
                value={engine.muted ? 0 : engine.volume}
                onChange={(e) => engine.setVolume(parseFloat(e.target.value))}
                className="range range-xs range-primary w-20"
                aria-label="Volume"
              />
            </div>

            <button type="button" className="btn btn-ghost btn-xs btn-circle" onClick={() => store.setExpanded(true)} title="Expand">
              <span className="w-4 h-4"><Ic.Expand /></span>
            </button>
          </div>
        </div>
      </div>

      {/* ── Now Playing overlay ── */}
      {p.expanded && (
        <div className="fixed inset-0 z-[60] bg-base-300/98 backdrop-blur-xl flex flex-col animate-[mr-nowplaying-in_.25s_ease]">
          {/* header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-base-content/10">
            <span className="text-sm font-semibold opacity-70">Now Playing</span>
            <button type="button" className="btn btn-ghost btn-sm btn-circle" onClick={() => store.setExpanded(false)} title="Close">
              <span className="w-5 h-5"><Ic.Minimize /></span>
            </button>
          </div>

          <div className="flex-1 flex flex-col lg:flex-row min-h-0">
            {/* left: art + transport */}
            <div className="lg:w-2/5 flex flex-col items-center justify-center gap-4 p-6 shrink-0">
              <div className="w-48 h-48 sm:w-64 sm:h-64 rounded-2xl bg-base-100 overflow-hidden shadow-2xl flex items-center justify-center">
                {current.poster_path
                  ? <img src={current.poster_path} alt="" className="object-cover w-full h-full" />
                  : <span className="w-16 h-16 opacity-30"><Ic.Music /></span>}
              </div>
              <div className="text-center min-w-0 max-w-full">
                <div className="text-lg font-bold truncate">{current.title || current.name || "Unknown"}</div>
                <div className="text-sm opacity-60 truncate">{current.artist || current.artist_name || ""}{current.album ? " · " + current.album : ""}</div>
              </div>

              <div className="w-full max-w-md"><Visualizer height={48} barCount={48} /></div>

              {/* seek */}
              <div className="w-full max-w-md flex items-center gap-2">
                <span className="text-[10px] tabular-nums opacity-60">{fmt(p.currentTime)}</span>
                <input
                  ref={seekRef}
                  type="range" min="0" max={p.duration || 0} step="0.1"
                  value={p.currentTime}
                  onChange={(e) => store.seek(parseFloat(e.target.value))}
                  className="range range-xs range-primary flex-1"
                  aria-label="Seek"
                />
                <span className="text-[10px] tabular-nums opacity-60">{fmt(p.duration)}</span>
              </div>

              {/* transport */}
              <div className="flex items-center gap-2">
                <button type="button" className={"btn btn-ghost btn-sm btn-circle " + (p.shuffle ? "text-primary" : "")} onClick={() => store.toggleShuffle()}>
                  <span className="w-5 h-5"><Ic.Shuffle /></span>
                </button>
                <button type="button" className="btn btn-ghost btn-circle" onClick={() => store.prev()}>
                  <span className="w-6 h-6"><Ic.SkipBack /></span>
                </button>
                <button type="button" className="btn btn-primary btn-lg btn-circle" onClick={() => store.toggle()}>
                  <span className="w-7 h-7">{p.playing ? <Ic.Pause /> : <Ic.Play />}</span>
                </button>
                <button type="button" className="btn btn-ghost btn-circle" onClick={() => store.next()}>
                  <span className="w-6 h-6"><Ic.SkipForward /></span>
                </button>
                <button type="button" className={"btn btn-ghost btn-sm btn-circle " + (p.repeat !== "off" ? "text-primary" : "")} onClick={() => store.cycleRepeat()}>
                  <span className="w-5 h-5">{p.repeat === "one" ? <Ic.RepeatOne /> : <Ic.Repeat />}</span>
                </button>
                <button type="button" className={"btn btn-ghost btn-sm btn-circle " + (p.radioEnabled ? "text-primary" : "")} onClick={() => store.toggleRadio()} title="Radio mode — keeps playing similar tracks when the queue runs out">
                  <span className="w-5 h-5"><Ic.Radio /></span>
                </button>
              </div>

              {/* volume + crossfade */}
              <div className="w-full max-w-md grid grid-cols-2 gap-4">
                <label className="flex items-center gap-2">
                  <span className="w-4 h-4 opacity-60 shrink-0">{engine.muted ? <Ic.VolumeMute /> : <Ic.Volume />}</span>
                  <input type="range" min="0" max="1" step="0.01" value={engine.muted ? 0 : engine.volume}
                    onChange={(e) => engine.setVolume(parseFloat(e.target.value))}
                    className="range range-xs range-primary flex-1" aria-label="Volume" />
                </label>
                <label className="flex items-center gap-2" title={engine.gaplessEnabled ? "Crossfade (disabled while Gapless is on)" : "Crossfade seconds"}>
                  <span className="w-4 h-4 opacity-60 shrink-0"><Ic.Gauge /></span>
                  <input type="range" min="0" max="12" step="1" value={engine.crossfade}
                    disabled={engine.gaplessEnabled}
                    onChange={(e) => engine.setCrossfade(parseInt(e.target.value, 10))}
                    className="range range-xs range-secondary flex-1 disabled:opacity-30" aria-label="Crossfade" />
                  <span className="text-[10px] tabular-nums opacity-60 w-6">{engine.crossfade}s</span>
                </label>
              </div>
              <label className="flex items-center gap-2 self-start" title="Gapless playback — pre-loads the next track and starts it instantly with no fade or gap. Mutually exclusive with crossfade.">
                <span className={"w-4 h-4 shrink-0 " + (engine.gaplessEnabled ? "text-primary" : "opacity-60")}><Ic.Disc /></span>
                <span className="text-xs opacity-80">Gapless</span>
                <input type="checkbox" className="toggle toggle-xs toggle-primary"
                  checked={engine.gaplessEnabled}
                  onChange={(e) => engine.setGaplessEnabled(e.target.checked)}
                  aria-label="Gapless playback" />
              </label>
            </div>

            {/* right: tabs */}
            <div className="flex-1 flex flex-col min-h-0 border-t lg:border-t-0 lg:border-l border-base-content/10">
              <div className="tabs tabs-boxed m-3 mb-0 bg-base-200">
                {[["queue", "Queue", Ic.Queue], ["lyrics", "Lyrics", Ic.Lyrics], ["eq", "Equalizer", Ic.Sliders]].map(([k, label, Icon]) => (
                  <button key={k} type="button"
                    className={"tab gap-1 " + (p.activeTab === k ? "tab-active" : "")}
                    onClick={() => store.setActiveTab(k)}>
                    <span className="w-4 h-4"><Icon /></span>{label}
                  </button>
                ))}
              </div>
              <div className="flex-1 min-h-0 p-3 overflow-hidden">
                {p.activeTab === "queue" && <QueuePanel />}
                {p.activeTab === "lyrics" && <Lyrics />}
                {p.activeTab === "eq" && <Equalizer />}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function QueuePanel() {
  const { queue, index, store } = useMusicPlayer();
  const dragRef = useRef(null);

  if (!queue.length) {
    return <div className="flex items-center justify-center h-full opacity-40 text-sm">Queue is empty</div>;
  }
  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-2 px-1">
        <span className="text-xs opacity-60">{queue.length} tracks</span>
        <div className="flex items-center gap-1">
          <button type="button" className="btn btn-ghost btn-xs" onClick={() => store.cacheQueueForOffline()} title="Download queue for offline">
            <span className="w-3.5 h-3.5 mr-1"><Ic.Download /></span>Download all
          </button>
          <button type="button" className="btn btn-ghost btn-xs" onClick={() => store.clearQueue()}>Clear</button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto space-y-1 pr-1">
        {queue.map((it, i) => {
          const active = i === index;
          const liked = store.isLiked(it);
          return (
            <div
              key={it._qid || i}
              draggable
              onDragStart={() => { dragRef.current = i; }}
              onDragOver={(e) => e.preventDefault()}
              onDrop={() => { if (dragRef.current != null) store.moveInQueue(dragRef.current, i); dragRef.current = null; }}
              className={"flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer group " + (active ? "bg-primary/15 text-primary" : "hover:bg-base-content/5")}
              onClick={() => store.jumpTo(i, true)}
            >
              <span className="text-[10px] tabular-nums opacity-40 w-5 shrink-0">{i + 1}</span>
              <div className="flex-1 min-w-0">
                <div className="text-xs font-medium truncate">{it.title || it.name || "Unknown"}</div>
                <div className="text-[10px] opacity-50 truncate">{it.artist || it.artist_name || ""}</div>
              </div>
              {active && <span className="w-2 h-2 rounded-full bg-primary animate-pulse shrink-0" />}
              <button type="button"
                className={"btn btn-ghost btn-xs btn-circle " + (store.isOffline(it) ? "text-primary opacity-100" : "opacity-0 group-hover:opacity-100")}
                disabled={store.isOfflineBusy(it)}
                onClick={(e) => { e.stopPropagation(); store.toggleOffline(it); }}
                title={store.isOffline(it) ? "Remove offline copy" : "Download for offline"}>
                <span className={"w-3.5 h-3.5" + (store.isOfflineBusy(it) ? " animate-pulse" : "")}><Ic.Download /></span>
              </button>
              <button type="button"
                className={"btn btn-ghost btn-xs btn-circle opacity-0 group-hover:opacity-100 " + (liked ? "text-error opacity-100" : "")}
                onClick={(e) => { e.stopPropagation(); store.toggleLike(it); }} title="Like">
                <span className="w-3.5 h-3.5">{liked ? <Ic.HeartFill /> : <Ic.Heart />}</span>
              </button>
              <button type="button"
                className="btn btn-ghost btn-xs btn-circle opacity-0 group-hover:opacity-100"
                onClick={(e) => { e.stopPropagation(); store.removeAt(i); }} title="Remove">
                <span className="w-3.5 h-3.5"><Ic.X /></span>
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
