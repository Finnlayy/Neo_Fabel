import {afterEach, describe, expect, it, vi} from "vitest";
import {
  firebaseAuthErrorMessage,
  isFirebaseConfigured,
  isLoopbackIpOrigin,
  readFirebaseWebConfig,
  redirectLoopbackIpToLocalhost,
} from "./firebase";

describe("firebase config", () => {
  it("reports unconfigured when vite firebase vars are absent", () => {
    // In vitest, env vars are typically unset unless provided.
    const config = readFirebaseWebConfig();
    if (!config) {
      expect(isFirebaseConfigured()).toBe(false);
    } else {
      expect(config.projectId).toBeTruthy();
      expect(isFirebaseConfigured()).toBe(true);
    }
  });

  it("maps provider errors to controlled user-facing messages", () => {
    expect(firebaseAuthErrorMessage({code: "auth/popup-blocked"})).toContain("popup was blocked");
    expect(firebaseAuthErrorMessage({code: "auth/unauthorized-domain"})).toContain("not authorized");
    expect(firebaseAuthErrorMessage({message: "The requested action is invalid"})).toContain(
      "localhost:5173",
    );
    expect(firebaseAuthErrorMessage({code: "auth/popup-closed-by-user"})).toContain("credential");
    expect(firebaseAuthErrorMessage(new Error("secret provider detail"))).toContain(
      "Google sign-in failed",
    );
  });
});

describe("loopback origin guard", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("detects 127.0.0.1 as a distinct Firebase origin", () => {
    vi.stubGlobal("window", {
      location: {hostname: "127.0.0.1", href: "http://127.0.0.1:5173/", origin: "http://127.0.0.1:5173"},
    });
    expect(isLoopbackIpOrigin()).toBe(true);
  });

  it("rewrites 127.0.0.1 to localhost before auth", () => {
    const replace = vi.fn();
    vi.stubGlobal("window", {
      location: {
        hostname: "127.0.0.1",
        href: "http://127.0.0.1:5173/workspace?x=1",
        origin: "http://127.0.0.1:5173",
        replace,
      },
    });
    expect(redirectLoopbackIpToLocalhost()).toBe(true);
    expect(replace).toHaveBeenCalledWith("http://localhost:5173/workspace?x=1");
  });

  it("does not rewrite localhost", () => {
    const replace = vi.fn();
    vi.stubGlobal("window", {
      location: {
        hostname: "localhost",
        href: "http://localhost:5173/",
        origin: "http://localhost:5173",
        replace,
      },
    });
    expect(isLoopbackIpOrigin()).toBe(false);
    expect(redirectLoopbackIpToLocalhost()).toBe(false);
    expect(replace).not.toHaveBeenCalled();
  });
});
