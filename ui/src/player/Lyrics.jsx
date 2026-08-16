import React, { useEffect, useMemo, useRef, useState } from "react";
import useMusicPlayer from "./useMusicPlayer.js";

/* Parse LRC format → [{time, text}] sorted by time. */
export function parseLrc(text) {
  if (!text) return [];
  const out = [];
  const re = /\[(\d+):(\d+(?:\.\d+)?)\]/g;
  const lines = String(text).split(/\r?\n/);
  for (const line of lines) {
    const stamps = [];
    let m;
    re.lastIndex = 0;
    while ((m = re.exec(line)) !== null) {
      stamps.push(parseInt(m[1], 10) * 60 + parseFloat(m[2]));
    }
    const txt = line.replace(re, "").trim();
    if (stamps.length && txt) stamps.forEach((t) => out.push({ time: t, text: txt }));
  }
  return out.sort((a, b) => a.time - b.time);
}

export default function Lyrics() {
  const { current, currentTime, store } = useMusicPlayer();
  const [data, setData] = useState(null); // {synced, plain, source}
  const [loading, setLoading] = useState(false);
  const activeRef = useRef(null);
  const path = current && current.path;

  useEffect(() => {
    setData(null);
    if (!path) return;
    let cancelled = false;
    setLoading(true);
    const params = new URLSearchParams({
      path,
      title: current.title || "",
      artist: current.artist || "",
      album: current.album || "",
      duration: current.duration_ms ? String(Math.round(current.duration_ms / 1000)) : "",
    });
    fetch("/api/music/lyrics?" + params.toString())
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (!cancelled) setData(d); })
      .catch(() => { if (!cancelled) setData(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [path]); // eslint-disable-line react-hooks/exhaustive-deps

  const synced = useMemo(() => (data && data.synced ? parseLrc(data.synced) : []), [data]);

  const activeIdx = useMemo(() => {
    if (!synced.length) return -1;
    let idx = -1;
    for (let i = 0; i < synced.length; i++) {
      if (synced[i].time <= currentTime + 0.15) idx = i; else break;
    }
    return idx;
  }, [synced, currentTime]);

  useEffect(() => {
    if (activeRef.current) {
      activeRef.current.scrollIntoView({ block: "center", behavior: "smooth" });
    }
  }, [activeIdx]);

  if (!current) {
    return <div className="flex items-center justify-center h-full opacity-40 text-sm">Play a track to see lyrics</div>;
  }
  if (loading) {
    return <div className="flex items-center justify-center h-full opacity-40 text-sm">Loading lyrics…</div>;
  }
  if (!data || (!synced.length && !data.plain)) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-2 opacity-40 text-sm">
        <span>No lyrics found</span>
        <span className="text-[10px]">Add a .lrc or .txt sidecar file next to the audio, or embed lyrics tags</span>
      </div>
    );
  }

  if (synced.length) {
    return (
      <div className="lyrics-scroll h-full overflow-y-auto px-4 py-8 space-y-3">
        {synced.map((l, i) => (
          <button
            key={i}
            type="button"
            ref={i === activeIdx ? activeRef : null}
            onClick={() => store.seek(l.time)}
            className={
              "block w-full text-center transition-all duration-300 cursor-pointer " +
              (i === activeIdx
                ? "text-primary text-xl font-bold scale-105"
                : i < activeIdx
                ? "opacity-40 text-base"
                : "opacity-60 text-base hover:opacity-90")
            }
          >
            {l.text}
          </button>
        ))}
      </div>
    );
  }

  return (
    <div className="lyrics-scroll h-full overflow-y-auto px-6 py-8">
      <pre className="whitespace-pre-wrap text-center text-sm leading-7 opacity-80 font-sans">{data.plain}</pre>
    </div>
  );
}
