import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn() }),
  usePathname: () => "/",
}));

const useAuthMock = vi.fn();
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => useAuthMock(),
}));

import Home from "@/app/page";

describe("Home", () => {
  beforeEach(() => {
    replace.mockClear();
  });

  it("redirects to /dashboard once the auth check has settled", async () => {
    useAuthMock.mockReturnValue({ isLoading: false });
    render(<Home />);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard"));
  });

  it("does not redirect while the auth check is still in flight", () => {
    useAuthMock.mockReturnValue({ isLoading: true });
    render(<Home />);
    expect(replace).not.toHaveBeenCalled();
  });
});
