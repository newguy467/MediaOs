/* ─────────────────────────────────────────────────────────────────────────────
 * MediaOs Music Store — framework-agnostic pub/sub global player state
 * Queue, transport, shuffle, repeat, likes, play counts, crossfade prefetch.
 * ───────────────────────────────────────────────────────────────────────────── */
import engine, { PREFETCH_LEAD_SEC } from "./engine.js";
import { cacheTrack, uncacheTrack, cachedTrackUrls, offlineSupported } from "./offline.js";
import { api } from "../api.js";

const LS = {
  queue: "mos.music.queue",
  index: "mos.music.index",
  shuffle: "mos.music.shuffle",
  repeat: "mos.music.repeat",
  radio: "mos.music.radio",
  likes: "mos.music.likes",
  plays: "mos.music.plays",
};

function lsGet(key, fallback) {
  try {
    const v = localStorage.getItem(key);
    return v == null ? fallback : JSON.parse(v);
  } catch { return fallback; }
}
function lsSet(key, val) {
  try { localStorage.setItem(key, JSON.stringify(val)); } catch { /* noop */ }
}

export function streamUrl(path) {
  return "/api/player/stream?path=" + encodeURIComponent(path);
}

function makeId() {
  return Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
}

class MusicStore {
  constructor() {
    this._subs = new Set();
    this.state = {
      queue: lsGet(LS.queue, []),
      index: lsGet(LS.index, -1),
      shuffle: lsGet(LS.shuffle, false),
      repeat: lsGet(LS.repeat, "off"), // off | all | one
      radioEnabled: lsGet(LS.radio, false),
      playing: false,
      currentTime: 0,
      duration: 0,
      likes: lsGet(LS.likes, {}),   // key: path → true
      plays: lsGet(LS.plays, {}),   // key: path → count
      offline: {},                  // key: path → true (populated async from Cache Storage)
      offlineBusy: {},              // key: path → true while caching/uncaching is in flight
      expanded: false,              // Now Playing overlay
      activeTab: "queue",           // queue | lyrics | eq
    };
    this._shuffleHistory = [];
    this._playStart = 0;
    this._scrobbled = false;
    this._pendingNextIndex = null; // cached peekNextIndex() result while a crossfade/gapless prefetch is in flight
    this._bindEngine();
    this._hydrateOffline();
  }

  /* ── offline caching ── */
  async _hydrateOffline() {
    if (!offlineSupported()) return;
    try {
      const urls = await cachedTrackUrls();
      if (!urls.length) return;
      const offline = { ...this.state.offline };
      for (const it of this.state.queue) {
        const url = streamUrl(it.path);
        const abs = new URL(url, window.location.origin).toString();
        if (urls.includes(abs)) offline[it.path] = true;
      }
      this._set({ offline });
    } catch { /* best effort */ }
  }
  isOffline(item) { return !!(item && item.path && this.state.offline[item.path]); }
  isOfflineBusy(item) { return !!(item && item.path && this.state.offlineBusy[item.path]); }
  async toggleOffline(item) {
    if (!item || !item.path || !offlineSupported()) return;
    const path = item.path;
    if (this.state.offlineBusy[path]) return;
    this._set({ offlineBusy: { ...this.state.offlineBusy, [path]: true } });
    try {
      if (this.state.offline[path]) {
        await uncacheTrack(streamUrl(path));
        this._set({ offline: { ...this.state.offline, [path]: false } });
      } else {
        const ok = await cacheTrack(streamUrl(path));
        if (ok) this._set({ offline: { ...this.state.offline, [path]: true } });
      }
    } finally {
      const busy = { ...this.state.offlineBusy };
      delete busy[path];
      this._set({ offlineBusy: busy });
    }
  }
  async cacheQueueForOffline() {
    for (const it of this.state.queue) {
      if (!this.state.offline[it.path]) await this.toggleOffline(it);
    }
  }

  /* ── pub/sub ── */
  subscribe(cb) { this._subs.add(cb); return () => this._subs.delete(cb); }
  getState() { return this.state; }
  _emit() { this._subs.forEach((cb) => { try { cb(this.state); } catch (e) { console.error(e); } }); }
  _set(patch) { this.state = { ...this.state, ...patch }; this._emit(); }

