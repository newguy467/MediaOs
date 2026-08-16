import React, { useState, useEffect, useCallback, useRef } from "react";
import Ic, { Icons, P } from "../icons.jsx";
import { getToken, setToken, getAdvanced, setAdvancedFlag, AUTH_TOKEN_KEY } from "../storage.js";
import { api, TMDB, adultFetch } from "../api.js";
import { PageChrome, PosterTile, LibraryModuleShell, MediaDetailShell, LibraryLegend, LibraryHeader, MediaCard, StatusBadgeStack, libraryStatuses, CollectionProgressWidget, TeachEmpty, AddModal } from "../components/ui.jsx";
import { InteractiveResultsPanel, InteractiveResultsTable, MediaPlayer, HlsVideo } from "../components/media.jsx";

function CalendarPage({ setPage }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [cursor, setCursor] = useState(() => {
    const d = new Date();
    return new Date(d.getFullYear(), d.getMonth(), 1);
  });
  const [selected, setSelected] = useState(null); // YYYY-MM-DD
  const [filter, setFilter] = useState('all'); // all | episode | movie

  const load = () => {
    setLoading(true);
    const start = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
    const end = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0);
    const pad = (n) => String(n).padStart(2,'0');
    const fmt = (d) => `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;
    // expand range slightly for list continuity
    const s = new Date(start); s.setDate(s.getDate() - 7);
    const e = new Date(end); e.setDate(e.getDate() + 7);
    api.calendar.list(fmt(s), fmt(e)).then(setItems).catch(()=>[]).finally(()=>setLoading(false));
  };
  useEffect(() => { load(); }, [cursor]);

  const today = new Date().toISOString().slice(0,10);
  const byDate = {};
  (items||[]).forEach(it => {
    if (filter !== 'all' && it.kind && it.kind !== filter) return;
    // legacy items without kind are episodes
    const kind = it.kind || 'episode';
    if (filter !== 'all' && kind !== filter) return;
    (byDate[it.air_date] = byDate[it.air_date] || []).push({...it, kind});
  });

  // Month grid
  const year = cursor.getFullYear();
  const month = cursor.getMonth();
  const firstDow = new Date(year, month, 1).getDay(); // 0 Sun
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells = [];
  for (let i = 0; i < firstDow; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) {
    const key = `${year}-${String(month+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
    cells.push({ day: d, key, events: byDate[key] || [] });
  }
  while (cells.length % 7 !== 0) cells.push(null);

  const monthLabel = cursor.toLocaleString(undefined, { month: 'long', year: 'numeric' });
  const selectedEvents = selected ? (byDate[selected] || []) : [];

  return (
    <div className="space-y-4 max-w-6xl">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex-1 min-w-[180px]">
          <h1 className="mr-page-title">Calendar</h1>
          <p className="text-xs opacity-50">TV air dates + recent movie adds — dense month grid</p>
        </div>
        <div className="join">
          <button type="button" className="btn btn-sm join-item" onClick={()=>setCursor(new Date(year, month-1, 1))}>‹</button>
          <button type="button" className="btn btn-sm join-item btn-ghost min-w-[140px]" onClick={()=>setCursor(new Date())}>{monthLabel}</button>
          <button type="button" className="btn btn-sm join-item" onClick={()=>setCursor(new Date(year, month+1, 1))}>›</button>
        </div>
        <div className="join">
          <button type="button" className={"btn btn-xs join-item "+(filter==='all'?'btn-primary':'')} onClick={()=>setFilter('all')}>All</button>
          <button type="button" className={"btn btn-xs join-item "+(filter==='episode'?'btn-primary':'')} onClick={()=>setFilter('episode')}>TV</button>
          <button type="button" className={"btn btn-xs join-item "+(filter==='movie'?'btn-primary':'')} onClick={()=>setFilter('movie')}>Movies</button>
        </div>
      </div>

      {loading ? <span className="loading loading-spinner"/> : (
        <div className="grid lg:grid-cols-5 gap-4">
          <div className="lg:col-span-3 card bg-base-200 border border-base-content/5 shadow-sm overflow-hidden">
            <div className="grid grid-cols-7 text-[10px] uppercase tracking-wide opacity-50 border-b border-base-content/10">
              {['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].map(d=>(
                <div key={d} className="p-2 text-center font-medium">{d}</div>
              ))}
            </div>
            <div className="grid grid-cols-7 auto-rows-fr">
              {cells.map((c, i) => {
                if (!c) return <div key={'e'+i} className="min-h-[72px] bg-base-300/20 border border-base-content/5" />;
                const isToday = c.key === today;
                const isSel = c.key === selected;
                const ev = c.events;
                return (
                  <button key={c.key} type="button"
                    className={"min-h-[72px] p-1.5 text-left border border-base-content/5 transition hover:bg-primary/10 "
                      + (isToday ? "bg-primary/15 " : "bg-base-100/40 ")
                      + (isSel ? "ring-2 ring-primary ring-inset " : "")}
                    onClick={()=>setSelected(c.key)}>
                    <div className={"text-xs font-semibold mb-1 "+(isToday?'text-primary':'opacity-70')}>{c.day}</div>
                    <div className="space-y-0.5">
                      {ev.slice(0,3).map((e,j)=>(
                        <div key={j} className={"truncate text-[9px] px-1 rounded "
                          + (e.kind==='movie' ? 'bg-secondary/30 text-secondary-content' : e.has_file ? 'bg-success/25' : 'bg-warning/20')}>
                          {e.kind==='movie' ? (e.movie_title||'Movie') : `${e.series_title||''} S${String(e.season_number||0).padStart(2,'0')}E${String(e.episode_number||0).padStart(2,'0')}`}
                        </div>
                      ))}
                      {ev.length>3 && <div className="text-[9px] opacity-50">+{ev.length-3} more</div>}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="lg:col-span-2 space-y-3">
            <div className="card bg-base-200 border border-base-content/5">
              <div className="card-body p-4 gap-2">
                <h2 className="font-semibold text-sm">{selected || 'Select a day'}</h2>
                {!selected && <p className="text-xs opacity-50">Click a day on the grid to see episodes and movies.</p>}
                {selected && selectedEvents.length===0 && <p className="text-xs opacity-50">Nothing scheduled.</p>}
                <div className="space-y-2 max-h-[420px] overflow-y-auto">
                  {selectedEvents.map((ep,i)=>(
                    <button type="button" key={i} className="flex items-start gap-2 p-2 rounded-lg bg-base-300/40 w-full text-left hover:bg-primary/10"
                      onClick={()=>{
                        const id = ep.media_item_id || ep.series_id || ep.movie_id || ep.id;
                        const mt = ep.kind === 'movie' ? 'movie' : 'tv';
                        if (id) {
                          window.dispatchEvent(new CustomEvent('mediaos-open-item', { detail: { mediaType: mt, id } }));
                          if (setPage) setPage(mt === 'movie' ? 'movies' : 'tv');
                        }
                      }}>
                      <div className="w-8 h-12 rounded bg-base-300 overflow-hidden shrink-0">
                        {ep.poster_path ? <img src={ep.poster_path} alt="" className="object-cover w-full h-full"/> : null}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-medium truncate">
                          {ep.kind==='movie' ? ep.movie_title : ep.series_title}
                        </div>
                        <div className="text-[11px] opacity-60">
                          {ep.kind==='movie' ? (ep.year || 'Movie') :
                            `S${String(ep.season_number).padStart(2,'0')}E${String(ep.episode_number).padStart(2,'0')}${ep.episode_title?` — ${ep.episode_title}`:''}`}
                        </div>
                      </div>
                      <span className={`badge badge-xs ${ep.has_file?'badge-success':ep.status==='downloading'?'badge-info':'badge-ghost'}`}>
                        {ep.has_file?'have':ep.status}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <div className="card bg-base-200/60 border border-base-content/5">
              <div className="card-body p-3 gap-1 text-[11px] opacity-60">
                <div><span className="inline-block w-2 h-2 rounded bg-warning/60 mr-1"/> Missing episode</div>
                <div><span className="inline-block w-2 h-2 rounded bg-success/50 mr-1"/> On disk</div>
                <div><span className="inline-block w-2 h-2 rounded bg-secondary/50 mr-1"/> Movie add</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}



export { CalendarPage };
