import React, { useState, useEffect, useCallback } from "react";
import { LibraryModuleShell, TeachEmpty, PageChrome } from "../components/ui.jsx";


function PluginsPage({ setPage }) {
  return (
    <div className="space-y-4 max-w-xl">
      <h1 className="mr-page-title">Plugins</h1>
      <p className="text-sm opacity-70">
        Plugin install and management moved to the <strong>Module &amp; Plugin Store</strong>
        (built-in modules + community plugins from GitHub).
      </p>
      <button type="button" className="btn btn-primary btn-sm" onClick={() => setPage && setPage("modules")}>
        Open Module &amp; Plugin Store
      </button>
      <p className="text-xs opacity-50">
        Announce Lab (autobrr-style filters) lives under <strong>Homelab → Announce Lab</strong> — not a separate plugin container.
      </p>
    </div>
  );
}

export default PluginsPage;