  /* ── engine wiring ── */
  _bindEngine() {
    engine.on("timeupdate", () => {
      const ct = engine.currentTime;
      const dur = engine.duration;
      this._set({ currentTime: ct, duration: dur });
      this._maybeScrobble(ct, dur);
      this._maybePrefetchNext(ct, dur);
      engine.tickCrossfade(ct, dur);
    });
    engine.on("ended", () => this._onEnded());
    engine.on("trackadvance", () => this._onEngineAdvance());
    engine.on("play", () => this._set({ playing: true }));
    engine.on("pause", () => this._set({ playing: false }));
    engine.on("loadedmetadata", () => this._set({ duration: engine.duration }));
  }

  current() {
    const { queue, index } = this.state;
    return index >= 0 && index < queue.length ? queue[index] : null;
  }

  /* ── queue management ── */
  setQueue(items, startIndex = 0, autoplay = true) {
    const queue = (items || []).map((it) => ({ ...it, _qid: it._qid || makeId() }));
    lsSet(LS.queue, queue);
    const index = queue.length ? Math.min(startIndex, queue.length - 1) : -1;
    lsSet(LS.index, index);
    this._shuffleHistory = [];
    this._pendingNextIndex = null;
    this._set({ queue, index });
    if (autoplay && index >= 0) this._loadCurrent(true);
  }
  enqueue(items) {
    const queue = this.state.queue.slice();
    (Array.isArray(items) ? items : [items]).forEach((it) => queue.push({ ...it, _qid: makeId() }));
    lsSet(LS.queue, queue);
    this._set({ queue });
    if (this.state.index < 0 && queue.length) this.jumpTo(0, true);
  }
  enqueueNext(item) {
    const queue = this.state.queue.slice();
    const at = this.state.index + 1;
    queue.splice(at, 0, { ...item, _qid: makeId() });
    lsSet(LS.queue, queue);
    this._pendingNextIndex = null;
    engine.prepareNext(null);
    this._set({ queue });
  }
  removeAt(i) {
    const queue = this.state.queue.slice();
    if (i < 0 || i >= queue.length) return;
    queue.splice(i, 1);
    let index = this.state.index;
    if (i < index) index -= 1;
    else if (i === index) {
      index = Math.min(index, queue.length - 1);
      lsSet(LS.queue, queue); lsSet(LS.index, index);
      this._set({ queue, index });
      if (index >= 0) this._loadCurrent(true); else this.stop();
      return;
    }
    lsSet(LS.queue, queue); lsSet(LS.index, index);
    this._pendingNextIndex = null;
    engine.prepareNext(null);
    this._set({ queue, index });
  }
  clearQueue() {
    lsSet(LS.queue, []); lsSet(LS.index, -1);
    this._shuffleHistory = [];
    this._pendingNextIndex = null;
    this.stop();
    this._set({ queue: [], index: -1 });
  }
  moveInQueue(from, to) {
    const queue = this.state.queue.slice();
    if (from < 0 || from >= queue.length || to < 0 || to >= queue.length) return;
    const [it] = queue.splice(from, 1);
    queue.splice(to, 0, it);
    let index = this.state.index;
    if (from === index) index = to;
    else if (from < index && to >= index) index -= 1;
    else if (from > index && to <= index) index += 1;
    lsSet(LS.queue, queue); lsSet(LS.index, index);
    this._pendingNextIndex = null;
    engine.prepareNext(null);
    this._set({ queue, index });
  }
  jumpTo(i, autoplay = true) {
    if (i < 0 || i >= this.state.queue.length) return;
    lsSet(LS.index, i);
    this._set({ index: i });
    this._loadCurrent(autoplay);
  }

