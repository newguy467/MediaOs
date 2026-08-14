import React from "react";
import { PageChrome } from "../components/ui.jsx";

export default function AboutPage() {
  return (
    <PageChrome title="About MediaOS">
      <div className="max-w-3xl space-y-6 p-4">
        <div>
          <h1 className="text-2xl font-bold">MediaOS</h1>
          <p className="opacity-70 mt-1">The complete self-hosted media &amp; games OS</p>
        </div>

        <section className="prose prose-sm max-w-none">
          <h2 className="text-lg font-semibold">Attribution</h2>
          <p>
            MediaOS re-implements useful ideas and workflows from the open-source media
            ecosystem under a clean FastAPI + React architecture. We do not wholesale copy
            other codebases. Credit and inspiration:
          </p>
          <ul className="list-disc pl-5 space-y-1 text-sm">
            <li><strong>Sonarr / Radarr / Lidarr / Readarr / Prowlarr</strong> — core *arr library, quality, and indexer patterns</li>
            <li><strong>Recyclarr / TRaSH Guides</strong> — live quality definitions and custom formats</li>
            <li><strong>Questarr</strong> — games module concepts</li>
            <li><strong>scrob</strong> — local scrobbling and watch progress</li>
            <li><strong>Yamtrack</strong> — unified multi-media tracking ideas</li>
            <li><strong>Cinephage</strong> — stream-as-primary and Live TV depth</li>
            <li><strong>bobarr</strong> — multi-quality retention simplicity</li>
            <li><strong>Mylar3</strong> — comics pull-lists and arcs</li>
            <li><strong>Headphones</strong> — music hierarchy</li>
            <li><strong>Prismarr</strong> — dense dashboard and calendar</li>
            <li><strong>Organizr</strong> — Homelab Links</li>
            <li><strong>Maintainerr / Huntarr / NeutArr / Cleanuparr</strong> — maintenance and hunt patterns</li>
          </ul>
          <p className="text-sm opacity-70 mt-3">
            All credit to their authors. MediaOS remains independently implemented.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold">License</h2>
          <p className="text-sm opacity-80">MIT — see the repository LICENSE file.</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold">Links</h2>
          <ul className="text-sm space-y-1">
            <li><a className="link" href="https://github.com/newguy467/MediaOs" target="_blank" rel="noreferrer">GitHub repository</a></li>
            <li>Documentation: VISION.md, ARCHITECTURE.md, ROADMAP.md, ABSORPTION.md</li>
          </ul>
        </section>
      </div>
    </PageChrome>
  );
}
