import {getApps, initializeApp, type FirebaseApp} from "firebase/app";
import {
  browserSessionPersistence,
  getAuth,
  GoogleAuthProvider,
  onAuthStateChanged,
  setPersistence,
  signInWithPopup,
  signOut as firebaseSignOut,
  type Auth,
  type User,
} from "firebase/auth";

let app: FirebaseApp | null = null;
let auth: Auth | null = null;
let persistenceReady: Promise<void> | null = null;

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

export function getFirebaseAuth(): Auth | null {
  const config = readFirebaseWebConfig();
  if (!config) return null;

  if (!app) app = getApps().length ? getApps()[0]! : initializeApp(config);
  if (!auth) {
    auth = getAuth(app);
    // Keep the Firebase session for this browser tab/session without storing
    // application-managed bearer tokens in localStorage or sessionStorage.
    persistenceReady = setPersistence(auth, browserSessionPersistence);
  }
  return auth;
}

async function requireFirebaseAuth(): Promise<Auth> {
  const instance = getFirebaseAuth();
  if (!instance) throw new Error("Firebase Auth is not configured");
  await persistenceReady;
  return instance;
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

export async function signInWithGoogle(): Promise<User> {
  const instance = await requireFirebaseAuth();
  const provider = new GoogleAuthProvider();
  provider.setCustomParameters({prompt: "select_account"});
  const credential = await signInWithPopup(instance, provider);
  return credential.user;
}

export async function signOut(): Promise<void> {
  const instance = getFirebaseAuth();
  if (instance) await firebaseSignOut(instance);
}

export function firebaseAuthErrorMessage(error: unknown): string {
  const code =
    typeof error === "object" && error !== null && "code" in error
      ? String((error as {code?: unknown}).code)
      : "";

  switch (code) {
    case "auth/popup-closed-by-user":
    case "auth/cancelled-popup-request":
      return "Google sign-in was cancelled.";
    case "auth/popup-blocked":
      return "The Google sign-in popup was blocked. Allow popups and try again.";
    case "auth/unauthorized-domain":
      return "This domain is not authorized in Firebase Authentication.";
    case "auth/operation-not-allowed":
      return "Google sign-in is not enabled for this Firebase project.";
    case "auth/network-request-failed":
      return "Google sign-in could not reach Firebase. Check the network and try again.";
    default:
      return "Google sign-in failed. Please try again.";
  }
}
