import React, { useRef, useEffect } from "react";
import engine from "./engine.js";

/* Canvas spectrum visualizer — 48 bars, log-bucket mapping, DaisyUI theme gradient. */
export default function Visualizer({ height = 56, barCount = 48, className = "" }) {
  const canvasRef = useRef(null);
  const rafRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    let running = true;
    let t = 0;

    const readTheme = () => {
      const cs = getComputedStyle(document.documentElement);
      return [
        cs.getPropertyValue("--p").trim() || "139 92 246",
        cs.getPropertyValue("--s").trim() || "219 39 119",
        cs.getPropertyValue("--a").trim() || "34 197 94",
      ];
    };
    let colors = readTheme();
    const mo = new MutationObserver(() => { colors = readTheme(); });
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "class"] });

    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      const w = canvas.clientWidth, h = canvas.clientHeight;
      canvas.width = Math.max(1, w * dpr);
      canvas.height = Math.max(1, h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);
    resize();

    const draw = () => {
      if (!running) return;
      const w = canvas.clientWidth, h = canvas.clientHeight;
      ctx.clearRect(0, 0, w, h);
      const data = engine.getFrequencyData();
      const playing = data && !engine.paused;
      const gap = 2;
      const bw = (w - gap * (barCount - 1)) / barCount;

      for (let i = 0; i < barCount; i++) {
        let v;
        if (playing) {
          // log-bucket mapping across frequency bins (start at bin 1: log scale needs a nonzero base)
          const minF = 1, maxF = data.length - 1;
          const lo = Math.floor(minF * Math.pow(maxF / minF, i / barCount));
          const hi = Math.floor(minF * Math.pow(maxF / minF, (i + 1) / barCount));
          let sum = 0, n = 0;
          for (let j = Math.max(0, lo); j <= Math.min(maxF, hi); j++) { sum += data[j]; n++; }
          v = n ? sum / n / 255 : 0;
        } else {
          // idle wave
          v = 0.12 + 0.08 * Math.sin(t / 24 + i * 0.5) * Math.sin(t / 40 + i * 0.2);
        }
        const bh = Math.max(2, v * h);
        const x = i * (bw + gap);
        const y = h - bh;
        const c = colors[i % colors.length];
        const grad = ctx.createLinearGradient(0, y, 0, h);
        grad.addColorStop(0, `oklch(${c} / 0.95)`);
        grad.addColorStop(1, `oklch(${c} / 0.35)`);
        ctx.fillStyle = grad;
        if (ctx.roundRect) {
          ctx.beginPath();
          ctx.roundRect(x, y, bw, bh, Math.min(3, bw / 2));
          ctx.fill();
        } else {
          ctx.fillRect(x, y, bw, bh);
        }
      }
      t++;
      rafRef.current = requestAnimationFrame(draw);
    };
    rafRef.current = requestAnimationFrame(draw);

    return () => {
      running = false;
      cancelAnimationFrame(rafRef.current);
      ro.disconnect();
      mo.disconnect();
    };
  }, [barCount]);

  return <canvas ref={canvasRef} className={"w-full block " + className} style={{ height }} aria-hidden="true" />;
}
