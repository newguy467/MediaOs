import { useSyncExternalStore } from "react";
import musicStore from "./store.js";

export function useMusicPlayer() {
  const state = useSyncExternalStore(
    (cb) => musicStore.subscribe(cb),
    () => musicStore.getState(),
    () => musicStore.getState()
  );
  const current = musicStore.current();
  return { ...state, store: musicStore, current };
}

export default useMusicPlayer;
