import { useState, useEffect, useRef, useCallback } from "react";
import { api, TMDB } from "../api.js";
import Ic from "../icons.jsx";

/**
 * Global search modal — searches the local library (movies/tv/music/books/
 * comics/manga/audiobooks/adult/games) via GET /api/search, grouped by
 * media type. Opens on the 'mediaos-open-search' window event (dispatched
 * from the sidebar nav), mirroring how AiChatPanel listens for
 * 'mediaos-open-ai'. On result click, switches the page and dispatches
 * 'mediaos-open-item' so the target page can open that item's detail view.
 */
export default function GlobalSearch({ setPage }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef(null);
  const debounceRef = useRef(null);

  useEffect(() => {
    const openSearch = () => setOpen(true);
    window.addEventListener("mediaos-open-search", openSearch);
    return () => window.removeEventListener("mediaos-open-search", openSearch);
  }, []);

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current && inputRef.current.focus(), 30);
    } else {
      setQ("");
      setData(null);
    }
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const runSearch = useCallback((query) => {
    if (!query.trim()) { setData(null); setBusy(false); return; }
    setBusy(true);
    api.search(query, 6)
      .then((d) => setData(d))
      .catch(() => setData({ query, groups: [], total: 0 }))
      .finally(() => setBusy(false));
  }, []);

  function onChange(e) {
    const val = e.target.value;
    setQ(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => runSearch(val), 300);
  }

  function openItem(item) {
    setOpen(false);
    if (item.page) setPage && setPage(item.page);
    window.dispatchEvent(new CustomEvent("mediaos-open-item", {
      detail: { mediaType: item.media_type, id: item.id },
    }));
  }

  if (!open) return null;

  const groups = data?.groups || [];

  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center pt-[10vh] px-4 bg-black/60" onClick={() => setOpen(false)}>
      <div
        className="w-full max-w-2xl rounded-xl shadow-2xl border border-base-300 bg-base-100 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 px-3 py-2 border-b border-base-300">
          <Ic.Search />
          <input
            ref={inputRef}
            value={q}
            onChange={onChange}
            placeholder="Search your library — movies, TV, music, books, comics…"
            className="input input-ghost flex-1 focus:outline-none bg-transparent"
          />
          <button type="button" className="btn btn-ghost btn-xs btn-circle" onClick={() => setOpen(false)}>✕</button>
        </div>

        <div className="max-h-[60vh] overflow-y-auto">
          {busy && <div className="p-4 text-xs opacity-60">Searching…</div>}
          {!busy && q.trim() && groups.length === 0 && (
            <div className="p-4 text-xs opacity-60">No matches in your library for "{q}"</div>
          )}
          {!busy && !q.trim() && (
            <div className="p-4 text-xs opacity-50">Start typing to search everything already in your library.</div>
          )}
          {groups.map((g) => (
            <div key={g.media_type} className="px-3 py-2 border-b border-base-200 last:border-0">
              <div className="text-[10px] uppercase tracking-wide opacity-50 mb-1 px-1">{g.label}</div>
              <div className="space-y-0.5">
                {g.items.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className="w-full flex items-center gap-3 text-left px-2 py-1.5 rounded hover:bg-base-200"
                    onClick={() => openItem(item)}
                  >
                    {item.poster_path
                      ? <img className="w-8 h-11 object-cover rounded flex-shrink-0 bg-base-300"
                             src={item.poster_path.startsWith('http') ? item.poster_path : `${TMDB}${item.poster_path}`}
                             alt="" loading="lazy" />
                      : <div className="w-8 h-11 rounded bg-base-300 flex-shrink-0" />}
                    <div className="min-w-0">
                      <div className="text-sm truncate">{item.title}</div>
                      {item.subtitle && <div className="text-xs opacity-50 truncate">{item.subtitle}</div>}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
