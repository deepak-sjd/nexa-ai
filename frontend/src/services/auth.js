// ============================================================
// AUTH CLIENT
// ------------------------------------------------------------
// Login token storage + a fetch wrapper that adds the token to
// every API call. App.jsx uses `authFetch` instead of `fetch`.
// ============================================================

import { API_BASE_URL } from "./api";

const TOKEN_KEY = "nexa-token";

export const AUTH_EXPIRED_EVENT = "nexa-auth-expired";

export function getToken() {
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token) {
  try {
    window.localStorage.setItem(TOKEN_KEY, token);
  } catch {
    // Storage disabled: the user just has to log in again next visit.
  }
}

export function clearToken() {
  try {
    window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    // ignore
  }
}

/**
 * fetch() + "Authorization: Bearer <token>". If the server says the
 * token is no longer valid (401), the user is signed out everywhere.
 */
export async function authFetch(input, init = {}) {
  const token = getToken();
  const headers = new Headers(init.headers || {});

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(input, { ...init, headers });

  if (response.status === 401 && token) {
    clearToken();
    window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
  }

  return response;
}

function errorMessage(data, status) {
  const detail = data?.detail;

  if (typeof detail === "string" && detail.trim()) {
    return detail.trim();
  }

  if (Array.isArray(detail)) {
    const first = detail[0]?.msg;

    if (typeof first === "string") {
      return first.replace(/^Value error, /, "");
    }

    return "Please check your details and try again.";
  }

  if (status === 429) {
    return "Too many attempts. Please wait a minute and try again.";
  }

  return "Something went wrong. Please try again.";
}

async function postJson(path, body) {
  let response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error(
      "Can't reach the server. It may be waking up - try again in a moment."
    );
  }

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(errorMessage(data, response.status));
  }

  return data;
}

// Each resolves to { access_token, user }
export const register = (payload) => postJson("/auth/register", payload);

export const login = (payload) => postJson("/auth/login", payload);

export const loginWithGoogle = (credential) =>
  postJson("/auth/google", { credential });

/** The signed-in user. Rejects with `.status` set when it fails. */
export async function fetchMe() {
  const response = await authFetch(`${API_BASE_URL}/auth/me`, {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    const error = new Error("Could not load your account.");
    error.status = response.status;
    throw error;
  }

  return response.json();
}
