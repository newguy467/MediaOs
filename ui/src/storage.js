/* localStorage helpers for MediaOs UI */
export const AUTH_TOKEN_KEY = 'mediaos_token';

export function getToken() {
  try { return localStorage.getItem(AUTH_TOKEN_KEY); } catch { return null; }
}

export function setToken(t) {
  try {
    if (t) localStorage.setItem(AUTH_TOKEN_KEY, t);
    else localStorage.removeItem(AUTH_TOKEN_KEY);
  } catch {}
}

export function getAdvanced() {
  try { return localStorage.getItem('mediaos-advanced') === '1'; } catch { return false; }
}

export function setAdvancedFlag(v) {
  try { localStorage.setItem('mediaos-advanced', v ? '1' : '0'); } catch {}
}
