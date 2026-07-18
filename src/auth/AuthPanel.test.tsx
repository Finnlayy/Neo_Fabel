import React from "react";
import {fireEvent, render, screen, waitFor} from "@testing-library/react";
import {beforeEach, describe, expect, it, vi} from "vitest";

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
  user: null,
  signInGoogle,
  signOut,
}));

vi.mock("./AuthProvider", () => ({useAuth: () => authState}));

import AuthPanel from "./AuthPanel";

describe("AuthPanel", () => {
  beforeEach(() => {
    authState.ready = true;
    authState.configured = true;
    authState.uid = null;
    authState.email = null;
    authState.displayName = null;
    authState.error = null;
    signInGoogle.mockReset().mockResolvedValue(undefined);
    signOut.mockReset().mockResolvedValue(undefined);
  });

  it("starts the Firebase Google popup flow", async () => {
    render(<AuthPanel />);
    fireEvent.click(screen.getByRole("button", {name: "Continue with Google"}));
    await waitFor(() => expect(signInGoogle).toHaveBeenCalledTimes(1));
  });

  it("offers logout for an authenticated user", async () => {
    authState.uid = "firebase-user";
    authState.email = "user@example.com";
    render(<AuthPanel compact />);
    fireEvent.click(screen.getByRole("button", {name: "Sign out"}));
    await waitFor(() => expect(signOut).toHaveBeenCalledTimes(1));
  });
});
