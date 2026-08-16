/**
 * React Router + lazy page map for MediaOS UI.
 * Deep links + code-splitting; setPage API preserved via usePageRoute.
 */
import React, { lazy, Suspense } from "react";
import { BrowserRouter, useNavigate, useLocation } from "react-router-dom";

export const PAGE_PATHS = {
  dashboard: "/",
  movies: "/movies",
  tv: "/tv",
  music: "/music",
  books: "/books",
  audiobooks: "/audiobooks",
  comics: "/comics",
  manga: "/manga",
  livetv: "/livetv",
  games: "/games",
  discover: "/discover",
  calendar: "/calendar",
  queue: "/queue",
  activity: "/activity",
  modules: "/modules",
  migrate: "/migrate",
  "migrate-wizard": "/migrate",
  wanted: "/wanted",
  youtube: "/youtube",
  podcasts: "/podcasts",
  converter: "/converter",
  library: "/library",
  "settings-hub": "/settings",
  "settings-quality-matrix": "/settings/quality-matrix",
  "settings-subtitles": "/settings/subtitles",
  "settings-adult": "/settings/adult",
  "settings-hunt": "/settings/hunt",
  "settings-setup": "/settings/setup",
  setup: "/setup",
  login: "/login",
  widgets: "/widgets",
  indexers: "/indexers",
  import: "/import",
  collections: "/collections",
  smartlists: "/smartlists",
  logs: "/logs",
  workers: "/workers",
  about: "/about",
  adult: "/adult",
  backup: "/backup",
  "converter-dashboard": "/converter",
  "external-arr": "/external-arr",
  homelab: "/homelab",
  "library-player": "/library",
  plugins: "/plugins",
  requests: "/requests",
  scrobbling: "/scrobbling",
  tracking: "/tracking",
  "widget-layout": "/widgets",
  "settings-quality": "/settings/quality",
  "settings-vpn": "/settings/vpn",
  "settings-youtube": "/settings/youtube",
  "settings-downloads": "/settings/downloads",
  "settings-library": "/settings/library",
  "settings-indexers": "/settings/indexers",
  "settings-indexers-cfg": "/settings/indexers-cfg",
  "settings-system": "/settings/system",
  "settings-metadata": "/settings/metadata",
  "settings-debrid": "/settings/debrid",
  "settings-usenet": "/settings/usenet",
  "settings-auth": "/settings/auth",
  "settings-sessions": "/settings/sessions",
  "settings-integrations": "/settings/integrations",
  "settings-themes": "/settings/themes",
  "settings-users": "/settings/users",
  "settings-cleanup": "/settings/cleanup",
};


export function pathForPage(page) {
  if (!page) return "/";
  if (PAGE_PATHS[page]) return PAGE_PATHS[page];
  if (page.startsWith("settings")) {
    const rest = page.replace(/^settings-?/, "") || "";
    return rest ? `/settings/${rest}` : "/settings";
  }
  return `/${page}`;
}

export function pageForPath(pathname) {
  const clean = (pathname || "/").replace(/\/+$/, "") || "/";
  for (const [k, v] of Object.entries(PAGE_PATHS)) {
    if (v === clean) return k;
  }
  if (clean.startsWith("/settings/")) {
    const rest = clean.slice("/settings/".length);
    return rest ? `settings-${rest}` : "settings-hub";
  }
  if (clean === "/settings") return "settings-hub";
  const seg = clean.replace(/^\//, "").split("/")[0];
  return seg || "dashboard";
}

export function usePageRoute(page, setPage) {
  const navigate = useNavigate();
  const location = useLocation();
  React.useEffect(() => {
    const fromUrl = pageForPath(location.pathname);
    if (fromUrl && fromUrl !== page) setPage(fromUrl);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);
  React.useEffect(() => {
    const target = pathForPage(page);
    if (location.pathname !== target) navigate(target, { replace: true });
  }, [page, location.pathname, navigate]);
  return { navigate, location };
}

export function LazyFallback() {
  return (
    <div className="p-8 flex items-center justify-center opacity-60 text-sm">
      Loading…
    </div>
  );
}

export function withRouter(AppComponent) {
  return function RoutedApp(props) {
    return (
      <BrowserRouter>
        <Suspense fallback={<LazyFallback />}>
          <AppComponent {...props} />
        </Suspense>
      </BrowserRouter>
    );
  };
}

export { BrowserRouter, lazy, Suspense };
