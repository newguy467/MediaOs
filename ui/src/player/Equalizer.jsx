import React, { useEffect, useState } from "react";
import engine, { EQ_LABELS, EQ_PRESETS } from "./engine.js";

/* 10-band graphic equalizer panel. */
export default function Equalizer() {
  const [, force] = useState(0);
  useEffect(() => engine.on("eqchange", () => force((x) => x + 1)), []);

  const gains = engine.eqGains;
  const preset = engine.eqPreset;
  const enabled = engine.eqEnabled;

  return (
    <div className="flex flex-col h-full">
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <select
          className="select select-bordered select-sm"
          value={EQ_PRESETS[preset] ? preset : "custom"}
          onChange={(e) => engine.applyPreset(e.target.value)}
        >
          {Object.keys(EQ_PRESETS).map((k) => (
            <option key={k} value={k}>{k[0].toUpperCase() + k.slice(1)}</option>
          ))}
          {!EQ_PRESETS[preset] && <option value="custom">Custom</option>}
        </select>
        <button
          type="button"
          className={"btn btn-sm " + (enabled ? "btn-primary" : "btn-ghost")}
          onClick={() => engine.setEqEnabled(!enabled)}
        >
          {enabled ? "EQ On" : "EQ Off"}
        </button>
        <button type="button" className="btn btn-sm btn-ghost" onClick={() => engine.resetEq()}>
          Reset
        </button>
      </div>

      <div className="flex-1 flex items-end justify-between gap-1 sm:gap-2 px-1 overflow-x-auto">
        {EQ_LABELS.map((label, i) => (
          <div key={label} className="flex flex-col items-center gap-1 shrink-0">
            <span className="text-[10px] tabular-nums opacity-60 h-4">
              {gains[i] > 0 ? "+" : ""}{Math.round(gains[i])}
            </span>
            <input
              type="range"
              min="-12"
              max="12"
              step="0.5"
              value={gains[i]}
              onChange={(e) => engine.setBand(i, parseFloat(e.target.value))}
              className="eq-slider range range-xs range-primary"
              aria-label={`${label} Hz`}
            />
            <span className="text-[10px] opacity-50">{label}</span>
          </div>
        ))}
      </div>
      <p className="text-[10px] opacity-40 mt-3 text-center">±12 dB per band · ISO octave centers</p>
    </div>
  );
}
