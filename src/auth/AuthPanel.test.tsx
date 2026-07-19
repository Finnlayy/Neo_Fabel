import React from "react";
import {cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";

const signInGoogle = vi.hoisted(() => vi.fn());
const signOut = vi.hoisted(() => vi.fn());
const authState = vi.hoisted(() => ({
  ready: true,
  configured: true,
  uid: null as string | null,
  email: null as string | null,
  displayName: null as string | null,
  photoUrl: null as string | null,
  error: null as string | null,
  lastErrorCode: null as string | null,
  originHint: null as string | null,
  origin: "http://localhost:5173",
  user: null,
  signInGoogle,
  signOut,
}));

vi.mock("./AuthProvider", () => ({useAuth: () => authState}));

import AuthPanel from "./AuthPanel";

describe("AuthPanel", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    authState.ready = true;
    authState.configured = true;
    authState.uid = null;
    authState.email = null;
    authState.displayName = null;
    authState.error = null;
    authState.lastErrorCode = null;
    authState.origin = "http://localhost:5173";
    signInGoogle.mockReset().mockResolvedValue(undefined);
    signOut.mockReset().mockResolvedValue(undefined);
  });

  it("starts the Firebase Google popup flow", async () => {
    render(<AuthPanel />);
    fireEvent.click(screen.getByRole("button", {name: "Continue with Google"}));
    await waitFor(() => expect(signInGoogle).toHaveBeenCalledWith({forceRedirect: false}));
  });

  it("offers redirect sign-in as a fallback", async () => {
    render(<AuthPanel />);
    fireEvent.click(screen.getByRole("button", {name: "Use redirect sign-in"}));
    await waitFor(() => expect(signInGoogle).toHaveBeenCalledWith({forceRedirect: true}));
  });

  it("shows a visible auth status line while signed out", () => {
    const {container} = render(<AuthPanel />);
    const status = container.querySelector('[data-testid="auth-status-line"]');
    expect(status?.textContent ?? "").toMatch(/Auth:\s*ready/);
    expect(status?.textContent ?? "").toContain("localhost:5173");
  });

  it("offers logout for an authenticated user", async () => {
    authState.uid = "firebase-user";
    authState.email = "user@example.com";
    render(<AuthPanel compact />);
    fireEvent.click(screen.getByRole("button", {name: "Sign out"}));
    await waitFor(() => expect(signOut).toHaveBeenCalledTimes(1));
  });
});
