import {getApp, getApps, initializeApp, type FirebaseApp} from "firebase/app";
import {
  browserLocalPersistence,
  browserPopupRedirectResolver,
  GoogleAuthProvider,
  getAuth,
  getRedirectResult,
  initializeAuth,
  onAuthStateChanged,
  signInWithPopup,
  signInWithRedirect,
  signOut as firebaseSignOut,
  type Auth,
  type User,
} from "firebase/auth";

let app: FirebaseApp | null = null;
let auth: Auth | null = null;
let redirectResultPromise: Promise<User | null> | null = null;

export type FirebaseWebConfig = {
  apiKey: string;
  authDomain: string;
  projectId: string;
  appId: string;
  messagingSenderId?: string;
  storageBucket?: string;
};

export function readFirebaseWebConfig(): FirebaseWebConfig | null {
  const apiKey = import.meta.env.VITE_FIREBASE_API_KEY?.trim();
  const authDomain = import.meta.env.VITE_FIREBASE_AUTH_DOMAIN?.trim();
  const projectId = import.meta.env.VITE_FIREBASE_PROJECT_ID?.trim();
  const appId = import.meta.env.VITE_FIREBASE_APP_ID?.trim();
  if (!apiKey || !authDomain || !projectId || !appId) return null;

  return {
    apiKey,
    authDomain,
    projectId,
    appId,
    messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID?.trim() || undefined,
    storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET?.trim() || undefined,
  };
}

export function isFirebaseConfigured(): boolean {
  return readFirebaseWebConfig() !== null;
}

/** True when the page origin is 127.0.0.1 (Firebase treats this differently from localhost). */
export function isLoopbackIpOrigin(): boolean {
  return typeof window !== "undefined" && window.location.hostname === "127.0.0.1";
}

/**
 * Firebase's default authorized domain is `localhost`, not `127.0.0.1`.
 * Send users to the matching origin before any auth UI runs.
 * Returns true when a navigation was started (caller should stop rendering).
 */
export function redirectLoopbackIpToLocalhost(): boolean {
  if (typeof window === "undefined" || !isLoopbackIpOrigin()) return false;
  const next = new URL(window.location.href);
  next.hostname = "localhost";
  window.location.replace(next.toString());
  return true;
}

/** Hostnames Firebase treats as distinct authorized domains. */
export function authOriginHint(): string | null {
  if (typeof window === "undefined") return null;
  if (isLoopbackIpOrigin()) {
    return "You are on 127.0.0.1. Neo Fabel is redirecting you to http://localhost:5173 (required for Firebase Google sign-in).";
  }
  return null;
}

export function currentAuthOrigin(): string {
  if (typeof window === "undefined") return "ssr";
  return window.location.origin;
}

export function getFirebaseAuth(): Auth | null {
  const config = readFirebaseWebConfig();
  if (!config) return null;

  if (!app) {
    app = getApps().length ? getApp() : initializeApp(config);
  }

  if (!auth) {
    try {
      // Prefer initializeAuth so persistence + popup resolver are set before any sign-in.
      auth = initializeAuth(app, {
        persistence: browserLocalPersistence,
        popupRedirectResolver: browserPopupRedirectResolver,
      });
    } catch {
      // Hot reload / second mount: Auth already initialized for this app.
      auth = getAuth(app);
    }
  }
  return auth;
}

async function requireFirebaseAuth(): Promise<Auth> {
  const instance = getFirebaseAuth();
  if (!instance) throw new Error("Firebase Auth is not configured");
  return instance;
}

function googleProvider(): GoogleAuthProvider {
  const provider = new GoogleAuthProvider();
  provider.setCustomParameters({prompt: "select_account"});
  provider.addScope("profile");
  provider.addScope("email");
  return provider;
}

function errorCode(error: unknown): string {
  if (typeof error === "object" && error !== null && "code" in error) {
    return String((error as {code?: unknown}).code ?? "");
  }
  return "";
}

function shouldFallbackToRedirect(error: unknown): boolean {
  const code = errorCode(error);
  const message =
    typeof error === "object" && error !== null && "message" in error
      ? String((error as {message?: unknown}).message)
      : error instanceof Error
        ? error.message
        : "";
  const lower = `${code} ${message}`.toLowerCase();

  return (
    code === "auth/popup-blocked" ||
    code === "auth/popup-closed-by-user" ||
    code === "auth/cancelled-popup-request" ||
    code === "auth/internal-error" ||
    lower.includes("requested action is invalid") ||
    lower.includes("cross-origin-opener-policy") ||
    lower.includes("window.closed")
  );
}

