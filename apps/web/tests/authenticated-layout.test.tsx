import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn() }),
  usePathname: () => "/dashboard",
}));

const useAuthMock = vi.fn();
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => useAuthMock(),
}));

import AuthenticatedLayout from "@/app/(authenticated)/layout";

describe("AuthenticatedLayout route guard", () => {
  beforeEach(() => {
    replace.mockClear();
  });

  it("redirects to /login when there is no authenticated user", async () => {
    useAuthMock.mockReturnValue({ user: null, isLoading: false });
    render(<AuthenticatedLayout>{"protected content"}</AuthenticatedLayout>);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
  });

  it("renders children once a user is present, without redirecting", () => {
    useAuthMock.mockReturnValue({
      user: { id: "1", email: "admin@dealeriq.dev", role_key: "admin" },
      isLoading: false,
    });
    render(<AuthenticatedLayout>protected content</AuthenticatedLayout>);
    expect(screen.getByText("protected content")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("shows a loading state and does not redirect while the session is still resolving", () => {
    useAuthMock.mockReturnValue({ user: null, isLoading: true });
    render(<AuthenticatedLayout>protected content</AuthenticatedLayout>);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });
});
