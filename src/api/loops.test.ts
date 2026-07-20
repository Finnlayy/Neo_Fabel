import {describe, expect, it, vi, beforeEach} from "vitest";
import {fetchLoopsStatus, startPaperLoop, startLiveLoop} from "./loops";

vi.mock("./client", () => ({
  apiRequest: vi.fn(),
}));

import {apiRequest} from "./client";

describe("loops api client", () => {
  beforeEach(() => {
    vi.mocked(apiRequest).mockReset();
  });

  it("fetches loop status", async () => {
    vi.mocked(apiRequest).mockResolvedValueOnce({
      paper: {running: false, mode: "paper"},
      live: {running: false, can_start: false, deadman_armed: false, autonomy: 2, live_enabled: false},
    });
    const status = await fetchLoopsStatus();
    expect(apiRequest).toHaveBeenCalledWith("/api/v1/loops/status");
    expect(status.paper.running).toBe(false);
  });

  it("posts paper start", async () => {
    vi.mocked(apiRequest).mockResolvedValueOnce({started: true});
    await startPaperLoop();
    expect(apiRequest).toHaveBeenCalledWith("/api/v1/loops/paper/start", {method: "POST"});
  });

  it("posts live start", async () => {
    vi.mocked(apiRequest).mockResolvedValueOnce({started: true});
    await startLiveLoop();
    expect(apiRequest).toHaveBeenCalledWith("/api/v1/loops/live/start", {method: "POST"});
  });
});
