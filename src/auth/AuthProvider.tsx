import React, {createContext, useContext, useEffect, useMemo, useState} from "react";
import type {User} from "firebase/auth";
import {setApiTokenProvider} from "../api/client";
import {
  authOriginHint,
  consumeRedirectResult,
  currentAuthOrigin,
  firebaseAuthErrorMessage,
  getFirebaseAuth,
  isFirebaseConfigured,
  signInWithGoogle,
  signOut as firebaseSignOut,
  subscribeAuth,
} from "./firebase";

type AuthState = {
  ready: boolean;
  configured: boolean;
  uid: string | null;
  email: string | null;
  displayName: string | null;
  photoUrl: string | null;
  error: string | null;
  lastErrorCode: string | null;
  originHint: string | null;
  origin: string;
  user: User | null;
  signInGoogle: (options?: {forceRedirect?: boolean}) => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

function readErrorCode(error: unknown): string | null {
  if (typeof error === "object" && error !== null && "code" in error) {
    const code = (error as {code?: unknown}).code;
    return typeof code === "string" && code ? code : null;
  }
  return null;
}

export function AuthProvider({children}: {children: React.ReactNode}) {
  const configured = isFirebaseConfigured();
  const [ready, setReady] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastErrorCode, setLastErrorCode] = useState<string | null>(null);
  const [originHint] = useState<string | null>(() => authOriginHint());
  const [origin] = useState(() => currentAuthOrigin());

  useEffect(() => {
    if (!configured) {
      setUser(null);
      setReady(true);
      return;
    }

    let unsubscribe = () => undefined;
    let cancelled = false;

    void (async () => {
      try {
        const redirected = await consumeRedirectResult();
        if (!cancelled && redirected) {
          setUser(redirected);
          setError(null);
          setLastErrorCode(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(firebaseAuthErrorMessage(err));
          setLastErrorCode(readErrorCode(err));
          console.error("[auth] Redirect result error:", err);
        }
      }

      if (cancelled) return;

      // Seed immediately from the Auth singleton in case the first observer tick is delayed.
      const current = getFirebaseAuth()?.currentUser ?? null;
      if (current) setUser(current);

      unsubscribe = subscribeAuth((next) => {
        setUser(next);
        setReady(true);
        if (next) {
          setError(null);
          setLastErrorCode(null);
        }
      });
    })();

    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, [configured]);

  // Always attach the signed-in user's ID token to API calls (Telegram/paper/AI).
  // Do not rely on a separate Auth.currentUser lookup that can race after popup/redirect.
  useEffect(() => {
    if (!user) {
      setApiTokenProvider(null);
      return;
    }
    setApiTokenProvider(async () => {
      try {
        return await user.getIdToken();
      } catch (err) {
        console.error("[auth] getIdToken failed:", err);
        return null;
      }
    });
    return () => setApiTokenProvider(null);
  }, [user]);

  const value = useMemo<AuthState>(
    () => ({
      ready,
      configured,
      uid: user?.uid ?? null,
      email: user?.email ?? null,
      displayName: user?.displayName ?? null,
      photoUrl: user?.photoURL ?? null,
      error,
      lastErrorCode,
      originHint,
      origin,
      user,
      signInGoogle: async (options) => {
        setError(null);
        setLastErrorCode(null);
        try {
          const result = await signInWithGoogle(options);
          if (result.mode === "redirect") {
            // Page is navigating to Google; keep busy UI via caller until unload.
            return;
          }
          setUser(result.user);
          setReady(true);
        } catch (err) {
          const message = firebaseAuthErrorMessage(err);
          setError(message);
          setLastErrorCode(readErrorCode(err));
          console.error("[auth] Google sign-in failed:", err);
          // If the popup appeared to work but this tab has no user, keep signed-out UI honest.
          if (!getFirebaseAuth()?.currentUser) setUser(null);
          throw err;
        }
      },
      signOut: async () => {
        setError(null);
        setLastErrorCode(null);
        await firebaseSignOut();
        setUser(null);
      },
    }),
    [configured, error, lastErrorCode, origin, originHint, ready, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