export async function getIdToken(forceRefresh = false): Promise<string | null> {
  const current = getFirebaseAuth()?.currentUser;
  if (!current) return null;
  return current.getIdToken(forceRefresh);
}

export function subscribeAuth(callback: (user: User | null) => void): () => void {
  const instance = getFirebaseAuth();
  if (!instance) {
    callback(null);
    return () => undefined;
  }
  return onAuthStateChanged(instance, callback);
}

/** Complete a pending redirect sign-in (no-op when none). Safe to call once per page load. */
export function consumeRedirectResult(): Promise<User | null> {
  if (!redirectResultPromise) {
    redirectResultPromise = (async () => {
      const instance = getFirebaseAuth();
      if (!instance) return null;
      try {
        const result = await getRedirectResult(instance);
        return result?.user ?? null;
      } catch (error) {
        console.error("[auth] getRedirectResult failed:", error);
        throw error;
      }
    })();
  }
  return redirectResultPromise;
}

export type GoogleSignInResult =
  | {mode: "popup"; user: User}
  | {mode: "redirect"; user: null};

export async function signInWithGoogle(options?: {
  forceRedirect?: boolean;
}): Promise<GoogleSignInResult> {
  const instance = await requireFirebaseAuth();
  const provider = googleProvider();

  if (options?.forceRedirect || isLoopbackIpOrigin()) {
    await signInWithRedirect(instance, provider, browserPopupRedirectResolver);
    return {mode: "redirect", user: null};
  }

  try {
    const credential = await signInWithPopup(instance, provider, browserPopupRedirectResolver);
    const user = credential.user ?? instance.currentUser;
    if (!user) {
      throw Object.assign(new Error("Google sign-in finished without a Firebase user session."), {
        code: "auth/no-current-user",
      });
    }
    // Force a token fetch so a broken session cannot look like a silent success.
    await user.getIdToken();
    return {mode: "popup", user};
  } catch (error) {
    if (shouldFallbackToRedirect(error)) {
      console.warn("[auth] Popup sign-in failed; falling back to redirect:", error);
      await signInWithRedirect(instance, provider, browserPopupRedirectResolver);
      return {mode: "redirect", user: null};
    }
    throw error;
  }
}

export async function signOut(): Promise<void> {
  const instance = getFirebaseAuth();
  if (instance) await firebaseSignOut(instance);
}

export function firebaseAuthErrorMessage(error: unknown): string {
  const code = errorCode(error);
  const message =
    typeof error === "object" && error !== null && "message" in error
      ? String((error as {message?: unknown}).message)
      : error instanceof Error
        ? error.message
        : "";

  const lower = `${code} ${message}`.toLowerCase();
  if (lower.includes("requested action is invalid") || lower.includes("missing required data")) {
    return "Firebase rejected the sign-in. Use http://localhost:5173 (not 127.0.0.1), add both domains under Authentication → Settings → Authorized domains, and enable Google sign-in.";
  }

  switch (code) {
    case "auth/popup-closed-by-user":
    case "auth/cancelled-popup-request":
      return "Google sign-in closed before Firebase received a credential. Retry, or use redirect sign-in. Prefer http://localhost:5173 in Chrome/Edge (not Cursor Simple Browser).";
    case "auth/popup-blocked":
      return "The Google sign-in popup was blocked. Allow popups, or use redirect sign-in.";
    case "auth/unauthorized-domain":
      return "This domain is not authorized in Firebase. Add both localhost and 127.0.0.1 under Authentication → Settings → Authorized domains.";
    case "auth/operation-not-allowed":
      return "Google sign-in is not enabled. Enable the Google provider under Authentication → Sign-in method.";
    case "auth/network-request-failed":
      return "Google sign-in could not reach Firebase. Check the network and try again.";
    case "auth/internal-error":
      return "Firebase rejected the sign-in (often unauthorized domain or Google provider off). Use http://localhost:5173 and enable Google in Authentication.";
    case "auth/no-current-user":
      return "Google sign-in did not establish a session in this tab. Retry from http://localhost:5173 in Chrome/Edge.";
    default:
      return "Google sign-in failed. Enable Google sign-in, authorize localhost and 127.0.0.1, then retry from http://localhost:5173 in Chrome/Edge.";
  }
}
