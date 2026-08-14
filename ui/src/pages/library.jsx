import React, { useState } from "react";
import { LibraryModuleShell, PosterTile, TeachEmpty } from "../components/ui.jsx";

export function LibraryBrowserPage({ movies = [], series = [], music = [], books = [], setMiniPlayer, setPage }) {
  const [tab, setTab] = useState("movies");
  const [q, setQ] = useState("");

  const downloaded = (list) => (list || []).filter(x => x.file_path || x.status === "downloaded");
  let items = [];
  if (tab === "movies") items = downloaded(movies);
  else if (tab === "tv") items = series || [];
  else if (tab === "music") items = downloaded(music);
  else if (tab === "books") items = downloaded(books);
  if (q.trim()) {
    const f = q.toLowerCase();
    items = items.filter(x => (x.title || "").toLowerCase().includes(f));
  }

  return (
    <LibraryModuleShell
      title="Library player"
      active={tab}
      onNav={setTab}
      nav={[
        { id: "movies", label: "Movies" },
        { id: "tv", label: "TV" },
        { id: "music", label: "Music" },
        { id: "books", label: "Books" },
      ]}
      tools={<input className="mr-search" placeholder="Filter…" value={q} onChange={e => setQ(e.target.value)} />}
    >
      <p className="text-xs opacity-60 mb-3">Play downloaded items in the built-in player without Jellyfin.</p>
      <div className="poster-grid">
        {items.map(item => (
          <PosterTile
            key={item.id}
            title={item.title}
            year={item.year}
            poster={item.poster_path}
            status={item.status}
            onClick={() => {
              if (setMiniPlayer && item.file_path) {
                setMiniPlayer({ title: item.title, path: item.file_path, itemId: item.id });
              } else if (tab === "tv" && setPage) {
                setPage("tv");
              }
            }}
          />
        ))}
      </div>
      {!items.length && (
        <TeachEmpty
          title="Nothing playable here"
          actionLabel={tab === "tv" ? "Open TV" : tab === "music" ? "Open Music" : tab === "books" ? "Open Books" : "Open Movies"}
          onAction={() => setPage && setPage(tab === "tv" ? "tv" : tab === "music" ? "music" : tab === "books" ? "books" : "movies")}
        >
          <p>Downloaded items with a file path appear here for built-in playback. TV series open the TV library to pick an episode.</p>
        </TeachEmpty>
      )}
    </LibraryModuleShell>
  );
}

export default LibraryBrowserPage;
