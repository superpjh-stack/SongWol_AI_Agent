const KEY = 'songwol-token';

export function loadAccessCode(): string {
  // Keep an existing tab signed in while upgrading from session-only storage.
  for (const storage of ['localStorage', 'sessionStorage'] as const) {
    try {
      const value: unknown = JSON.parse(window[storage].getItem(KEY) || 'null');
      if (typeof value === 'string' && value) return value;
    } catch { /* A browser may restrict storage or contain an old invalid value. */ }
  }
  return '';
}

export function rememberAccessCode(value: string): boolean {
  if (!value) return true;
  try {
    localStorage.setItem(KEY, JSON.stringify(value));
  } catch {
    try { sessionStorage.setItem(KEY, JSON.stringify(value)); } catch { /* In-memory access still works. */ }
    return false;
  }
  try { sessionStorage.removeItem(KEY); } catch { /* Persistent storage already succeeded. */ }
  return true;
}

export function forgetAccessCode() {
  for (const storage of ['localStorage', 'sessionStorage'] as const) {
    try { window[storage].removeItem(KEY); } catch { /* Storage may be unavailable. */ }
  }
}
