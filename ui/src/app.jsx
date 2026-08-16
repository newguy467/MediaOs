import React, { useState, useEffect, useCallback, useRef } from "react";
import { createRoot } from "react-dom/client";
import { withRouter, usePageRoute } from "./routes.jsx";
import "./styles.css";
import Ic, { Icons, P } from "./icons.jsx";
import { getToken, setToken, getAdvanced, setAdvancedFlag, AUTH_TOKEN_KEY } from "./storage.js";
import AiChatPanel from "./AiChatPanel.jsx";
import { api, TMDB } from "./api.js";
import {
  PageChrome, SplashScreen, LogoMark, CollectionProgressWidget, ThemesPage, ThemeToggle,
  StatsGrid, LibraryLegend,
} from "./components/ui.jsx";
import { MediaPlayer } from "./components/media.jsx";
import MusicPlayerBar from "./player/MusicPlayerBar.jsx";
import GlobalSearch from "./components/GlobalSearch.jsx";

const lazyNamed = (loader, name) => React.lazy(() => loader().then(m => ({ default: m[name] || m.default })));

const MoviesPage = lazyNamed(() => import("./pages/movies.jsx"), "MoviesPage");
const MovieDetailPage = lazyNamed(() => import("./pages/movies.jsx"), "MovieDetailPage");
const TvPage = lazyNamed(() => import("./pages/tv.jsx"), "TvPage");
const SeriesDetailPage = lazyNamed(() => import("./pages/tv.jsx"), "SeriesDetailPage");
const DiscoverPage = lazyNamed(() => import("./pages/discover.jsx"), "DiscoverPage");
const ImportPage = lazyNamed(() => import("./pages/import.jsx"), "ImportPage");
const QualityProfilesPage = lazyNamed(() => import("./pages/quality.jsx"), "QualityProfilesPage");
const QualityMatrixPage = lazyNamed(() => import("./pages/quality.jsx"), "QualityMatrixPage");
const QualityLabPage = lazyNamed(() => import("./pages/quality.jsx"), "QualityLabPage");
const LogsPage = lazyNamed(() => import("./pages/activity.jsx"), "LogsPage");
const ActivityPage = lazyNamed(() => import("./pages/activity.jsx"), "ActivityPage");
const SessionsAdminPage = lazyNamed(() => import("./pages/settings.jsx"), "SessionsAdminPage");
const ConfigGroupPage = lazyNamed(() => import("./pages/settings.jsx"), "ConfigGroupPage");
const SubtitlesSettingsPage = lazyNamed(() => import("./pages/settings.jsx"), "SubtitlesSettingsPage");
const WantedSubtitlesPage = lazyNamed(() => import("./pages/settings.jsx"), "WantedSubtitlesPage");
const VpnSettingsPage = lazyNamed(() => import("./pages/settings.jsx"), "VpnSettingsPage"); // also settings-vpnsettingspage.jsx
const SettingsHubPage = lazyNamed(() => import("./pages/settings.jsx"), "SettingsHubPage");
const UsersPermissionsPage = lazyNamed(() => import("./pages/settings.jsx"), "UsersPermissionsPage");
const BooksPage = lazyNamed(() => import("./pages/books.jsx"), "BooksPage");
const BookDetailPage = lazyNamed(() => import("./pages/books.jsx"), "BookDetailPage");
const ComicsPage = lazyNamed(() => import("./pages/comics.jsx"), "ComicsPage");
const MangaPage = React.lazy(() => import("./pages/manga.jsx"));
const ComicDetailPage = lazyNamed(() => import("./pages/comics.jsx"), "ComicDetailPage");
const YouTubePage = lazyNamed(() => import("./pages/youtube.jsx"), "YouTubePage");
const CollectionsPage = lazyNamed(() => import("./pages/collections.jsx"), "CollectionsPage");
const PodcastsPage = lazyNamed(() => import("./pages/podcasts.jsx"), "PodcastsPage");
const LiveTvPage = lazyNamed(() => import("./pages/livetv.jsx"), "LiveTvPage");
const LibraryBrowserPage = lazyNamed(() => import("./pages/library.jsx"), "LibraryBrowserPage");
const AudiobooksPage = lazyNamed(() => import("./pages/audiobooks.jsx"), "AudiobooksPage");
const AudiobookDetailPage = lazyNamed(() => import("./pages/audiobooks.jsx"), "AudiobookDetailPage");
const CalendarPage = lazyNamed(() => import("./pages/calendar.jsx"), "CalendarPage");
const SmartListsPage = lazyNamed(() => import("./pages/smartlists.jsx"), "SmartListsPage");
const RequestsPage = lazyNamed(() => import("./pages/requests.jsx"), "RequestsPage");
const QueuePage = lazyNamed(() => import("./pages/queue.jsx"), "QueuePage");
const IndexersPage = lazyNamed(() => import("./pages/indexers.jsx"), "IndexersPage");
const IntegrationsPage = lazyNamed(() => import("./pages/integrations.jsx"), "IntegrationsPage");
const WantedPage = lazyNamed(() => import("./pages/wanted.jsx"), "WantedPage");
const ModuleStorePage = lazyNamed(() => import("./pages/modules.jsx"), "ModuleStorePage");
const FirstRunTour = lazyNamed(() => import("./components/first-run-tour.jsx"), "FirstRunTour");
const SetupWizardPage = lazyNamed(() => import("./pages/setup.jsx"), "SetupWizardPage");
const MigrateWizardPage = lazyNamed(() => import("./pages/migrate-wizard.jsx"), "MigrateWizardPage");
const DashboardPage = lazyNamed(() => import("./pages/dashboard.jsx"), "DashboardPage");
const GuidedFirstRun = lazyNamed(() => import("./pages/dashboard.jsx"), "GuidedFirstRun");
const GlossaryPage = lazyNamed(() => import("./pages/dashboard.jsx"), "GlossaryPage");
const OverhaulDashboardPage = lazyNamed(() => import("./pages/dashboard.jsx"), "OverhaulDashboardPage");
const ConverterDashboard = lazyNamed(() => import("./pages/converter.jsx"), "ConverterDashboard");
const ConverterGpuWizard = lazyNamed(() => import("./pages/converter.jsx"), "ConverterGpuWizard");
const ConverterQueue = lazyNamed(() => import("./pages/converter.jsx"), "ConverterQueue");
const ConverterScan = lazyNamed(() => import("./pages/converter.jsx"), "ConverterScan");
const ConverterPresets = lazyNamed(() => import("./pages/converter.jsx"), "ConverterPresets");
const MusicPage = lazyNamed(() => import("./pages/music.jsx"), "MusicPage");
const MusicDetailPage = lazyNamed(() => import("./pages/music.jsx"), "MusicDetailPage");
const AdultPage = lazyNamed(() => import("./pages/adult.jsx"), "AdultPage");
const AdultDetailPage = lazyNamed(() => import("./pages/adult.jsx"), "AdultDetailPage");
const AdultSettingsPage = lazyNamed(() => import("./pages/adult.jsx"), "AdultSettingsPage");
const HomelabLinksPage = React.lazy(() => import("./pages/homelab.jsx"));
const GamesPage = React.lazy(() => import("./pages/games.jsx"));
const ScrobblingPage = React.lazy(() => import("./pages/scrobbling.jsx"));
const TrackingPage = React.lazy(() => import("./pages/tracking.jsx"));
const AboutPage = React.lazy(() => import("./pages/about.jsx"));
const BackupPage = React.lazy(() => import("./pages/backup.jsx"));
const PluginsPage = React.lazy(() => import("./pages/plugins.jsx"));
const WidgetLayoutPage = React.lazy(() => import("./pages/widgets.jsx"));
const ExternalArrPage = React.lazy(() => import("./pages/external-arr.jsx"));

