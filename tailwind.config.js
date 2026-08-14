/** @type {import('tailwindcss').Config} */
export default {
  content: ["./ui/index.html", "./ui/src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      boxShadow: {
        poster: "0 12px 40px -10px rgba(0,0,0,0.75)",
        glow: "0 0 24px rgba(139, 92, 246, 0.35)",
      },
    },
  },
  plugins: [require("daisyui")],
  daisyui: {
    themes: [
      {
        mediaos: {
          primary: "#8b5cf6",
          "primary-content": "#ffffff",
          secondary: "#a78bfa",
          "secondary-content": "#1a1030",
          accent: "#c084fc",
          "accent-content": "#1a1030",
          neutral: "#1c1733",
          "neutral-content": "#e8e4f8",
          "base-100": "#0b0914",
          "base-200": "#12101f",
          "base-300": "#1c1733",
          "base-content": "#f3f0ff",
          info: "#38bdf8",
          success: "#34d399",
          warning: "#fbbf24",
          error: "#f87171",
          "rounded-box": "1rem",
          "rounded-btn": "0.75rem",
        },
      },
      "dark", "night", "dracula", "synthwave", "cyberpunk", "abyss",
      "luxury", "dim", "black", "forest", "halloween", "nord", "business",
      "coffee", "winter", "sunset", "aqua", "garden", "lofi", "pastel",
      "fantasy", "wireframe", "cmyk", "autumn", "acid", "lemonade", "retro",
      "valentine", "bumblebee", "caramellatte", "silk",
      "light", "cupcake", "corporate", "emerald",
    ],
    darkTheme: "mediaos",
  },
};
