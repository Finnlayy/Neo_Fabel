import React, {useState} from "react";
import {useAuth} from "./AuthProvider";

function GoogleMark() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4" focusable="false">
      <path fill="#4285F4" d="M21.6 12.23c0-.71-.06-1.4-.18-2.07H12v3.92h5.38a4.6 4.6 0 0 1-2 3.02v2.54h3.24c1.9-1.75 2.98-4.33 2.98-7.41Z" />
      <path fill="#34A853" d="M12 22c2.7 0 4.98-.9 6.64-2.43l-3.24-2.54c-.9.6-2.05.96-3.4.96-2.61 0-4.82-1.76-5.61-4.13H3.04v2.62A10 10 0 0 0 12 22Z" />
      <path fill="#FBBC05" d="M6.39 13.86A6 6 0 0 1 6.08 12c0-.65.11-1.28.31-1.86V7.52H3.04A10 10 0 0 0 2 12c0 1.61.39 3.14 1.04 4.48l3.35-2.62Z" />
      <path fill="#EA4335" d="M12 6.01c1.47 0 2.79.5 3.82 1.49l2.88-2.88A9.65 9.65 0 0 0 12 2a10 10 0 0 0-8.96 5.52l3.35 2.62C7.18 7.77 9.39 6.01 12 6.01Z" />
    </svg>
  );
}

export default function AuthPanel({compact = false}: {compact?: boolean}) {
  const auth = useAuth();
  const [busy, setBusy] = useState(false);

  async function handleSignIn() {
    setBusy(true);
    try {
      await auth.signInGoogle();
    } catch {
      // The provider exposes a controlled, user-facing error message.
    } finally {
      setBusy(false);
    }
  }

  async function handleSignOut() {
    setBusy(true);
    try {
      await auth.signOut();
    } finally {
      setBusy(false);
    }
  }

  if (!auth.ready) {
    return <p className={`text-xs ${compact ? "text-slate-400" : "text-slate-500"}`}>Checking sign-in…</p>;
  }

  if (auth.uid) {
    return (
      <div className={`flex flex-wrap items-center gap-2 ${compact ? "" : "rounded border border-slate-200 bg-white p-3"}`}>
        <span className={`text-xs ${compact ? "text-slate-300" : "text-slate-600"}`}>
          {!compact && "Signed in as "}
          <span className={`font-semibold ${compact ? "text-cyan-300" : "text-slate-900"}`}>
            {auth.displayName || auth.email || auth.uid}
          </span>
        </span>
        <button
          type="button"
          disabled={busy}
          className={`min-h-11 rounded border px-3 text-xs font-semibold disabled:opacity-60 ${
            compact ? "border-white/20 text-slate-200 hover:bg-white/5" : "border-slate-300 hover:bg-slate-50"
          }`}
          onClick={() => void handleSignOut()}
        >
          {busy ? "Signing out…" : "Sign out"}
        </button>
      </div>
    );
  }

  if (!auth.configured) {
    if (compact) {
      return <span className="text-[10px] text-amber-300/90 uppercase tracking-wider">Google sign-in not configured</span>;
    }
    return (
      <div className="rounded border border-amber-300 bg-amber-50 p-3 text-sm text-slate-800" role="status">
        <p className="font-medium">Google sign-in is not configured</p>
        <p className="mt-1 text-xs text-slate-600">
          Add the public <code className="font-mono">VITE_FIREBASE_*</code> web configuration and enable Google in
          Firebase Authentication. Manual bearer-token login is intentionally disabled.
        </p>
      </div>
    );
  }

  return (
    <div className={compact ? "" : "rounded border border-slate-200 bg-white p-4"}>
      {!compact && (
        <div className="mb-3">
          <h3 className="text-sm font-semibold text-slate-900">Sign in</h3>
          <p className="mt-1 text-xs text-slate-600">Use your Google account through Firebase Authentication.</p>
        </div>
      )}
      <button
        type="button"
        disabled={busy}
        className={`min-h-11 rounded border text-sm font-semibold disabled:opacity-60 inline-flex items-center justify-center gap-2 ${
          compact
            ? "border-white/20 px-3 text-slate-100 hover:bg-white/5"
            : "w-full border-slate-300 px-4 text-slate-900 hover:bg-slate-50"
        }`}
        onClick={() => void handleSignIn()}
      >
        <GoogleMark />
        {busy ? "Opening Google…" : "Continue with Google"}
      </button>
      {auth.error && (
        <p className={`mt-2 text-xs ${compact ? "text-rose-300" : "text-rose-700"}`} role="alert">
          {auth.error}
        </p>
      )}
    </div>
  );
}