function applyTheme(t) {
  const name = t || 'mediaos';
  document.documentElement.setAttribute('data-theme', name);
  try { localStorage.setItem('mediaos-theme', name); } catch (_) {}
  // Keep body class in sync for any CSS that keys off it
  document.body && document.body.setAttribute('data-theme', name);
}
function storedTheme() {
  return localStorage.getItem('mediaos-theme') || 'mediaos' || 'mediaos';
}

/* Icons imported from ./icons.jsx as Ic */


/* ── Auth token (Bearer) ─────────────────────────────────────────────────── */
/* storage helpers imported from ./storage.js */

const ADULT_UNLOCK_KEY = 'mediaos_adult_unlock';

function Sidebar({ page, setPage, counts, onClose, advanced, enabledModules, theme, setTheme, signedIn, onSignOut }) {
  // Flat primary nav — filtered by enabled modules (movies+tv always on).
  // Side UI customized via Module Store. Optional modules only appear when enabled.
  const em = enabledModules || ['movies','tv','music','books','audiobooks','comics','homelab'];
  const primaryAll = [
    { key: 'movies', label: 'Movies', Icon: Ic.Film, count: counts.movies, mod: 'movies' },
    { key: 'tv', label: 'TV', Icon: Ic.Tv, count: counts.tv, mod: 'tv' },
    { key: 'music', label: 'Music', Icon: Ic.Music, count: counts.music, mod: 'music' },
    { key: 'books', label: 'Books', Icon: Ic.Book, count: counts.books, mod: 'books' },
    { key: 'audiobooks', label: 'Audiobooks', Icon: Ic.Headphones, count: counts.audiobooks, mod: 'audiobooks' },
    { key: 'comics', label: 'Comics', Icon: Ic.Book, mod: 'comics' },
    { key: 'manga', label: 'Manga', Icon: Ic.Book, mod: 'manga' },
    { key: 'games', label: 'Games', Icon: Ic.Box, mod: 'games' },
    { key: 'youtube', label: 'YouTube', Icon: Ic.Compass, mod: 'youtube' },
    { key: 'podcasts', label: 'Podcasts', Icon: Ic.Rss, mod: 'podcasts' },
    { key: 'homelab', label: 'Homelab', Icon: Ic.Server, mod: 'homelab' },
    { key: 'discover', label: 'Discover', Icon: Ic.Compass, mod: null },
    { key: 'queue', label: 'Queue', Icon: Ic.Download, mod: null },
    { key: 'settings-hub', label: 'Settings', Icon: Ic.Settings, mod: null },
    { key: 'modules', label: 'Module Store', Icon: Ic.Box, mod: null },
    { key: 'adult', label: 'Adult', Icon: Ic.Shield, count: counts.adult, mod: 'adult' },
  ];
  // Basic mode: core library modules only in primary; advanced unlocks Live TV / Converter nav
  const advancedOnlyMods = new Set(['livetv', 'converter']);
  const advancedOnlyPages = new Set(['indexers', 'settings-quality-matrix', 'settings-quality']);
  const primary = primaryAll.filter(i => {
    if (!i.mod) return true;
    if (!em.includes(i.mod)) return false;
    if (!advanced && advancedOnlyMods.has(i.mod)) return false;
    if (!advanced && advancedOnlyPages.has(i.key)) return false;
    return true;
  });
  const secondaryAll = [
    { key: 'dashboard', label: 'Home', Icon: Ic.Home, mod: null },
    { key: 'global-search', label: 'Search', Icon: Ic.Search, mod: null },
    { key: 'ai-search', label: 'AI Search', Icon: Ic.Search, mod: null },
    { key: 'scrobbling', label: 'History', Icon: Ic.Activity, mod: 'scrobbling' },
    { key: 'tracking', label: 'Tracking', Icon: Ic.List, mod: 'tracking' },
    { key: 'backup', label: 'Backup', Icon: Ic.Server, mod: null },
    { key: 'plugins', label: 'Plugins', Icon: Ic.Box, mod: null },
    { key: 'widget-layout', label: 'Widgets', Icon: Ic.Home, mod: null },
    { key: 'external-arr', label: 'External *arr', Icon: Ic.Server, mod: null },
    { key: 'about', label: 'About', Icon: Ic.Box, mod: null },
    { key: 'wanted', label: 'Wanted', Icon: Ic.AlertTri, mod: null },
    { key: 'library-player', label: 'Watch', Icon: Ic.Film, mod: null },
    { key: 'calendar', label: 'Calendar', Icon: Ic.Calendar, mod: null },
    { key: 'requests', label: 'Requests', Icon: Ic.Inbox, count: counts.requests, mod: null },
    { key: 'livetv', label: 'Live TV', Icon: Ic.Radio, mod: 'livetv' },
  ];
  const secondary = secondaryAll.filter(i => {
    if (!i.mod) return true;
    if (!em.includes(i.mod)) return false;
    if (!advanced && advancedOnlyMods.has(i.mod)) return false;
    if (!advanced && advancedOnlyPages.has(i.key)) return false;
    return true;
  });
  if (advanced) {
    if (em.includes('converter')) secondary.push({ key: 'converter-dashboard', label: 'Converter', Icon: Ic.Activity });
    secondary.push({ key: 'activity', label: 'History', Icon: Ic.Activity });
  }

  const isActive = (k) => page === k || (k === 'settings-hub' && String(page).startsWith('settings'));

  return (
    <aside className="mr-sidebar flex flex-col h-full">
      <div className="mr-brand">
        <div className="mr-brand-mark">
          <LogoMark size={28} />
        </div>
        <div>
          <div className="mr-brand-title">MediaOS</div>
          <div className="text-[10px] opacity-50 tracking-wide">media automation</div>
        </div>
        {onClose && (
          <button type="button" className="btn btn-ghost btn-xs btn-circle ml-auto lg:hidden" aria-label="Close menu" onClick={onClose}>✕</button>
        )}
      </div>

      <nav className="flex-1 overflow-y-auto py-3 space-y-0.5">
        {primary.map(item => (
          <button
            key={item.key}
            type="button"
            className={'mr-nav-item' + (isActive(item.key) ? ' active' : '')}
            onClick={() => {
              if (item.key === 'ai-search') {
                window.dispatchEvent(new CustomEvent('mediaos-open-ai'));
                onClose && onClose();
                return;
              }
              if (item.key === 'global-search') {
                window.dispatchEvent(new CustomEvent('mediaos-open-search'));
                onClose && onClose();
                return;
              }
              setPage(item.key);
              onClose && onClose();
            }}
          >
            <span className="nav-icon"><item.Icon /></span>
            <span className="flex-1">{item.label}</span>
            {item.count != null && item.count > 0 && (
              <span className="text-[10px] opacity-70 tabular-nums">{item.count}</span>
            )}
          </button>
        ))}
        <div className="mx-4 my-3 border-t border-primary/10" />
        {secondary.map(item => (
          <button
            key={item.key}
            type="button"
            className={'mr-nav-item' + (isActive(item.key) ? ' active' : '')}
            onClick={() => {
              if (item.key === 'ai-search') {
                window.dispatchEvent(new CustomEvent('mediaos-open-ai'));
                onClose && onClose();
                return;
              }
              if (item.key === 'global-search') {
                window.dispatchEvent(new CustomEvent('mediaos-open-search'));
                onClose && onClose();
                return;
              }
              setPage(item.key);
              onClose && onClose();
            }}
          >
            <span className="nav-icon"><item.Icon /></span>
            <span className="flex-1">{item.label}</span>
          </button>
        ))}
      </nav>

      <div className="px-3 pb-2 flex items-center justify-between gap-2">
        <span className="text-[10px] uppercase tracking-wide opacity-40">Appearance</span>
        <ThemeToggle theme={theme || "mediaos"} setTheme={setTheme || (() => {})} />
      </div>
      <div className="px-3 pb-2">
        {signedIn ? (
          <button type="button" className="btn btn-ghost btn-xs w-full" onClick={() => onSignOut && onSignOut()}>Sign out</button>
        ) : (
          <button type="button" className="btn btn-primary btn-xs w-full" onClick={() => { setPage && setPage('login'); onClose && onClose(); }}>Sign in</button>
        )}
      </div>
      <div className="mr-server-card">
        <div className="label">MediaOS Server</div>
        <div className="value">Library ready</div>
        <div className="bar"><span style={{ width: '52%' }} /></div>
        <div className="text-[10px] opacity-50 mt-1">52% planned capacity</div>
      </div>
    </aside>
  );
}




