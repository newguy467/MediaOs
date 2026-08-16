/* MediaOS service worker.
 *
 * Three strategies, matched in order in the fetch handler:
 *  1. /api/player/stream — cache-first against the SAME cache name
 *     offline.js writes into ("mediaos-audio-v1"). Tracks only land in
 *     this cache when the user explicitly taps the offline toggle
 *     (offline.js's cacheTrack) — this worker never writes to the audio
 *     cache itself, only reads from it, so ordinary listening never
 *     grows storage unbounded.
 *  2. Same-origin static app-shell assets (JS/CSS/images under /assets/,
 *     icons, the HTML document) — stale-while-revalidate, precached on
 *     install so the shell loads offline too.
 *  3. Everything else (all other /api/* calls — lists, mutations, etc.)
 *     — network only, no offline support attempted.
 *
 * IMPORTANT: AUDIO_CACHE must stay byte-for-byte identical to
 * OFFLINE_CACHE in ui/src/player/offline.js. A mismatch here silently
 * breaks offline playback (the SW would read from a bucket nothing
 * ever writes into).
 */

const AUDIO_CACHE = "mediaos-audio-v1";
const SHELL_CACHE = "mediaos-shell-v1";

const PRECACHE_URLS = [
  "/",
  "/manifest.webmanifest",
  "/favicon.png",
  "/icon-192.png",
  "/logo-icon.png",
  "/logo-icon-64.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .catch(() => {})
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) =>
        Promise.all(
          names
            .filter((n) => n !== AUDIO_CACHE && n !== SHELL_CACHE)
            .map((n) => caches.delete(n))
        )
      )
      .then(() => self.clients.claim())
  );
});

function isStreamRequest(url) {
  return url.pathname === "/api/player/stream";
}

function isApiRequest(url) {
  return url.pathname.startsWith("/api/");
}

function isShellAsset(url) {
  if (url.origin !== self.location.origin) return false;
  if (isApiRequest(url)) return false;
  return (
    url.pathname === "/" ||
    url.pathname.startsWith("/assets/") ||
    url.pathname.endsWith(".png") ||
    url.pathname.endsWith(".webmanifest") ||
    url.pathname.endsWith(".ico")
  );
}

/* Slice a cached (un-ranged) Response against an incoming Range header
 * and return a 206 partial response, the same way a real HTTP server
 * would. <audio> elements issue Range requests even for same-origin
 * src, so a plain cache.match() would otherwise hand back a 200 with
 * the whole file and confuse the element's seeking/duration logic. */
async function rangedResponseFromCache(cachedResponse, rangeHeader) {
  const buffer = await cachedResponse.arrayBuffer();
  const total = buffer.byteLength;

  if (!rangeHeader) {
    return new Response(buffer, {
      status: 200,
      headers: {
        "Content-Type": cachedResponse.headers.get("Content-Type") || "audio/mpeg",
        "Content-Length": String(total),
        "Accept-Ranges": "bytes",
      },
    });
  }

  const match = /bytes=(\d*)-(\d*)/.exec(rangeHeader);
  let start = match && match[1] ? parseInt(match[1], 10) : 0;
  let end = match && match[2] ? parseInt(match[2], 10) : total - 1;
  if (Number.isNaN(start)) start = 0;
  if (Number.isNaN(end) || end >= total) end = total - 1;
  if (start > end) start = 0;

  const slice = buffer.slice(start, end + 1);
  return new Response(slice, {
    status: 206,
    headers: {
      "Content-Type": cachedResponse.headers.get("Content-Type") || "audio/mpeg",
      "Content-Range": `bytes ${start}-${end}/${total}`,
      "Content-Length": String(slice.byteLength),
      "Accept-Ranges": "bytes",
    },
  });
}

async function handleStreamRequest(request) {
  const cache = await caches.open(AUDIO_CACHE);
  const cached = await cache.match(request.url, { ignoreVary: true, ignoreSearch: false });
  if (cached) {
    try {
      return await rangedResponseFromCache(cached, request.headers.get("Range"));
    } catch {
      // fall through to network on any slicing failure
    }
  }
  try {
    return await fetch(request);
  } catch (err) {
    return new Response(null, { status: 504, statusText: "Offline and not cached" });
  }
}

async function handleShellAsset(request) {
  const cache = await caches.open(SHELL_CACHE);
  const cached = await cache.match(request);
  const networkPromise = fetch(request)
    .then((res) => {
      if (res && res.ok) cache.put(request, res.clone());
      return res;
    })
    .catch(() => null);
  return cached || (await networkPromise) || new Response(null, { status: 504 });
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);

  if (isStreamRequest(url)) {
    event.respondWith(handleStreamRequest(request));
    return;
  }

  if (isShellAsset(url)) {
    event.respondWith(handleShellAsset(request));
    return;
  }

  // All other /api/* calls: network only, no offline support attempted.
});
