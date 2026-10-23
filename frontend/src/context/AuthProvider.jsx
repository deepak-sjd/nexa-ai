import { useCallback, useEffect, useMemo, useState } from "react";

import { AuthContext } from "./authContext";
import {
  AUTH_EXPIRED_EVENT,
  clearToken,
  fetchMe,
  getToken,
  login,
  loginWithGoogle,
  register,
  setToken,
} from "../services/auth";

export default function AuthProvider({ children }) {
  // `loading` is true only while a saved token is being checked.
  const [state, setState] = useState(() => ({
    user: null,
    loading: Boolean(getToken()),
  }));

  // Restore the session on page load.
  useEffect(() => {
    if (!getToken()) {
      return undefined;
    }

    let cancelled = false;

    fetchMe()
      .then((user) => {
        if (!cancelled) {
          setState({ user, loading: false });
        }
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }

        // Only a 401 means the token is bad. A network error just
        // shows the login page and keeps the token for next time.
        if (error.status === 401) {
          clearToken();
        }

        setState({ user: null, loading: false });
      });

    return () => {
      cancelled = true;
    };
  }, []);

  // authFetch fires this when any API call comes back 401.
  useEffect(() => {
    function handleExpired() {
      setState({ user: null, loading: false });
    }

    window.addEventListener(AUTH_EXPIRED_EVENT, handleExpired);

    return () =>
      window.removeEventListener(AUTH_EXPIRED_EVENT, handleExpired);
  }, []);

  const finish = useCallback((result) => {
    setToken(result.access_token);
    setState({ user: result.user, loading: false });
  }, []);

  const signIn = useCallback(
    async (email, password) => finish(await login({ email, password })),
    [finish]
  );

  const signUp = useCallback(
    async ({ email, password, name }) =>
      finish(await register({ email, password, name })),
    [finish]
  );

  const signInWithGoogle = useCallback(
    async (credential) => finish(await loginWithGoogle(credential)),
    [finish]
  );

  const logout = useCallback(() => {
    clearToken();
    window.google?.accounts?.id?.disableAutoSelect?.();
    setState({ user: null, loading: false });
  }, []);

  const value = useMemo(
    () => ({
      user: state.user,
      loading: state.loading,
      signIn,
      signUp,
      signInWithGoogle,
      logout,
    }),
    [state, signIn, signUp, signInWithGoogle, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
