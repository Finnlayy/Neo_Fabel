import {beforeEach, describe, expect, it, vi} from "vitest";

const getIdToken = vi.hoisted(() => vi.fn());

vi.mock("../auth/firebase", () => ({getIdToken}));

import {apiRequest, setApiTokenProvider} from "./client";

describe("apiRequest Firebase authentication", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    getIdToken.mockReset();
    setApiTokenProvider(null);
  });

  it("attaches the current Firebase ID token", async () => {
    getIdToken.mockResolvedValue("firebase-id-token");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ok: true}), {
        status: 200,
        headers: {"Content-Type": "application/json"},
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiRequest<{ok: boolean}>("/api/private")).resolves.toEqual({ok: true});
    const headers = new Headers(fetchMock.mock.calls[0][1].headers);
    expect(headers.get("Authorization")).toBe("Bearer firebase-id-token");
  });

  it("forces one token refresh and retries once after a 401", async () => {
    getIdToken.mockResolvedValueOnce("expired-token").mockResolvedValueOnce("fresh-token");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({detail: {code: "auth_invalid", message: "expired"}}), {
          status: 401,
          headers: {"Content-Type": "application/json"},
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ok: true}), {
          status: 200,
          headers: {"Content-Type": "application/json"},
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiRequest<{ok: boolean}>("/api/private")).resolves.toEqual({ok: true});
    expect(getIdToken).toHaveBeenNthCalledWith(2, true);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const retryHeaders = new Headers(fetchMock.mock.calls[1][1].headers);
    expect(retryHeaders.get("Authorization")).toBe("Bearer fresh-token");
  });

  it("does not overwrite an explicitly supplied authorization header", async () => {
    getIdToken.mockResolvedValue("firebase-id-token");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ok: true}), {
        status: 200,
        headers: {"Content-Type": "application/json"},
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await apiRequest("/api/custom", {headers: {Authorization: "Bearer route-scoped-token"}});
    const headers = new Headers(fetchMock.mock.calls[0][1].headers);
    expect(headers.get("Authorization")).toBe("Bearer route-scoped-token");
  });
});