function ModuleDisabled({ name, setPage }) {
  return (
    <div className="p-8 max-w-lg mx-auto text-center space-y-3">
      <h1 className="mr-page-title">{name} is off</h1>
      <p className="text-sm opacity-60">This module is not enabled. Turn it on in the Module Store to use this section.</p>
      <button type="button" className="btn btn-primary btn-sm" onClick={() => setPage && setPage("modules")}>Open Module Store</button>
    </div>
  );
}

function PageContent({ page, movies, series, music=[], books=[], audiobooks=[], refreshMovies, refreshSeries, setPage, theme, setTheme, setMiniPlayer, enabledModules=['movies','tv','music','books','audiobooks','comics','homelab'], setEnabledModules, advanced, setAdvanced, libLoading=false }) {
  switch(page) {
    case 'widgets': return <OverhaulDashboardPage setPage={setPage} />;
    case 'homelab': return (enabledModules||[]).includes('homelab') ? <HomelabLinksPage /> : <ModuleDisabled name="Homelab" setPage={setPage} />;
    case 'games': return (enabledModules||[]).includes('games') ? <GamesPage setPage={setPage} /> : <ModuleDisabled name="Games" setPage={setPage} />;
    case 'scrobbling': return (enabledModules||[]).includes('scrobbling') ? <ScrobblingPage /> : <ModuleDisabled name="History / Scrobbling" setPage={setPage} />;
    case 'tracking': return (enabledModules||[]).includes('tracking') ? <TrackingPage /> : <ModuleDisabled name="Tracking" setPage={setPage} />;
    case 'about': return <AboutPage />;
    case 'backup': return <BackupPage />;
    case 'plugins': return <PluginsPage setPage={setPage} />;
    case 'widget-layout': return <WidgetLayoutPage />;
    case 'external-arr': return <ExternalArrPage />;
    case 'dashboard':    return <><DashboardPage movies={movies} series={series} setPage={setPage} enabledModules={enabledModules} /><CollectionProgressWidget setPage={setPage} /></>;
    case 'comics':       return (enabledModules||[]).includes('comics') ? <ComicsPage setPage={setPage} /> : <ModuleDisabled name="Comics" setPage={setPage} />;
    case 'manga':        return (enabledModules||[]).includes('manga') ? <MangaPage setPage={setPage} /> : <ModuleDisabled name="Manga" setPage={setPage} />;
    case 'youtube':      return (enabledModules||[]).includes('youtube') ? <YouTubePage /> : <ModuleDisabled name="YouTube" setPage={setPage} />;
    case 'collections':  return <CollectionsPage />;
    case 'podcasts':     return (enabledModules||[]).includes('podcasts') ? <PodcastsPage setMiniPlayer={setMiniPlayer} /> : <ModuleDisabled name="Podcasts" setPage={setPage} />;
    case 'movies':       return <MoviesPage movies={movies} refreshMovies={refreshMovies} setMiniPlayer={setMiniPlayer} setPage={setPage} libLoading={libLoading} />;
    case 'tv':           return <TvPage series={series} refreshSeries={refreshSeries} setMiniPlayer={setMiniPlayer} setPage={setPage} libLoading={libLoading} />;
    case 'discover':     return <DiscoverPage movies={movies} series={series} refreshMovies={refreshMovies} refreshSeries={refreshSeries} enabledModules={enabledModules} setPage={setPage} />;
    case 'requests':     return <RequestsPage />;
    case 'import':       return <ImportPage movies={movies} series={series} />;
    case 'quality-lab': return <QualityLabPage />;
    case 'workers': return <div className="p-6 space-y-3 max-w-3xl"><h1 className="mr-page-title">Workers</h1><p className="text-sm opacity-60">Background schedulers: missing search, library watch, Jackett sync (6h), EPG refresh, cleanup, converter watch. Live progress is on Queue (SSE) and History.</p><div className="flex gap-2"><button type="button" className="btn btn-sm" onClick={()=>setPage&&setPage('queue')}>Queue</button><button type="button" className="btn btn-sm" onClick={()=>setPage&&setPage('activity')}>History</button><button type="button" className="btn btn-sm" onClick={()=>setPage&&setPage('logs')}>Logs</button></div></div>;
    case 'parity': return <div className='p-6'><h1 className='mr-page-title'>Stack parity</h1><p className='text-sm opacity-60'>mediaos replaces Sonarr/Radarr/Lidarr/Readarr/Bazarr/Prowlarr for day-to-day. Use <strong>Migrate</strong> for *arr import, Quality for TRaSH/packs, Integrations for external URLs.</p><ul className='list-disc ml-5 text-sm mt-3 space-y-1'><li>Movies + TV + quality + indexers ✅</li><li>Music artists/albums/tracks ✅</li><li>Books + audiobooks ✅</li><li>Subtitles wanted ✅</li><li>Cleanuparr-style cleaner ✅</li></ul></div>;
    case 'adult': return (enabledModules||[]).includes('adult') ? <AdultPage /> : <ModuleDisabled name="Adult" setPage={setPage} />;
    case 'settings-hub': return <SettingsHubPage setPage={setPage} advanced={advanced} setAdvanced={setAdvanced} enabledModules={enabledModules} />;
    case 'settings-users': return <UsersPermissionsPage />;
    case 'modules': return <ModuleStorePage enabledModules={enabledModules} setEnabledModules={setEnabledModules} setPage={setPage} />;
    case 'settings-setup': return <SetupWizardPage onDone={()=>{ if(setPage) setPage('dashboard'); }} />;
    case 'setup': return <SetupWizardPage onDone={()=>{ if(setPage) setPage('dashboard'); }} />;
    case 'migrate': return <MigrateWizardPage setPage={setPage} />;
    case 'migrate-wizard': return <MigrateWizardPage setPage={setPage} />;
    case 'login': return <LoginPage setPage={setPage} />;
    case 'glossary': return <GlossaryPage />;
    case 'wanted-subtitles': return <WantedSubtitlesPage setPage={setPage} />;
    case 'wanted': return <WantedPage />;
    case 'queue':        return <QueuePage />;
    case 'logs': return <LogsPage />;
    case 'activity':     return <ActivityPage movies={movies} setPage={setPage} />;
    case 'settings-quality': return <QualityProfilesPage />;
    case 'settings-quality-matrix': return <QualityMatrixPage setPage={setPage} />;
    case 'settings-vpn':     return <VpnSettingsPage />;
    case 'settings-youtube': return <ConfigGroupPage group="youtube" title="YouTube / Login" Icon={Ic.Compass} description="Creator downloads, cookies login for age-restricted content, and SponsorBlock ad/sponsor removal. Changes apply immediately." setPage={setPage} />;
    case 'settings-themes': return <ThemesPage currentTheme={theme} setTheme={setTheme} />;
    case 'settings-indexers':  return <IndexersPage />;
    case 'settings-downloads': return <ConfigGroupPage group="downloads" title="Download Clients" Icon={Ic.Download} description="qBittorrent, SABnzbd, NZBGet — changes apply immediately, no restart." setPage={setPage} />;
    case 'settings-library':   return <ConfigGroupPage group="library" title="Library Storage" Icon={Ic.Folder} description="Library and downloads paths — changes apply immediately, no restart." setPage={setPage} />;
    case 'settings-indexers-cfg': return <ConfigGroupPage group="indexers" title="Indexers / Prowlarr / Jackett" Icon={Ic.Server} description="Prowlarr optional. Jackett sync + Cardigann builtins replace most indexer management." setPage={setPage} />;
    case 'settings-subtitles': return <SubtitlesSettingsPage setPage={setPage} />;
    case 'settings-adult': return <AdultSettingsPage setPage={setPage} />;
    case 'settings-hunt': return <ConfigGroupPage group="hunt" title="Hunt engine" Icon={Ic.Activity} description="Built-in NeutArr/Huntarr-class aggressive missing search + optional upgrades. Runs on a schedule; no extra container." setPage={setPage} />;
    case 'settings-cleanup': return <ConfigGroupPage group="cleanup" title="Queue cleaner" Icon={Ic.AlertTri} description="Cleanuparr-style strikes, stall detection, seed ratio." setPage={setPage} />;
    case 'settings-system':    return <ConfigGroupPage group="system" title="System" Icon={Ic.Server} description="Search, upgrades, and notification settings — changes apply immediately, no restart." setPage={setPage} />;
    case 'settings-metadata': return <ConfigGroupPage group="metadata" title="Metadata APIs" Icon={Ic.Compass} description="TMDb, TVDb, ComicVine, Trakt — changes apply immediately." setPage={setPage} />;
    case 'settings-debrid': return <ConfigGroupPage group="debrid" title="Debrid providers" Icon={Ic.Download} description="Real-Debrid, TorBox, AllDebrid, Premiumize, put.io, and more." setPage={setPage} />;
    
    case 'settings-usenet': return <ConfigGroupPage group="usenet" title="Usenet / NNTP" Icon={Ic.Server} description="NNTP for seekable streaming (SABnzbd/NZBGet are under Downloads)." setPage={setPage} />;
    case 'settings-auth': return <ConfigGroupPage group="auth" title="Authentication" Icon={Ic.Users} description="Admin login, API keys, ARR-compat key." setPage={setPage} />;
    case 'settings-sessions':  return <SessionsAdminPage />;
    case 'settings-integrations': return <IntegrationsPage />;
    case 'music':        return (enabledModules||[]).includes('music') ? <MusicPage setPage={setPage} /> : <ModuleDisabled name="Music" setPage={setPage} />;
    case 'books':        return (enabledModules||[]).includes('books') ? <BooksPage setPage={setPage} /> : <ModuleDisabled name="Books" setPage={setPage} />;
    case 'audiobooks':   return (enabledModules||[]).includes('audiobooks') ? <AudiobooksPage setPage={setPage} /> : <ModuleDisabled name="Audiobooks" setPage={setPage} />;
    case 'calendar':     return <CalendarPage setPage={setPage} />;
    case 'library-player': return <LibraryBrowserPage movies={movies} series={series} music={music} books={books} setMiniPlayer={setMiniPlayer} setPage={setPage} />;
    case 'livetv': return (enabledModules||[]).includes('livetv') ? <LiveTvPage /> : <ModuleDisabled name="Live TV" setPage={setPage} />;
    case 'converter-dashboard': return (enabledModules||[]).includes('converter') || advanced ? <ConverterDashboard setPage={setPage} /> : <ModuleDisabled name="Converter" setPage={setPage} />;
    case 'converter-gpu': return (enabledModules||[]).includes('converter') || advanced ? <ConverterGpuWizard /> : <ModuleDisabled name="Converter" setPage={setPage} />;
    case 'converter-queue': return (enabledModules||[]).includes('converter') || advanced ? <ConverterQueue /> : <ModuleDisabled name="Converter" setPage={setPage} />;
    case 'converter-scan': return (enabledModules||[]).includes('converter') || advanced ? <ConverterScan /> : <ModuleDisabled name="Converter" setPage={setPage} />;
    case 'converter-presets': return (enabledModules||[]).includes('converter') || advanced ? <ConverterPresets /> : <ModuleDisabled name="Converter" setPage={setPage} />;
    case 'converter': return (enabledModules||[]).includes('converter') || advanced ? <ConverterDashboard setPage={setPage} /> : <ModuleDisabled name="Converter" setPage={setPage} />;
        case 'smartlists':   return <SmartListsPage />;
    default:             return <><DashboardPage movies={movies} series={series} music={music} books={books} audiobooks={audiobooks} setPage={setPage} enabledModules={enabledModules} /><CollectionProgressWidget setPage={setPage} /></>;
  }
}

