/* ─────────────────────────────────────────────────────────────────────────────
 * Offline track caching for the music player.
 * Uses the Cache Storage API directly from the page (no service-worker
 * round-trip needed to write into the cache — sw.js just needs to *read*
 * from the same cache name to serve cached tracks while offline).
 * ───────────────────────────────────────────────────────────────────────────── */

export const OFFLINE_CACHE = "mediaos-audio-v1";

export function offlineSupported() {
  return typeof window !== "undefined" && "caches" in window;
}

function keyFor(url) {
  // Cache against an absolute URL so sw.js range-request handling (which
  // matches on request.url) lines up with what gets fetched at playback time.
  return new URL(url, window.location.origin).toString();
}

export async function isTrackCached(url) {
  if (!offlineSupported() || !url) return false;
  try {
    const cache = await caches.open(OFFLINE_CACHE);
    const match = await cache.match(keyFor(url), { ignoreVary: true });
    return !!match;
  } catch {
    return false;
  }
}

export async function cacheTrack(url) {
  if (!offlineSupported() || !url) return false;
  try {
    const cache = await caches.open(OFFLINE_CACHE);
    const res = await fetch(url, { credentials: "same-origin" });
    if (!res.ok) return false;
    // Store the full, un-ranged response so sw.js can slice range requests
    // out of it later — most browsers issue a Range header for <audio src>.
    await cache.put(keyFor(url), res.clone());
    return true;
  } catch {
    return false;
  }
}

export async function uncacheTrack(url) {
  if (!offlineSupported() || !url) return false;
  try {
    const cache = await caches.open(OFFLINE_CACHE);
    return await cache.delete(keyFor(url));
  } catch {
    return false;
  }
}

export async function cachedTrackUrls() {
  if (!offlineSupported()) return [];
  try {
    const cache = await caches.open(OFFLINE_CACHE);
    const reqs = await cache.keys();
    return reqs.map((r) => r.url);
  } catch {
    return [];
  }
}

export async function offlineCacheSizeEstimate() {
  if (typeof navigator === "undefined" || !navigator.storage || !navigator.storage.estimate) return null;
  try {
    const { usage, quota } = await navigator.storage.estimate();
    return { usage, quota };
  } catch {
    return null;
  }
}
