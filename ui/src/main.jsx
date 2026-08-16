import "./styles.css";
import { mount } from "./app.jsx";

const el = document.getElementById("root");
if (el) mount(el);

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}
