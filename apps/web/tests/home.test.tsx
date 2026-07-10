import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Home from "@/app/page";

describe("Home page", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the DealerIQ wordmark and an online status when the API is healthy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ status: "ok" }),
      }),
    );

    const ui = await Home();
    render(ui);

    expect(screen.getByAltText("DealerIQ")).toBeInTheDocument();
    expect(screen.getByText(/API status: online/i)).toBeInTheDocument();
  });

  it("renders an offline status when the API is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("connection refused")));

    const ui = await Home();
    render(ui);

    expect(screen.getByText(/API status: offline/i)).toBeInTheDocument();
  });
});
