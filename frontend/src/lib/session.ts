/**
 * Session Token Manager
 * Manages an anonymous client session UUID stored in localStorage under 'gvg_session_token'.
 * Ensures hold locks and cart selections persist across reloads and mobile tab switches.
 */

const SESSION_TOKEN_KEY = 'gvg_session_token';

function generateUUID(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  // Fallback RFC4122 v4 UUID generator
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function getSessionToken(): string {
  if (typeof window === 'undefined' || !window.localStorage) {
    return generateUUID();
  }

  try {
    let token = localStorage.getItem(SESSION_TOKEN_KEY);
    if (!token || token.trim() === '') {
      token = generateUUID();
      localStorage.setItem(SESSION_TOKEN_KEY, token);
    }
    return token;
  } catch {
    return generateUUID();
  }
}

export function resetSessionToken(): string {
  const token = generateUUID();
  if (typeof window !== 'undefined' && window.localStorage) {
    try {
      localStorage.setItem(SESSION_TOKEN_KEY, token);
    } catch {
      // ignore
    }
  }
  return token;
}

export function clearSessionToken(): void {
  if (typeof window !== 'undefined' && window.localStorage) {
    try {
      localStorage.removeItem(SESSION_TOKEN_KEY);
    } catch {
      // ignore
    }
  }
}

