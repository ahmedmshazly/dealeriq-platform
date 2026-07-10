"use client";

import { useAuth } from "@/lib/auth-context";
import {
  Grid3x3,
  LayoutDashboard,
  LineChart,
  LogOut,
  ShieldCheck,
  ShoppingCart,
  Target,
  UserCog,
  Users as UsersIcon,
  Warehouse,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/inventory", label: "Inventory", icon: Warehouse },
  { href: "/customers", label: "Customers", icon: UsersIcon },
  { href: "/leads", label: "Leads", icon: Target },
  { href: "/orders", label: "Orders", icon: ShoppingCart },
];

// forecasts:view / inventory-intel:view are granted to admin/manager/analyst, not sales (SRS
// role table) — the API enforces the real check, this just hides the links cosmetically for a
// role that would 403.
const ANALYTICS_NAV_ITEMS = [
  { href: "/analytics", label: "Analytics", icon: LineChart },
  { href: "/inventory-intel", label: "Inventory Intel", icon: Grid3x3 },
];

// Admin-only nav — the API enforces the real permission check (FR-011); this hides the link
// cosmetically for roles that would get a 403 anyway.
const ADMIN_NAV_ITEMS = [
  { href: "/admin/users", label: "Users", icon: UsersIcon },
  { href: "/admin/permissions", label: "Permissions", icon: ShieldCheck },
  { href: "/admin/audit-log", label: "Audit Log", icon: UserCog },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const pathname = usePathname();

  const items = [
    ...NAV_ITEMS,
    ...(user?.role_key !== "sales" ? ANALYTICS_NAV_ITEMS : []),
    ...(user?.role_key === "admin" ? ADMIN_NAV_ITEMS : []),
  ];

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-[230px] flex-col bg-neutral-900 px-4 py-6 text-white">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/dealeriq-lockup-h-dark.svg" alt="DealerIQ" width={140} height={34} className="mb-8 px-2" />
        <nav className="flex flex-1 flex-col gap-1">
          {items.map(({ href, label, icon: Icon }) => {
            const active = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-3 rounded-control px-3 py-2 text-sm transition-colors duration-fast ${
                  active ? "bg-neutral-800 text-white" : "text-neutral-400 hover:bg-neutral-800/60"
                }`}
              >
                <Icon size={18} strokeWidth={1.5} />
                {label}
              </Link>
            );
          })}
        </nav>
        <button
          onClick={() => logout()}
          className="flex items-center gap-3 rounded-control px-3 py-2 text-sm text-neutral-400 hover:bg-neutral-800/60"
        >
          <LogOut size={18} strokeWidth={1.5} />
          Sign out
        </button>
      </aside>
      <main className="flex-1 bg-surface-canvas px-8 py-6">{children}</main>
    </div>
  );
}