/* ── App Root ────────────────────────────────────────────────────────────── */



function LoginForm({ onSuccess, onCancel, title, subtitle, embedded, mode = 'direct' }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const firstField = useRef(null);

  useEffect(() => {
    const t = setTimeout(() => firstField.current && firstField.current.focus(), 50);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    const onFail = (ev) => {
      setErr((ev.detail && ev.detail.message) || 'Login failed');
      setBusy(false);
    };
    window.addEventListener('mediaos-auth-failed', onFail);
    return () => window.removeEventListener('mediaos-auth-failed', onFail);
  }, []);

  const submit = async (e) => {
    e && e.preventDefault();
    if (!username.trim()) { setErr('Username required'); return; }
    setBusy(true);
    setErr('');
    // bridge: 401 interceptor waits on mediaos-auth-credentials
    if (mode === 'bridge') {
      window.dispatchEvent(new CustomEvent('mediaos-auth-credentials', {
        detail: { username: username.trim(), password },
      }));
      return;
    }
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.trim(), password }),
      });
      const j = await res.json().catch(() => ({}));
      if (j.token) {
        setToken(j.token);
        window.dispatchEvent(new CustomEvent('mediaos-auth-success'));
        onSuccess && onSuccess(j);
        return;
      }
      setErr(j.detail || j.message || 'Login failed');
    } catch {
      setErr('Login failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className={embedded ? 'card-body gap-3' : 'card bg-base-200 shadow-xl border border-primary/20 max-w-sm w-full mx-auto card-body gap-3'} onSubmit={submit}>
      <h2 id="login-title" className="card-title text-lg">{title || 'Sign in to MediaOS'}</h2>
      {subtitle && <p className="text-xs opacity-60">{subtitle}</p>}
      <label className="form-control">
        <span className="label-text text-xs">Username</span>
        <input ref={firstField} className="input input-bordered input-sm" autoComplete="username"
          value={username} onChange={e => setUsername(e.target.value)} />
      </label>
      <label className="form-control">
        <span className="label-text text-xs">Password</span>
        <input type="password" className="input input-bordered input-sm" autoComplete="current-password"
          value={password} onChange={e => setPassword(e.target.value)} />
      </label>
      {err && <p className="text-error text-sm" role="alert">{err}</p>}
      <div className="card-actions justify-end gap-2 mt-1">
        {onCancel && <button type="button" className="btn btn-ghost btn-sm" onClick={onCancel}>Cancel</button>}
        <button type="submit" className="btn btn-primary btn-sm" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
      </div>
    </form>
  );
}