  /* ── transport ── */
  _loadCurrent(autoplay) {
    const cur = this.current();
    if (!cur || !cur.path) return;
    this._pendingNextIndex = null;
    engine.load(streamUrl(cur.path));
    this._playStart = Date.now();
    this._scrobbled = false;
    if (autoplay) engine.play();
  }
  play() {
    if (!this.current() && this.state.queue.length) { this.jumpTo(0, true); return; }
    engine.play();
  }
  pause() { engine.pause(); }
  toggle() {
    if (!this.current()) { this.play(); return; }
    if (engine.paused) engine.play(); else engine.pause();
  }
  stop() { this._pendingNextIndex = null; engine.stop(); this._set({ playing: false, currentTime: 0 }); }
  seek(sec) { engine.seek(sec); }
  seekBy(delta) { engine.seek(engine.currentTime + delta); }

  next(auto = false) {
    const { queue, index, shuffle, repeat } = this.state;
    if (!queue.length) return;
    if (repeat === "one" && auto) { this.seek(0); this.play(); return; }
    if (shuffle) {
      if (queue.length === 1) { this.seek(0); this.play(); return; }
      this._shuffleHistory.push(index);
      let n = index;
      while (n === index) n = Math.floor(Math.random() * queue.length);
      this.jumpTo(n, true);
      return;
    }
    const n = index + 1;
    if (n < queue.length) { this.jumpTo(n, true); return; }
    if (repeat === "all") { this.jumpTo(0, true); return; }
    if (this.state.radioEnabled) { this._extendRadio(); return; }
    this._set({ playing: false });
  }
  prev() {
    const { queue, index, shuffle } = this.state;
    if (!queue.length) return;
    // restart if >3s in
    if (engine.currentTime > 3) { this.seek(0); return; }
    if (shuffle && this._shuffleHistory.length) {
      const p = this._shuffleHistory.pop();
      this.jumpTo(p, true);
      return;
    }
    const p = index - 1;
    if (p >= 0) this.jumpTo(p, true);
    else this.seek(0);
  }

  _onEnded() { this.next(true); }

  toggleRadio() {
    const radioEnabled = !this.state.radioEnabled;
    lsSet(LS.radio, radioEnabled);
    this._set({ radioEnabled });
  }

  _radioRowToQueueItem(r) {
    return {
      id: r.id,
      path: r.file_path,
      title: r.title,
      artist: r.artist_name || "",
      album: r.album_title || "",
      poster_path: r.poster_path || null,
      duration_ms: r.duration_ms,
      track_number: r.track_number,
      disc_number: r.disc_number,
    };
  }

  // Called when the queue runs out (not shuffle, not repeat-all) and radio
  // mode is on — fetches similar tracks seeded from the track that just
  // ended and appends them, then advances into the first one. Falls back
  // to stopping (same as radio mode off) if the seed has no id or the
  // fetch comes back empty, so a network hiccup can't spin silently.
  async _extendRadio() {
    if (this._radioBusy) return;
    const seed = this.current();
    if (!seed || !seed.id) { this._set({ playing: false }); return; }
    this._radioBusy = true;
    let rows = [];
    try { rows = await api.music.radio(seed.id, 10); } catch { rows = []; }
    this._radioBusy = false;
    const items = (Array.isArray(rows) ? rows : []).map(r => this._radioRowToQueueItem(r)).filter(it => it.path);
    if (!items.length) { this._set({ playing: false }); return; }
    const queue = [...this.state.queue, ...items];
    this._set({ queue });
    lsSet(LS.queue, queue);
    this.jumpTo(this.state.index + 1, true);
  }

  toggleShuffle() {
    const shuffle = !this.state.shuffle;
    lsSet(LS.shuffle, shuffle);
    this._shuffleHistory = [];
    this._pendingNextIndex = null;
    engine.prepareNext(null);
    this._set({ shuffle });
  }
  cycleRepeat() {
    const order = ["off", "all", "one"];
    const repeat = order[(order.indexOf(this.state.repeat) + 1) % order.length];
    lsSet(LS.repeat, repeat);
    this._pendingNextIndex = null;
    engine.prepareNext(null);
    this._set({ repeat });
  }

