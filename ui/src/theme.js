/* MediaOS theme registry. Keep the layout independent from palette choice. */
export const THEMES = [
  "mediaos", "dark", "night", "dracula", "synthwave", "cyberpunk", "abyss",
  "luxury", "dim", "black", "forest", "halloween", "nord", "business", "coffee",
  "winter", "sunset", "aqua", "garden", "lofi", "pastel", "fantasy", "wireframe",
  "cmyk", "autumn", "acid", "lemonade", "retro", "valentine", "bumblebee",
  "caramellatte", "silk", "light", "cupcake", "corporate", "emerald"
];

export const THEME_GROUPS = [
  { label: "MediaOS", themes: ["mediaos"] },
  { label: "Dark", themes: ["dark", "night", "dracula", "synthwave", "cyberpunk", "abyss", "luxury", "dim", "black", "forest", "halloween", "nord", "business", "coffee", "winter"] },
  { label: "Color", themes: ["sunset", "aqua", "garden", "lofi", "pastel", "fantasy", "retro", "valentine", "bumblebee", "autumn", "acid", "lemonade", "cmyk", "caramellatte", "silk"] },
  { label: "Light", themes: ["light", "cupcake", "corporate", "emerald", "wireframe"] },
];

export function isValidTheme(theme) {
  return THEMES.includes(theme);
}

export function normalizeTheme(theme) {
  return isValidTheme(theme) ? theme : "mediaos";
}

export function getStoredTheme() {
  try {
    return normalizeTheme(localStorage.getItem("mediaos-theme"));
  } catch (_) {
    return "mediaos";
  }
}

export function applyTheme(theme) {
  const name = normalizeTheme(theme);
  if (typeof document !== "undefined") {
    document.documentElement.setAttribute("data-theme", name);
    if (document.body) document.body.setAttribute("data-theme", name);
  }
  try { localStorage.setItem("mediaos-theme", name); } catch (_) {}
  return name;
}

export function nextTheme(theme) {
  const current = normalizeTheme(theme);
  const index = THEMES.indexOf(current);
  return THEMES[(index + 1) % THEMES.length];
}
