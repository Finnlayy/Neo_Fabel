import React, {createContext, useContext, useEffect, useMemo, useState} from "react";
import type {User} from "firebase/auth";
import {
  firebaseAuthErrorMessage,
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
  user: User | null;
  signInGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({children}: {children: React.ReactNode}) {
  const configured = isFirebaseConfigured();
  const [ready, setReady] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!configured) {
      setUser(null);
      setReady(true);
      return;
    }

    return subscribeAuth((next) => {
      setUser(next);
      setReady(true);
    });
  }, [configured]);

  const value = useMemo<AuthState>(
    () => ({
      ready,
      configured,
      uid: user?.uid ?? null,
      email: user?.email ?? null,
      displayName: user?.displayName ?? null,
      photoUrl: user?.photoURL ?? null,
      error,
      user,
      signInGoogle: async () => {
        setError(null);
        try {
          const next = await signInWithGoogle();
          setUser(next);
        } catch (err) {
          setError(firebaseAuthErrorMessage(err));
          throw err;
        }
      },
      signOut: async () => {
        setError(null);
        await firebaseSignOut();
        setUser(null);
      },
    }),
    [configured, error, ready, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
