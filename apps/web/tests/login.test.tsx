import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn() }),
  usePathname: () => "/login",
}));

vi.mock("next-themes", () => ({
  useTheme: () => ({ resolvedTheme: "light", setTheme: vi.fn() }),
}));

const loginMock = vi.fn();
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ login: loginMock }),
}));

import LoginPage from "@/app/login/page";

describe("LoginPage", () => {
  beforeEach(() => {
    push.mockClear();
    loginMock.mockReset();
  });

  it("submits the entered credentials and routes to /dashboard on success", async () => {
    loginMock.mockResolvedValue({ mustChangePassword: false });
    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: "admin@dealeriq.dev" },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: "ChangeMe123!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() =>
      expect(loginMock).toHaveBeenCalledWith("admin@dealeriq.dev", "ChangeMe123!"),
    );
    await waitFor(() => expect(push).toHaveBeenCalledWith("/dashboard"));
  });

  it("routes to /change-password when the account must change its password", async () => {
    loginMock.mockResolvedValue({ mustChangePassword: true });
    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: "sales@dealeriq.dev" },
    });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "temp-pass" } });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/change-password"));
  });

  it("shows an error message when login fails", async () => {
    loginMock.mockRejectedValue(new Error("nope"));
    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: "wrong@dealeriq.dev" },
    });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "wrong" } });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/invalid email or password/i)).toBeInTheDocument();
  });
});
