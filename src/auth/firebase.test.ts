import {describe, expect, it} from "vitest";
import {firebaseAuthErrorMessage, isFirebaseConfigured, readFirebaseWebConfig} from "./firebase";

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
    expect(firebaseAuthErrorMessage(new Error("secret provider detail"))).toBe(
      "Google sign-in failed. Please try again.",
    );
  });
});
