import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
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

// AppShell (rendered once authenticated) polls the alerts badge count via react-query, so any
// render exercising the authenticated branch needs a real QueryClientProvider in the tree —
// retries disabled so a test never hangs waiting on the (unmocked, network-less) query to settle.
function renderWithQueryClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("AuthenticatedLayout route guard", () => {
  beforeEach(() => {
    replace.mockClear();
  });

  it("redirects to /login when there is no authenticated user", async () => {
    useAuthMock.mockReturnValue({ user: null, isLoading: false });
    renderWithQueryClient(<AuthenticatedLayout>{"protected content"}</AuthenticatedLayout>);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
  });

  it("renders children once a user is present, without redirecting", () => {
    useAuthMock.mockReturnValue({
      user: {
        id: "1",
        email: "admin@dealeriq.dev",
        role_key: "admin",
        must_change_password: false,
      },
      isLoading: false,
    });
    renderWithQueryClient(<AuthenticatedLayout>protected content</AuthenticatedLayout>);
    expect(screen.getByText("protected content")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("redirects to /change-password when must_change_password is set", async () => {
    useAuthMock.mockReturnValue({
      user: {
        id: "1",
        email: "admin@dealeriq.dev",
        role_key: "admin",
        must_change_password: true,
      },
      isLoading: false,
    });
    renderWithQueryClient(<AuthenticatedLayout>protected content</AuthenticatedLayout>);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/change-password"));
    expect(screen.queryByText("protected content")).not.toBeInTheDocument();
  });

  it("shows a loading state and does not redirect while the session is still resolving", () => {
    useAuthMock.mockReturnValue({ user: null, isLoading: true });
    renderWithQueryClient(<AuthenticatedLayout>protected content</AuthenticatedLayout>);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });
});
