import { Menu, X } from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useMatches } from "react-router";

import { Logo } from "@/components/brand/Logo";
import { footerNav, mainNav, UNAVAILABLE_HINT, type NavItem } from "@/components/layout/nav";
import { ThemeToggle } from "@/components/layout/ThemeToggle";
import { product } from "@/config/product";
import { Button } from "@/components/ui/button";
import { UserMenu } from "@/features/auth/UserMenu";
import { AiRuntimeBanner } from "@/features/system/AiRuntimeBanner";
import { StatusIndicator } from "@/features/system/StatusIndicator";
import { WorkspaceSwitcher } from "@/features/workspaces/WorkspaceSwitcher";
import { cn } from "@/lib/utils";

export interface RouteHandle {
  title?: string;
}

function NavEntry({ item }: { item: NavItem }) {
  const { label, icon: Icon, to, end } = item;
  const base = "flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[13.5px] transition-colors";
  if (!to) {
    return (
      <span
        aria-disabled="true"
        title={UNAVAILABLE_HINT}
        className={cn(base, "cursor-not-allowed text-muted-foreground/55")}
      >
        <Icon className="size-4" aria-hidden />
        {label}
      </span>
    );
  }
  return (
    <NavLink
      to={to}
      end={end ?? false}
      className={({ isActive }) =>
        cn(
          base,
          "hover:bg-accent hover:text-accent-foreground",
          isActive && "bg-accent font-medium text-accent-foreground",
        )
      }
    >
      <Icon className="size-4" aria-hidden />
      {label}
    </NavLink>
  );
}

function Sidebar({ className }: { className?: string }) {
  return (
    <aside
      className={cn(
        "flex w-60 shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground",
        className,
      )}
    >
      <div className="flex h-14 items-center px-4">
        <Logo />
      </div>
      <nav aria-label="Main" className="flex-1 overflow-y-auto px-2.5 py-3">
        <ul className="space-y-0.5">
          {mainNav.map((item) => (
            <li key={item.label}>
              <NavEntry item={item} />
            </li>
          ))}
        </ul>
      </nav>
      <div className="border-t border-sidebar-border px-2.5 py-3">
        <ul>
          {footerNav.map((item) => (
            <li key={item.label}>
              <NavEntry item={item} />
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}

export function AppShell() {
  const matches = useMatches();
  const location = useLocation();
  // The mobile menu belongs to the page it was opened on, so navigating closes it.
  const [menuPath, setMenuPath] = useState<string | null>(null);
  const menuOpen = menuPath === location.pathname;
  const setMenuOpen = (open: boolean) => {
    setMenuPath(open ? location.pathname : null);
  };
  const title =
    [...matches]
      .reverse()
      .map((m) => (m.handle as RouteHandle | undefined)?.title)
      .find(Boolean) ?? "";

  useEffect(() => {
    document.title = title ? `${title} · ${product.name}` : product.name;
  }, [title]);

  return (
    <div className="flex min-h-svh">
      <Sidebar className="sticky top-0 hidden h-svh md:flex" />
      {menuOpen && (
        <div className="fixed inset-0 z-40 flex md:hidden">
          <Sidebar className="relative z-50 h-full shadow-xl" />
          <button
            type="button"
            aria-label="Close navigation"
            className="flex-1 bg-foreground/30"
            onClick={() => {
              setMenuOpen(false);
            }}
          />
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-background/90 px-4 backdrop-blur md:px-8">
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            aria-label={menuOpen ? "Close navigation" : "Open navigation"}
            onClick={() => {
              setMenuOpen(!menuOpen);
            }}
          >
            {menuOpen ? <X /> : <Menu />}
          </Button>
          {/* Pages carry their own heading; the bar repeats it only on small screens. */}
          <p className="text-[15px] font-medium md:hidden">{title}</p>
          <WorkspaceSwitcher />
          <div className="ml-auto flex items-center gap-1">
            <StatusIndicator />
            <ThemeToggle />
            <UserMenu />
          </div>
        </header>
        <AiRuntimeBanner />
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 md:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
