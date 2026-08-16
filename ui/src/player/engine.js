/* ─────────────────────────────────────────────────────────────────────────────
 * MediaOs Music Engine — Web Audio API singleton
 * Signal chain (per deck):
 *   <audio> → MediaElementSource → deckGain → [shared: 10× BiquadFilter → AnalyserNode → masterGain] → destination
 *
 * Two decks (A/B) share one EQ/analyser/master chain but have independent
 * <audio> elements and per-deck gain nodes. This lets us actually overlap
 * two tracks (crossfade) or pre-load the next track into the idle deck and
 * flip to it the instant the current one ends (gapless) — a single
 * <audio> element can't do either.
 *
 * NOTE (session 5, read before touching): an earlier version of this file
 * had a single <audio> element and `setCrossfade()` only stored a number —
 * `_maybePrefetchCrossfade` in store.js never actually faded anything. If
 * you're chasing a bug where old crossfade behavior seemed to do nothing,
 * that's why. This rewrite makes crossfade and gapless both real.
 * ───────────────────────────────────────────────────────────────────────────── */

export const EQ_FREQS = [31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000];
export const EQ_LABELS = ["31", "62", "125", "250", "500", "1k", "2k", "4k", "8k", "16k"];

export const EQ_PRESETS = {
  flat:       [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
  bass:       [6, 5, 4, 2, 1, 0, 0, 0, 0, 0],
  treble:     [0, 0, 0, 0, 0, 1, 2, 4, 5, 6],
  vocal:      [-2, -1, 0, 2, 4, 4, 3, 1, 0, -1],
  rock:       [4, 3, 1, -1, -2, 0, 2, 3, 4, 4],
  pop:        [-1, 2, 4, 4, 2, 0, -1, -1, 1, 2],
  jazz:       [3, 2, 1, 2, -1, -1, 0, 1, 2, 3],
  classical:  [4, 3, 0, 0, 0, 0, -2, -2, 0, 3],
  electronic: [5, 4, 1, 0, -2, 1, 0, 2, 4, 5],
  hiphop:     [5, 4, 2, 1, -1, -1, 1, 0, 2, 3],
  acoustic:   [3, 2, 1, 1, 2, 2, 2, 3, 3, 2],
  loudness:   [5, 3, 0, 0, -1, 0, -1, 0, 3, 5],
  spoken:     [-3, -2, 0, 1, 3, 4, 4, 3, 1, 0],
};

const LS = {
  volume: "mos.music.volume",
  muted: "mos.music.muted",
  eqGains: "mos.music.eq.gains",
  eqPreset: "mos.music.eq.preset",
  eqEnabled: "mos.music.eq.enabled",
  crossfade: "mos.music.crossfade",
  gapless: "mos.music.gapless",
};

function lsGet(key, fallback) {
  try {
    const v = localStorage.getItem(key);
    return v == null ? fallback : JSON.parse(v);
  } catch {
    return fallback;
  }
}
function lsSet(key, val) {
  try { localStorage.setItem(key, JSON.stringify(val)); } catch { /* noop */ }
}

// How long before track-end store.js should start preloading the next
// track's <audio> element, regardless of crossfade length — gapless needs
// a lead time too since `.load()` + enough buffering isn't instant.
export const PREFETCH_LEAD_SEC = 4;

class MusicEngine {
  constructor() {
    this.ctx = null;
    this.decks = null;       // [{audio, source, gain}, {audio, source, gain}] once _ensure() runs
    this.active = 0;         // index into this.decks of the "now playing" deck
    this.filters = [];
    this.analyser = null;
    this.gainNode = null;    // master volume/mute gain, post-EQ/analyser
    this._listeners = {};
    this._freqData = null;

    this._nextUrl = null;    // url currently loaded into the idle deck, or null
    this._nextReady = false; // idle deck has fired canplay for _nextUrl
    this._crossfading = false;
    this._cfTimer = null;

    this.volume = lsGet(LS.volume, 0.9);
    this.muted = lsGet(LS.muted, false);
    this.eqGains = lsGet(LS.eqGains, EQ_PRESETS.flat.slice());
    this.eqPreset = lsGet(LS.eqPreset, "flat");
    this.eqEnabled = lsGet(LS.eqEnabled, true);
    this.crossfade = lsGet(LS.crossfade, 0);       // seconds 0..12
    this.gaplessEnabled = lsGet(LS.gapless, false); // mutually exclusive with crossfade > 0 in the UI
  }

  /* ── event emitter ── */
  on(evt, cb) {
    (this._listeners[evt] = this._listeners[evt] || []).push(cb);
    return () => this.off(evt, cb);
  }
  off(evt, cb) {
    const arr = this._listeners[evt];
    if (!arr) return;
    const i = arr.indexOf(cb);
    if (i >= 0) arr.splice(i, 1);
  }
  emit(evt, ...args) {
    (this._listeners[evt] || []).slice().forEach((cb) => {
      try { cb(...args); } catch (e) { console.error("[engine]", e); }
    });
  }

  get idleIndex() { return this.active === 0 ? 1 : 0; }
  get activeDeck() { return this.decks ? this.decks[this.active] : null; }
  get idleDeck() { return this.decks ? this.decks[this.idleIndex] : null; }

  /* ── lazy init (must be called from a user gesture) ── */
  _ensure() {
    if (this.decks) return;

    const AC = window.AudioContext || window.webkitAudioContext;
    this.ctx = new AC();

    // Build 10-band EQ: lowshelf → 8× peaking → highshelf (shared by both decks)
    this.filters = EQ_FREQS.map((freq, i) => {
      const f = this.ctx.createBiquadFilter();
      if (i === 0) f.type = "lowshelf";
      else if (i === EQ_FREQS.length - 1) f.type = "highshelf";
      else { f.type = "peaking"; f.Q.value = 1.1; }
      f.frequency.value = freq;
      f.gain.value = this.eqEnabled ? (this.eqGains[i] || 0) : 0;
      return f;
    });

    this.analyser = this.ctx.createAnalyser();
    this.analyser.fftSize = 256;
    this.analyser.smoothingTimeConstant = 0.82;
    this._freqData = new Uint8Array(this.analyser.frequencyBinCount);

    this.gainNode = this.ctx.createGain();
    this.gainNode.gain.value = this.muted ? 0 : this.volume;

    // shared tail: filters chain → analyser → master gain → destination
    for (let i = 1; i < this.filters.length; i++) { this.filters[i - 1].connect(this.filters[i]); }
    this.filters[this.filters.length - 1].connect(this.analyser);
    this.analyser.connect(this.gainNode);
    this.gainNode.connect(this.ctx.destination);

    this.decks = [this._makeDeck(), this._makeDeck()];
    this.decks[this.active].gain.gain.value = 1;
    this.decks[this.idleIndex].gain.gain.value = 0;
  }

  _makeDeck() {
    const audio = new Audio();
    audio.crossOrigin = "anonymous";
    audio.preload = "auto";
    const source = this.ctx.createMediaElementSource(audio);
    const gain = this.ctx.createGain();
    gain.gain.value = 0;
    source.connect(gain);
    gain.connect(this.filters[0]);

    const deck = { audio, source, gain };

    // proxy events, but only for whichever deck is currently "active" —
    // the idle deck's own timeupdate/etc. are internal bookkeeping only.
    const proxied = ["timeupdate", "play", "pause", "loadedmetadata", "durationchange", "waiting", "playing", "error", "stalled"];
    proxied.forEach((e) => audio.addEventListener(e, () => {
      if (this.decks && this.decks[this.active] === deck) this.emit(e);
    }));
    audio.addEventListener("canplay", () => {
      if (this.decks && this.decks[this.idleIndex] === deck && audio.src === this._nextUrl) {
        this._nextReady = true;
      }
      if (this.decks && this.decks[this.active] === deck) this.emit("canplay");
    });
    audio.addEventListener("ended", () => this._onDeckEnded(deck));

    return deck;
  }

  resume() {
    this._ensure();
    if (this.ctx && this.ctx.state === "suspended") this.ctx.resume().catch(() => {});
  }

  /* ── transport (always targets the active deck) ── */
  load(src) {
    this._ensure();
    this._cancelCrossfade();
    // if this src is already sitting pre-buffered in the idle deck (we were
    // asked to load what we'd already prefetched), just swap decks instead
    // of a redundant network fetch.
    if (this._nextUrl === src && this.idleDeck) {
      this._swapDecks();
      this.activeDeck.gain.gain.value = 1;
      return;
    }
    this._nextUrl = null;
    this._nextReady = false;
    const deck = this.activeDeck;
    deck.gain.gain.value = 1;
    deck.audio.src = src;
    deck.audio.load();
    // make sure the idle deck is silent and stopped
    const idle = this.idleDeck;
    if (idle) { idle.gain.gain.value = 0; idle.audio.pause(); }
  }
  play() {
    this.resume();
    if (!this.activeDeck) return;
    const p = this.activeDeck.audio.play();
    if (p && p.catch) p.catch(() => {});
  }
  pause() { if (this.activeDeck) this.activeDeck.audio.pause(); }
  stop() {
    if (!this.activeDeck) return;
    this._cancelCrossfade();
    this.activeDeck.audio.pause();
    try { this.activeDeck.audio.currentTime = 0; } catch { /* noop */ }
    this._nextUrl = null;
    this._nextReady = false;
  }
  seek(sec) {
    if (!this.activeDeck || !isFinite(sec)) return;
    try { this.activeDeck.audio.currentTime = Math.max(0, sec); } catch { /* noop */ }
  }
  get currentTime() { return this.activeDeck ? this.activeDeck.audio.currentTime : 0; }
  get duration() { return this.activeDeck && isFinite(this.activeDeck.audio.duration) ? this.activeDeck.audio.duration : 0; }
  get paused() { return this.activeDeck ? this.activeDeck.audio.paused : true; }

  /* ── prefetch / crossfade / gapless ──
   * Called by store.js (which owns queue/shuffle/repeat logic) once it
   * knows what track would play next, a few seconds before the current
   * one ends. `url` is the next track's stream URL, or null if there is
   * no next track (end of queue, repeat off).
   */
  prepareNext(url) {
    if (!this.decks) return;
    if (!url) { this._nextUrl = null; this._nextReady = false; return; }
    if (this._nextUrl === url) return; // already prefetching/prefetched this one
    this._nextUrl = url;
    this._nextReady = false;
    const idle = this.idleDeck;
    idle.gain.gain.value = 0;
    idle.audio.src = url;
    idle.audio.load();
  }

  // Called from store's timeupdate handler once per tick. Owns the actual
  // crossfade ramp; gapless is instead handled reactively in `_onDeckEnded`.
  tickCrossfade(ct, dur) {
    if (!this.crossfade || this._crossfading || !dur) return;
    if (!this._nextUrl || !this._nextReady) return;
    if (dur - ct > this.crossfade) return;
    this._startCrossfade();
  }

  _startCrossfade() {
    const from = this.activeDeck;
    const to = this.idleDeck;
    if (!from || !to || !this._nextUrl) return;
    this._crossfading = true;
    const dur = this.crossfade;
    const now = this.ctx.currentTime;

    try { to.audio.currentTime = 0; } catch { /* noop */ }
    const p = to.audio.play();
    if (p && p.catch) p.catch(() => {});

    from.gain.gain.cancelScheduledValues(now);
    from.gain.gain.setValueAtTime(from.gain.gain.value, now);
    from.gain.gain.linearRampToValueAtTime(0, now + dur);

    to.gain.gain.cancelScheduledValues(now);
    to.gain.gain.setValueAtTime(0, now);
    to.gain.gain.linearRampToValueAtTime(1, now + dur);

    // hand off "now playing" to the incoming deck right away, so the UI
    // (title, progress bar, scrobble timer) tracks the new track for the
    // whole overlap window rather than jumping at the very end of it.
    this._swapDecks();
    this.emit("trackadvance");

    this._cfTimer = setTimeout(() => {
      this._crossfading = false;
      this._cfTimer = null;
      const old = this.decks[this.idleIndex]; // the deck we just faded out of
      old.audio.pause();
      old.gain.gain.value = 0;
    }, dur * 1000);
  }

  _cancelCrossfade() {
    if (this._cfTimer) { clearTimeout(this._cfTimer); this._cfTimer = null; }
    if (this._crossfading && this.decks) {
      // a linearRampToValueAtTime automation curve keeps running on the
      // AudioParam even after we stop caring about it — cancel it on both
      // decks, not just the setTimeout, or a manual skip mid-crossfade can
      // leave a gain node ramping toward a stale target.
      const now = this.ctx.currentTime;
      this.decks.forEach((d) => d.gain.gain.cancelScheduledValues(now));
    }
    this._crossfading = false;
  }

  _swapDecks() {
    this.active = this.idleIndex === 0 ? 1 : 0; // idleIndex was computed pre-swap
    this._nextUrl = null;
    this._nextReady = false;
  }

  _onDeckEnded(deck) {
    if (this.decks[this.idleIndex] === deck) return; // stray event from a deck we already faded out
    if (this._crossfading) return; // crossfade already handed off; ignore the old deck's own `ended`
    // gapless: if we pre-loaded the next track and it's ready, flip to it
    // immediately with no gap. If not ready in time, fall through to a
    // normal `ended` emit so store.js does its usual full reload — a late
    // gapless swap that still has a gap isn't worth reaching for.
    if (!this.crossfade && this.gaplessEnabled && this._nextUrl && this._nextReady) {
      const to = this.idleDeck;
      to.gain.gain.value = 1;
      const p = to.audio.play();
      if (p && p.catch) p.catch(() => {});
      this._swapDecks();
      this.emit("trackadvance");
      return;
    }
    this.emit("ended");
  }

  /* ── volume ── */
  setVolume(v) {
    this.volume = Math.min(1, Math.max(0, v));
    lsSet(LS.volume, this.volume);
    if (this.gainNode && !this.muted) this.gainNode.gain.value = this.volume;
    this.emit("volumechange");
  }
  setMuted(m) {
    this.muted = !!m;
    lsSet(LS.muted, this.muted);
    if (this.gainNode) this.gainNode.gain.value = this.muted ? 0 : this.volume;
    this.emit("volumechange");
  }
  toggleMute() { this.setMuted(!this.muted); }

  /* ── equalizer ── */
  _applyEq() {
    if (!this.filters.length) return;
    this.filters.forEach((f, i) => {
      const target = this.eqEnabled ? (this.eqGains[i] || 0) : 0;
      try { f.gain.setTargetAtTime(target, this.ctx.currentTime, 0.02); }
      catch { f.gain.value = target; }
    });
  }
  setBand(i, db) {
    this.eqGains[i] = Math.min(12, Math.max(-12, db));
    this.eqPreset = "custom";
    lsSet(LS.eqGains, this.eqGains);
    lsSet(LS.eqPreset, this.eqPreset);
    this._applyEq();
    this.emit("eqchange");
  }
  applyPreset(name) {
    const p = EQ_PRESETS[name];
    if (!p) return;
    this.eqGains = p.slice();
    this.eqPreset = name;
    lsSet(LS.eqGains, this.eqGains);
    lsSet(LS.eqPreset, this.eqPreset);
    this._applyEq();
    this.emit("eqchange");
  }
  setEqEnabled(on) {
    this.eqEnabled = !!on;
    lsSet(LS.eqEnabled, this.eqEnabled);
    this._applyEq();
    this.emit("eqchange");
  }
  resetEq() { this.applyPreset("flat"); }

  /* ── crossfade / gapless settings — mutually exclusive in the UI ── */
  setCrossfade(sec) {
    this.crossfade = Math.min(12, Math.max(0, sec));
    lsSet(LS.crossfade, this.crossfade);
    if (this.crossfade > 0 && this.gaplessEnabled) {
      this.gaplessEnabled = false;
      lsSet(LS.gapless, false);
    }
    this.emit("cfchange");
  }
  setGaplessEnabled(on) {
    this.gaplessEnabled = !!on;
    lsSet(LS.gapless, this.gaplessEnabled);
    if (this.gaplessEnabled && this.crossfade > 0) {
      this.crossfade = 0;
      lsSet(LS.crossfade, 0);
    }
    this.emit("cfchange");
  }

  /* ── analyser ── */
  getFrequencyData() {
    if (!this.analyser) return null;
    this.analyser.getByteFrequencyData(this._freqData);
    return this._freqData;
  }
}

export const engine = new MusicEngine();
export default engine;