function LoginPage({ setPage }) {
  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center p-6 gap-4">
      <div className="flex items-center gap-2 mb-2">
        <LogoMark size={36} />
        <span className="font-bold text-lg bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">MediaOS</span>
      </div>
      <LoginForm
        title="Sign in"
        subtitle="Use your MediaOS admin or user account."
        onSuccess={() => setPage && setPage('dashboard')}
      />
      <button type="button" className="btn btn-ghost btn-xs opacity-60" onClick={() => setPage && setPage('dashboard')}>
        Continue without signing in
      </button>
    </div>
  );
}

function LoginModal() {
  const [open, setOpen] = useState(false);
  const panelRef = useRef(null);
  const prevFocus = useRef(null);

  const cancel = () => {
    window.dispatchEvent(new CustomEvent('mediaos-auth-credentials', { detail: null }));
    setOpen(false);
  };

  useEffect(() => {
    const onReq = () => { setOpen(true); };
    const onFail = () => { setOpen(true); };
    const onOk = () => { setOpen(false); };
    window.addEventListener('mediaos-auth-required', onReq);
    window.addEventListener('mediaos-auth-failed', onFail);
    window.addEventListener('mediaos-auth-success', onOk);
    return () => {
      window.removeEventListener('mediaos-auth-required', onReq);
      window.removeEventListener('mediaos-auth-failed', onFail);
      window.removeEventListener('mediaos-auth-success', onOk);
    };
  }, []);

  // Body scroll lock + focus trap while open
  useEffect(() => {
    if (!open) return undefined;
    prevFocus.current = document.activeElement;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const panel = panelRef.current;
    const focusable = () =>
      panel
        ? Array.from(panel.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'))
            .filter((el) => !el.hasAttribute('disabled') && el.offsetParent !== null)
        : [];

    const onKey = (ev) => {
      if (ev.key === 'Escape') {
        ev.preventDefault();
        cancel();
        return;
      }
      if (ev.key !== 'Tab') return;
      const list = focusable();
      if (!list.length) return;
      const first = list[0];
      const last = list[list.length - 1];
      if (ev.shiftKey && document.activeElement === first) {
        ev.preventDefault();
        last.focus();
      } else if (!ev.shiftKey && document.activeElement === last) {
        ev.preventDefault();
        first.focus();
      }
    };
    window.addEventListener('keydown', onKey);
    // Initial focus
    setTimeout(() => {
      const list = focusable();
      if (list[0]) list[0].focus();
    }, 30);

    return () => {
      document.body.style.overflow = prevOverflow;
      window.removeEventListener('keydown', onKey);
      try { prevFocus.current && prevFocus.current.focus && prevFocus.current.focus(); } catch (_) {}
    };
  }, [open]);

  // Bridge: when modal is used for 401, submit via event (api.js waiter).
  // LoginForm does direct login — for modal we also support event bridge via credentials.
  if (!open) return null;

  const onModalSuccess = () => {
    // Token already set by LoginForm; notify waiters with a synthetic credentials noop path
    // api.js shared waiter may still be pending — dispatch credentials null is cancel.
    // Better: dispatch success only; waiters that already got token via setToken retry.
    setOpen(false);
  };

  // For 401 flow, api.js waits on mediaos-auth-credentials. Provide a form that dispatches that.
  return (
    <div
      className="fixed inset-0 z-[80] flex items-center justify-center bg-black/60 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="login-title"
    >
      <div ref={panelRef} className="card bg-base-200 shadow-2xl w-full max-w-sm border border-primary/30">
        <LoginForm
          embedded
          mode="bridge"
          title="Sign in to MediaOS"
          subtitle="Your session expired or authentication is required."
          onCancel={cancel}
          onSuccess={onModalSuccess}
        />
      </div>
    </div>
  );
}


function App() {
  const [splash, setSplash] = useState(true);
  const [page, setPage] = useState('dashboard');
  try { usePageRoute(page, setPage); } catch (e) { /* outside router in tests */ }
  useEffect(() => {
    const MAP = {
      dashboard: 'Home', movies: 'Movies', tv: 'TV', music: 'Music', books: 'Books',
      audiobooks: 'Audiobooks', comics: 'Comics', manga: 'Manga', games: 'Games',
      youtube: 'YouTube', podcasts: 'Podcasts', livetv: 'Live TV', discover: 'Discover',
      queue: 'Queue', library: 'Library', wanted: 'Wanted', calendar: 'Calendar',
      requests: 'Requests', adult: 'Adult', homelab: 'Homelab', login: 'Sign in',
      setup: 'Setup', about: 'About', modules: 'Module Store', scrobbling: 'History',
      tracking: 'Tracking', converter: 'Converter', 'settings-hub': 'Settings',
    };
    const key = String(page || 'dashboard');
    const label = MAP[key] || key.replace(/^settings-?/, 'Settings · ').replace(/-/g, ' ');
    document.title = `${label} · MediaOS`;
  }, [page]);
  const [miniPlayer, setMiniPlayer] = useState(null); // {itemId,episodeId,videoId,path,title}
  const [advanced, setAdvanced] = useState(() => getAdvanced());
  const [enabledModules, setEnabledModules] = useState(['movies','tv','music','books','audiobooks','comics','homelab']);
  const [signedIn, setSignedIn] = useState(() => !!getToken());
  useEffect(()=>{
    const sync = () => setSignedIn(!!getToken());
    window.addEventListener('mediaos-auth-success', sync);
    window.addEventListener('storage', sync);
    return () => {
      window.removeEventListener('mediaos-auth-success', sync);
      window.removeEventListener('storage', sync);
    };
  }, []);
  useEffect(()=>{
    fetch('/api/modules/enabled').then(r=>r.json()).then(d=>{
      if (d.enabled && d.enabled.length) setEnabledModules(d.enabled);
    }).catch(()=>{});
  }, []);

  const [theme, setThemeState] = useState(storedTheme());
  useEffect(() => { applyTheme(theme); }, [theme]);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [movies, setMovies] = useState([]);
  const [series, setSeries] = useState([]);
  const [libLoading, setLibLoading] = useState(true);
  const [music, setMusic] = useState([]);
  const [books, setBooks] = useState([]);
  const [audiobooks, setAudiobooks] = useState([]);
  const [adult, setAdult] = useState([]);
  const [setupNeeded, setSetupNeeded] = useState(false);
  const [setupChecked, setSetupChecked] = useState(false);
  const [pendingRequests, setPendingRequests] = useState(0);

  function setTheme(t) { setThemeState(t); applyTheme(t); }

  const refreshMovies = useCallback(async()=>{
    try { setMovies(await api.movies.list()); } catch(e){}
  }, []);
  const refreshSeries = useCallback(async()=>{
    try { setSeries(await api.tv.list()); } catch(e){}
  }, []);
  const refreshMusic = useCallback(async()=>{
    try { setMusic(await api.music.list()); } catch(e){}
  }, []);
  const refreshBooks = useCallback(async()=>{
    try { setBooks(await api.books.list()); } catch(e){}
  }, []);
  const refreshAudiobooks = useCallback(async()=>{
    try { setAudiobooks(await api.audiobooks.list()); } catch(e){}
  }, []);
  const refreshAdult = useCallback(async()=>{
    try { setAdult(await api.adult.list()); } catch(e){ /* locked or disabled */ }
  }, []);
  const refreshRequests = useCallback(async()=>{
    try { setPendingRequests((await api.requests.list('pending')).length); } catch(e){}
  }, []);

  useEffect(()=>{
    // Live SSE updates (queue/activity/workers)
    let es;
    try {
      es = new EventSource('/api/sse/events');
      es.addEventListener('worker', ()=>{});
      es.addEventListener('activity', ()=>{});
      es.addEventListener('queue', ()=>{ refreshRequests(); });
    } catch(e) {}
    Promise.all([
      refreshMovies(), refreshSeries(), refreshMusic(), refreshBooks(), refreshAudiobooks(), refreshAdult(), refreshRequests()
    ]).finally(() => setLibLoading(false));
    api.setup.status().then(s=>{ setSetupNeeded(!s.complete); setSetupChecked(true); if(!s.complete) setPage('setup'); }).catch(()=>setSetupChecked(true));
    const t = setTimeout(()=>setSplash(false), 1200);
    const i = setInterval(refreshRequests, 30000);
    return ()=>{ clearInterval(i); clearTimeout(t); try{ es && es.close(); }catch(e){} };
  }, []);

  const counts = {
    movies: movies.length,
    tv: series.length,
    music: music.length,
    books: books.length,
    audiobooks: audiobooks.length,
    adult: adult.length,
    requests: pendingRequests,
  };

  return (
    <>
    <SplashScreen visible={splash} />
    <div className="drawer lg:drawer-open min-h-screen mr-shell" data-sidebar="left">
      <input id="mr-drawer" type="checkbox" className="drawer-toggle"
        checked={mobileOpen} onChange={e=>setMobileOpen(e.target.checked)} readOnly />

      <div className="drawer-content flex flex-col mr-main">
        <div className="navbar mr-topbar lg:hidden">
          <label htmlFor="mr-drawer" className="btn btn-ghost btn-square btn-sm" aria-label="Open menu" onClick={()=>setMobileOpen(!mobileOpen)}>
            <span className="w-5 h-5" aria-hidden="true"><Ic.Menu /></span>
          </label>
          <div className="mr-brand-mark !w-7 !h-7">
            <LogoMark size={22} />
          </div>
          <span className="font-bold ml-1 tracking-tight bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">MediaOS</span>
          <div className="flex-1" />
          {signedIn ? (
            <button type="button" className="btn btn-ghost btn-xs" onClick={() => { setToken(null); setSignedIn(false); }}>Sign out</button>
          ) : (
            <button type="button" className="btn btn-primary btn-xs" onClick={() => setPage('login')}>Sign in</button>
          )}
          <ThemeToggle theme={theme} setTheme={setTheme} />
        </div>
        <main className="flex-1 mr-content mos-page">
          {page === 'dashboard' && <FirstRunTour setPage={setPage} />}
          {setupNeeded && page !== 'setup' && (
            <div className="mx-3 mt-3 alert alert-warning text-sm py-2 flex flex-wrap items-center gap-2">
              <span className="flex-1">Setup is not finished — paths, modules, and admin account may be incomplete.</span>
              <button type="button" className="btn btn-warning btn-xs" onClick={() => setPage('setup')}>Resume setup</button>
              <button type="button" className="btn btn-ghost btn-xs" onClick={() => setSetupNeeded(false)}>Dismiss</button>
            </div>
          )}
          {!signedIn && page !== 'login' && page !== 'setup' && (
            <div className="mx-3 mt-2 alert alert-info text-xs py-1.5 flex flex-wrap items-center gap-2 opacity-90">
              <span className="flex-1">Browsing without signing in — some actions require a session (local installs often leave auth open).</span>
              <button type="button" className="btn btn-info btn-xs" onClick={() => setPage('login')}>Sign in</button>
            </div>
          )}
          <PageChrome title={page}><PageContent page={page} movies={movies} series={series}
            music={music} books={books} audiobooks={audiobooks}
            refreshMovies={refreshMovies} refreshSeries={refreshSeries}
            setPage={setPage} theme={theme} setTheme={setTheme} setMiniPlayer={setMiniPlayer}
            enabledModules={enabledModules} setEnabledModules={setEnabledModules}
            advanced={advanced} setAdvanced={setAdvanced} libLoading={libLoading} /></PageChrome>
        </main>
        {miniPlayer && (
          <div className="fixed inset-x-0 bottom-16 lg:bottom-0 z-40 p-2 bg-base-300/95 border-t border-primary/40 backdrop-blur shadow-lg">
            <MediaPlayer
              compact
              itemId={miniPlayer.itemId}
              episodeId={miniPlayer.episodeId}
              videoId={miniPlayer.videoId}
              path={miniPlayer.path}
              title={miniPlayer.title}
              onClose={()=>setMiniPlayer(null)}
            />
          </div>
        )}
        <MusicPlayerBar />
        <GlobalSearch setPage={setPage} />
        <nav className="mr-bottom-nav lg:hidden" aria-label="Primary">
          {[
            {k:'dashboard', label:'Home', Icon:Ic.Home},
            {k:'wanted', label:'Wanted', Icon:Ic.AlertTri},
            {k:'queue', label:'Queue', Icon:Ic.Download},
            {k:'discover', label:'Discover', Icon:Ic.Compass},
            {k:'settings-hub', label:'Settings', Icon:Ic.Settings},
          ].map(i=>(
            <button type="button" key={i.k} aria-label={i.label} aria-current={page===i.k||(i.k==='settings-hub'&&String(page).startsWith('settings'))?'page':undefined}
              className={page===i.k||(i.k==='settings-hub'&&String(page).startsWith('settings'))?'active':''}
              onClick={()=>setPage(i.k)}>
              <span className="w-5 h-5" aria-hidden="true"><i.Icon /></span>
              {i.label}
            </button>
          ))}
        </nav>
      </div>

      <div className="drawer-side z-30" style={{gridColumn: 1}}>
        <label htmlFor="mr-drawer" className="drawer-overlay mr-drawer-backdrop" onClick={()=>setMobileOpen(false)} />
        <Sidebar page={page} setPage={p=>{setPage(p);}} counts={counts} onClose={()=>setMobileOpen(false)} advanced={advanced} enabledModules={enabledModules} theme={theme} setTheme={setTheme} signedIn={signedIn} onSignOut={()=>{ setToken(null); setSignedIn(false); }} />
      </div>
    </div>
    <AiChatPanel />
    <LoginModal />
    </>
  );
}

const RoutedApp = withRouter(App);

export function mount(el) {
  createRoot(el).render(<RoutedApp />);
}

if (typeof document !== "undefined") {
  try { document.documentElement.setAttribute('data-theme', localStorage.getItem('mediaos-theme') || 'mediaos'); } catch (e) {}

  const root = document.getElementById("root");
  if (root) mount(root);
}