  /* ── likes & play counts ── */
  likeKey(item) { return item && (item.path || item.id || item.title); }
  isLiked(item) { const k = this.likeKey(item); return !!(k && this.state.likes[k]); }
  toggleLike(item) {
    const k = this.likeKey(item);
    if (!k) return;
    const likes = { ...this.state.likes };
    if (likes[k]) delete likes[k]; else likes[k] = true;
    lsSet(LS.likes, likes);
    this._set({ likes });
  }
  playCount(item) { const k = this.likeKey(item); return (k && this.state.plays[k]) || 0; }

  _maybeScrobble(ct, dur) {
    if (this._scrobbled || !dur) return;
    const cur = this.current();
    if (!cur) return;
    const threshold = Math.min(30, dur * 0.5);
    if (ct >= threshold) {
      this._scrobbled = true;
      const k = this.likeKey(cur);
      const plays = { ...this.state.plays, [k]: (this.state.plays[k] || 0) + 1 };
      lsSet(LS.plays, plays);
      this._set({ plays });
      this._scrobbleOut(cur);
    }
  }

  // Fire-and-forget push to whichever of Last.fm/ListenBrainz are enabled —
  // the backend no-ops per its own *_scrobble_out flag/credentials, same
  // pattern as Trakt, so it's safe to call both unconditionally here.
  _scrobbleOut(item) {
    if (!item || !item.id) return;
    try { api.scrobble.lastfm(item.id).catch(() => {}); } catch { /* noop */ }
    try { api.scrobble.listenbrainz(item.id).catch(() => {}); } catch { /* noop */ }
    // Local play-count ping for library_most_played smart playlists — same
    // fire-and-forget pattern/trigger point, no second threshold timer.
    try { api.music.trackPlayed(item.id).catch(() => {}); } catch { /* noop */ }
  }

  // Figures out which queue index would play next, without mutating any
  // state — used to prefetch into the engine's idle deck ahead of time for
  // crossfade/gapless. For shuffle, the pick is random; we cache it in
  // `_pendingNextIndex` so the prefetch and the eventual real advance agree
  // on the same track instead of rolling twice.
  _peekNextIndex() {
    const { queue, index, shuffle, repeat } = this.state;
    if (!queue.length) return -1;
    if (repeat === "one") return index; // loops the same track
    if (shuffle) {
      if (this._pendingNextIndex != null) return this._pendingNextIndex;
      if (queue.length === 1) return index;
      let n = index;
      while (n === index) n = Math.floor(Math.random() * queue.length);
      this._pendingNextIndex = n;
      return n;
    }
    const n = index + 1;
    if (n < queue.length) return n;
    if (repeat === "all") return 0;
    return -1; // end of queue
  }

  _maybePrefetchNext(ct, dur) {
    if (!dur) return;
    const wantsLead = engine.crossfade || engine.gaplessEnabled;
    if (!wantsLead) return;
    const lead = Math.max(engine.crossfade, PREFETCH_LEAD_SEC);
    if (dur - ct > lead) return;
    const idx = this._peekNextIndex();
    if (idx < 0) { engine.prepareNext(null); return; }
    const it = this.state.queue[idx];
    if (!it || !it.path) return;
    engine.prepareNext(streamUrl(it.path));
  }

  // The engine itself flipped decks (crossfade completed its handoff, or a
  // gapless swap fired on `ended`) — sync store state to match without
  // triggering another load, since the audio is already playing.
  _onEngineAdvance() {
    // `state.index` hasn't moved yet at this point, so this recomputes the
    // same answer `_maybePrefetchNext` already prefetched against — for
    // shuffle specifically that's only guaranteed because `_peekNextIndex`
    // caches its random pick in `_pendingNextIndex` until consumed here.
    const idx = this._peekNextIndex();
    const prevIndex = this.state.index;
    this._pendingNextIndex = null;
    if (idx < 0 || idx >= this.state.queue.length) return;
    if (this.state.shuffle && idx !== prevIndex) this._shuffleHistory.push(prevIndex);
    lsSet(LS.index, idx);
    this._playStart = Date.now();
    this._scrobbled = false;
    this._set({ index: idx, playing: true });
  }

  /* ── UI state ── */
  setExpanded(v) { this._set({ expanded: !!v }); }
  setActiveTab(t) { this._set({ activeTab: t }); }
}

export const musicStore = new MusicStore();
export default musicStore;
